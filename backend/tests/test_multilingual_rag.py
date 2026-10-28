import json
import os
import re
import time
import uuid
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import SessionLocal
from app.embeddings.deps import get_embedding_provider
from app.embeddings.local import LocalEmbeddingProvider
from app.evaluation.multilingual import (
    MultilingualCaseMeasurement,
    summarize_measurements,
)
from app.llm import GenerationResult
from app.llm.deps import get_llm_provider
from app.llm.ollama import OllamaLLMProvider
from app.main import app
from app.models.document import Document
from app.models.document_chunk import EMBEDDING_DIMENSION
from app.models.extracted_page import ExtractedPage
from app.services import indexing as indexing_service


DATASET_PATH = Path(__file__).parent / "data" / "multilingual_evaluation_v1.0.json"
DEVANAGARI = re.compile(r"[\u0900-\u097f]")


def load_dataset() -> dict:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


class DeterministicMultilingualEmbeddingProvider:
    """Test-only bilingual semantic space; it does not model provider quality."""

    provider_name = "fake-multilingual"
    model_name = "fake-en-hi-concepts-v1"
    dimension = EMBEDDING_DIMENSION

    @staticmethod
    def _vector(text: str) -> list[float]:
        lowered = text.casefold()
        concepts = (
            (0, ("archive", "code name", "blue lotus", "अभिलेख", "कोड नाम", "गुप्त कोड")),
            (1, ("surya", "research centre", "research center", "which city", "सूर्य", "मुख्य केंद्र", "जयपुर")),
            (2, ("garden", "sunrise", "botanical", "उद्यान", "सूर्योदय")),
            (3, ("river", "water", "monday", "नदी", "पानी", "सोमवार")),
        )
        vector = [0.0] * EMBEDDING_DIMENSION
        for axis, markers in concepts:
            if any(marker in lowered for marker in markers):
                vector[axis] = 1.0
                return vector
        vector[20] = 1.0
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class DeterministicMultilingualLLMProvider:
    provider_name = "fake"
    model_name = "fake-grounded-en-hi-v1"

    def __init__(self):
        self.prompts: list[str] = []

    def generate(self, system_instruction: str, user_prompt: str) -> GenerationResult:
        self.prompts.append(user_prompt)
        question = user_prompt.split("<QUESTION>\n", 1)[1].split("\n</QUESTION>", 1)[0]
        explicit_hindi = "Answer language preference: Hindi" in user_prompt
        explicit_english = "Answer language preference: English" in user_prompt
        hindi_answer = explicit_hindi or (not explicit_english and DEVANAGARI.search(question))
        archive = any(marker in question.casefold() for marker in ("archive", "अभिलेख", "गुप्त कोड"))
        if archive:
            answer = "अभिलेख का कोड नाम ब्लू लोटस है।" if hindi_answer else "The archive code name is Blue Lotus."
        else:
            answer = "मुख्य केंद्र जयपुर में है।" if hindi_answer else "The main centre is Jaipur."
        return GenerationResult(answer, self.model_name, "STOP")


def authenticated_client(email: str) -> tuple[TestClient, dict]:
    client = TestClient(app)
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "multilingual-evaluation-password",
            "display_name": email.split("@", 1)[0],
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "multilingual-evaluation-password"},
    )
    assert login.status_code == 200
    return client, registration.json()


def create_workspace(client: TestClient, name: str) -> dict:
    response = client.post("/api/v1/workspaces", json={"name": name})
    assert response.status_code == 201
    return response.json()


def create_and_index_document(
    workspace_id: str,
    user_id: int,
    document_key: str,
    document_data: dict,
    provider,
) -> tuple[UUID, UUID]:
    text = document_data["text"]
    with SessionLocal() as db:
        document = Document(
            workspace_id=UUID(workspace_id),
            uploaded_by=user_id,
            original_filename=document_data["filename"],
            storage_provider="test",
            storage_key=f"multilingual/{uuid.uuid4()}.pdf",
            content_type="application/pdf",
            file_size=max(1, len(text.encode("utf-8"))),
            checksum=(document_key.encode().hex() + "0" * 64)[:64],
            status="PROCESSED",
            page_count=1,
        )
        db.add(document)
        db.flush()
        page = ExtractedPage(
            document_id=document.id,
            page_number=document_data["page_number"],
            text=text,
            character_count=len(text),
        )
        db.add(page)
        db.commit()
        db.refresh(document)
        indexed = indexing_service.index_document(db, document, provider)
        chunk_id = indexed.chunks[0].id
        return indexed.id, chunk_id


def answer_language_is_correct(answer: str, expected_language: str) -> bool:
    has_devanagari = DEVANAGARI.search(answer) is not None
    return has_devanagari if expected_language == "Hindi" else not has_devanagari


def run_case(case: dict, dataset: dict) -> MultilingualCaseMeasurement:
    embedding = DeterministicMultilingualEmbeddingProvider()
    llm = DeterministicMultilingualLLMProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: embedding
    app.dependency_overrides[get_llm_provider] = lambda: llm
    try:
        client, user = authenticated_client(
            f"multilingual-{case['id'].casefold().replace('_', '-')}-"
            f"{uuid.uuid4().hex[:8]}@example.com"
        )
        workspace = create_workspace(client, f"Evaluation {case['id']}")
        identities = {}
        for key in case["corpus"]:
            identities[key] = create_and_index_document(
                workspace["id"], user["id"], key, dataset["documents"][key], embedding
            )

        search_started = time.perf_counter()
        search_response = client.post(
            f"/api/v1/workspaces/{workspace['id']}/search",
            json={"query": case["query"], "top_k": min(3, len(case["corpus"]))},
        )
        assert search_response.status_code == 200
        search_items = search_response.json()["items"]
        expected_document_id, expected_chunk_id = identities[case["expected_document"]]
        top_1_correct = bool(search_items) and search_items[0]["chunk_id"] == str(expected_chunk_id)
        top_k_relevant = str(expected_chunk_id) in {item["chunk_id"] for item in search_items}

        request = {"query": case["query"], "top_k": min(3, len(case["corpus"]))}
        if case["answer_language"]:
            request["answer_language"] = case["answer_language"]
        rag_response = client.post(
            f"/api/v1/workspaces/{workspace['id']}/rag", json=request
        )
        latency_ms = (time.perf_counter() - search_started) * 1000
        assert rag_response.status_code == 200
        payload = rag_response.json()
        expected_language = case["answer_language"] or case["query_language"]
        answer_correct = answer_language_is_correct(payload["answer"], expected_language)
        top_source = payload["sources"][0]
        expected_document = dataset["documents"][case["expected_document"]]
        citation_correct = (
            top_source["document_id"] == str(expected_document_id)
            and top_source["chunk_id"] == str(expected_chunk_id)
            and top_source["filename"] == expected_document["filename"]
            and top_source["page_number"] == case["expected_page"]
        )
        assert expected_document["text"] in llm.prompts[-1]
        persisted = client.get(
            f"/api/v1/workspaces/{workspace['id']}/rag/responses/{payload['response_id']}"
        )
        assert persisted.status_code == 200
        assert persisted.json() == payload
        assert case["expected_answer_marker"] in payload["answer"]
        return MultilingualCaseMeasurement(
            case_id=case["id"],
            top_1_correct=top_1_correct,
            top_k_relevant=top_k_relevant,
            answer_language_correct=answer_correct,
            citation_provenance_correct=citation_correct,
            latency_ms=latency_ms,
        )
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
        app.dependency_overrides.pop(get_llm_provider, None)


@pytest.mark.parametrize("case", load_dataset()["cases"], ids=lambda case: case["id"])
def test_multilingual_cross_language_matrix(case):
    measurement = run_case(case, load_dataset())
    assert measurement.top_1_correct
    assert measurement.top_k_relevant
    assert measurement.answer_language_correct
    assert measurement.citation_provenance_correct


def test_multilingual_evaluation_metrics_are_measured_and_reproducible():
    dataset = load_dataset()
    measurements = [run_case(case, dataset) for case in dataset["cases"]]
    summary = summarize_measurements(measurements)
    print("MULTILINGUAL_EVALUATION=" + json.dumps(summary, sort_keys=True))
    assert summary["case_count"] == 6
    assert summary["retrieval_top_1_accuracy_percent"] == 100.0
    assert summary["retrieval_top_k_recall_percent"] == 100.0
    assert summary["answer_language_accuracy_percent"] == 100.0
    assert summary["citation_provenance_accuracy_percent"] == 100.0
    assert summary["mean_rag_latency_ms"] > 0


def test_multilingual_workspace_isolation_with_original_hindi_text():
    dataset = load_dataset()
    embedding = DeterministicMultilingualEmbeddingProvider()
    app.dependency_overrides[get_embedding_provider] = lambda: embedding
    try:
        owner, user = authenticated_client("multilingual-isolation-owner@example.com")
        outsider, _ = authenticated_client("multilingual-isolation-outsider@example.com")
        private_workspace = create_workspace(owner, "निजी कार्यक्षेत्र")
        public_to_owner = create_workspace(owner, "Other owner workspace")
        _, chunk_id = create_and_index_document(
            private_workspace["id"],
            user["id"],
            "hindi_solar",
            dataset["documents"]["hindi_solar"],
            embedding,
        )
        query = "Where is the Surya research project's main centre?"
        allowed = owner.post(
            f"/api/v1/workspaces/{private_workspace['id']}/search",
            json={"query": query, "top_k": 5},
        )
        assert allowed.status_code == 200
        assert allowed.json()["items"][0]["chunk_id"] == str(chunk_id)
        assert allowed.json()["items"][0]["text"] == dataset["documents"]["hindi_solar"]["text"]
        no_sources = owner.post(
            f"/api/v1/workspaces/{public_to_owner['id']}/search",
            json={"query": query, "top_k": 5},
        )
        assert no_sources.status_code == 409
        assert no_sources.json()["detail"]["code"] == "NO_RESEARCH_READY_SOURCES"
        assert outsider.post(
            f"/api/v1/workspaces/{private_workspace['id']}/search",
            json={"query": query, "top_k": 5},
        ).status_code == 404
        assert TestClient(app).post(
            f"/api/v1/workspaces/{private_workspace['id']}/search",
            json={"query": query},
        ).status_code == 401
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)


@pytest.mark.skipif(
    os.getenv("AURORA_RUN_REAL_MULTILINGUAL_TEST") != "1",
    reason="explicit, local Qwen3 multilingual evaluation only",
)
def test_real_qwen3_cross_language_retrieval_generation_and_provenance():
    embedding = LocalEmbeddingProvider(
        settings.LOCAL_EMBEDDING_MODEL, settings.EMBEDDING_DIMENSION
    )
    llm = OllamaLLMProvider(
        base_url=settings.OLLAMA_BASE_URL,
        model_name=settings.OLLAMA_MODEL,
        think=False,
    )
    app.dependency_overrides[get_embedding_provider] = lambda: embedding
    app.dependency_overrides[get_llm_provider] = lambda: llm
    try:
        client, user = authenticated_client("real-multilingual-evaluation@example.com")
        workspace = create_workspace(client, "Real multilingual evaluation")
        hindi_data = {
            "filename": "नक्षत्र-परियोजना.pdf",
            "page_number": 3,
            "text": "नक्षत्र परियोजना का मुख्य अनुसंधान केंद्र जयपुर में स्थित है।",
        }
        english_data = {
            "filename": "zephyr-laboratory.pdf",
            "page_number": 5,
            "text": "The Zephyr laboratory is located in Wellington, New Zealand.",
        }
        _, hindi_chunk = create_and_index_document(
            workspace["id"], user["id"], "real_hindi", hindi_data, embedding
        )
        _, english_chunk = create_and_index_document(
            workspace["id"], user["id"], "real_english", english_data, embedding
        )
        cases = [
            {
                "query": "Where is the main research centre of the Nakshatra project?",
                "answer_language": "English",
                "expected_chunk": hindi_chunk,
                "expected_filename": hindi_data["filename"],
                "expected_page": 3,
                "answer_marker": "Jaipur",
                "language": "English",
            },
            {
                "query": "ज़ेफिर प्रयोगशाला कहाँ स्थित है?",
                "answer_language": "Hindi",
                "expected_chunk": english_chunk,
                "expected_filename": english_data["filename"],
                "expected_page": 5,
                "answer_marker": "वेलिंगटन",
                "language": "Hindi",
            },
        ]
        measurements = []
        for case in cases:
            started = time.perf_counter()
            search = client.post(
                f"/api/v1/workspaces/{workspace['id']}/search",
                json={"query": case["query"], "top_k": 2},
            )
            assert search.status_code == 200
            top_1 = search.json()["items"][0]["chunk_id"] == str(case["expected_chunk"])
            rag = client.post(
                f"/api/v1/workspaces/{workspace['id']}/rag",
                json={
                    "query": case["query"],
                    "top_k": 2,
                    "answer_language": case["answer_language"],
                },
            )
            latency = (time.perf_counter() - started) * 1000
            assert rag.status_code == 200
            payload = rag.json()
            source = payload["sources"][0]
            language_correct = answer_language_is_correct(payload["answer"], case["language"])
            citation_correct = (
                source["chunk_id"] == str(case["expected_chunk"])
                and source["filename"] == case["expected_filename"]
                and source["page_number"] == case["expected_page"]
            )
            measurements.append(
                MultilingualCaseMeasurement(
                    case_id=case["query"],
                    top_1_correct=top_1,
                    top_k_relevant=any(
                        item["chunk_id"] == str(case["expected_chunk"])
                        for item in search.json()["items"]
                    ),
                    answer_language_correct=language_correct
                    and case["answer_marker"].casefold() in payload["answer"].casefold(),
                    citation_provenance_correct=citation_correct,
                    latency_ms=latency,
                )
            )
        summary = summarize_measurements(measurements)
        print("REAL_MULTILINGUAL_EVALUATION=" + json.dumps(summary, sort_keys=True))
        assert summary["retrieval_top_1_accuracy_percent"] == 100.0
        assert summary["answer_language_accuracy_percent"] == 100.0
        assert summary["citation_provenance_accuracy_percent"] == 100.0
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
        app.dependency_overrides.pop(get_llm_provider, None)

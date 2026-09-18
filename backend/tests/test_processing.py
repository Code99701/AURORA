from io import BytesIO
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.document import Document
from app.models.extracted_page import ExtractedPage
from app.models.content_unit import ContentUnit
from app.models.ingestion_run import IngestionRun
from app.models.document_chunk import DocumentChunk, EMBEDDING_DIMENSION
from app.ocr.base import OCRError, OCRResult
from app.ocr.deps import get_ocr_provider
from app.processing.text import clean_extracted_text
from app.services import processing as processing_service
from app.services import indexing as indexing_service
from app.storage.base import StorageError
from app.storage.deps import get_file_storage
from app.storage.local import LocalFileStorage


class UnusedOCR:
    provider_name = "unused"

    def recognize(self, image, timeout_seconds):
        raise AssertionError("OCR should not be called for this test")


class SuccessfulOCR:
    provider_name = "fake"

    def recognize(self, image, timeout_seconds):
        return OCRResult(
            text="Recognized canonical vector outline evidence for research",
            confidence=0.96,
            language="eng",
            regions=({"x": 1, "y": 2, "width": 3, "height": 4},),
        )


class FailingOCR:
    provider_name = "fake"

    def recognize(self, image, timeout_seconds):
        raise OCRError("OCR_TIMEOUT", "OCR exceeded the allowed processing time", 422)


class StableEmbeddingProvider:
    provider_name = "test"
    model_name = "test-embedding"
    dimension = EMBEDDING_DIMENSION

    def embed_documents(self, texts):
        return [[1.0] + [0.0] * (self.dimension - 1) for _ in texts]

    def embed_query(self, text):
        return [1.0] + [0.0] * (self.dimension - 1)


def build_text_pdf(page_texts: list[str | None]) -> bytes:
    """Build a deterministic text PDF without an extra test dependency."""
    objects: list[bytes] = []
    page_object_numbers: list[int] = []
    content_object_numbers: list[int] = []

    # Object 1 is Catalog, object 2 is Pages, object 3 is Helvetica.
    next_object = 4
    for _ in page_texts:
        page_object_numbers.append(next_object)
        content_object_numbers.append(next_object + 1)
        next_object += 2

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{number} 0 R" for number in page_object_numbers)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_texts)} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for page_number, raw_text in enumerate(page_texts):
        page_object = page_object_numbers[page_number]
        content_object = content_object_numbers[page_number]
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_object} 0 R >>"
            ).encode()
        )
        if raw_text is None:
            stream = b""
        else:
            escaped = raw_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1")
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode()
            + stream
            + b"\nendstream"
        )

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_number} 0 obj\n".encode())
        output.extend(body)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    return bytes(output)


def build_vector_pdf() -> bytes:
    stream = b"72 700 m 90 730 l 108 700 l h f 116 700 m 134 730 l 152 700 l h f"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << >> /Contents 4 0 R >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode())
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode()
    )
    return bytes(output)


def combine_pdfs(*documents: bytes) -> bytes:
    writer = PdfWriter()
    for document in documents:
        writer.append(BytesIO(document))
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def local_storage(tmp_path: Path):
    storage = LocalFileStorage(tmp_path / "processing-storage")
    app.dependency_overrides[get_file_storage] = lambda: storage
    try:
        yield storage
    finally:
        app.dependency_overrides.pop(get_file_storage, None)


def authenticated_client(email: str) -> tuple[TestClient, dict]:
    client = TestClient(app)
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "processing-password",
            "display_name": email.split("@", 1)[0],
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "processing-password"},
    )
    assert login.status_code == 200
    return client, registration.json()


def create_workspace(client: TestClient, name: str) -> dict:
    response = client.post("/api/v1/workspaces", json={"name": name})
    assert response.status_code == 201
    return response.json()


def upload_pdf(client: TestClient, workspace_id: str, content: bytes) -> dict:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("processing.pdf", content, "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


def process(client: TestClient, workspace_id: str, document_id: str):
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/{document_id}/process"
    )


def test_text_cleaning_is_deterministic_and_preserves_paragraphs():
    source = "  First\t line \r\n second   line\x00\n\n\n Third line  "
    expected = "First line second line\n\nThird line"
    assert clean_extracted_text(source) == expected
    assert clean_extracted_text(source) == expected
    assert clean_extracted_text("") == ""
    assert clean_extracted_text(None) == ""


def test_valid_multi_page_pdf_extracts_pages_and_updates_status(local_storage):
    client, _ = authenticated_client("processing-success@example.com")
    workspace = create_workspace(client, "Processing success")
    document = upload_pdf(client, workspace["id"], build_text_pdf(["First page", "Second page"]))

    response = process(client, workspace["id"], document["id"])
    assert response.status_code == 200
    assert response.json()["status"] == "PROCESSED"
    assert response.json()["page_count"] == 2
    assert response.json()["processing_error"] is None
    assert response.json()["processed_at"] is not None

    with SessionLocal() as db:
        pages = db.scalars(
            select(ExtractedPage)
            .where(ExtractedPage.document_id == UUID(document["id"]))
            .order_by(ExtractedPage.page_number)
        ).all()
        assert [page.page_number for page in pages] == [1, 2]
        assert [page.text for page in pages] == ["First page", "Second page"]
        assert [page.character_count for page in pages] == [10, 11]


def test_vector_pdf_ocr_creates_active_canonical_units_and_compatible_page(local_storage):
    app.dependency_overrides[get_ocr_provider] = lambda: SuccessfulOCR()
    try:
        client, _ = authenticated_client("processing-vector-ocr@example.com")
        workspace = create_workspace(client, "Vector OCR")
        document = upload_pdf(client, workspace["id"], build_vector_pdf())
        response = process(client, workspace["id"], document["id"])
    finally:
        app.dependency_overrides.pop(get_ocr_provider, None)

    assert response.status_code == 200
    assert response.json()["status"] == "PROCESSED"
    assert response.json()["processing_stage"] == "COMPLETE"
    with SessionLocal() as db:
        run = db.scalar(
            select(IngestionRun).where(
                IngestionRun.document_id == UUID(document["id"]),
                IngestionRun.status == "ACTIVE",
            )
        )
        assert run is not None
        assert run.adapter_id == "aurora.pdf"
        unit = db.scalar(
            select(ContentUnit).where(ContentUnit.ingestion_run_id == run.id)
        )
        page = db.scalar(
            select(ExtractedPage).where(
                ExtractedPage.document_id == UUID(document["id"])
            )
        )
        assert unit is not None and page is not None
        assert unit.extraction_method == "OCR"
        assert unit.locator == {"v": 1, "type": "pdf_page", "page": 1}
        assert unit.confidence == pytest.approx(0.96)
        assert page.content_unit_id == unit.id
        assert page.text == unit.text


def test_failed_reprocessing_preserves_last_valid_pages_and_index(local_storage):
    app.dependency_overrides[get_ocr_provider] = lambda: SuccessfulOCR()
    client, _ = authenticated_client("processing-atomic-ocr@example.com")
    workspace = create_workspace(client, "Atomic OCR")
    document = upload_pdf(client, workspace["id"], build_vector_pdf())
    try:
        assert process(client, workspace["id"], document["id"]).status_code == 200
    finally:
        app.dependency_overrides.pop(get_ocr_provider, None)

    with SessionLocal() as db:
        stored = db.get(Document, UUID(document["id"]))
        indexing_service.index_document(db, stored, StableEmbeddingProvider())
        original_page = db.scalar(
            select(ExtractedPage).where(ExtractedPage.document_id == stored.id)
        )
        original_page_id = original_page.id
        original_text = original_page.text
        original_chunk_count = db.scalar(
            select(func.count()).select_from(DocumentChunk).where(
                DocumentChunk.document_id == stored.id
            )
        )

    app.dependency_overrides[get_ocr_provider] = lambda: FailingOCR()
    try:
        failed = process(client, workspace["id"], document["id"])
    finally:
        app.dependency_overrides.pop(get_ocr_provider, None)

    assert failed.status_code == 422
    assert failed.json()["detail"]["code"] == "OCR_TIMEOUT"
    with SessionLocal() as db:
        stored = db.get(Document, UUID(document["id"]))
        page = db.scalar(
            select(ExtractedPage).where(ExtractedPage.document_id == stored.id)
        )
        assert stored.status == "PROCESSED"
        assert stored.processing_error == "OCR_TIMEOUT"
        assert stored.indexing_status == "INDEXED"
        assert page.id == original_page_id
        assert page.text == original_text
        assert db.scalar(
            select(func.count()).select_from(DocumentChunk).where(
                DocumentChunk.document_id == stored.id
            )
        ) == original_chunk_count
        assert db.scalar(
            select(func.count()).select_from(IngestionRun).where(
                IngestionRun.document_id == stored.id,
                IngestionRun.status == "ACTIVE",
            )
        ) == 1
        assert db.scalar(
            select(func.count()).select_from(IngestionRun).where(
                IngestionRun.document_id == stored.id,
                IngestionRun.status == "FAILED",
            )
        ) == 1


def test_empty_page_is_preserved_when_document_has_usable_text(local_storage):
    client, _ = authenticated_client("processing-empty-page@example.com")
    workspace = create_workspace(client, "Empty page")
    document = upload_pdf(client, workspace["id"], build_text_pdf(["Usable page", None]))

    response = process(client, workspace["id"], document["id"])
    assert response.status_code == 200
    with SessionLocal() as db:
        pages = db.scalars(
            select(ExtractedPage)
            .where(ExtractedPage.document_id == UUID(document["id"]))
            .order_by(ExtractedPage.page_number)
        ).all()
        assert len(pages) == 2
        assert pages[1].page_number == 2
        assert pages[1].text == ""
        assert pages[1].character_count == 0


def test_partial_document_is_persisted_and_only_usable_units_are_indexed(local_storage):
    app.dependency_overrides[get_ocr_provider] = lambda: FailingOCR()
    try:
        client, _ = authenticated_client("processing-partial@example.com")
        workspace = create_workspace(client, "Partial processing")
        document = upload_pdf(
            client,
            workspace["id"],
            combine_pdfs(build_text_pdf(["Native retained evidence"]), build_vector_pdf()),
        )
        response = process(client, workspace["id"], document["id"])
    finally:
        app.dependency_overrides.pop(get_ocr_provider, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "PARTIALLY_PROCESSED"
    assert payload["processing_stage"] == "PARTIAL"
    assert payload["processing_summary"]["usable_unit_count"] == 1
    assert payload["processing_summary"]["failed_unit_count"] == 1

    with SessionLocal() as db:
        stored = db.get(Document, UUID(document["id"]))
        run = db.scalar(
            select(IngestionRun).where(
                IngestionRun.document_id == stored.id,
                IngestionRun.status == "ACTIVE",
            )
        )
        units = db.scalars(
            select(ContentUnit)
            .where(ContentUnit.ingestion_run_id == run.id)
            .order_by(ContentUnit.ordinal)
        ).all()
        assert run.outcome == "PARTIAL"
        assert run.failure_code is None
        assert run.duration_ms is not None
        assert [unit.status for unit in units] == ["USABLE", "FAILED"]
        assert units[1].issue_code == "OCR_TIMEOUT"

        indexing_service.index_document(db, stored, StableEmbeddingProvider())
        chunks = db.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == stored.id)
        ).all()
        assert chunks
        assert {chunk.content_unit_id for chunk in chunks} == {units[0].id}


def test_processing_in_progress_is_rejected_without_starting_another_run(local_storage):
    client, _ = authenticated_client("processing-concurrency@example.com")
    workspace = create_workspace(client, "Concurrent processing")
    document = upload_pdf(client, workspace["id"], build_text_pdf(["Evidence"]))
    with SessionLocal() as db:
        stored = db.get(Document, UUID(document["id"]))
        stored.status = "PROCESSING"
        db.commit()

    response = process(client, workspace["id"], document["id"])
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "DOCUMENT_PROCESSING_IN_PROGRESS"
    with SessionLocal() as db:
        assert db.scalar(
            select(func.count()).select_from(IngestionRun).where(
                IngestionRun.document_id == UUID(document["id"])
            )
        ) == 0


def test_indexing_reads_non_page_canonical_units_without_legacy_page(local_storage):
    client, _ = authenticated_client("canonical-section-index@example.com")
    workspace = create_workspace(client, "Canonical section")
    document = upload_pdf(client, workspace["id"], build_text_pdf(["Placeholder"]))

    with SessionLocal() as db:
        stored = db.get(Document, UUID(document["id"]))
        run = IngestionRun(
            document_id=stored.id,
            version=1,
            adapter_id="test.section",
            adapter_version="1.0",
            source_format="test",
            status="ACTIVE",
            outcome="COMPLETE",
            unit_count=1,
            diagnostics={"usable_unit_count": 1},
        )
        db.add(run)
        db.flush()
        section_text = "Canonical section evidence independent of a PDF page."
        unit = ContentUnit(
            document_id=stored.id,
            ingestion_run_id=run.id,
            ordinal=0,
            kind="SECTION",
            text=section_text,
            character_count=len(section_text),
            locator_version=1,
            locator={"v": 1, "type": "section", "path": ["Introduction"]},
            extraction_method="NATIVE",
            content_type="text/plain",
            status="USABLE",
            unit_metadata={"heading": "Introduction"},
        )
        db.add(unit)
        stored.status = "PROCESSED"
        stored.processing_stage = "COMPLETE"
        stored.processing_summary = {"usable_unit_count": 1}
        db.commit()

        indexing_service.index_document(db, stored, StableEmbeddingProvider())
        chunk = db.scalar(
            select(DocumentChunk).where(DocumentChunk.document_id == stored.id)
        )
        assert chunk is not None
        assert chunk.content_unit_id == unit.id
        assert chunk.extracted_page_id is None
        assert chunk.page_number is None


@pytest.mark.parametrize(
    ("case_name", "page_texts"),
    [("zero-pages", []), ("empty-page", [None]), ("whitespace-page", ["   "])],
)
def test_empty_or_image_only_pdf_is_marked_failed(local_storage, case_name, page_texts):
    client, _ = authenticated_client(
        f"processing-no-text-{case_name}@example.com"
    )
    workspace = create_workspace(client, "No extractable text")
    document = upload_pdf(client, workspace["id"], build_text_pdf(page_texts))

    response = process(client, workspace["id"], document["id"])
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "NO_EXTRACTABLE_TEXT"
    with SessionLocal() as db:
        stored = db.get(Document, UUID(document["id"]))
        assert stored.status == "FAILED"
        assert stored.processing_error == "NO_EXTRACTABLE_TEXT"
        assert stored.page_count == len(page_texts)
        assert stored.processed_at is None
        assert db.scalar(
            select(func.count()).select_from(ExtractedPage).where(
                ExtractedPage.document_id == stored.id
            )
        ) == 0


def test_corrupt_pdf_fails_safely(local_storage):
    client, _ = authenticated_client("processing-corrupt@example.com")
    workspace = create_workspace(client, "Corrupt PDF")
    document = upload_pdf(client, workspace["id"], b"%PDF-corrupt-but-upload-validates")

    response = process(client, workspace["id"], document["id"])
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "PDF_EXTRACTION_ERROR",
        "message": "PDF text extraction failed",
    }
    assert "storage" not in response.text.casefold()
    with SessionLocal() as db:
        stored = db.get(Document, UUID(document["id"]))
        assert stored.status == "FAILED"
        assert stored.processing_error == "PDF_EXTRACTION_ERROR"


def test_storage_read_failure_becomes_failed():
    class ReadFailingStorage:
        provider_name = "test"

        def save(self, key, source):
            return None

        def open(self, key):
            raise StorageError("private provider detail")

        def delete(self, key):
            return None

        def exists(self, key):
            return True

    storage = ReadFailingStorage()
    app.dependency_overrides[get_file_storage] = lambda: storage
    try:
        client, _ = authenticated_client("processing-storage-error@example.com")
        workspace = create_workspace(client, "Storage failure")
        document = upload_pdf(client, workspace["id"], build_text_pdf(["Text"]))
        response = process(client, workspace["id"], document["id"])
    finally:
        app.dependency_overrides.pop(get_file_storage, None)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "STORAGE_READ_ERROR"
    assert "private provider detail" not in response.text
    with SessionLocal() as db:
        assert db.get(Document, UUID(document["id"])).status == "FAILED"


def test_reprocessing_replaces_pages_without_duplicates(local_storage):
    client, _ = authenticated_client("processing-repeat@example.com")
    workspace = create_workspace(client, "Repeat processing")
    document = upload_pdf(client, workspace["id"], build_text_pdf(["One", "Two"]))

    assert process(client, workspace["id"], document["id"]).status_code == 200
    assert process(client, workspace["id"], document["id"]).status_code == 200
    with SessionLocal() as db:
        pages = db.scalars(
            select(ExtractedPage).where(ExtractedPage.document_id == UUID(document["id"]))
        ).all()
        assert len(pages) == 2
        assert {page.page_number for page in pages} == {1, 2}


def test_processing_persistence_failure_marks_document_failed(local_storage, monkeypatch):
    client, _ = authenticated_client("processing-db-error@example.com")
    workspace = create_workspace(client, "Persistence failure")
    document_payload = upload_pdf(client, workspace["id"], build_text_pdf(["Persist me"]))

    with SessionLocal() as db:
        document = db.get(Document, UUID(document_payload["id"]))
        original_commit = db.commit
        calls = 0

        def fail_second_commit():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise SQLAlchemyError("test persistence failure")
            original_commit()

        monkeypatch.setattr(db, "commit", fail_second_commit)
        with pytest.raises(processing_service.DocumentProcessingError) as error:
            processing_service.process_document(
                db, local_storage, document, UnusedOCR()
            )
        assert error.value.code == "EXTRACTED_CONTENT_PERSISTENCE_ERROR"

    with SessionLocal() as db:
        stored = db.get(Document, UUID(document_payload["id"]))
        assert stored.status == "FAILED"
        assert stored.processing_error == "EXTRACTED_CONTENT_PERSISTENCE_ERROR"
        assert db.scalar(
            select(func.count()).select_from(ExtractedPage).where(
                ExtractedPage.document_id == stored.id
            )
        ) == 0


def test_unauthenticated_processing_is_rejected(local_storage):
    response = TestClient(app).post(
        "/api/v1/workspaces/00000000-0000-0000-0000-000000000001/"
        "documents/00000000-0000-0000-0000-000000000002/process"
    )
    assert response.status_code == 401


def test_cross_workspace_processing_is_blocked(local_storage):
    client, _ = authenticated_client("processing-cross-workspace@example.com")
    first_workspace = create_workspace(client, "Processing first")
    second_workspace = create_workspace(client, "Processing second")
    document = upload_pdf(client, first_workspace["id"], build_text_pdf(["Private text"]))

    response = process(client, second_workspace["id"], document["id"])
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"
    with SessionLocal() as db:
        assert db.get(Document, UUID(document["id"])).status == "UPLOADED"


def test_non_member_processing_is_concealed(local_storage):
    owner_client, _ = authenticated_client("processing-owner@example.com")
    outsider_client, _ = authenticated_client("processing-outsider@example.com")
    workspace = create_workspace(owner_client, "Private processing")
    document = upload_pdf(owner_client, workspace["id"], build_text_pdf(["Private text"]))

    response = process(outsider_client, workspace["id"], document["id"])
    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def test_document_detail_exposes_safe_processing_information(local_storage):
    client, _ = authenticated_client("processing-detail@example.com")
    workspace = create_workspace(client, "Processing detail")
    document = upload_pdf(client, workspace["id"], build_text_pdf(["Detail text"]))
    process(client, workspace["id"], document["id"])

    response = client.get(
        f"/api/v1/workspaces/{workspace['id']}/documents/{document['id']}"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "PROCESSED"
    assert payload["page_count"] == 1
    assert payload["processing_error"] is None
    assert payload["processed_at"] is not None
    assert "storage_key" not in payload
    assert "text" not in payload


def test_extracted_page_migration_upgrade_downgrade_and_reupgrade(
    disposable_database, run_alembic
):
    database_url = make_url(str(settings.SQLALCHEMY_DATABASE_URI)).set(
        database=disposable_database
    )
    migration_engine = create_engine(database_url)
    try:
        run_alembic("upgrade", "e84c19ad5b72", database=disposable_database)
        run_alembic("upgrade", "head", database=disposable_database)
        with migration_engine.connect() as connection:
            columns = set(
                connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name='documents'"
                    )
                ).scalars()
            )
            assert {"page_count", "processing_error", "processed_at"}.issubset(columns)
            assert connection.execute(
                text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name='extracted_pages')"
                )
            ).scalar_one() is True

        run_alembic("downgrade", "e84c19ad5b72", database=disposable_database)
        with migration_engine.connect() as connection:
            columns = set(
                connection.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name='documents'"
                    )
                ).scalars()
            )
            assert not {"page_count", "processing_error", "processed_at"} & columns
            assert connection.execute(
                text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name='extracted_pages')"
                )
            ).scalar_one() is False

        run_alembic("upgrade", "head", database=disposable_database)
        with migration_engine.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name='extracted_pages')"
                )
            ).scalar_one() is True
    finally:
        migration_engine.dispose()


def test_canonical_ingestion_migration_upgrade_downgrade_and_reupgrade(
    disposable_database, run_alembic
):
    run_alembic("upgrade", "e2f4a6b8c0d1", database=disposable_database)
    migration_url = make_url(str(settings.SQLALCHEMY_DATABASE_URI)).set(
        database=disposable_database
    )
    migration_engine = create_engine(migration_url)
    try:
        run_alembic("upgrade", "f4a1c2d3e5b6", database=disposable_database)
        with migration_engine.connect() as connection:
            inspector = inspect(connection)
            assert "ingestion_runs" in inspector.get_table_names()
            assert "content_units" in inspector.get_table_names()
            assert "processing_stage" in {
                column["name"] for column in inspector.get_columns("documents")
            }
            assert "content_unit_id" in {
                column["name"] for column in inspector.get_columns("extracted_pages")
            }
            assert "content_unit_id" in {
                column["name"] for column in inspector.get_columns("document_chunks")
            }

        run_alembic("downgrade", "e2f4a6b8c0d1", database=disposable_database)
        with migration_engine.connect() as connection:
            inspector = inspect(connection)
            assert "ingestion_runs" not in inspector.get_table_names()
            assert "content_units" not in inspector.get_table_names()
            assert "processing_stage" not in {
                column["name"] for column in inspector.get_columns("documents")
            }

        run_alembic("upgrade", "f4a1c2d3e5b6", database=disposable_database)
        with migration_engine.connect() as connection:
            assert {"ingestion_runs", "content_units"}.issubset(
                set(inspect(connection).get_table_names())
            )
    finally:
        migration_engine.dispose()


def test_ingestion_hardening_migration_round_trip(disposable_database, run_alembic):
    run_alembic("upgrade", "f4a1c2d3e5b6", database=disposable_database)
    migration_url = make_url(str(settings.SQLALCHEMY_DATABASE_URI)).set(
        database=disposable_database
    )
    migration_engine = create_engine(migration_url)
    try:
        run_alembic("upgrade", "a5b7c9d1e3f5", database=disposable_database)
        with migration_engine.connect() as connection:
            inspector = inspect(connection)
            assert "processing_summary" in {
                column["name"] for column in inspector.get_columns("documents")
            }
            assert {"failure_stage", "outcome", "duration_ms", "diagnostics"}.issubset(
                {column["name"] for column in inspector.get_columns("ingestion_runs")}
            )
            assert {"parent_unit_id", "content_type", "status", "issue_code"}.issubset(
                {column["name"] for column in inspector.get_columns("content_units")}
            )
            chunk_columns = {
                column["name"]: column
                for column in inspector.get_columns("document_chunks")
            }
            assert chunk_columns["extracted_page_id"]["nullable"] is True
            assert chunk_columns["page_number"]["nullable"] is True

        run_alembic("downgrade", "f4a1c2d3e5b6", database=disposable_database)
        with migration_engine.connect() as connection:
            inspector = inspect(connection)
            assert "processing_summary" not in {
                column["name"] for column in inspector.get_columns("documents")
            }
            chunk_columns = {
                column["name"]: column
                for column in inspector.get_columns("document_chunks")
            }
            assert chunk_columns["extracted_page_id"]["nullable"] is False
            assert chunk_columns["page_number"]["nullable"] is False

        run_alembic("upgrade", "head", database=disposable_database)
    finally:
        migration_engine.dispose()

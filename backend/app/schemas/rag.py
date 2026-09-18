import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings


class RAGRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=100)
    answer_language: str | None = Field(default=None, min_length=2, max_length=50)

    @field_validator("query")
    @classmethod
    def query_must_have_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be blank")
        return value

    @field_validator("top_k")
    @classmethod
    def top_k_must_respect_service_limit(cls, value: int) -> int:
        if value > settings.RETRIEVAL_MAX_TOP_K:
            raise ValueError(f"top_k must be at most {settings.RETRIEVAL_MAX_TOP_K}")
        return value

    @field_validator("answer_language")
    @classmethod
    def normalize_answer_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("answer_language must not be blank")
        return value


class RAGSource(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    citation_id: uuid.UUID
    position: int
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    filename: str
    page_number: int | None
    similarity: float
    locator: dict | None = None
    extraction_method: str | None = None


class RAGResponse(BaseModel):
    response_id: uuid.UUID
    answer: str
    sources: list[RAGSource]
    insufficient_evidence: bool
    model: str | None

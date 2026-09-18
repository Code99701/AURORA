import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings
from app.schemas.rag import RAGSource


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=120)


class ConversationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=120)


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    total: int


class ConversationMessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: Literal["USER", "ASSISTANT"]
    content: str
    created_at: datetime
    response_id: uuid.UUID | None = None
    sources: list[RAGSource] = Field(default_factory=list)
    insufficient_evidence: bool = False
    model: str | None = None
    latency_ms: int | None = None


class ConversationMessagesResponse(BaseModel):
    items: list[ConversationMessageResponse]
    total: int


class ConversationMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=100)
    answer_language: str | None = Field(default=None, min_length=2, max_length=50)

    @field_validator("content")
    @classmethod
    def content_must_have_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content must not be blank")
        return value

    @field_validator("top_k")
    @classmethod
    def top_k_must_respect_limit(cls, value: int) -> int:
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


class ConversationTurnResponse(BaseModel):
    conversation: ConversationResponse
    user_message: ConversationMessageResponse
    assistant_message: ConversationMessageResponse

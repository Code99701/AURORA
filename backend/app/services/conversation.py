from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import monotonic
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.embeddings import EmbeddingProvider
from app.llm import (
    LLMProvider,
    LLMProviderError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
)
from app.models.conversation import Conversation, ConversationMessage
from app.models.rag_response import RAGResponseRecord
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.conversation import ConversationCreate, ConversationUpdate
from app.services import rag as rag_service


DEFAULT_TITLE = "New research"
CONVERSATION_LIST_LIMIT = 50
MESSAGE_LIST_LIMIT = 200


@dataclass(frozen=True)
class ConversationStreamEvent:
    event_type: str
    phase: str | None = None
    text: str = ""
    user_message: ConversationMessage | None = None
    assistant_message: ConversationMessage | None = None
    result: rag_service.RAGResult | None = None


class ConversationError(Exception):
    def __init__(self, code: str, public_message: str, status_code: int):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.status_code = status_code


def derive_title(content: str) -> str:
    """Create a deterministic, whitespace-normalized title without an LLM call."""
    normalized = " ".join(content.split())
    if len(normalized) <= 72:
        return normalized
    shortened = normalized[:69].rsplit(" ", 1)[0] or normalized[:69]
    return f"{shortened}…"


def create_conversation(
    db: Session, workspace: Workspace, user: User, data: ConversationCreate
) -> Conversation:
    conversation = Conversation(
        workspace_id=workspace.id,
        user_id=user.id,
        title=data.title or DEFAULT_TITLE,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_conversations(
    db: Session, workspace: Workspace, user: User
) -> list[Conversation]:
    statement = (
        select(Conversation)
        .where(
            Conversation.workspace_id == workspace.id,
            Conversation.user_id == user.id,
        )
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .limit(CONVERSATION_LIST_LIMIT)
    )
    return list(db.scalars(statement).all())


def count_conversations(db: Session, workspace: Workspace, user: User) -> int:
    return db.scalar(
        select(func.count()).select_from(Conversation).where(
            Conversation.workspace_id == workspace.id,
            Conversation.user_id == user.id,
        )
    ) or 0


def get_conversation(
    db: Session, workspace: Workspace, user: User, conversation_id: UUID
) -> Conversation | None:
    return db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace.id,
            Conversation.user_id == user.id,
        )
    )


def rename_conversation(
    db: Session, conversation: Conversation, data: ConversationUpdate
) -> Conversation:
    conversation.title = data.title
    db.commit()
    db.refresh(conversation)
    return conversation


def list_messages(db: Session, conversation: Conversation) -> list[ConversationMessage]:
    recent_ids = (
        select(ConversationMessage.id)
        .where(ConversationMessage.conversation_id == conversation.id)
        .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
        .limit(MESSAGE_LIST_LIMIT)
    )
    statement = (
        select(ConversationMessage)
        .where(ConversationMessage.id.in_(recent_ids))
        .order_by(ConversationMessage.created_at, ConversationMessage.id)
    )
    return list(db.scalars(statement).all())


def count_messages(db: Session, conversation: Conversation) -> int:
    return db.scalar(
        select(func.count()).select_from(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation.id
        )
    ) or 0


def bounded_history(
    db: Session, conversation: Conversation
) -> tuple[tuple[str, str], ...]:
    if (
        settings.CONVERSATION_HISTORY_MAX_MESSAGES == 0
        or settings.CONVERSATION_HISTORY_MAX_CHARACTERS == 0
    ):
        return ()
    recent = list(
        db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation.id)
            .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
            .limit(settings.CONVERSATION_HISTORY_MAX_MESSAGES)
        ).all()
    )
    selected: list[tuple[str, str]] = []
    remaining = settings.CONVERSATION_HISTORY_MAX_CHARACTERS
    for message in recent:
        if remaining <= 0:
            break
        content = message.content[:remaining]
        if content:
            selected.append((message.role.lower(), content))
            remaining -= len(content)
    return tuple(reversed(selected))


def send_message(
    db: Session,
    workspace: Workspace,
    user: User,
    conversation: Conversation,
    content: str,
    top_k: int,
    answer_language: str | None,
    embedding_provider: EmbeddingProvider,
    llm_provider: LLMProvider,
) -> tuple[ConversationMessage, ConversationMessage, rag_service.RAGResult]:
    history = bounded_history(db, conversation)
    user_message = ConversationMessage(
        conversation_id=conversation.id,
        role="USER",
        content=content,
        created_at=datetime.now(timezone.utc),
    )
    if conversation.title == DEFAULT_TITLE and not history:
        conversation.title = derive_title(content)
    db.add(user_message)
    try:
        db.flush()
    except SQLAlchemyError as exc:
        db.rollback()
        raise ConversationError(
            "MESSAGE_PERSISTENCE_ERROR", "Your message could not be saved", 500
        ) from exc

    started = monotonic()
    try:
        result = rag_service.answer_question(
            db=db,
            workspace=workspace,
            requested_by=user.id,
            query=content,
            top_k=top_k,
            answer_language=answer_language,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
            conversation_history=history,
            persist_commit=False,
        )
        assistant_message = ConversationMessage(
            conversation_id=conversation.id,
            role="ASSISTANT",
            content=result.answer,
            rag_response_id=result.response_id,
            model=result.model,
            latency_ms=max(0, round((monotonic() - started) * 1000)),
            created_at=max(
                datetime.now(timezone.utc), user_message.created_at + timedelta(microseconds=1)
            ),
        )
        db.add(assistant_message)
        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(assistant_message)
        db.refresh(conversation)
        return user_message, assistant_message, result
    except rag_service.RAGError:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise ConversationError(
            "MESSAGE_PERSISTENCE_ERROR", "The grounded response could not be saved", 500
        ) from exc


async def stream_message(
    db: Session,
    workspace: Workspace,
    user: User,
    conversation: Conversation,
    content: str,
    top_k: int,
    answer_language: str | None,
    embedding_provider: EmbeddingProvider,
    llm_provider: LLMProvider,
):
    """Stream one turn and atomically persist only a completed grounded answer."""
    history = bounded_history(db, conversation)
    user_message = ConversationMessage(
        conversation_id=conversation.id,
        role="USER",
        content=content,
        created_at=datetime.now(timezone.utc),
    )
    if conversation.title == DEFAULT_TITLE and not history:
        conversation.title = derive_title(content)
    db.add(user_message)
    committed = False
    started = monotonic()
    try:
        db.flush()
        yield ConversationStreamEvent(event_type="state", phase="retrieving")
        preparation = rag_service.prepare_question(
            db=db,
            workspace=workspace,
            query=content,
            top_k=top_k,
            answer_language=answer_language,
            embedding_provider=embedding_provider,
            conversation_history=history,
            llm_provider=llm_provider,
        )

        if preparation.insufficient_evidence:
            answer = rag_service.INSUFFICIENT_EVIDENCE_ANSWER
            model = None
            # This is deterministic application output, not simulated model tokens.
            yield ConversationStreamEvent(event_type="text_delta", text=answer)
        else:
            assert preparation.prompt is not None
            answer_parts: list[str] = []
            answer_characters = 0
            model = llm_provider.model_name
            completed = False
            yield ConversationStreamEvent(event_type="state", phase="streaming")
            try:
                async for provider_event in llm_provider.stream_generate(
                    preparation.prompt.system_instruction,
                    preparation.prompt.user_prompt,
                ):
                    if provider_event.event_type == "text_delta":
                        if not provider_event.text:
                            continue
                        answer_characters += len(provider_event.text)
                        if answer_characters > settings.STREAMING_MAX_RESPONSE_CHARACTERS:
                            raise LLMProviderError(
                                "Generation provider exceeded the response limit"
                            )
                        answer_parts.append(provider_event.text)
                        yield ConversationStreamEvent(
                            event_type="text_delta", text=provider_event.text
                        )
                    elif provider_event.event_type == "completion":
                        model = provider_event.model_name or model
                        completed = True
                answer = "".join(answer_parts).strip()
                if not completed or not answer:
                    raise LLMProviderError(
                        "Generation provider returned an incomplete stream"
                    )
            except LLMQuotaExhaustedError as exc:
                raise rag_service.RAGError(
                    "LLM_QUOTA_EXHAUSTED",
                    str(exc),
                    429,
                ) from exc
            except LLMRateLimitError as exc:
                raise rag_service.RAGError(
                    "LLM_RATE_LIMIT_ERROR",
                    "Generation service is temporarily rate limited",
                    503,
                ) from exc
            except LLMProviderError as exc:
                raise rag_service.RAGError(
                    "LLM_PROVIDER_ERROR", "Grounded answer generation failed", 503
                ) from exc

        yield ConversationStreamEvent(event_type="state", phase="finalizing")
        result = rag_service.persist_prepared_answer(
            db=db,
            workspace=workspace,
            requested_by=user.id,
            preparation=preparation,
            answer=answer,
            model=model,
            commit=False,
        )
        assistant_message = ConversationMessage(
            conversation_id=conversation.id,
            role="ASSISTANT",
            content=result.answer,
            rag_response_id=result.response_id,
            model=result.model,
            latency_ms=max(0, round((monotonic() - started) * 1000)),
            created_at=max(
                datetime.now(timezone.utc),
                user_message.created_at + timedelta(microseconds=1),
            ),
        )
        db.add(assistant_message)
        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()
        committed = True
        db.refresh(user_message)
        db.refresh(assistant_message)
        db.refresh(conversation)
        yield ConversationStreamEvent(
            event_type="complete",
            user_message=user_message,
            assistant_message=assistant_message,
            result=result,
        )
    except (rag_service.RAGError, ConversationError):
        raise
    except SQLAlchemyError as exc:
        raise ConversationError(
            "MESSAGE_PERSISTENCE_ERROR",
            "The grounded response could not be saved",
            500,
        ) from exc
    finally:
        if not committed:
            db.rollback()


def delete_conversation(db: Session, conversation: Conversation) -> None:
    response_ids = list(
        db.scalars(
            select(ConversationMessage.rag_response_id).where(
                ConversationMessage.conversation_id == conversation.id,
                ConversationMessage.rag_response_id.is_not(None),
            )
        ).all()
    )
    try:
        db.delete(conversation)
        db.flush()
        if response_ids:
            db.execute(delete(RAGResponseRecord).where(RAGResponseRecord.id.in_(response_ids)))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise ConversationError(
            "CONVERSATION_DELETE_ERROR", "The conversation could not be deleted", 500
        ) from exc

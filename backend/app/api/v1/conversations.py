import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_workspace_member
from app.db.session import SessionLocal, get_db
from app.embeddings.base import EmbeddingProvider
from app.embeddings.deps import get_embedding_provider
from app.llm.base import LLMProvider
from app.llm.deps import get_llm_provider
from app.models.conversation import Conversation, ConversationMessage
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.schemas.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationMessageCreate,
    ConversationMessageResponse,
    ConversationMessagesResponse,
    ConversationResponse,
    ConversationTurnResponse,
    ConversationUpdate,
)
from app.schemas.rag import RAGSource
from app.services import conversation as conversation_service
from app.services import rag as rag_service


router = APIRouter()


def _authorized_conversation(
    db: Session,
    workspace: Workspace,
    current_user: User,
    conversation_id: uuid.UUID,
) -> Conversation:
    conversation = conversation_service.get_conversation(
        db, workspace, current_user, conversation_id
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def _message_response(
    db: Session,
    workspace: Workspace,
    message: ConversationMessage,
    rag_result: rag_service.RAGResult | None = None,
    resolve_rag: bool = True,
) -> ConversationMessageResponse:
    if resolve_rag and rag_result is None and message.rag_response_id is not None:
        rag_result = rag_service.get_response(db, workspace, message.rag_response_id)
    return ConversationMessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
        response_id=rag_result.response_id if rag_result else None,
        sources=(
            [RAGSource.model_validate(source) for source in rag_result.sources]
            if rag_result
            else []
        ),
        insufficient_evidence=(rag_result.insufficient_evidence if rag_result else False),
        model=message.model,
        latency_ms=message.latency_ms,
    )


@router.post(
    "/{workspace_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    workspace_id: uuid.UUID,
    payload: ConversationCreate,
    workspace: Workspace = Depends(require_workspace_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    return conversation_service.create_conversation(db, workspace, current_user, payload)


@router.get(
    "/{workspace_id}/conversations", response_model=ConversationListResponse
)
def list_conversations(
    workspace_id: uuid.UUID,
    workspace: Workspace = Depends(require_workspace_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationListResponse:
    items = conversation_service.list_conversations(db, workspace, current_user)
    return ConversationListResponse(
        items=items,
        total=conversation_service.count_conversations(db, workspace, current_user),
    )


@router.get(
    "/{workspace_id}/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
def get_conversation(
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    workspace: Workspace = Depends(require_workspace_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    return _authorized_conversation(db, workspace, current_user, conversation_id)


@router.patch(
    "/{workspace_id}/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
def rename_conversation(
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    workspace: Workspace = Depends(require_workspace_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    conversation = _authorized_conversation(db, workspace, current_user, conversation_id)
    return conversation_service.rename_conversation(db, conversation, payload)


@router.delete(
    "/{workspace_id}/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    workspace: Workspace = Depends(require_workspace_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    conversation = _authorized_conversation(db, workspace, current_user, conversation_id)
    try:
        conversation_service.delete_conversation(db, conversation)
    except conversation_service.ConversationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.public_message},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{workspace_id}/conversations/{conversation_id}/messages",
    response_model=ConversationMessagesResponse,
)
def list_messages(
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    workspace: Workspace = Depends(require_workspace_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationMessagesResponse:
    conversation = _authorized_conversation(db, workspace, current_user, conversation_id)
    messages = conversation_service.list_messages(db, conversation)
    rag_results = rag_service.get_responses(
        db,
        workspace,
        [message.rag_response_id for message in messages if message.rag_response_id],
    )
    items = [
        _message_response(
            db,
            workspace,
            message,
            rag_results.get(message.rag_response_id) if message.rag_response_id else None,
            resolve_rag=False,
        )
        for message in messages
    ]
    return ConversationMessagesResponse(
        items=items, total=conversation_service.count_messages(db, conversation)
    )


@router.post(
    "/{workspace_id}/conversations/{conversation_id}/messages",
    response_model=ConversationTurnResponse,
)
def send_message(
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    payload: ConversationMessageCreate,
    workspace: Workspace = Depends(require_workspace_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    llm_provider: LLMProvider = Depends(get_llm_provider),
) -> ConversationTurnResponse:
    conversation = _authorized_conversation(db, workspace, current_user, conversation_id)
    try:
        user_message, assistant_message, rag_result = conversation_service.send_message(
            db=db,
            workspace=workspace,
            user=current_user,
            conversation=conversation,
            content=payload.content,
            top_k=payload.top_k,
            answer_language=payload.answer_language,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
        )
    except (conversation_service.ConversationError, rag_service.RAGError) as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.public_message},
        )
    return ConversationTurnResponse(
        conversation=ConversationResponse.model_validate(conversation),
        user_message=_message_response(db, workspace, user_message),
        assistant_message=_message_response(db, workspace, assistant_message, rag_result),
    )


def _sse(event: str, payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    return f"event: {event}\ndata: {data}\n\n"


@router.post(
    "/{workspace_id}/conversations/{conversation_id}/messages/stream",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {}}},
        401: {"description": "Authentication required"},
        404: {"description": "Workspace or conversation not found"},
    },
)
async def stream_message(
    request: Request,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    payload: ConversationMessageCreate,
    workspace: Workspace = Depends(require_workspace_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    llm_provider: LLMProvider = Depends(get_llm_provider),
) -> StreamingResponse:
    """Stream a grounded turn while preserving v1.2 authorization and persistence."""
    conversation = _authorized_conversation(
        db, workspace, current_user, conversation_id
    )
    try:
        rag_service.require_research_ready(db, workspace)
    except rag_service.RAGError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.public_message},
        )
    authorized_workspace_id = workspace.id
    authorized_user_id = current_user.id
    authorized_conversation_id = conversation.id

    async def event_stream():
        with SessionLocal() as stream_db:
            stream_workspace = stream_db.scalar(
                select(Workspace)
                .join(WorkspaceMembership)
                .where(
                    Workspace.id == authorized_workspace_id,
                    WorkspaceMembership.user_id == authorized_user_id,
                )
            )
            stream_user = stream_db.get(User, authorized_user_id)
            stream_conversation = (
                conversation_service.get_conversation(
                    stream_db,
                    stream_workspace,
                    stream_user,
                    authorized_conversation_id,
                )
                if stream_workspace is not None
                and stream_user is not None
                and stream_user.is_active
                else None
            )
            if stream_conversation is None:
                yield _sse(
                    "error",
                    {
                        "code": "CONVERSATION_UNAVAILABLE",
                        "message": "The conversation is no longer available",
                        "retryable": False,
                    },
                )
                return
            stream = conversation_service.stream_message(
                db=stream_db,
                workspace=stream_workspace,
                user=stream_user,
                conversation=stream_conversation,
                content=payload.content,
                top_k=payload.top_k,
                answer_language=payload.answer_language,
                embedding_provider=embedding_provider,
                llm_provider=llm_provider,
            )
            try:
                async for event in stream:
                    if await request.is_disconnected():
                        await stream.aclose()
                        return
                    if event.event_type == "state":
                        yield _sse("state", {"phase": event.phase})
                    elif event.event_type == "text_delta":
                        yield _sse("text_delta", {"text": event.text})
                    elif event.event_type == "complete":
                        assert event.user_message is not None
                        assert event.assistant_message is not None
                        assert event.result is not None
                        turn = ConversationTurnResponse(
                            conversation=ConversationResponse.model_validate(
                                stream_conversation
                            ),
                            user_message=_message_response(
                                stream_db, stream_workspace, event.user_message
                            ),
                            assistant_message=_message_response(
                                stream_db,
                                stream_workspace,
                                event.assistant_message,
                                event.result,
                            ),
                        )
                        yield _sse("complete", turn.model_dump(mode="json"))
            except (
                conversation_service.ConversationError,
                rag_service.RAGError,
            ) as exc:
                yield _sse(
                    "error",
                    {
                        "code": exc.code,
                        "message": exc.public_message,
                        "retryable": exc.status_code >= 500,
                    },
                )
            finally:
                await stream.aclose()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

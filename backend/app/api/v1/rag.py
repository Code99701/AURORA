import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_workspace_member
from app.db.session import get_db
from app.embeddings.base import EmbeddingProvider
from app.embeddings.deps import get_embedding_provider
from app.llm.base import LLMProvider
from app.llm.deps import get_llm_provider
from app.models.workspace import Workspace
from app.models.user import User
from app.schemas.rag import RAGRequest, RAGResponse, RAGSource
from app.services import rag as rag_service


router = APIRouter()


@router.post(
    "/{workspace_id}/rag",
    response_model=RAGResponse,
    response_model_exclude_none=True,
)
def answer_workspace_question(
    workspace_id: uuid.UUID,
    payload: RAGRequest,
    workspace: Workspace = Depends(require_workspace_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    llm_provider: LLMProvider = Depends(get_llm_provider),
) -> RAGResponse:
    try:
        result = rag_service.answer_question(
            db=db,
            workspace=workspace,
            requested_by=current_user.id,
            query=payload.query,
            top_k=payload.top_k,
            answer_language=payload.answer_language,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
        )
    except rag_service.RAGError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.public_message},
        )
    return RAGResponse(
        response_id=result.response_id,
        answer=result.answer,
        sources=[RAGSource.model_validate(source) for source in result.sources],
        insufficient_evidence=result.insufficient_evidence,
        model=result.model,
    )


@router.get(
    "/{workspace_id}/rag/responses/{response_id}",
    response_model=RAGResponse,
    response_model_exclude_none=True,
)
def get_rag_response(
    workspace_id: uuid.UUID,
    response_id: uuid.UUID,
    workspace: Workspace = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> RAGResponse:
    result = rag_service.get_response(db, workspace, response_id)
    if result is None:
        raise HTTPException(status_code=404, detail="RAG response not found")
    return RAGResponse(
        response_id=result.response_id,
        answer=result.answer,
        sources=[RAGSource.model_validate(source) for source in result.sources],
        insufficient_evidence=result.insufficient_evidence,
        model=result.model,
    )


@router.get(
    "/{workspace_id}/rag/citations/{citation_id}",
    response_model=RAGSource,
    response_model_exclude_none=True,
)
def get_citation_source(
    workspace_id: uuid.UUID,
    citation_id: uuid.UUID,
    workspace: Workspace = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> RAGSource:
    source = rag_service.get_citation_source(db, workspace, citation_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Citation source not found")
    return RAGSource.model_validate(source)

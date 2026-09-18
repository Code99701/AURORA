import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_workspace_member
from app.db.session import get_db
from app.embeddings.base import EmbeddingProvider
from app.embeddings.deps import get_embedding_provider
from app.models.workspace import Workspace
from app.schemas.retrieval import SearchRequest, SearchResponse, SearchResult
from app.services import retrieval as retrieval_service


router = APIRouter()


@router.post("/{workspace_id}/search", response_model=SearchResponse)
def search_workspace(
    workspace_id: uuid.UUID,
    payload: SearchRequest,
    workspace: Workspace = Depends(require_workspace_member),
    db: Session = Depends(get_db),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> SearchResponse:
    try:
        results = retrieval_service.search_workspace(
            db, workspace, payload.query, payload.top_k, provider
        )
    except retrieval_service.RetrievalError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.public_message},
        )
    items = [SearchResult.model_validate(result, from_attributes=True) for result in results]
    return SearchResponse(query=payload.query, items=items, total=len(items))

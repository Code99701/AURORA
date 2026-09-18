import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    require_workspace_member,
    require_workspace_owner,
)
from app.db.session import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.services import workspace as workspace_service
from app.storage.base import FileStorage, StorageError
from app.storage.deps import get_file_storage


router = APIRouter()


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    data: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Workspace:
    return workspace_service.create_workspace(db, data, current_user)


@router.get("", response_model=WorkspaceListResponse)
def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceListResponse:
    items = workspace_service.list_user_workspaces(db, current_user)
    return WorkspaceListResponse(items=items, total=len(items))


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(
    workspace_id: uuid.UUID,
    workspace: Workspace = Depends(require_workspace_member),
) -> Workspace:
    return workspace


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
def update_workspace(
    workspace_id: uuid.UUID,
    data: WorkspaceUpdate,
    workspace: Workspace = Depends(require_workspace_owner),
    db: Session = Depends(get_db),
) -> Workspace:
    return workspace_service.update_workspace(db, workspace, data)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(
    workspace_id: uuid.UUID,
    workspace: Workspace = Depends(require_workspace_owner),
    db: Session = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
) -> Response:
    try:
        workspace_service.delete_workspace(db, storage, workspace)
    except StorageError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document storage is unavailable",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

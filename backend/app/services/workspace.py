from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate
from app.storage.base import FileStorage


OWNER_ROLE = "OWNER"


def create_workspace(db: Session, data: WorkspaceCreate, creator: User) -> Workspace:
    """Create a workspace and its OWNER membership atomically."""
    workspace = Workspace(
        name=data.name,
        description=data.description,
        created_by=creator.id,
    )
    db.add(workspace)
    db.flush()
    db.add(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=creator.id,
            role=OWNER_ROLE,
        )
    )
    db.commit()
    db.refresh(workspace)
    return workspace


def list_user_workspaces(db: Session, user: User) -> list[Workspace]:
    statement = (
        select(Workspace)
        .join(WorkspaceMembership)
        .where(WorkspaceMembership.user_id == user.id)
        .order_by(Workspace.created_at, Workspace.id)
    )
    return list(db.scalars(statement).all())


def update_workspace(
    db: Session, workspace: Workspace, data: WorkspaceUpdate
) -> Workspace:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(workspace, field, value)
    db.commit()
    db.refresh(workspace)
    return workspace


def delete_workspace(db: Session, storage: FileStorage, workspace: Workspace) -> None:
    """Remove private document objects before cascading workspace metadata."""
    for document in workspace.documents:
        storage.delete(document.storage_key)
    db.delete(workspace)
    db.commit()

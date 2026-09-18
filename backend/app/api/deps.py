import uuid

from fastapi import Depends, Request, HTTPException, Path, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timezone
import logging

from app.db.session import get_db
from app.core.config import settings
from app.core.security import hash_session_token
from app.models.user import User
from app.models.session import Session as DBSession
from app.models.workspace import Workspace, WorkspaceMembership

logger = logging.getLogger(__name__)

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Dependency to resolve the currently authenticated user based on the HttpOnly cookie.
    Validates the session token, expiration, revocation, and user status.
    Returns 401 if authentication fails.
    """
    # 1. Read authentication cookie
    raw_token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # 2. Hash token to look up session
    token_hash = hash_session_token(raw_token)
    
    # 3. Resolve session from DB
    session = db.scalars(
        select(DBSession).where(DBSession.token_hash == token_hash)
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )
    
    # 4. Check if session is revoked
    if session.revoked_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )
    
    # 5. Check if session is expired
    now = datetime.now(timezone.utc)
    if session.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )
    
    # 6. Resolve user
    user = session.user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )
        
    # 7. Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled"
        )
        
    # Optimization: Only update last_seen_at if it's been more than an hour
    # to avoid unnecessary database writes on every single request.
    if (now - session.last_seen_at).total_seconds() > 3600:
        session.last_seen_at = now
        db.commit()

    return user


def get_current_workspace(
    workspace_id: uuid.UUID = Path(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Workspace:
    """Resolve a workspace only when the authenticated user is a member.

    Nonexistent and unauthorized workspace UUIDs intentionally share a 404
    response so callers cannot enumerate workspaces they do not belong to.
    """
    workspace = db.scalars(
        select(Workspace)
        .join(WorkspaceMembership)
        .where(
            Workspace.id == workspace_id,
            WorkspaceMembership.user_id == current_user.id,
        )
    ).first()
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    return workspace


def require_workspace_member(
    workspace: Workspace = Depends(get_current_workspace),
) -> Workspace:
    """Require membership and return the authorized workspace."""
    return workspace


def require_workspace_owner(
    workspace: Workspace = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Workspace:
    """Require the current member to hold the immutable OWNER role."""
    role = db.scalar(
        select(WorkspaceMembership.role).where(
            WorkspaceMembership.workspace_id == workspace.id,
            WorkspaceMembership.user_id == current_user.id,
        )
    )
    if role != "OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace owner access required",
        )
    return workspace

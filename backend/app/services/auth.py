import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_session_token, hash_password
from app.models.external_identity import ExternalIdentity
from app.models.session import Session as DBSession
from app.models.user import User


class OAuthAccountConflictError(Exception):
    """The verified email belongs to an account not linked to this identity."""


class OAuthIdentityPersistenceError(Exception):
    """The external identity could not be persisted safely."""


def issue_session(db: Session, response: Response, user: User) -> DBSession:
    """Create AURORA's standard opaque database session and HttpOnly cookie."""
    raw_token, token_hash = generate_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.SESSION_EXPIRY_DAYS)
    session = DBSession(user_id=user.id, token_hash=token_hash, expires_at=expires_at)
    db.add(session)
    db.commit()
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.SESSION_EXPIRY_DAYS * 24 * 60 * 60,
        path="/",
    )
    return session


def resolve_google_user(
    db: Session,
    *,
    subject: str,
    email: str,
    display_name: str | None,
) -> User:
    identity = db.scalars(
        select(ExternalIdentity).where(
            ExternalIdentity.provider == "google",
            ExternalIdentity.provider_subject == subject,
        )
    ).first()
    if identity is not None:
        return identity.user

    normalized_email = email.strip().casefold()
    if db.scalars(select(User).where(User.email == normalized_email)).first() is not None:
        raise OAuthAccountConflictError

    safe_name = (display_name or normalized_email.split("@", 1)[0]).strip()
    safe_name = safe_name[:100] or "AURORA user"
    # The schema intentionally keeps password_hash non-null for compatibility.
    # This random value is discarded and cannot be used to authenticate.
    user = User(
        email=normalized_email,
        password_hash=hash_password(secrets.token_urlsafe(48)),
        display_name=safe_name,
    )
    db.add(user)
    db.flush()
    db.add(
        ExternalIdentity(
            user_id=user.id,
            provider="google",
            provider_subject=subject,
            email=normalized_email,
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        identity = db.scalars(
            select(ExternalIdentity).where(
                ExternalIdentity.provider == "google",
                ExternalIdentity.provider_subject == subject,
            )
        ).first()
        if identity is not None:
            return identity.user
        if db.scalars(select(User).where(User.email == normalized_email)).first() is not None:
            raise OAuthAccountConflictError from exc
        raise OAuthIdentityPersistenceError from exc
    db.refresh(user)
    return user

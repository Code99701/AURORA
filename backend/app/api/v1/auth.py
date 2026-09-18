from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from datetime import datetime, timezone
import logging
import secrets

from app.db.session import get_db
from app.core.config import settings
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    generate_oauth_transaction,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.auth.google import (
    GoogleIdentityVerificationError,
    GoogleOIDCClient,
    GoogleTokenExchangeError,
    get_google_oidc_client,
)
from app.models.user import User
from app.models.session import Session as DBSession
from app.schemas.user import UserCreate, UserRead, UserLogin
from app.schemas.auth import (
    AuthProvidersResponse,
    LoginResponse,
    LogoutResponse,
)
from app.api.deps import get_current_user
from app.services.auth import (
    OAuthAccountConflictError,
    OAuthIdentityPersistenceError,
    issue_session,
    resolve_google_user,
)

logger = logging.getLogger(__name__)

router = APIRouter()

OAUTH_STATE_COOKIE = "aurora_oauth_state"
OAUTH_NONCE_COOKIE = "aurora_oauth_nonce"
OAUTH_PKCE_COOKIE = "aurora_oauth_pkce"
OAUTH_COOKIE_PATH = "/api/v1/auth/google"
OAUTH_SUCCESS_PATH = "/workspaces"
OAUTH_ERROR_PATH = "/login?oauth_error={}"


def _oauth_redirect(error_code: str | None = None) -> RedirectResponse:
    destination = OAUTH_SUCCESS_PATH if error_code is None else OAUTH_ERROR_PATH.format(error_code)
    response = RedirectResponse(destination, status_code=status.HTTP_303_SEE_OTHER)
    response.headers["Cache-Control"] = "no-store"
    for cookie_name in (OAUTH_STATE_COOKIE, OAUTH_NONCE_COOKIE, OAUTH_PKCE_COOKIE):
        response.delete_cookie(
            cookie_name,
            path=OAUTH_COOKIE_PATH,
            secure=settings.COOKIE_SECURE,
            httponly=True,
            samesite=settings.COOKIE_SAMESITE,
        )
    return response


def _set_oauth_cookie(response: Response, key: str, value: str) -> None:
    response.set_cookie(
        key=key,
        value=value,
        max_age=settings.GOOGLE_OAUTH_TRANSACTION_TTL_SECONDS,
        path=OAUTH_COOKIE_PATH,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
    )


@router.get("/providers", response_model=AuthProvidersResponse)
def auth_providers() -> AuthProvidersResponse:
    return AuthProvidersResponse(google={"enabled": settings.GOOGLE_OAUTH_ENABLED})


@router.get("/google/authorize")
def google_authorize(
    google: GoogleOIDCClient | None = Depends(get_google_oidc_client),
) -> RedirectResponse:
    if google is None:
        return _oauth_redirect("oauth_unavailable")
    state_value, nonce, verifier, challenge = generate_oauth_transaction()
    response = RedirectResponse(
        google.authorization_url(
            state=state_value,
            nonce=nonce,
            code_challenge=challenge,
        ),
        status_code=status.HTTP_302_FOUND,
    )
    response.headers["Cache-Control"] = "no-store"
    _set_oauth_cookie(response, OAUTH_STATE_COOKIE, state_value)
    _set_oauth_cookie(response, OAUTH_NONCE_COOKIE, nonce)
    _set_oauth_cookie(response, OAUTH_PKCE_COOKIE, verifier)
    return response


@router.get("/google/callback")
def google_callback(
    request: Request,
    db: Session = Depends(get_db),
    google: GoogleOIDCClient | None = Depends(get_google_oidc_client),
) -> RedirectResponse:
    returned_state = request.query_params.get("state")
    expected_state = request.cookies.get(OAUTH_STATE_COOKIE)
    nonce = request.cookies.get(OAUTH_NONCE_COOKIE)
    verifier = request.cookies.get(OAUTH_PKCE_COOKIE)
    if (
        not returned_state
        or not expected_state
        or not nonce
        or not verifier
        or not secrets.compare_digest(returned_state, expected_state)
    ):
        return _oauth_redirect("oauth_invalid_state")
    provider_error = request.query_params.get("error")
    if provider_error:
        return _oauth_redirect(
            "oauth_cancelled" if provider_error == "access_denied" else "oauth_provider_error"
        )
    code = request.query_params.get("code")
    if not code or len(code) > 4096:
        return _oauth_redirect("oauth_invalid_response")
    if google is None:
        return _oauth_redirect("oauth_unavailable")
    try:
        id_token = google.exchange_code(code=code, code_verifier=verifier)
        identity = google.verify_id_token(token=id_token, nonce=nonce)
        user = resolve_google_user(
            db,
            subject=identity.subject,
            email=identity.email,
            display_name=identity.display_name,
        )
        if not user.is_active:
            return _oauth_redirect("oauth_inactive_account")
        response = _oauth_redirect()
        issue_session(db, response, user)
        return response
    except OAuthAccountConflictError:
        return _oauth_redirect("oauth_account_conflict")
    except GoogleTokenExchangeError as exc:
        logger.warning(
            "Google sign-in failed during authorization code exchange (%s)",
            exc.reason,
        )
        error_code = (
            "oauth_provider_unreachable"
            if exc.reason == "network_error"
            else "oauth_invalid_response"
        )
        return _oauth_redirect(error_code)
    except GoogleIdentityVerificationError:
        logger.warning("Google sign-in failed during ID token verification")
        return _oauth_redirect("oauth_invalid_response")
    except (OAuthIdentityPersistenceError, SQLAlchemyError):
        db.rollback()
        logger.exception("Google sign-in persistence failed")
        return _oauth_redirect("oauth_provider_error")

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Registers a new user.
    """
    email_norm = str(user_in.email).strip().casefold()
    
    # Reject duplicate email
    existing = db.scalars(select(User).where(User.email == email_norm)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
        
    # Create user
    user = User(
        email=email_norm,
        password_hash=hash_password(user_in.password),
        display_name=user_in.display_name
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    db.refresh(user)
    
    return user


@router.post("/login", response_model=LoginResponse)
def login(user_in: UserLogin, response: Response, db: Session = Depends(get_db)):
    """
    Authenticates a user and sets a secure HttpOnly cookie.
    """
    # Use generic failure response
    invalid_creds_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password"
    )
    
    email_norm = str(user_in.email).strip().casefold()
    user = db.scalars(select(User).where(User.email == email_norm)).first()
    
    if not user:
        verify_password(user_in.password, DUMMY_PASSWORD_HASH)
        raise invalid_creds_exc
        
    if not user.is_active:
        raise invalid_creds_exc
        
    if not verify_password(user_in.password, user.password_hash):
        raise invalid_creds_exc
        
    issue_session(db, response, user)
    
    return LoginResponse(user=user)


@router.post("/logout", response_model=LogoutResponse)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """
    Logs out the user by revoking the session and clearing the cookie.
    """
    raw_token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    
    if raw_token:
        token_hash = hash_session_token(raw_token)
        session = db.scalars(select(DBSession).where(DBSession.token_hash == token_hash)).first()
        
        if session and not session.revoked_at:
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()
            
    # Always clear the cookie
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        path="/",
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE
    )
    
    return LogoutResponse()


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns the currently authenticated user's profile.
    """
    return current_user

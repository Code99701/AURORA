from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import secrets
from urllib.parse import urlencode

from email_validator import EmailNotValidError, validate_email
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token as google_id_token
import requests

from app.core.config import settings


GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


class GoogleOIDCError(Exception):
    """Base class for sanitized Google OIDC failures."""


class GoogleTokenExchangeError(GoogleOIDCError):
    """The authorization code could not be exchanged."""

    def __init__(self, reason: str = "provider_rejected") -> None:
        super().__init__(reason)
        self.reason = reason


class GoogleIdentityVerificationError(GoogleOIDCError):
    """The returned identity token was not trustworthy or complete."""


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str
    display_name: str | None


class GoogleOIDCClient:
    def __init__(self, *, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self.client_id = client_id
        self._client_secret = client_secret
        self.redirect_uri = redirect_uri

    def authorization_url(
        self, *, state: str, nonce: str, code_challenge: str
    ) -> str:
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "nonce": nonce,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{query}"

    def exchange_code(self, *, code: str, code_verifier: str) -> str:
        try:
            response = requests.post(
                GOOGLE_TOKEN_ENDPOINT,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self._client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": code_verifier,
                },
                timeout=10,
            )
        except requests.RequestException as exc:
            raise GoogleTokenExchangeError("network_error") from exc
        if not response.ok:
            reason = "provider_rejected"
            try:
                provider_reason = response.json().get("error")
            except (ValueError, AttributeError):
                provider_reason = None
            if provider_reason in {
                "invalid_client",
                "invalid_grant",
                "invalid_request",
                "redirect_uri_mismatch",
                "unauthorized_client",
            }:
                reason = provider_reason
            raise GoogleTokenExchangeError(reason)
        try:
            token = response.json().get("id_token")
        except (ValueError, AttributeError) as exc:
            raise GoogleTokenExchangeError from exc
        if not isinstance(token, str) or not token:
            raise GoogleTokenExchangeError("missing_id_token")
        return token

    def verify_id_token(self, *, token: str, nonce: str) -> GoogleIdentity:
        try:
            claims = google_id_token.verify_oauth2_token(
                token,
                GoogleAuthRequest(),
                audience=self.client_id,
            )
        except (ValueError, GoogleAuthError) as exc:
            raise GoogleIdentityVerificationError from exc

        now = datetime.now(timezone.utc).timestamp()
        subject = claims.get("sub")
        email = claims.get("email")
        issuer = claims.get("iss")
        audience = claims.get("aud")
        expires_at = claims.get("exp")
        token_nonce = claims.get("nonce")
        if (
            not isinstance(subject, str)
            or not subject
            or not isinstance(email, str)
            or claims.get("email_verified") is not True
            or issuer not in GOOGLE_ISSUERS
            or audience != self.client_id
            or not isinstance(expires_at, (int, float))
            or expires_at <= now
            or not isinstance(token_nonce, str)
            or not secrets.compare_digest(token_nonce, nonce)
        ):
            raise GoogleIdentityVerificationError
        try:
            normalized_email = validate_email(
                email, check_deliverability=False
            ).normalized.casefold()
        except EmailNotValidError as exc:
            raise GoogleIdentityVerificationError from exc
        name = claims.get("name")
        display_name = name.strip()[:100] if isinstance(name, str) and name.strip() else None
        return GoogleIdentity(
            subject=subject,
            email=normalized_email,
            display_name=display_name,
        )


@lru_cache
def get_google_oidc_client() -> GoogleOIDCClient | None:
    if not settings.GOOGLE_OAUTH_ENABLED:
        return None
    if (
        settings.GOOGLE_OAUTH_CLIENT_ID is None
        or settings.GOOGLE_OAUTH_CLIENT_SECRET is None
        or settings.GOOGLE_OAUTH_REDIRECT_URI is None
    ):
        return None
    return GoogleOIDCClient(
        client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
        client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET.get_secret_value(),
        redirect_uri=settings.GOOGLE_OAUTH_REDIRECT_URI,
    )

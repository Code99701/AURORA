from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app.auth import google as google_module
from app.auth.google import (
    GoogleIdentity,
    GoogleIdentityVerificationError,
    GoogleOIDCClient,
    GoogleTokenExchangeError,
    get_google_oidc_client,
)
from app.core.config import Settings, settings
from app.core.security import hash_password, hash_session_token
from app.db.session import SessionLocal
from app.main import app
from app.models.external_identity import ExternalIdentity
from app.models.session import Session as DBSession
from app.models.user import User
from app.storage.deps import get_file_storage
from app.storage.local import LocalFileStorage


CALLBACK_PATH = "/api/v1/auth/google/callback"
AUTHORIZE_PATH = "/api/v1/auth/google/authorize"
TEST_SECRET = "test-google-client-secret-never-return"
PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


class FakeGoogleOIDCClient:
    def __init__(
        self,
        identity: GoogleIdentity | None = None,
        *,
        exchange_error: bool = False,
        exchange_error_reason: str = "provider_rejected",
        verification_error: bool = False,
    ) -> None:
        self.identity = identity or GoogleIdentity(
            subject="google-sub-default",
            email="google-default@example.com",
            display_name="Google User",
        )
        self.exchange_error = exchange_error
        self.exchange_error_reason = exchange_error_reason
        self.verification_error = verification_error
        self.exchanges: list[tuple[str, str]] = []

    def authorization_url(self, *, state: str, nonce: str, code_challenge: str) -> str:
        return "https://accounts.google.com/o/oauth2/v2/auth?" + parse_url_query(
            {
                "client_id": "test-client-id",
                "redirect_uri": "http://localhost:3000/api/v1/auth/google/callback",
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "nonce": nonce,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )

    def exchange_code(self, *, code: str, code_verifier: str) -> str:
        self.exchanges.append((code, code_verifier))
        if self.exchange_error:
            raise GoogleTokenExchangeError(self.exchange_error_reason)
        return "mock-signed-id-token"

    def verify_id_token(self, *, token: str, nonce: str) -> GoogleIdentity:
        assert token == "mock-signed-id-token"
        assert nonce
        if self.verification_error:
            raise GoogleIdentityVerificationError
        return self.identity


def parse_url_query(values: dict[str, str]) -> str:
    from urllib.parse import urlencode

    return urlencode(values)


@pytest.fixture
def oauth_enabled(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_ENABLED", True)
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", SecretStr(TEST_SECRET))
    monkeypatch.setattr(
        settings,
        "GOOGLE_OAUTH_REDIRECT_URI",
        "http://localhost:3000/api/v1/auth/google/callback",
    )


def oauth_test_client(fake: FakeGoogleOIDCClient) -> TestClient:
    app.dependency_overrides[get_google_oidc_client] = lambda: fake
    return TestClient(app)


def begin_oauth(client: TestClient):
    response = client.get(AUTHORIZE_PATH, follow_redirects=False)
    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["location"]).query)
    return response, query


def finish_oauth(client: TestClient, state: str, *, extra: str = ""):
    suffix = f"&{extra}" if extra else ""
    return client.get(
        f"{CALLBACK_PATH}?state={state}&code=valid-one-time-code{suffix}",
        follow_redirects=False,
    )


def create_existing_identity(
    *, email: str, subject: str, active: bool = True, role: str = "USER"
) -> int:
    with SessionLocal.begin() as db:
        user = User(
            email=email,
            password_hash=hash_password("existing-password"),
            display_name="Existing User",
            is_active=active,
            system_role=role,
        )
        db.add(user)
        db.flush()
        db.add(
            ExternalIdentity(
                user_id=user.id,
                provider="google",
                provider_subject=subject,
                email=email,
            )
        )
        return user.id


def test_authorization_starts_with_state_nonce_pkce_and_secure_transaction_cookies(
    oauth_enabled,
):
    fake = FakeGoogleOIDCClient()
    client = oauth_test_client(fake)
    try:
        response, query = begin_oauth(client)
    finally:
        app.dependency_overrides.pop(get_google_oidc_client, None)

    assert query["response_type"] == ["code"]
    assert query["scope"] == ["openid email profile"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"][0] != query["nonce"][0]
    assert len(query["code_challenge"][0]) == 43
    cookie_headers = "\n".join(response.headers.get_list("set-cookie")).lower()
    assert all(name in cookie_headers for name in ("aurora_oauth_state", "aurora_oauth_nonce", "aurora_oauth_pkce"))
    assert cookie_headers.count("httponly") == 3
    assert cookie_headers.count("samesite=lax") == 3
    assert "max-age=600" in cookie_headers
    assert TEST_SECRET not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_invalid_state_is_rejected_before_code_exchange(oauth_enabled):
    fake = FakeGoogleOIDCClient()
    client = oauth_test_client(fake)
    try:
        begin_oauth(client)
        response = client.get(
            f"{CALLBACK_PATH}?state=attacker-state&code=code",
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(get_google_oidc_client, None)
    assert response.headers["location"] == "/login?oauth_error=oauth_invalid_state"
    assert fake.exchanges == []
    assert "max-age=0" in response.headers.get("set-cookie", "").lower()


def test_missing_code_and_consent_denial_are_safe(oauth_enabled):
    fake = FakeGoogleOIDCClient()
    client = oauth_test_client(fake)
    try:
        _, query = begin_oauth(client)
        missing = client.get(
            f"{CALLBACK_PATH}?state={query['state'][0]}", follow_redirects=False
        )
        _, second_query = begin_oauth(client)
        denied = client.get(
            f"{CALLBACK_PATH}?state={second_query['state'][0]}&error=access_denied&error_description={TEST_SECRET}",
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(get_google_oidc_client, None)
    assert missing.headers["location"] == "/login?oauth_error=oauth_invalid_response"
    assert denied.headers["location"] == "/login?oauth_error=oauth_cancelled"
    assert TEST_SECRET not in denied.text


@pytest.mark.parametrize(
    ("fake", "expected"),
    [
        (FakeGoogleOIDCClient(exchange_error=True), "oauth_invalid_response"),
        (
            FakeGoogleOIDCClient(
                exchange_error=True,
                exchange_error_reason="network_error",
            ),
            "oauth_provider_unreachable",
        ),
        (FakeGoogleOIDCClient(verification_error=True), "oauth_invalid_response"),
    ],
)
def test_exchange_and_identity_failures_are_sanitized(oauth_enabled, fake, expected):
    client = oauth_test_client(fake)
    try:
        _, query = begin_oauth(client)
        response = finish_oauth(client, query["state"][0])
    finally:
        app.dependency_overrides.pop(get_google_oidc_client, None)
    assert response.headers["location"] == f"/login?oauth_error={expected}"
    assert TEST_SECRET not in response.text
    assert settings.AUTH_COOKIE_NAME not in response.cookies


@pytest.mark.parametrize(
    "claim_override",
    [
        {"aud": "wrong-client"},
        {"iss": "https://attacker.invalid"},
        {"exp": 1},
        {"nonce": "wrong-nonce"},
        {"email_verified": False},
        {"sub": ""},
        {"email": None},
    ],
    ids=[
        "wrong-audience",
        "wrong-issuer",
        "expired",
        "wrong-nonce",
        "unverified-email",
        "missing-subject",
        "missing-email",
    ],
)
def test_id_token_claim_validation_rejects_substitution(monkeypatch, claim_override):
    now = int(datetime.now(timezone.utc).timestamp())
    claims = {
        "sub": "google-claim-sub",
        "email": "claims@example.com",
        "email_verified": True,
        "iss": "https://accounts.google.com",
        "aud": "expected-client",
        "exp": now + 300,
        "nonce": "expected-nonce",
        "name": "Claims User",
    }
    claims.update(claim_override)
    monkeypatch.setattr(
        google_module.google_id_token,
        "verify_oauth2_token",
        lambda *args, **kwargs: claims,
    )
    client = GoogleOIDCClient(
        client_id="expected-client",
        client_secret="server-secret",
        redirect_uri="http://localhost:3000/api/v1/auth/google/callback",
    )
    with pytest.raises(GoogleIdentityVerificationError):
        client.verify_id_token(token="mock-token", nonce="expected-nonce")


def test_new_google_identity_creates_user_and_standard_opaque_session(oauth_enabled):
    fake = FakeGoogleOIDCClient(
        GoogleIdentity("google-new-sub", "google-new@example.com", "New Google User")
    )
    client = oauth_test_client(fake)
    try:
        _, query = begin_oauth(client)
        response = finish_oauth(client, query["state"][0], extra="next=https://evil.example")
        me = client.get("/api/v1/auth/me")
    finally:
        app.dependency_overrides.pop(get_google_oidc_client, None)

    assert response.status_code == 303
    assert response.headers["location"] == "/workspaces"
    assert me.status_code == 200
    assert me.json()["email"] == "google-new@example.com"
    assert me.json()["system_role"] == "USER"
    cookie_header = "\n".join(response.headers.get_list("set-cookie"))
    assert f"{settings.AUTH_COOKIE_NAME}=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "samesite=lax" in cookie_header.lower()
    raw_token = client.cookies.get(settings.AUTH_COOKIE_NAME)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "google-new@example.com"))
        identity = db.scalar(
            select(ExternalIdentity).where(
                ExternalIdentity.provider_subject == "google-new-sub"
            )
        )
        session = db.scalar(select(DBSession).where(DBSession.user_id == user.id))
        assert identity.user_id == user.id
        assert session.token_hash == hash_session_token(raw_token)
        assert session.token_hash != raw_token
        assert "mock-signed" not in identity.email


def test_completed_oauth_transaction_cannot_be_replayed(oauth_enabled):
    fake = FakeGoogleOIDCClient(
        GoogleIdentity("google-replay-sub", "google-replay@example.com", "Replay Test")
    )
    client = oauth_test_client(fake)
    try:
        _, query = begin_oauth(client)
        state_value = query["state"][0]
        first = finish_oauth(client, state_value)
        replay = finish_oauth(client, state_value)
    finally:
        app.dependency_overrides.pop(get_google_oidc_client, None)
    assert first.headers["location"] == "/workspaces"
    assert replay.headers["location"] == "/login?oauth_error=oauth_invalid_state"
    assert len(fake.exchanges) == 1


def test_existing_google_subject_logs_into_mapped_user_and_preserves_admin_role(oauth_enabled):
    user_id = create_existing_identity(
        email="google-admin@example.com", subject="google-admin-sub", role="ADMIN"
    )
    fake = FakeGoogleOIDCClient(
        GoogleIdentity("google-admin-sub", "changed-email@example.com", "Changed")
    )
    client = oauth_test_client(fake)
    try:
        _, query = begin_oauth(client)
        response = finish_oauth(client, query["state"][0])
        me = client.get("/api/v1/auth/me")
    finally:
        app.dependency_overrides.pop(get_google_oidc_client, None)
    assert response.headers["location"] == "/workspaces"
    assert me.json()["id"] == user_id
    assert me.json()["email"] == "google-admin@example.com"
    assert me.json()["system_role"] == "ADMIN"


def test_matching_password_email_is_never_silently_linked(oauth_enabled):
    password_client = TestClient(app)
    registration = password_client.post(
        "/api/v1/auth/register",
        json={
            "email": "password-conflict@example.com",
            "password": "conflict-password",
            "display_name": "Password Owner",
        },
    )
    assert registration.status_code == 201
    fake = FakeGoogleOIDCClient(
        GoogleIdentity("unlinked-google-sub", "password-conflict@example.com", "Other")
    )
    client = oauth_test_client(fake)
    try:
        _, query = begin_oauth(client)
        response = finish_oauth(client, query["state"][0])
    finally:
        app.dependency_overrides.pop(get_google_oidc_client, None)
    assert response.headers["location"] == "/login?oauth_error=oauth_account_conflict"
    assert settings.AUTH_COOKIE_NAME not in response.cookies
    with SessionLocal() as db:
        assert db.scalar(
            select(ExternalIdentity).where(
                ExternalIdentity.provider_subject == "unlinked-google-sub"
            )
        ) is None


def test_inactive_google_user_is_rejected(oauth_enabled):
    create_existing_identity(
        email="inactive-google@example.com", subject="inactive-google-sub", active=False
    )
    fake = FakeGoogleOIDCClient(
        GoogleIdentity("inactive-google-sub", "inactive-google@example.com", "Inactive")
    )
    client = oauth_test_client(fake)
    try:
        _, query = begin_oauth(client)
        response = finish_oauth(client, query["state"][0])
    finally:
        app.dependency_overrides.pop(get_google_oidc_client, None)
    assert response.headers["location"] == "/login?oauth_error=oauth_inactive_account"
    assert settings.AUTH_COOKIE_NAME not in response.cookies


def test_provider_status_is_minimal_and_disabled_authorize_is_safe(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_ENABLED", False)
    get_google_oidc_client.cache_clear()
    client = TestClient(app)
    status_response = client.get("/api/v1/auth/providers")
    authorize_response = client.get(AUTHORIZE_PATH, follow_redirects=False)
    assert status_response.json() == {"google": {"enabled": False}}
    assert TEST_SECRET not in status_response.text
    assert authorize_response.headers["location"] == "/login?oauth_error=oauth_unavailable"


def test_google_login_preserves_workspace_and_private_resource_authorization(
    oauth_enabled, tmp_path
):
    storage = LocalFileStorage(tmp_path / "oauth-private-storage")
    app.dependency_overrides[get_file_storage] = lambda: storage
    fake = FakeGoogleOIDCClient(
        GoogleIdentity("google-rbac-sub", "google-rbac@example.com", "OAuth Owner")
    )
    owner = oauth_test_client(fake)
    try:
        _, query = begin_oauth(owner)
        finish_oauth(owner, query["state"][0])
        workspace = owner.post(
            "/api/v1/workspaces",
            json={"name": "OAuth private workspace", "description": "Private"},
        ).json()
        document = owner.post(
            f"/api/v1/workspaces/{workspace['id']}/documents",
            files={"file": ("oauth.pdf", PDF_BYTES, "application/pdf")},
        ).json()
        conversation = owner.post(
            f"/api/v1/workspaces/{workspace['id']}/conversations", json={}
        ).json()

        outsider = TestClient(app)
        outsider.post(
            "/api/v1/auth/register",
            json={
                "email": "oauth-rbac-outsider@example.com",
                "password": "outsider-password",
                "display_name": "Outsider",
            },
        )
        outsider.post(
            "/api/v1/auth/login",
            json={"email": "oauth-rbac-outsider@example.com", "password": "outsider-password"},
        )
        assert owner.get(f"/api/v1/workspaces/{workspace['id']}").status_code == 200
        assert outsider.get(f"/api/v1/workspaces/{workspace['id']}").status_code == 404
        assert outsider.get(
            f"/api/v1/workspaces/{workspace['id']}/documents/{document['id']}"
        ).status_code == 404
        assert outsider.get(
            f"/api/v1/workspaces/{workspace['id']}/conversations/{conversation['id']}"
        ).status_code == 404
        assert TestClient(app).get("/api/v1/workspaces").status_code == 401
    finally:
        app.dependency_overrides.pop(get_file_storage, None)
        app.dependency_overrides.pop(get_google_oidc_client, None)


def test_duplicate_provider_identity_is_rejected_by_database(oauth_enabled):
    create_existing_identity(
        email="identity-first@example.com", subject="duplicate-provider-sub"
    )
    with SessionLocal() as db:
        second = User(
            email="identity-second@example.com",
            password_hash=hash_password("second-password"),
            display_name="Second",
        )
        db.add(second)
        db.flush()
        db.add(
            ExternalIdentity(
                user_id=second.id,
                provider="google",
                provider_subject="duplicate-provider-sub",
                email=second.email,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_google_oauth_settings_require_complete_https_ready_configuration():
    with pytest.raises(ValidationError):
        Settings(GOOGLE_OAUTH_ENABLED=True, _env_file=None)
    valid = Settings(
        GOOGLE_OAUTH_ENABLED=True,
        GOOGLE_OAUTH_CLIENT_ID="client-id",
        GOOGLE_OAUTH_CLIENT_SECRET="secret",
        GOOGLE_OAUTH_REDIRECT_URI="http://localhost:3000/api/v1/auth/google/callback",
        _env_file=None,
    )
    assert valid.GOOGLE_OAUTH_CLIENT_SECRET.get_secret_value() == "secret"
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            COOKIE_SECURE=True,
            GOOGLE_OAUTH_ENABLED=True,
            GOOGLE_OAUTH_CLIENT_ID="client-id",
            GOOGLE_OAUTH_CLIENT_SECRET="secret",
            GOOGLE_OAUTH_REDIRECT_URI="http://example.com/api/v1/auth/google/callback",
            _env_file=None,
        )


def test_frontend_has_no_google_client_secret_configuration():
    frontend = Path(__file__).resolve().parents[2] / "frontend"
    inspected = [
        path
        for path in frontend.rglob("*")
        if path.is_file()
        and "node_modules" not in path.parts
        and ".next" not in path.parts
        and path.suffix in {".ts", ".tsx", ".js", ".mjs", ".json"}
    ]
    content = "\n".join(path.read_text(encoding="utf-8") for path in inspected)
    assert "GOOGLE_OAUTH_CLIENT_SECRET" not in content
    assert TEST_SECRET not in content


def test_external_identity_migration_upgrade_downgrade_and_reupgrade(
    disposable_database, run_alembic
):
    database_url = make_url(str(settings.SQLALCHEMY_DATABASE_URI)).set(
        database=disposable_database
    )
    engine = create_engine(database_url)
    try:
        run_alembic("upgrade", "c91a2d7e4f10", database=disposable_database)
        with engine.connect() as connection:
            assert connection.scalar(
                text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name='external_identities')"
                )
            ) is False
        run_alembic("upgrade", "head", database=disposable_database)
        with engine.connect() as connection:
            assert connection.scalar(
                text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name='external_identities')"
                )
            ) is True
        run_alembic("downgrade", "c91a2d7e4f10", database=disposable_database)
        with engine.connect() as connection:
            assert connection.scalar(
                text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name='external_identities')"
                )
            ) is False
        run_alembic("upgrade", "head", database=disposable_database)
    finally:
        engine.dispose()

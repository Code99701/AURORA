from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
import secrets
import hashlib

# Initialize the Argon2 password hasher
ph = PasswordHasher()

# A fixed Argon2id hash makes unknown-email login attempts perform the same
# expensive verification step as known-email attempts. The plaintext value is
# not a credential and is never accepted by the authentication flow.
DUMMY_PASSWORD_HASH = ph.hash("aurora-login-timing-placeholder")

def hash_password(password: str) -> str:
    """
    Hashes a password using Argon2id.
    """
    return ph.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verifies a password against an Argon2id hash.
    Returns True if valid, False otherwise.
    """
    try:
        return ph.verify(hashed_password, password)
    except (VerificationError, InvalidHashError):
        return False

def generate_session_token() -> tuple[str, str]:
    """
    Generates a cryptographically secure random session token.
    Returns a tuple of (raw_token, token_hash).
    
    The raw_token is sent to the client (HttpOnly cookie).
    The token_hash is stored in the database.
    """
    # 32 bytes (256 bits) of entropy, base64 url-safe encoded (~43 chars)
    raw_token = secrets.token_urlsafe(32)
    
    # Hash the token before storing it
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    
    return raw_token, token_hash

def hash_session_token(raw_token: str) -> str:
    """
    Hashes an existing raw token (e.g., from a cookie) to look up in the DB.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_oauth_transaction() -> tuple[str, str, str, str]:
    """Return state, nonce, PKCE verifier, and its S256 challenge."""
    import base64

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return state, nonce, code_verifier, code_challenge


def _get_reset_signing_key() -> bytes:
    from app.core.config import settings

    if settings.GOOGLE_OAUTH_CLIENT_SECRET:
        secret_val = settings.GOOGLE_OAUTH_CLIENT_SECRET.get_secret_value()
        return hashlib.sha256(secret_val.encode("utf-8")).digest()
    return hashlib.sha256(b"aurora-secure-signing-secret-placeholder").digest()


def create_password_reset_token(user_id: int, email: str, expires_in_seconds: int = 900) -> str:
    """
    Creates a signed, tamper-proof password reset token valid for 15 minutes by default.
    Format: <base64url_payload>.<base64url_hmac_signature>
    """
    import base64
    import hmac
    import json
    import time

    payload = {
        "uid": user_id,
        "em": email.strip().casefold(),
        "exp": int(time.time()) + expires_in_seconds,
        "nonce": secrets.token_hex(8),
    }
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("ascii").rstrip("=")
    key = _get_reset_signing_key()
    signature = hmac.new(key, payload_b64.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{payload_b64}.{sig_b64}"


def verify_password_reset_token(token: str) -> dict | None:
    """
    Verifies a password reset token.
    Returns dict with user_id and email if valid and unexpired, else None.
    """
    import base64
    import hmac
    import json
    import time

    if not token or "." not in token:
        return None
    parts = token.split(".")
    if len(parts) != 2:
        return None
    payload_b64, sig_b64 = parts
    try:
        key = _get_reset_signing_key()
        expected_sig = hmac.new(key, payload_b64.encode("ascii"), hashlib.sha256).digest()
        sig_padding = "=" * (-len(sig_b64) % 4)
        provided_sig = base64.urlsafe_b64decode(sig_b64 + sig_padding)
        if not hmac.compare_digest(expected_sig, provided_sig):
            return None

        payload_padding = "=" * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + payload_padding)
        payload = json.loads(payload_bytes.decode("utf-8"))

        if payload.get("exp", 0) < int(time.time()):
            return None

        return {
            "user_id": int(payload["uid"]),
            "email": str(payload["em"]),
        }
    except Exception:
        return None


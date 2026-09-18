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

# Security Foundation v0.3

Security Foundation v0.3 implements local email/password authentication with opaque, server-side sessions. It does not use JWT, Redis, OAuth, browser storage, workspace authorization, or frontend code.

## Stored data

`users` contains `id`, normalized unique email, Argon2id `password_hash`, `display_name`, `system_role`, `is_active`, and timestamps. The database and ORM default roles to `USER` and active status to `true`. API response schemas never contain `password_hash`.

`sessions` contains `id`, `user_id`, a unique indexed SHA-256 `token_hash`, expiry and activity timestamps, and an optional revocation timestamp. It references `users` with cascading deletion. The raw token exists only in the browser cookie and is never persisted or returned in a response body.

## Authentication flow

Registration normalizes email using trimmed Unicode-aware case folding, rejects duplicates, hashes the password with `argon2-cffi`'s Argon2id implementation, and stores no plaintext password.

Login returns the same `Invalid email or password` response for unknown email, incorrect password, and inactive accounts. Unknown-email attempts perform a dummy Argon2id verification to reduce account-enumeration timing differences. A successful login generates a 256-bit random token with Python's `secrets` module, stores only its SHA-256 digest, and sets the raw value in an HttpOnly cookie.

`get_current_user()` hashes the cookie, resolves the server-side session, rejects missing, expired, or revoked sessions, resolves the associated user, and rejects inactive accounts. It updates `last_seen_at` at most hourly.

Logout revokes the matching database session and clears the cookie. It is idempotent and does not reveal whether a session existed.

## Cookie configuration

Local defaults are:

```dotenv
AUTH_COOKIE_NAME=aurora_session
SESSION_EXPIRY_DAYS=7
COOKIE_SECURE=False
COOKIE_SAMESITE=lax
```

The cookie is HttpOnly, applies to `/`, and receives a matching maximum age. Production configuration rejects `COOKIE_SECURE=False`; `SameSite=None` is rejected unless the cookie is also Secure.

## Endpoints

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

`/auth/me` uses the shared `get_current_user()` dependency and returns HTTP 401 without a valid active session.

## Test isolation and coverage

Authentication tests run only in the suite's disposable PostgreSQL database. They cover registration, normalized duplicate rejection, Argon2id storage, absence of plaintext, valid and invalid login, generic failures, server-side session creation, hashed tokens, HttpOnly cookies, authenticated identity resolution, logout, revocation, expiration, inactive users, and response secret exclusion.

This foundation authenticates identity only. Workspace ownership, membership, and authorization are explicitly deferred to a later milestone.

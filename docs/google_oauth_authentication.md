# Google OAuth / OpenID Connect Authentication

## Purpose and architecture

Google Sign-In is an additional way to establish an AURORA session. It does
not replace email/password authentication and does not introduce a second
session system.

```text
Browser on http://localhost:3000
  -> GET /api/v1/auth/google/authorize (Next.js same-origin rewrite)
  -> Google authorization endpoint
  -> GET /api/v1/auth/google/callback (Next.js same-origin rewrite)
  -> FastAPI verifies the Google identity
  -> AURORA resolves or creates its User
  -> AURORA creates its existing opaque Session row
  -> aurora_session HttpOnly cookie
  -> /workspaces
```

The configured callback is a public frontend-origin URL because the browser
enters AURORA through Next.js on port 3000. Next.js forwards `/api/*` to
FastAPI on port 8000. This keeps the callback and resulting host-only session
cookie first-party. The callback handler itself lives in FastAPI at
`GET /api/v1/auth/google/callback`.

Use `localhost` consistently during local development. Starting authorization
on `127.0.0.1` but returning to a `localhost` callback changes the cookie host
and correctly causes state validation to fail.

## Authorization-code flow

1. `GET /api/v1/auth/google/authorize` verifies that Google login is enabled.
2. FastAPI generates independent high-entropy state, nonce, and PKCE verifier
   values. It stores them only in short-lived HttpOnly, SameSite cookies.
3. FastAPI redirects to Google's authorization endpoint with `openid email
   profile`, the fixed configured callback, state, nonce, and an S256 PKCE
   challenge.
4. Google redirects the browser to the fixed callback with a one-time code.
5. FastAPI compares state before processing provider errors or the code. It
   exchanges the code directly with Google's token endpoint using the PKCE
   verifier and server-side client secret.
6. The `google-auth` verifier validates the ID-token signature. AURORA also
   requires the configured audience, a Google issuer, a future expiration,
   the original nonce, a stable non-empty `sub`, and a verified valid email.
7. AURORA resolves the identity and creates its normal database session. No
   Google access token, refresh token, or ID token is persisted.
8. OAuth transaction cookies are cleared on every callback result. Success
   redirects only to `/workspaces`; errors redirect only to an allowlisted
   `/login?oauth_error=...` value.

## Identity and account-linking policy

`external_identities` stores only:

- AURORA `user_id`
- provider (`google`)
- Google's stable subject identifier (`provider_subject`)
- optional verified email for minimal audit context
- creation and update timestamps

`(provider, provider_subject)` is unique, and a user can have at most one
identity for a provider. Existing password hashes and all User, Session,
workspace, document, RAG, and conversation relationships are unchanged.

The policy is deliberately conservative:

- An existing Google subject authenticates only its mapped AURORA user.
- A new subject with an unused verified email creates a new USER account and
  identity atomically.
- A new subject whose email matches any existing AURORA account is rejected
  with instructions to use password login. It is never linked by email alone.
- Inactive mapped users are rejected.

An authenticated account-linking feature is not part of this milestone. Until
one exists, a password account and a new Google identity with the same email
remain separate and cannot be merged through the OAuth callback.

OAuth-created users retain a random, discarded Argon2 value in the existing
non-null `password_hash` column. That value is unknown and cannot be used for
password login; retaining the column contract avoids changing the established
password architecture.

## Session and cookie behavior

Both password and Google login call the same `issue_session` service. It:

- generates the existing 256-bit opaque token;
- stores only its SHA-256 hash in PostgreSQL;
- applies the configured expiration;
- sets the existing `aurora_session` cookie with `HttpOnly`, configured
  `Secure`, configured `SameSite`, and path `/`.

The raw AURORA session token is never returned in JSON or read by frontend
JavaScript. Existing logout, revocation, expiry, current-user, workspace
membership, OWNER/MEMBER, USER/ADMIN, and concealed-resource dependencies apply
without a Google-specific branch.

## Environment variables

All Google credentials belong in the root `.env`, never in frontend
`NEXT_PUBLIC_*` variables:

```dotenv
GOOGLE_OAUTH_ENABLED=True
GOOGLE_OAUTH_CLIENT_ID=your-web-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-server-side-client-secret
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:3000/api/v1/auth/google/callback
GOOGLE_OAUTH_TRANSACTION_TTL_SECONDS=600
```

Configuration validation requires all values when enabled. The redirect must
be an absolute URL with exactly `/api/v1/auth/google/callback`, with no embedded
credentials, query, or fragment. HTTP is accepted only for `localhost` or
`127.0.0.1`; production requires HTTPS. Production must also set
`COOKIE_SECURE=True`.

## Google Cloud Console setup

Create or select a Google Cloud project, configure the OAuth consent screen,
and create an OAuth client with application type **Web application**.

For local development configure:

- Authorized JavaScript origin: `http://localhost:3000`
- Authorized redirect URI:
  `http://localhost:3000/api/v1/auth/google/callback`
- Requested identity scopes: `openid`, `email`, `profile`

The redirect URI must match character-for-character. If the consent screen is
in testing mode, add the intended Google accounts as test users. Copy the web
client ID and secret to the backend `.env`, run `alembic upgrade head`, restart
FastAPI and Next.js, and open `http://localhost:3000/login`.

Do not place the Gemini key or Google OAuth client secret in Google-visible
URLs, frontend environment files, browser storage, or JavaScript bundles.

## Safe errors

The callback never reflects provider descriptions or internal exceptions. The
frontend maps only these codes to user guidance:

- `oauth_cancelled`
- `oauth_invalid_state`
- `oauth_invalid_response`
- `oauth_provider_error`
- `oauth_account_conflict`
- `oauth_inactive_account`
- `oauth_unavailable`

Unknown values receive one generic message. Client secrets, provider token
responses, stack traces, database errors, and filesystem paths are not exposed.

## Testing strategy

Normal tests use a fake OIDC adapter and make no Google network requests. They
cover transaction generation, PKCE, state ordering, safe provider failures,
token-claim validation, new and existing identities, no email takeover,
inactive users, unchanged roles, opaque session creation, cookie attributes,
fixed redirects, workspace/resource isolation, database uniqueness, and the
Alembic upgrade/downgrade lifecycle. Existing password, logout, workspace,
document, RAG, conversation, and streaming tests remain the regression suite.

## Production considerations

- Use an HTTPS redirect URI on the real frontend origin and set
  `COOKIE_SECURE=True`.
- Restrict CORS to deployed AURORA origins even though the normal browser path
  is same-origin.
- Store the client secret in the deployment secret manager and rotate it if
  exposed.
- Keep dependencies patched so Google's signing-key and token verification
  behavior remains current.
- Monitor sanitized OAuth outcome codes, not authorization codes, ID tokens,
  secrets, or raw session cookies.
- Configure the consent screen, publishing state, branding, privacy policy,
  and authorized domain appropriate to the deployment.

Manual browser verification with a configured Google Cloud client remains
necessary because automated tests intentionally do not use real accounts or
consume provider quota.

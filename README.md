# AURORA

## AURORA: Multilingual RAG Platform

AURORA is a secure multilingual AI knowledge-discovery and
research-assistance platform based on Retrieval-Augmented Generation (RAG).

## Project Foundation

**V Semester Cornerstone Project**

**Topic #16 — Design and Development of Multilingual RAG Chatbot**

## Core Pipeline

Document Ingestion
→ Extraction
→ Cleaning
→ Chunking
→ Embeddings
→ Vector Storage
→ Retrieval
→ RAG
→ Citations
→ Multilingual Answer

## Architecture

- Frontend: Next.js 16 App Router + React 19 + TypeScript
- Backend: FastAPI + Python
- Database: PostgreSQL + pgvector
- AI: Gemini initially
- Authentication: Server-side sessions
- Authorization: RBAC
- Architecture: Modular monolith

## Development Principle

Learn
→ Build
→ Understand
→ Integrate
→ Test
→ Document
→ Viva

## Project Structure

```text
AURORA/
├── backend/
├── frontend/
├── docs/
├── learning/
├── tests/
└── scripts/
```

## Running the Database (v0.2)

1. Ensure Docker is running.
2. Copy `.env.example` to `.env` (already done if following setup).
3. Start the PostgreSQL database:
   ```powershell
   docker compose up -d db
   ```
4. Run database migrations:
   ```powershell
   cd backend
   alembic upgrade head
   ```

## Running the Backend (v0.1–v0.7)

1. Activate the environment:
   ```powershell
   .\backend\aurora-env\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r backend\requirements.txt
   ```
3. Run the application:
   ```powershell
   cd backend
   uvicorn app.main:app --reload
   ```
4. Run tests:
   ```powershell
   docker compose up -d db
   cd backend
   pytest tests/
   ```

The test suite creates and removes isolated `aurora_test_*` databases. It does
not clear the development database. Database and security implementation notes
are in `docs/database_foundation_v0.2.md` and
`docs/security_foundation_v0.3.md`. The workspace isolation and OWNER/MEMBER
authorization boundary is documented in `docs/workspace_authorization_v0.4.md`.

## Running the Frontend

The frontend uses a same-origin `/api` rewrite, so browser credentials remain
first-party while requests are forwarded to the FastAPI service.

```powershell
cd frontend
pnpm install
pnpm dev
```

Open `http://localhost:3000`. The backend origin defaults to
`http://127.0.0.1:8000`; override it with `AURORA_BACKEND_ORIGIN` when needed.
No Gemini or other provider secret belongs in the frontend environment.

### One-click Windows launcher

After Docker Desktop, Python, and Node.js are installed, double-click
`start-aurora.bat` in the AURORA root. It automatically starts PostgreSQL,
creates missing local environments when possible, installs missing
dependencies, applies Alembic migrations, opens the backend and frontend in
separate terminals, waits for the frontend, and opens `http://localhost:3000`.

The launcher does not stop PostgreSQL when its own window closes. Close the two
server terminals to stop the development servers; use `docker compose down`
from the AURORA root when you also want to stop the database.

Frontend quality gates:

```powershell
pnpm typecheck
pnpm lint
pnpm build
```

The design system and implementation notes are in
`design-system/aurora/MASTER.md` and `docs/frontend_foundation_v1.1.md`.

## Google Sign-In

Google OpenID Connect is available as an optional authentication method while
preserving AURORA's existing opaque PostgreSQL sessions and `aurora_session`
HttpOnly cookie. Configure the server-only Google variables from
`.env.example`, apply `alembic upgrade head`, and enter this exact local web
client redirect URI in Google Cloud:

```text
http://localhost:3000/api/v1/auth/google/callback
```

The callback is handled by FastAPI through the frontend's same-origin rewrite.
No Google tokens are stored, and a matching password-account email is never
silently linked. Setup, security controls, and production guidance are in
`docs/google_oauth_authentication.md`.

## Local Document Storage

The local MVP stores validated source binaries under the private, Git-ignored
`storage/uploads/` directory. PostgreSQL stores document metadata only. The
root and 10 MiB default upload limit can be changed with
`DOCUMENT_STORAGE_ROOT` and `DOCUMENT_MAX_SIZE_BYTES`; no cloud credentials are
required. See `docs/document_management_v0.5.md` for the storage abstraction,
workspace isolation, validation, and API behavior.

## Multi-Format Document Intelligence (v1.4.2)

The supported source formats are PDF, TXT, Markdown, CSV, TSV, DOCX, XLSX, and
PPTX. The workspace UI automatically uploads, detects, processes, and indexes
each source through the same canonical pipeline. PDF processing retains native
extraction plus selective local OCR for scanned, image, mixed, and
vector-outline pages:

```http
POST /api/v1/workspaces/{workspace_id}/documents/{document_id}/process
```

Processing reads the private binary only through `FileStorage`, selects an
allowlisted adapter after extension/MIME/container validation, creates
versioned canonical units with format-native provenance, and can retain useful
evidence as `PARTIALLY_PROCESSED`. Indexing reads usable canonical units
directly; `ExtractedPage` remains a PDF compatibility view. Tesseract 5 with
English/Hindi language data is required only for PDF pages needing OCR.

Current Office parsers are `python-docx`, `openpyxl`, and `python-pptx`.
DOC/PPT/XLS legacy files, images, HTML, JSON/XML, archives, audio/video, and
advanced visual interpretation remain unsupported. See
`docs/multiformat_document_intelligence_v1.4.2.md` for the format matrix,
provenance model, security controls, limits, test evidence, and known
limitations. The preceding PDF/canonical hardening remains documented in
`docs/universal_document_intelligence_hardening.md`.

## RAG Data Pipeline (v0.7)

After processing, a workspace member can build or reuse a page-aware vector
index and run authorized semantic search:

```http
POST /api/v1/workspaces/{workspace_id}/documents/{document_id}/index
POST /api/v1/workspaces/{workspace_id}/search
```

The deterministic 1,000-character/150-overlap chunker preserves canonical
locators and page provenance where applicable. Bounded candidate retrieval
adds within-document deduplication and multi-document diversity. Embeddings use
`gemini-embedding-001` at 768 dimensions through a
provider-neutral interface and are stored in PostgreSQL `vector(768)`. Search
uses exact cosine distance with workspace filtering in SQL. Configure
`GEMINI_API_KEY` to use the production adapter; tests use a deterministic fake
and make no cloud calls. See `docs/rag_data_pipeline_v0.7.md` for details.

## RAG Generation (v0.8)

Authorized workspace questions can now produce one-shot grounded answers:

```http
POST /api/v1/workspaces/{workspace_id}/rag
```

The server retrieves authorized chunks, applies a relevance threshold, builds a
bounded untrusted-evidence context, calls the configurable Gemini generation
model, and constructs source references from retrieval data. Empty or weak
evidence returns a controlled insufficient-evidence answer without calling the
LLM. See `docs/rag_generation_foundation_v0.8.md` for configuration, security,
testing, and limitations.

## Citations and Evidence (v0.9)

Successful and insufficient-evidence RAG results now receive stable persisted
response IDs. Each selected evidence chunk becomes an ordered, server-generated
citation stored transactionally with the response. Authorized members can fetch
the durable result using:

```http
GET /api/v1/workspaces/{workspace_id}/rag/responses/{response_id}
```

Citation metadata remains traceable through the real chunk, page, document, and
workspace relationships. Deleted evidence is never replaced by stale source
snapshots or exposed as a partial citation set. See
`docs/citations_and_evidence_foundation_v0.9.md` for the schema, lifecycle,
security boundary, and deletion behavior.

## Multilingual RAG Evaluation (v1.0)

AURORA's existing multilingual embedding path has now been evaluated for English
and Hindi, including same-language and cross-language retrieval in mixed corpora.
The original query is embedded without automatic translation, and retrieved
source text plus citation provenance remains in its original language.

The reproducible six-case automated matrix exercises real PostgreSQL/pgvector
retrieval with deterministic quota-free providers. A separate explicit test has
also verified both English-query→Hindi-source and Hindi-query→English-source
flows using the configured Gemini embedding and generation adapters. See
`docs/multilingual_rag_foundation_v1.0.md` for the measured results, methodology,
security checks, and limitations.

## Persistent Conversations and Chat UX (v1.2)

Research questions and grounded answers can now be organized into durable,
user-owned conversations inside an authorized workspace. The API supports
conversation creation, listing, retrieval, rename, deletion, history loading,
and message submission under `/api/v1/workspaces/{workspace_id}/conversations`.

Every follow-up performs fresh workspace-scoped semantic retrieval. Up to 8
recent messages and 6,000 characters are supplied only as untrusted contextual
information; they never become authorization evidence. Assistant messages link
to the existing persisted RAG response and citation records rather than copying
citation storage. See `docs/conversations_chat_ux_v1.2.md` for the schema,
security boundary, API, frontend states, testing, and v1.3 boundary.

## Streaming RAG (v1.3)

Persistent research turns can now use real provider-backed Server-Sent Events:

```http
POST /api/v1/workspaces/{workspace_id}/conversations/{conversation_id}/messages/stream
```

The endpoint preserves the synchronous v1.2 route as a fallback. It performs
fresh authorized retrieval, streams normalized provider text deltas, accumulates
the answer server-side, and atomically persists the completed user message,
assistant message, RAG response, and server-controlled citations before emitting
authoritative completion metadata. See `docs/streaming_rag_v1.3.md` for the SSE
protocol, cancellation and failure behavior, UI state machine, and limitations.

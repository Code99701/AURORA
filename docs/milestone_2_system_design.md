# AURORA Academic Submission
## Milestone 2: System Design and Working of Different Parts

**Project:** AURORA: Multilingual RAG Chatbot
**Academic context:** V Semester Cornerstone Project, Topic 16
**Document status:** Implementation-grounded submission document
**Verification basis:** AURORA repository implementation and project documentation inspected on 22 September 2026

> **Status legend**
> - **IMPLEMENTED:** Present in the repository and supported by code, API contracts, or automated tests.
> - **PLANNED:** Described as a future direction or intended extension in project documents, but not established as current behavior.
> - **DEFERRED:** Explicitly outside the current implementation scope.

This document covers Milestone 2 only. Problem identification, objectives, and requirement analysis from Milestone 1 are not recreated here.

## 1. System Design

### 1.1 Overall architecture

AURORA is implemented as a modular monolith with a browser frontend, a FastAPI backend, PostgreSQL with pgvector, and provider adapters for Gemini embeddings and generation. The backend is organized by responsibilities rather than deployed as separate microservices.

```text
User browser
    |
    | Next.js same-origin /api requests and SSE
    v
Next.js 16 App Router + React 19 + TypeScript
    |
    | forwarded API requests
    v
FastAPI application
    |-- authentication and session dependencies
    |-- workspace authorization
    |-- document and storage services
    |-- ingestion adapter registry and OCR boundary
    |-- canonical content and chunk indexing
    |-- embedding and LLM provider interfaces
    |-- retrieval, RAG context, prompt, and citation services
    |-- conversation persistence and streaming
    v
PostgreSQL + pgvector <---- local private file storage
    |
    | server-side provider calls
    v
Gemini embedding and generation adapters
```

**IMPLEMENTED:** The repository contains separate frontend and backend applications, a FastAPI application factory, versioned API routers, service modules, SQLAlchemy models, Alembic migrations, local file storage, provider-neutral embedding/LLM interfaces, and Gemini adapters.

**PLANNED/DEFERRED:** The repository does not establish a microservice deployment, queue worker, cache, second database, cloud storage service, LangChain/LangGraph workflow, agent workflow, or production deployment. These must not be presented as current architecture.

### 1.2 Frontend architecture

The frontend uses Next.js App Router, React, TypeScript, CSS modules, and a same-origin `/api` rewrite to the backend. The visible application is organized around authentication, workspaces, document management, and a research desk for conversations and evidence.

The research interface loads workspace conversations and messages, displays streamed assistant text, renders source buttons, retrieves authoritative citation details, and opens document sources through authorized APIs. The upload flow supports the repository's allowlisted formats: PDF, TXT, Markdown, CSV, TSV, DOCX, XLSX, and PPTX.

**Inputs:** User credentials, workspace actions, file uploads, conversation text, optional answer-language preference.

**Processing:** Client-side form and interaction state, API requests through the frontend API client, SSE event handling for streaming turns, optimistic display of a pending user message and assistant response, and evidence/source presentation.

**Outputs:** Login and workspace screens, document library and status information, research conversations, streamed answer text, and citation/source controls.

**Interaction:** The frontend never receives provider secrets, storage keys, embeddings, or model prompts. It calls the backend using authenticated same-origin requests and uses server-returned identifiers for conversations, responses, and citations.

**Status:** **IMPLEMENTED.** Frontend quality gates are defined for type checking, linting, and production build. Visual redesign is outside this submission.

### 1.3 Backend and API architecture

The backend is a FastAPI application mounted under a versioned API prefix. The main router includes health, authentication, workspace, document, retrieval, RAG, and conversation routes. Services contain business orchestration, while SQLAlchemy models and Pydantic schemas define persistence and API contracts.

Representative endpoints include:

| Operation | Endpoint | Status |
| --- | --- | --- |
| Register/login/session operations | `/api/v1/auth/...` | IMPLEMENTED |
| Workspace operations | `/api/v1/workspaces/...` | IMPLEMENTED |
| Upload/list/process/index documents | `/api/v1/workspaces/{workspace_id}/documents/...` | IMPLEMENTED |
| Semantic search | `/api/v1/workspaces/{workspace_id}/search` | IMPLEMENTED |
| One-shot grounded RAG | `/api/v1/workspaces/{workspace_id}/rag` | IMPLEMENTED |
| Durable response/citation lookup | `/api/v1/workspaces/{workspace_id}/rag/responses/...` and `/citations/...` | IMPLEMENTED |
| Conversations and messages | `/api/v1/workspaces/{workspace_id}/conversations/...` | IMPLEMENTED |
| Streaming conversation turn | `/messages/stream` | IMPLEMENTED |

Unhandled backend exceptions are converted to a generic JSON internal-server-error response. Provider failures are mapped to safe application error categories rather than exposing credentials or provider internals.

### 1.4 Authentication and authorization

Authentication uses server-side opaque sessions. On successful password login or Google OpenID Connect login, AURORA creates a database session containing a hash of the session token and sets the raw token in an `HttpOnly` cookie named by configuration. The cookie supports configured `Secure`, `SameSite`, expiry, and root-path behavior. Google identity data is persisted as an external identity; Google tokens are not stored.

Authorization is workspace-based. A workspace has memberships with the roles `OWNER` or `MEMBER`. API dependencies resolve the current authenticated user and then resolve a workspace only when that user is a member. Nonexistent and unauthorized workspace identifiers use the concealed 404 boundary. Owner-only operations include workspace update/delete and document deletion; ordinary members can use authorized document and research operations.

**Inputs:** Session cookie and workspace/resource identifiers.

**Processing:** Session lookup, expiry/revocation/activity checks, membership lookup, and owner-role checks. Resource queries also apply workspace and user ownership predicates where required.

**Outputs:** An authenticated user or a controlled authorization error; an authorized workspace object available to downstream services.

**Status:** **IMPLEMENTED.** Tests cover registration, password hashing, session behavior, logout/revocation, Google OAuth behavior, workspace isolation, OWNER/MEMBER authorization, and cross-workspace concealment.

### 1.5 Database architecture

PostgreSQL stores users, sessions, external identities, workspaces, memberships, documents, ingestion runs, canonical content units, extracted-page compatibility records, document chunks, RAG responses, citations, conversations, and messages. Alembic manages schema migrations.

Important relationships are:

```text
User -> Session / ExternalIdentity / WorkspaceMembership
Workspace -> Memberships / Documents / Conversations / RAGResponses
Document -> IngestionRuns / ContentUnits / ExtractedPages / DocumentChunks
RAGResponse -> ordered RAGCitations -> DocumentChunk -> Document -> Workspace
Conversation -> ConversationMessages -> persisted RAGResponse
```

Foreign keys, unique constraints, check constraints, cascading deletes, and transactional persistence protect consistency. Documents store metadata and a private storage key; source binaries are not stored in PostgreSQL.

**Status:** **IMPLEMENTED.** PostgreSQL and pgvector health, migration upgrade/downgrade behavior, persistence, and cascade behavior are covered by tests.

### 1.6 Document management

A document upload is validated before its private local storage object is committed. Document metadata includes workspace, uploader, original filename, canonical content type, file size, checksum, processing status, indexing status, and processing/indexing summaries. The local MVP stores source binaries below the configured private `storage/uploads/` root. Storage access is mediated by the `FileStorage` abstraction, which rejects arbitrary paths.

**Supported current source formats:** PDF, TXT, Markdown, CSV, TSV, DOCX, XLSX, and PPTX.

**Not supported in the current implementation:** DOC, PPT, XLS, RTF, HTML, JSON, XML, standalone images, archives as source documents, audio, video, legacy Office conversion, and embedded visual interpretation. These are not to be described as supported features.

**Status:** **IMPLEMENTED** for the allowlisted formats and local storage model. Cloud object storage migration is **DEFERRED**.

### 1.7 Document ingestion

The ingestion pipeline uses extension, declared MIME, file-size, and lightweight signature/container validation before an allowlisted adapter is selected. The adapter registry resolves a format-specific adapter. Adapters extract text and structure into a common `CanonicalDocument` result.

PDF processing supports native extraction and selective local OCR for eligible scanned, image, mixed, and vector-outline pages through the Tesseract boundary. Office Open XML packages are inspected for bounded archive size, path safety, required members, encrypted content, active content, and XML safety before parsing.

TXT and Markdown use bounded text processing. CSV and TSV use bounded parsing and row grouping. DOCX, XLSX, and PPTX use `python-docx`, `openpyxl`, and `python-pptx` respectively. Visual-only content is represented as metadata or skipped where the adapter cannot safely interpret its semantics.

**Processing states:** `UPLOADED`, `PROCESSING`, `PROCESSED`, `PARTIALLY_PROCESSED`, and `FAILED`.

**Outputs:** A staged ingestion run, canonical units, diagnostics, status, and compatible PDF page records where applicable. Activation replaces the prior active run atomically. Reprocessing failure can preserve a previous valid document state.

**Status:** **IMPLEMENTED.** OCR of standalone images, visual understanding, and unsupported source formats are **DEFERRED/UNSUPPORTED**.

### 1.8 Canonical document representation

`ContentUnit` is the format-neutral representation consumed by later pipeline stages. Each unit contains ordered ordinal information, kind, normalized text, character count, optional language, versioned generic locator, extraction method, content type, status, confidence, bounded metadata, and optional parent-unit relationship.

Examples of native provenance include PDF page number and geometry, text line ranges, Markdown heading paths, delimited row ranges, DOCX paragraph/table structure, XLSX sheet and cell ranges, and PPTX slide numbers.

Only `USABLE` units become indexable text. `SKIPPED` and `FAILED` units preserve structural or failure information without adding unusable text to retrieval.

**Status:** **IMPLEMENTED.** Claim-level semantic verification is **DEFERRED**.

### 1.9 Chunking

The indexer reads active usable canonical units and applies deterministic text chunking. The configured baseline is a maximum of 1,000 characters with 150 characters of overlap. The chunker prefers paragraph, sentence, newline, or whitespace boundaries near the end of a window and otherwise uses a hard character boundary.

Chunking is performed independently for each source unit, preserving page or native locator provenance. Each stored chunk includes document-wide and unit/page-local indexes, text, character count, approximate token count, page number when available, source relationships, and embedding metadata.

**Status:** **IMPLEMENTED.** More advanced semantic chunking is **PLANNED**, not current behavior.

### 1.10 Embeddings and PostgreSQL + pgvector

The provider-neutral embedding interface separates the indexing and query services from a concrete provider. The production Gemini embedding adapter uses `gemini-embedding-001`, with `RETRIEVAL_DOCUMENT` for indexed content and `RETRIEVAL_QUERY` for user questions. Vectors are normalized and stored in PostgreSQL as `vector(768)`.

The application rejects provider dimension mismatches before persistence or retrieval. A fingerprint covers source content, chunk settings, provider, model, and dimension; unchanged indexing can be reused without rebuilding the same index.

**Status:** **IMPLEMENTED.** Exact cosine distance is the current retrieval baseline. HNSW/IVFFlat approximate indexes are **DEFERRED** until corpus measurements justify them.

### 1.11 Semantic retrieval

An authorized query is embedded using the query task type. SQL joins document chunks to documents, filters by the authorized workspace and `INDEXED` document status, orders by exact cosine distance, and returns a bounded candidate set. Results are converted to similarity values and then deduplicated within a document. A round-robin selection provides diversity across documents up to the requested `top_k`.

**Inputs:** Authorized workspace, nonblank query, bounded `top_k`, embedding provider.

**Processing:** Query embedding, dimension validation, workspace-filtered cosine search, candidate bounding, duplicate suppression, and multi-document diversification.

**Outputs:** Retrieved chunks containing text, document/chunk identifiers, filename, page/native locator, extraction method, and similarity.

**Status:** **IMPLEMENTED.** Reranking, hybrid keyword/vector retrieval, query rewriting, and GraphRAG are **DEFERRED**.

### 1.12 RAG context construction

The RAG preparation step consumes only already-authorized retrieved chunks. It removes duplicate evidence, applies the configured relevance threshold, and serializes selected evidence into bounded evidence blocks. Each block includes server-known identifiers, filename, page number, locator, extraction method, similarity, and escaped source text marked as untrusted document material.

The default serialized context budget is 12,000 characters. The last usable evidence block may be truncated to stay within the deterministic budget. If no evidence remains, AURORA returns a controlled insufficient-evidence answer and does not call Gemini.

**Status:** **IMPLEMENTED.** The threshold is a baseline, not a calibrated confidence score.

### 1.13 Gemini generation

The LLM boundary is provider-neutral, while the production adapter calls Gemini's generation endpoint. A system instruction requires the model to answer only from retrieved evidence, treat document instructions as untrusted source material, avoid inventing identifiers or facts, and return the controlled insufficient-evidence statement when the evidence is inadequate.

The user prompt contains the question, an optional language preference, bounded conversation history marked as untrusted context, and authorized evidence. The server treats the language value as a preference rather than an authorization or prompt override.

**Inputs:** Grounded prompt, authorized evidence, optional bounded conversation history, Gemini configuration.

**Outputs:** Generated grounded answer text and provider model name, or a sanitized provider error.

**Status:** **IMPLEMENTED.** Model quality, broad factual accuracy, and production latency are not claimed here. Provider model availability and external evaluation beyond the repository's tests are not treated as verified facts.

### 1.14 Citation and evidence mechanism

After generation, the backend revalidates selected evidence against live `DocumentChunk` and `Document` rows inside the authorized workspace. It creates a durable `RAGResponseRecord` and ordered `RAGCitation` rows transactionally. Citation metadata is derived from the actual database relationships; model-generated identifiers cannot become authoritative citations.

The frontend uses citation IDs to request the authoritative source record and displays the filename, native location, and similarity. Deleting or reindexing source evidence prevents stale partial citation sets from being exposed.

**Status:** **IMPLEMENTED.** Citations connect an answer to selected evidence chunks; they do not prove that every individual sentence or claim is supported. Claim-level verification is **DEFERRED**.

### 1.15 Multilingual capability

AURORA preserves original source text and uses the embedding provider's shared semantic space rather than translating documents or queries inside the application. An optional `answer_language` preference is passed to the grounded prompt. If no language is selected, the prompt asks for the language of the question where practical.

The repository directly evaluates English and Hindi behavior with deterministic bilingual test providers and has opt-in real-provider tests. The implemented claim is technical support for this flow, not universal language quality or coverage.

**Status:** **IMPLEMENTED** for the repository's English/Hindi flow and evaluation fixtures. Broad multilingual quality, dialects, transliteration, and language coverage beyond verified cases are **PLANNED/DEFERRED**.

### 1.16 Conversation persistence

A workspace member can create and access conversations belonging to that user and workspace. Messages are persisted with role, content, timestamps, model, response relationship, and measured per-turn latency metadata. Recent conversation history is bounded by configured message and character limits before it is included in a new prompt. Conversation history is not treated as document evidence and does not expand authorization.

**Status:** **IMPLEMENTED.** The system also retains the synchronous message endpoint. Long-term memory, cross-conversation memory, and agentic memory are **DEFERRED**.

### 1.17 Streaming

The conversation stream endpoint returns Server-Sent Events. Events expose retrieval/generation phases, text deltas, completion data, and sanitized terminal errors. The backend uses a separate database session for the stream, checks authorization again, closes the provider stream on client cancellation, and persists the completed turn and citations only when completion succeeds. The frontend appends text deltas and reloads authoritative message state after completion.

**Status:** **IMPLEMENTED** for conversation RAG streaming. Streaming is not claimed for document ingestion or every API operation.

### 1.18 Workspace and data isolation

Workspace membership is checked before document, search, RAG, citation, and conversation operations. The retrieval SQL query independently filters documents by workspace. Conversation queries additionally constrain the current user. Storage keys and document paths are not client-controlled, and private binaries are accessed only through the storage abstraction.

Database cascades remove related files/records during workspace or document deletion. Citation lookup resolves live relationships within the same workspace, preventing a bare identifier from granting access.

**Status:** **IMPLEMENTED.** Tests cover non-member concealment, cross-workspace access, client-controlled provenance identifier rejection, document deletion, workspace deletion, and stream authorization.

### 1.19 Testing and reliability

The repository includes backend tests for authentication, database/migrations, health, documents, processing, RAG indexing, generation, citations, multilingual behavior, streaming, conversations, and workspaces. Frontend tests and frontend quality commands are also present. Provider fakes keep normal automated tests local and avoid cloud calls; live Gemini checks are explicitly opt-in.

Reliability mechanisms implemented in the code include bounded input/resource limits, deterministic chunking, embedding dimension validation, idempotent indexing fingerprints, transactional staged ingestion activation, transactional citation persistence, safe provider error categories, global exception handling, stream cancellation cleanup, and controlled insufficient-evidence responses.

**Status:** **IMPLEMENTED.** No unsupported accuracy, throughput, availability, cost, or production SLO claim is made in this document.

## 2. Working of Different Parts: End-to-End Operation

The following sequence describes the current implemented path.

### Step 1: User logs in

- **Purpose:** Establish an authenticated identity.
- **Input:** Registration/login credentials or optional Google OpenID Connect request.
- **Processing:** AURORA validates credentials or Google identity, creates an opaque database session, and sets an HttpOnly cookie.
- **Output:** Authenticated browser session and current-user context.
- **Interaction:** Authentication dependencies provide the user to workspace and resource routes.
- **Status:** **IMPLEMENTED.**

### Step 2: User opens a workspace

- **Purpose:** Establish the data-isolation boundary for research.
- **Input:** Workspace identifier and authenticated session.
- **Processing:** Backend verifies membership and, for owner operations, the OWNER role.
- **Output:** Authorized workspace object or concealed authorization error.
- **Interaction:** Every subsequent document, retrieval, RAG, citation, and conversation operation uses this boundary.
- **Status:** **IMPLEMENTED.**

### Step 3: User uploads a document

- **Purpose:** Add a private source document to the workspace.
- **Input:** Multipart file and workspace context.
- **Processing:** Filename, MIME, extension, size, signature/container, and storage constraints are checked; the source is stored privately and metadata is recorded.
- **Output:** Document record initially in `UPLOADED` state.
- **Interaction:** The document record becomes the parent for ingestion runs, canonical units, chunks, and citations.
- **Status:** **IMPLEMENTED** for the eight allowlisted source formats.

### Step 4: Backend validates and stores the document

- **Purpose:** Prevent unsafe or ambiguous input from reaching parsers.
- **Input:** Uploaded bytes and declared metadata.
- **Processing:** Allowlist resolution, checksum/metadata persistence, path-safe storage, and Office package safety inspection where relevant.
- **Output:** Validated private binary plus safe database metadata.
- **Interaction:** Processing reads the binary through `FileStorage`; clients never supply parser or storage paths directly.
- **Status:** **IMPLEMENTED.**

### Step 5: Content is extracted

- **Purpose:** Convert source bytes into usable text and structure.
- **Input:** Private stored binary and extraction limits.
- **Processing:** The selected adapter performs format-specific extraction. PDF may invoke selective Tesseract OCR through the OCR provider boundary.
- **Output:** `CanonicalDocument` with ordered drafts, diagnostics, outcome, and provenance.
- **Interaction:** The processing service stages the adapter result in a versioned ingestion run.
- **Status:** **IMPLEMENTED.**

### Step 6: Content is normalized and canonicalized

- **Purpose:** Give all supported formats one downstream contract.
- **Input:** Adapter extraction result.
- **Processing:** Text is normalized, unit kinds and content types are assigned, locators are versioned, and usable/skipped/failed status is recorded.
- **Output:** `ContentUnit` records with native provenance and optional parent relationships.
- **Interaction:** Indexing and later retrieval consume canonical units without format-specific retrieval branches.
- **Status:** **IMPLEMENTED.**

### Step 7: Content is chunked

- **Purpose:** Create bounded retrieval units while retaining source traceability.
- **Input:** Active usable canonical units.
- **Processing:** Deterministic 1,000-character chunks with 150-character overlap are generated within each source unit.
- **Output:** Chunk drafts with global and local indexes, character/token metadata, and page/native locator relationships.
- **Interaction:** Each chunk becomes one embedding input and later one possible citation target.
- **Status:** **IMPLEMENTED.**

### Step 8: Embeddings are generated

- **Purpose:** Represent source chunks in a semantic vector space.
- **Input:** Chunk text.
- **Processing:** The configured embedding provider uses the document retrieval task type, validates vector count and 768-dimensional shape, and normalizes vectors.
- **Output:** Validated vectors.
- **Interaction:** The indexer writes vectors to PostgreSQL `vector(768)`.
- **Status:** **IMPLEMENTED** with the Gemini production adapter and deterministic test fakes.

### Step 9: Vectors are stored

- **Purpose:** Make processed content searchable.
- **Input:** Chunks and validated vectors.
- **Processing:** Existing chunks are replaced only after new embeddings have been produced; indexing metadata and fingerprint are committed transactionally.
- **Output:** Document state `INDEXED` and durable `DocumentChunk` rows.
- **Interaction:** Semantic retrieval reads only indexed documents in the authorized workspace.
- **Status:** **IMPLEMENTED.**

### Step 10: User asks a question

- **Purpose:** Start a grounded research turn.
- **Input:** Conversation message, optional `top_k`, and optional answer-language preference.
- **Processing:** The backend confirms the conversation belongs to the current user and authorized workspace, then bounds recent history.
- **Output:** A retrieval-ready question.
- **Interaction:** The question enters the same RAG preparation path for synchronous and streaming conversations.
- **Status:** **IMPLEMENTED.**

### Step 11: Authorized semantic retrieval runs

- **Purpose:** Find relevant evidence without crossing workspace boundaries.
- **Input:** Question, workspace, and query embedding provider.
- **Processing:** Query embedding, exact cosine search in pgvector, workspace/indexed filters, relevance ordering, duplicate suppression, and document diversification.
- **Output:** Ordered retrieved chunks with similarity and provenance.
- **Interaction:** Only these authorized chunks may reach context construction.
- **Status:** **IMPLEMENTED.**

### Step 12: RAG context is constructed

- **Purpose:** Give Gemini bounded, traceable, untrusted source material.
- **Input:** Retrieved chunks after relevance filtering.
- **Processing:** Evidence is deduplicated, escaped, labeled, and serialized under a deterministic character budget. Weak/empty evidence takes the insufficient-evidence path.
- **Output:** Grounded prompt context or a controlled insufficient-evidence result.
- **Interaction:** The context builder does not perform authorization itself; it relies on the authorized retriever and later persistence revalidation.
- **Status:** **IMPLEMENTED.**

### Step 13: Gemini generates an answer

- **Purpose:** Synthesize a concise answer from supplied evidence.
- **Input:** System grounding instruction, user question, optional language preference, bounded history, and authorized evidence.
- **Processing:** Gemini generation through the server-side LLM adapter. Document text and conversation history are explicitly untrusted input.
- **Output:** Answer text and configured model name, or a sanitized provider error.
- **Interaction:** The server, not Gemini, remains authoritative for source identifiers and citations.
- **Status:** **IMPLEMENTED** when provider configuration is available; test fakes are used for normal automated tests.

### Step 14: Grounded answer and citations are persisted

- **Purpose:** Preserve a durable answer/evidence relationship.
- **Input:** Generated answer or insufficient-evidence result plus selected evidence.
- **Processing:** Live workspace/chunk revalidation, transactional response creation, ordered citation creation, and conversation assistant-message persistence.
- **Output:** Stable response ID, answer, source references, and persisted conversation turn.
- **Interaction:** Citation metadata is derived from live document/chunk relationships.
- **Status:** **IMPLEMENTED.**

### Step 15: Evidence is displayed to the user

- **Purpose:** Let the user inspect the basis of the answer.
- **Input:** Completed conversation turn and citation IDs.
- **Processing:** Frontend renders answer text and source controls; selecting a citation requests its authoritative source metadata and opens the authorized location/preview/download behavior supported for that format.
- **Output:** Answer with visible evidence references and source inspection affordances.
- **Interaction:** A citation ID alone is insufficient for access; the backend rechecks workspace authorization.
- **Status:** **IMPLEMENTED.**

## 3. Explicit Scope Boundary

### Implemented and verified in the repository

- Next.js frontend and FastAPI backend modular-monolith structure.
- Password sessions with HttpOnly cookies and optional Google OpenID Connect.
- Workspace membership and OWNER/MEMBER authorization.
- Private local document storage and metadata management.
- PDF, TXT, Markdown, CSV, TSV, DOCX, XLSX, and PPTX ingestion.
- PDF selective OCR through the Tesseract boundary.
- Versioned canonical content units and native provenance locators.
- Deterministic chunking with overlap.
- Gemini document/query embeddings and PostgreSQL `vector(768)` storage.
- Workspace-filtered exact cosine retrieval with deduplication/diversity.
- Bounded RAG context and grounded Gemini generation.
- Controlled insufficient-evidence behavior.
- Durable RAG responses and server-generated citations.
- English/Hindi multilingual flow and repository evaluation fixtures.
- Conversation persistence with bounded history.
- SSE streaming for conversation RAG turns.
- Input/resource limits, safe errors, transactions, and automated tests.

### Planned or deferred, not current implementation claims

- Empirically calibrated similarity thresholds and broad quality benchmarks.
- Claim-level citation verification or answer fact checking.
- Reranking, hybrid retrieval, query rewriting, and GraphRAG.
- Universal language support beyond the verified English/Hindi scope.
- Cloud object storage migration.
- Approximate vector indexes such as HNSW or IVFFlat.
- Queues, background workers, distributed services, caching, and agent workflows.
- Long-term or cross-conversation memory.
- Interpretation of standalone images, charts, visual-only slides, and embedded visuals.
- DOC/PPT/XLS/RTF/HTML/JSON/XML/archive/audio/video source ingestion.
- Production deployment, production user counts, cost savings, accuracy guarantees, and latency/SLO claims.

## 4. Information Not Verified

The repository inspection did not establish or measure the following, so this document intentionally makes no claim about them:

- Production deployment or operational availability.
- Production user count, corpus size, throughput, or cost savings.
- General Gemini accuracy, fluency, or universal multilingual quality.
- Statistically representative retrieval or answer quality benchmarks.
- Production latency or service-level objectives.
- Claim-by-claim citation correctness.
- Support for formats and visual semantics outside the explicitly allowlisted adapters.
- Cloud storage, distributed workers, or approximate-index operation.

## 5. Source Files Consulted

- `README.md`
- `docs/multiformat_document_intelligence_v1.4.2.md`
- `docs/rag_data_pipeline_v0.7.md`
- `docs/rag_generation_foundation_v0.8.md`
- `docs/citations_and_evidence_foundation_v0.9.md`
- `docs/multilingual_rag_foundation_v1.0.md`
- `docs/workspace_authorization_v0.4.md`
- `docs/document_management_v0.5.md`
- `docs/streaming_rag_v1.3.md`
- Backend API, service, ingestion, model, RAG, storage, and provider modules.
- Backend tests for authentication, documents, processing, retrieval, generation, citations, multilingual behavior, streaming, conversations, workspaces, database, and health.
- Frontend application components and API/streaming utilities.

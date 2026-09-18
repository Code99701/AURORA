# AURORA v1.2 — Persistent Conversations and Chat UX

## Objective

v1.2 turns the v1.1 one-shot research surface into a persistent research conversation experience. Conversations, messages, grounded RAG responses, and citation relationships survive reloads while workspace authorization remains the primary security boundary.

Streaming is deliberately excluded. Each message uses one normal request/response operation.

## Architecture

The existing modular monolith remains unchanged:

```text
Next.js UI
→ authenticated FastAPI route
→ workspace membership authorization
→ conversation application service
→ existing authorized RAG service
→ PostgreSQL + pgvector
→ configured embedding and LLM adapters
```

No microservice, Redis, task queue, separate memory/vector database, agent framework, reranker, hybrid retriever, or cache was introduced.

## Database changes

Alembic revision `c91a2d7e4f10` adds:

### `conversations`

- UUID primary key
- workspace UUID with `ON DELETE CASCADE`
- owning user ID with `ON DELETE CASCADE`
- persistent title
- created and updated timestamps
- workspace, user, and update-order indexes

### `conversation_messages`

- UUID primary key
- conversation UUID with `ON DELETE CASCADE`
- constrained `USER` or `ASSISTANT` role
- message content
- optional one-to-one RAG response UUID with `ON DELETE SET NULL`
- optional model and nonnegative latency metadata
- creation timestamp

Messages do not store embeddings, provider secrets, document identifiers submitted by the client, or raw provider telemetry.

Assistant messages link to `rag_responses`. Existing `rag_citations` remain the only citation store and continue to link to authoritative document chunks.

## API endpoints

All endpoints require an authenticated session and workspace membership. Conversation lookup additionally filters by workspace and current user.

```http
POST   /api/v1/workspaces/{workspace_id}/conversations
GET    /api/v1/workspaces/{workspace_id}/conversations
GET    /api/v1/workspaces/{workspace_id}/conversations/{conversation_id}
PATCH  /api/v1/workspaces/{workspace_id}/conversations/{conversation_id}
DELETE /api/v1/workspaces/{workspace_id}/conversations/{conversation_id}
GET    /api/v1/workspaces/{workspace_id}/conversations/{conversation_id}/messages
POST   /api/v1/workspaces/{workspace_id}/conversations/{conversation_id}/messages
```

The list returns at most 50 conversations ordered by most recent activity. Message history returns at most the 200 most recent messages in chronological display order.

## Conversation lifecycle

1. A user creates a private conversation within a workspace they can access.
2. The initial title is `New research`.
3. The first successful turn replaces it deterministically with a whitespace-normalized, safely truncated form of the first question.
4. The owner may rename the conversation explicitly.
5. Reloading the selected deep link restores the persisted list and message history.
6. Deletion removes only that conversation, its messages, and its linked RAG responses/citations. Workspace documents remain intact.

Conversation titles never require an extra LLM call.

## Message and RAG lifecycle

1. Validate the current user, workspace, conversation, and request schema.
2. Read bounded recent conversation context.
3. Stage the user message.
4. Run the existing RAG pipeline with fresh authorized retrieval for the current query.
5. Persist the existing RAG response and server-generated citations.
6. Persist the assistant message with the RAG response relationship and latency.
7. Commit the complete turn atomically.

If retrieval, provider generation, or persistence fails, the incomplete turn is rolled back and the API returns the existing sanitized structured error. No partial assistant message or orphaned RAG response is created.

Insufficient evidence remains a successful, persisted assistant result with no LLM call and no citations.

## Bounded context strategy

Defaults:

- `CONVERSATION_HISTORY_MAX_MESSAGES=8`
- `CONVERSATION_HISTORY_MAX_CHARACTERS=6000`

The prompt contains:

```text
current user query
+ bounded recent USER/ASSISTANT messages
+ freshly retrieved authorized evidence
```

Conversation history is escaped, delimited, labeled untrusted, and explicitly described as context rather than evidence. The current query always performs independent workspace-filtered retrieval. Old conversation content cannot expand workspace access, select document/chunk IDs, or bypass the relevance threshold.

Summarization, a memory database, and query rewriting are not part of v1.2.

## Authorization boundary

The enforced chain is:

```text
authenticated user
→ workspace membership lookup
→ workspace-scoped conversation lookup
→ conversation owner filter
→ fresh workspace-scoped retrieval
→ authorized evidence context
→ LLM
```

A conversation UUID alone never grants access. Non-members receive the same concealed workspace 404 used elsewhere. A workspace member cannot see another member's private conversations. Unauthenticated callers receive 401 responses.

## Citation behavior

The client cannot submit citation, chunk, or document IDs. The RAG service validates retrieved chunks against the authorized workspace before persistence. Assistant messages expose the existing server-generated citation ID, position, document, chunk, filename, page, and similarity through the authorized response model.

If source evidence is later deleted, the existing citation safety behavior applies: incomplete/stale citation sets are not reconstructed from snapshots.

## Frontend architecture

The v1.1 design system is reused. The research tab now contains:

- desktop conversation panel and responsive mobile drawer
- create, select, rename, and confirmed-delete controls
- explicit list loading, empty, error, and retry states
- deep-linked active conversation selection
- selected conversation header and persistent chronological history
- visually distinct research questions and grounded answers without generic chat bubbles
- evidence panels under each assistant response
- insufficient-evidence state
- composer with answer-language selection, Enter-to-send, Shift+Enter newline, disabled/submitting state, and retry-safe retained drafts

The UI renders only citation metadata returned by the authorized API. It does not stream or simulate token output.

## Error states

Handled states include list creation/loading failure, unavailable or deleted conversation, message-history failure, network error, RAG retrieval failure, provider/rate-limit failure, and persistence/deletion failure. Responses remain sanitized and do not expose stack traces, provider bodies, secrets, or internal paths.

## Testing

`backend/tests/test_conversations.py` covers:

- create/list/get/rename and recent ordering
- owner privacy inside a shared workspace
- non-member, unauthenticated, and cross-workspace rejection
- user/assistant/RAG/citation persistence
- history reload
- fresh retrieval for every follow-up
- bounded recent message and character limits
- insufficient-evidence persistence without an LLM call
- provider failure rollback and sanitized errors
- safe deletion and document preservation
- migration upgrade/downgrade/re-upgrade

The complete backend suite and frontend typecheck, lint, production build, responsive visual inspection, theme inspection, overflow check, and browser-console check are release gates.

## Limitations

- Conversation lists are capped at 50 and message history at 200; cursor pagination is a future enhancement.
- Conversation context is a recent window, not a summary.
- Conversations are private to their creator even when a workspace has multiple members.
- Requests are synchronous and may take as long as embedding retrieval plus generation.
- Retry repeats a whole request; no partial token recovery exists.

## v1.3 boundary

The recommended next milestone is **v1.3 Streaming RAG**. It may add a carefully authorized SSE/token-streaming transport and streaming-specific UI states. v1.2 contains no SSE, WebSocket, fake streaming, or token-by-token rendering.

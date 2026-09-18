# AURORA v1.3 — Streaming RAG

## 1. Objective

v1.3 adds real Server-Sent Events (SSE) to the persistent v1.2 research conversation. Streaming changes the transport and user experience; it does not create another retrieval, prompt, citation, or persistence architecture. The synchronous conversation endpoint remains available as a compatibility fallback.

## 2. Architecture

```text
authenticated Next.js client
→ POST SSE endpoint
→ workspace membership + conversation ownership
→ shared bounded-history conversation service
→ shared fresh authorized retrieval preparation
→ provider-neutral streaming LLM interface
→ accumulated server-side answer
→ existing RAG response/citation persistence
→ assistant-message persistence + atomic commit
→ authoritative completion event
```

The event iterator uses a fresh SQLAlchemy session because FastAPI closes request-scoped dependencies after returning a `StreamingResponse`. Authorization is performed before streaming and the authorized IDs are resolved again inside that stream-owned session.

## 3. SSE protocol

Endpoint:

```http
POST /api/v1/workspaces/{workspace_id}/conversations/{conversation_id}/messages/stream
Accept: text/event-stream
Content-Type: application/json
```

The body is the existing typed `ConversationMessageCreate` schema. Extra fields are forbidden, so clients cannot submit citation, document, or chunk identities.

Responses use `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`, UTF-8 JSON data, and named SSE events.

## 4. Event types

- `state`: `{ "phase": "retrieving" | "streaming" | "finalizing" }`
- `text_delta`: `{ "text": "..." }`
- `complete`: the authoritative persisted `ConversationTurnResponse`
- `error`: `{ "code": "...", "message": "sanitized public message", "retryable": true | false }`

The completion payload—not temporary text—is the durable source of message IDs, response ID, citations, model, latency, title, and timestamps. Provider usage may be normalized internally but is not exposed or persisted in v1.3.

## 5. Provider abstraction

`LLMProvider` now supports `stream_generate()`, which returns provider-neutral `StreamingGenerationEvent` values: `text_delta`, `usage`, and `completion`. Gemini's `streamGenerateContent?alt=sse` parsing stays inside `GeminiLLMProvider`; raw Gemini objects never reach routes or the browser.

## 6. Generation lifecycle

1. Validate authentication and request schema.
2. Authorize the workspace and private conversation.
3. Stage one user message in the stream transaction.
4. Load bounded recent conversation context.
5. Perform fresh workspace-scoped retrieval exactly once.
6. Build the existing bounded evidence prompt.
7. Stream provider deltas while accumulating text server-side.
8. Reject missing completion, empty text, provider failure, rate limits, and responses beyond the configured character bound.
9. Persist only the completed answer.

## 7. Persistence lifecycle

No write occurs per token. The user message is flushed but not committed before generation. After provider completion, the existing RAG persistence code revalidates every evidence chunk inside the workspace, creates the RAG response and server-controlled citations, creates one assistant message, and commits the complete turn atomically. Any pre-completion or persistence failure rolls the entire staged turn back.

`STREAMING_MAX_RESPONSE_CHARACTERS` defaults to 32,768 and bounds server-side accumulation independently of the provider token limit.

## 8. Disconnect behavior

The route checks `request.is_disconnected()` between normalized provider events. A disconnect closes the async generator. Gemini's `httpx` streaming context is then closed, which cancels the open HTTP response where the transport supports cancellation. The database transaction rolls back, so no user message, assistant message, RAG response, or citation is presented as completed. Cancellation cannot revoke bytes already generated or billed before the transport closes.

## 9. Error behavior

Authentication/authorization failures are normal HTTP errors before the SSE stream starts. Retrieval, provider, rate-limit, malformed stream, persistence, and reauthorization failures are terminal `error` events after streaming begins. Error events contain only application-controlled codes/messages. API keys, raw provider payloads, stack traces, credentials, and internal paths are not returned.

Partial text may have reached the browser before a terminal failure, but the UI removes that temporary turn, restores the draft, and offers retry. No `complete` event is emitted unless persistence succeeded.

## 10. Citation behavior

Citations are never streamed before completion and are never accepted from the client or model. The server derives them from authorized retrieved chunks, persists them using existing response/citation relationships, and sends them only in the final authoritative completion payload.

Insufficient evidence remains deterministic: Gemini is not called, the controlled answer and an empty citation list are persisted using the existing v1.2 semantics, and the turn completes normally.

## 11. Frontend state machine

```text
idle → submitting → retrieving → streaming → finalizing → idle
                          ↘ finalizing → idle (insufficient evidence)
any active state → error → retry
```

The UI immediately adds temporary user/assistant research turns, consumes actual SSE deltas, and batches text updates through `requestAnimationFrame`. It uses plain React text nodes, not unsafe HTML. Duplicate submission and conversation mutation are disabled while a request is active. Failure removes temporary messages and restores the draft.

Auto-follow continues only while the reader is within 96 pixels of the bottom. Scrolling upward suspends forced scrolling and reveals a 44px “Latest response” control. Reduced-motion preferences disable smooth transitions through the existing global rule.

## 12. Security model

The streaming route preserves the complete v1.2 chain:

```text
session authentication
→ workspace membership
→ owner-scoped conversation lookup
→ workspace-scoped retrieval
→ bounded untrusted history
→ authorized evidence
→ server-controlled citation persistence
```

A conversation UUID alone never authorizes access. The stream-owned database session rechecks workspace membership, active user status, conversation ownership, and workspace identity before work begins.

## 13. Testing

Backend coverage includes authenticated deltas/completion, all workspace and conversation isolation boundaries, persistence and citations, deterministic insufficient evidence, retrieval/provider/rate-limit/malformed-stream/persistence failures, secret sanitization, client-side generator cancellation, schema identity rejection, Gemini SSE normalization, and synchronous endpoint regression.

Frontend unit tests cover fragmented/multiline SSE parsing, successful and insufficient-evidence state transitions, malformed transitions, duplicate submission guards, and near-bottom scroll decisions. Browser QA covers the integrated UI, responsive widths, themes, overflow, console output, reload persistence, and representative success/failure states where the local providers permit them.

## 14. Limitations

- SSE uses POST plus `fetch()` rather than browser `EventSource`, because the request requires a JSON body.
- There is no resume token or replay after a network interruption.
- Temporary streamed text is not durable until the final event.
- Provider cancellation is best-effort at the HTTP transport boundary.
- Usage metadata is normalized internally but not persisted or shown.
- Markdown remains the existing safe paragraph rendering; v1.3 adds no markdown framework.

## 15. Future improvements

The next milestone is v1.4 Document Preview + Research Workspace. Later streaming work may add resumable streams, persisted usage accounting, or stronger transport observability without changing the authorization and citation boundaries established here.

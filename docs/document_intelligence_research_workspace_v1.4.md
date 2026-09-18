# AURORA v1.4 — Document Intelligence + Research Workspace

## Implementation status

AURORA v1.4 is implemented. The milestone extends the existing authenticated,
workspace-scoped, persistent, streaming RAG product; it does not replace its
retrieval, generation, citation, conversation, or authentication foundations.

No database migration or schema change was required.

## Functionality added

- Authorized inline PDF streaming with private, no-store response headers.
- A document inspector with metadata, lifecycle states, loading/error/unsupported
  handling, PDF rendering, download/open actions, and bounded page navigation.
- Deep-linked document inspection through `?document=<uuid>&page=<number>`.
- Server-authoritative citation resolution and citation-to-document/page navigation.
- Source-library filename search, lifecycle filtering, and deterministic sorting.
- Clear research-ready counts and guidance when a workspace has no indexed sources.
- Actionable evidence rows that preserve citation, chunk, document, page, filename,
  position, and similarity identity.
- Responsive document and research layouts using the existing AURORA semantic
  tokens, editorial typography, focus system, and light/dark themes.

## API changes

### `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/preview`

Streams an authorized PDF with `Content-Disposition: inline`,
`Cache-Control: private, no-store`, and `X-Content-Type-Options: nosniff`.
Workspace membership and workspace-scoped document lookup occur before storage is
opened. Missing storage, unavailable storage, and unsupported media return safe
errors.

### `GET /api/v1/workspaces/{workspace_id}/rag/citations/{citation_id}`

Resolves one persisted citation to its current authoritative source provenance.
The service joins the citation to its response, chunk, and document and requires
both response and document workspace identity to match the authorized workspace.
The client does not choose the document or page that is opened.

## Authorization and security

- Preview uses the same membership and concealed cross-workspace lookup boundary as
  document detail and download.
- Citation resolution rechecks workspace membership at the route and workspace
  identity across the persisted response/document graph in the service.
- Deleted chunks/documents cascade citations; stale citation resolution returns 404.
- Existing owner-only document deletion remains unchanged.
- Existing conversation ownership and fresh-session SSE authorization remain unchanged.
- PDF bytes are fetched with the authenticated cookie and rendered from a temporary
  object URL that is revoked when the inspector changes or unmounts.
- Real OAuth credentials remain in `.env`; `.env.example` contains blank placeholders.

## Multi-document research

The existing retriever already searches every `INDEXED` document in the authorized
workspace and orders chunks by cosine distance. v1.4 preserves that implementation.
Existing and new regression coverage verifies distinct citations from multiple
documents, server-side de-duplication, provenance identity, and workspace isolation.

## Insufficient-evidence investigation

The observed insufficient response was not caused by the similarity threshold. At
the time of the response, the affected workspace had:

- one document in `PROCESSED / NOT_INDEXED` state;
- zero indexed documents;
- zero document chunks; and
- a response with zero citations.

The retriever therefore had no eligible evidence. `RAG_MIN_SIMILARITY=0.30` was not
changed. The research composer now explains that no source is research-ready and
links the user back to the source library before a grounded question can be sent.

## Files created

- `frontend/components/document-preview.tsx`
- `frontend/components/document-preview.module.css`
- `frontend/lib/document-workspace.ts`
- `frontend/tests/document-workspace.test.mjs`
- `docs/document_intelligence_research_workspace_v1.4.md`

## Files modified

- `.env.example`
- `backend/app/api/v1/documents.py`
- `backend/app/api/v1/rag.py`
- `backend/app/services/rag.py`
- `backend/tests/test_documents.py`
- `backend/tests/test_citations.py`
- `frontend/app/layout.tsx`
- `frontend/app/(app)/workspaces/[workspaceId]/page.tsx`
- `frontend/components/document-library.tsx`
- `frontend/components/document-library.module.css`
- `frontend/components/research-desk.tsx`
- `frontend/components/research-desk.module.css`
- `frontend/components/workspace-view.tsx`
- `frontend/lib/api.ts`

## Verification performed

- Authorized preview bytes, inline headers, and private/no-store behavior.
- Unauthenticated, non-member, and cross-workspace concealment.
- Missing stored-document preview behavior.
- Authoritative citation resolution, cross-workspace rejection, and deleted citation behavior.
- Existing multi-document citation identity and retrieval boundaries.
- Existing conversation persistence and SSE streaming regressions.
- Google OAuth regression tests.
- Backend regression suite: **178 passed, 2 skipped**. The two warnings only report
  that pytest could not write its optional cache directory.
- Frontend: **15 unit tests passed**, TypeScript passed, ESLint passed, and the
  optimized Next.js production build passed.
- Real browser checks for document inspection, page 1 → page 2 navigation, deep-link
  state, citation → page 2 navigation, zero-index guidance, mobile research drawer,
  desktop/tablet/mobile reflow, both themes, keyboard-reachable controls, and a
  clean final browser console.

Browser QA used a disposable local account/workspace and removed both after testing.

## Known limitations

- Inline PDF rendering and native PDF toolbar behavior vary by browser. Download and
  a separately authorized inline-open action remain available.
- PDF preview currently loads the complete file into a browser object URL; byte-range
  streaming is deliberately deferred because the configured document limit is 10 MB.
- Search, filter, and sort are intentionally client-side for the current bounded
  workspace document list.
- A user must explicitly process and index a document; v1.4 does not introduce a job
  queue or fake background progress.

## Deliberately deferred

- Hybrid retrieval, reranking, GraphRAG, comparison agents, Redis, background job
  infrastructure, annotation layers, OCR, and non-PDF preview formats.

## Recommended v1.5 milestone

`AURORA v1.5 — Research Collections + Evaluation Visibility`: add saved source
collections within a workspace, explicit retrieval diagnostics for authorized users,
and reproducible evaluation views while retaining the current evidence and security
boundaries. Advanced retrieval should be considered only after evaluation data
demonstrates a concrete need.

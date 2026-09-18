# AURORA Frontend Foundation v1.1

## Scope

Frontend Foundation v1.1 turns the AURORA UI/UX Design Constitution into a working Next.js application connected to the existing v1.0 backend. It preserves the backend authorization boundary and does not place provider secrets in browser code.

## Implemented routes

- `/login` — login and registration with safe API errors and real server-side sessions.
- `/workspaces` — authenticated workspace register, empty state, and workspace creation dialog.
- `/workspaces/{workspaceId}` — source-library and evidence-first research views.

## Research interaction

The RAG view is deliberately not a chat transcript. It presents:

1. A focused research question.
2. A contextual wait state while the single backend request is active.
3. A grounded synthesis.
4. An insufficient-evidence notice when returned by the backend.
5. A separate evidence trail using server-provided source position, filename, page, and similarity.

No citation or source metadata is invented in the browser.

## Document lifecycle

The document library supports real PDF upload, refresh, download, processing, indexing, retry after failure, and confirmed deletion. UI status is derived from the backend's `status` and `indexing_status` fields. A lifecycle step changes only after its API operation completes; the frontend does not simulate extraction, chunking, embedding, or indexing progress.

## Design system

The design system is dark-first with a separately tuned light theme. It uses restrained cyan and violet accents for provenance, focus, and active state. Reusable primitives cover controls, fields, surfaces, badges, empty/loading/error states, navigation, tabs, and confirmation dialogs. All icons come from Lucide.

The full token and behavior contract is in `design-system/aurora/MASTER.md`.

## Accessibility and responsive behavior

- Semantic headings, navigation, dialogs, tab lists, tab panels, and form labels.
- Visible keyboard focus and Escape dismissal for dialogs.
- Minimum 44px primary interaction targets.
- Reduced-motion support.
- Persistent desktop navigation and a compact mobile drawer.
- Stacked mobile research and evidence panels.

## Configuration

`AURORA_BACKEND_ORIGIN` is server-only and defaults to `http://127.0.0.1:8000`. The Next.js rewrite forwards `/api/*` calls to the backend. The frontend `.env.example` contains no AI-provider secret.

## Verification

- TypeScript: passed.
- ESLint: passed.
- Next.js production build: passed.
- Backend functional regression suite: 127 passed, 2 opt-in live Gemini tests skipped.
- Docker restart persistence test: separately deselected during the sandboxed run because Docker engine access was denied; this is not a frontend test.
- Visual QA: login, workspace register, empty source library, and research views inspected in dark/light themes at 375px, 768px, 1024px, and 1440px.
- Browser console: no warnings or errors in inspected routes.
- Horizontal overflow: none at inspected breakpoints.

## Current backend limitation reflected honestly in the UI

The backend exposes coarse `PROCESSING` and `INDEXING` states, not separate extraction/chunking/embedding progress events. The frontend therefore uses contextual operation labels without pretending to know an unreported sub-stage. Streaming indicators are not shown because the current RAG endpoint is non-streaming.

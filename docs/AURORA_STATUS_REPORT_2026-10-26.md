# AURORA — Status Report & Fix Guide (for Antigravity)

Date: 2026-10-26 · Scope: `D:\Jarvis\projects\AURORA` · No project files were modified (only this report + logs in `D:\Jarvis\aurora_audit_logs\`).

**Evidence labels:** `[RUN]` = I executed it and saw the result. `[CODE]` = read in source, not executed. `[NOT VERIFIED]` = could not check.

---

## 1. What AURORA is

A multilingual (English + Hindi) **RAG research platform**: upload documents into private workspaces, ask questions, get answers grounded in your documents with citations.

| Layer | Tech |
|---|---|
| Frontend | Next.js 16.3 / React 19 / TypeScript, CSS Modules |
| Backend | FastAPI, SQLAlchemy 2, Alembic |
| DB | PostgreSQL 16 + pgvector (Docker) |
| AI | Gemini (embeddings 768-dim, LLM), Tesseract OCR (eng+hin) |
| Auth | Server-side sessions, HttpOnly cookie, Argon2id, optional Google OIDC |

Backend pipeline [CODE]: upload → parse (PDF/OCR, TXT, MD, CSV, DOCX, XLSX, PPTX) → chunk (1000 chars / 150 overlap) → embed → pgvector search → grounded prompt → answer + stored citations → persistent conversations, SSE streaming.

---

## 2. Verdict in one paragraph

**The backend is solid and well tested. The frontend is mostly a demo.** The screens a user actually lands on (workspace list, research chat, upload, document viewer) are hardcoded mock UI with fake timers and canned answers. The real API-connected components exist but are **not mounted anywhere**. So the product does not work end-to-end from the browser today, even though the backend can do it.

## 3. Completion estimate (my judgement, not a measured number)

| Area | Status | Est. |
|---|---|---|
| Database + migrations | Works [RUN] | ~95% |
| Backend API + RAG + auth | Works, tested [RUN] | ~85–90% |
| Frontend: auth pages | Wired to real API [CODE] | ~70% |
| Frontend: workspace list / chat / upload / viewer | **Mock only** [CODE] | ~10% real |
| Frontend: dashboard / settings | Real user+workspace data, some hardcoded text | ~60% |
| Deployment / ops / security hardening | Local-dev only | ~30% |
| **Whole product, user-visible** | | **~45–55%** |

---

## 4. Test results

| Check | Result |
|---|---|
| Backend `pytest` | **251 passed, 2 skipped, 0 failed** (91 s) [RUN]. Ran Alembic migrations through the latest revision on the real Postgres. |
| Frontend `tsc --noEmit` | Pass [RUN] |
| Frontend `next build` | Pass, 10 routes [RUN] |
| Frontend `eslint` | **Fail: 6 errors, 35 warnings** [RUN] |
| Frontend unit tests | Not run [NOT VERIFIED] |
| Live manual API calls against a running server | **Not done** [NOT VERIFIED] |

**"Are all APIs working?"** The backend test suite exercises the API layer against a real DB and passes, so the backend APIs are very likely working. But I did **not** hit a live server with real Gemini calls, so real embedding/LLM calls, real OCR on a scanned PDF, and the SSE stream in a browser are unconfirmed. The 2 skipped tests were not inspected.

ESLint errors [RUN]: `react-hooks/set-state-in-effect` in `hooks/use-auth.ts:37`, `use-chat.ts:33`, `use-documents.ts:31`, `use-media-query.ts:12`, `use-workspaces.ts:29`; and "variable used before declared" in `components/shared/command-palette.tsx:148`.

---

## 5. Major issues (ranked)

### CRITICAL — product doesn't work from the browser

**C1. Workspace screen is fake chat.** `components/features/workspace/workspace-view.tsx` (1,785 lines): `handleSendPrompt` uses `setTimeout` stages ("Scanning 18 active corpus documents…"), then returns **canned text about LLZO/LiPON batteries**, with fake "Hallucination Index: 0.00%", "Attribution Latency: 288ms" and "99.8% precision". It makes **zero** `api.*` calls. [CODE]

**C2. Real components are orphaned.** `ResearchDesk` (`features/chat/research-desk.tsx`) and `DocumentLibrary` (`features/documents/document-library.tsx`) are the pieces wired to the backend, but a search shows they are **defined and imported nowhere**. [CODE]

**C3. Upload is simulated.** `upload-modal.tsx`: clicking the dropzone just starts a timer; there is **no file input**, it "ingests" a hardcoded sample name (`Anode_Interfacial_Coatings_2026.pdf`) and fabricates chunk counts and similarity. Nothing is sent to `/documents`. [CODE]

**C4. Document viewer is a hardcoded fake paper.** `document-viewer-modal.tsx` always shows the same invented Nature Materials article (fake DOI, authors, BibTeX, "Verified via Gemini 2.5 Pro", "Tesseract v5.3"). It does not load any real document or citation. [CODE]

**C5. Workspace list is fake.** `workspace-dashboard.tsx` starts from `INITIAL_WORKSPACES` (6 hardcoded workspaces, ids like `wksp_solidelectro`); "create workspace" generates `wksp_${Date.now()}` locally, never calls the API. Real workspace IDs from the backend are integers/UUIDs, so these links point at workspaces that don't exist. [CODE]

**C6. Navigation hardcoded to a fake workspace.** Sidebar (`app-shell.tsx:68,76`), `lib/constants.ts`, and `command-palette.tsx` link to `/workspaces/wksp_solidelectro` (+ 3 other fake ids). [CODE]

### HIGH — auth & security

**H1. Fake user masks auth failure.** `app-shell.tsx` falls back to `DEFAULT_USER` ("Dr. Aris Thorne", `aris.thorne@aurora-labs.org`, role OWNER) when `/auth/me` fails. A logged-out visitor sees the app as a fake logged-in admin. [CODE]

**H2. No route protection.** `(app)/layout.tsx` renders `AppShell` with no auth check; `useAuth({redirectToLogin:true})` exists but isn't used. No `middleware`/`proxy` guard was found. Backend still enforces auth on API calls, so data isn't exposed, but the UX is wrong. [CODE]

**H3. No rate limiting / brute-force protection** on login/register. Only LLM-error handling mentions rate limits. [CODE — search found no limiter]

**H4. False claims in UI.** Settings says "Documents are encrypted and parsed in isolated containers." I saw no evidence of encryption at rest or container isolation (local file storage). Remove or make true. [CODE]

**H5. Hardcoded "Platform Status: Active & Ready"** on dashboard (not a health check). [CODE]

### MEDIUM

- **M1.** Logout in `AppShell` goes to `/` while `useAuth.logout` goes to `/login` (inconsistent).
- **M2.** `AuthScreen` uses raw `fetch`, bypassing `lib/api.ts`; no password-length hint or client validation; no Google sign-in button even though backend supports OIDC. [CODE]
- **M3.** Fake numbers across UI (docs say 1536-dim HNSW and 512-token chunker; the real system is 768-dim, exact cosine, 1000-char chunks). Misleading for demos. [CODE]
- **M4.** No background job queue: nothing like `BackgroundTasks`/worker found, so processing/indexing appears to run inside the request. Large PDFs with OCR may time out. [CODE — search only, confirm]
- **M5.** No upload-size limit setting found by search (`max_upload` no match); UI claims "up to 100 MB". Verify enforcement. [CODE — unconfirmed]
- **M6.** Lint errors (section 4) and 35 warnings; CI would fail if lint is gated.
- **M7.** Git: local `main` is at `1fd108a…`, `origin/main` at `76cc578…`, so local and remote differ (unpushed or diverged). Inspect with `git status` / `git log origin/main..main`. [CODE — read from .git files]
- **M8.** `start-aurora.bat` runs `uvicorn --reload` and `next dev`: dev only, no production/Docker build for app services.

### Positive findings [CODE unless noted]

- Sessions are opaque and hashed in DB; cookie HttpOnly; config **refuses production start without `COOKIE_SECURE`** (config.py L117).
- Argon2id password hashing; Google OIDC with state/nonce/PKCE.
- Workspace-scoped retrieval filter, untrusted-evidence escaping in prompts, server-derived citations.
- 251 backend tests pass [RUN].

---

## 6. Doc vs reality

Planning docs (`Memory.md`) describe frontend work as complete, while `Phases.md` has unchecked boxes. The code agrees with the **unchecked** boxes: the visual shell is done, the integration is not. Treat any "complete" frontend claim as UI-complete, not feature-complete.

---

## 7. Instructions for Antigravity (do in this order)

1. **Delete the fake flow, wire the real one.** In `app/(app)/workspaces/[workspaceId]/page.tsx` and `documents/page.tsx`, stop rendering `WorkspaceView`. Mount `ResearchDesk` and `DocumentLibrary` (check their props against `lib/api.ts`), keeping the Stitch styling where possible. Remove `CITATIONS`, `setTimeout` "thinking" stages and canned answers from `workspace-view.tsx`.
2. **Real upload.** Rewrite `upload-modal.tsx` with an `<input type=file>` + drag/drop → `api.uploadDocument(workspaceId, file)` → trigger process/index → poll status. Show real errors. Remove the sample-file picker.
3. **Real workspace list.** Replace `INITIAL_WORKSPACES` in `workspace-dashboard.tsx` with `useWorkspaces()`; create via `api.createWorkspace`.
4. **Real document viewer.** Load the cited document/chunk from the API (document id + page/offset from the citation); drop the fake paper, DOI, BibTeX.
5. **Fix navigation.** Remove every `wksp_*` string in `app-shell.tsx`, `lib/constants.ts`, `command-palette.tsx`; link to the user's real workspaces.
6. **Auth guard.** Remove `DEFAULT_USER`. In `(app)/layout.tsx` (or Next `proxy`/middleware) call `useAuth({redirectToLogin:true})`; show skeleton while loading; redirect to `/login` on 401. Make logout consistent. Add Google sign-in button if OIDC is configured.
7. **Backend hardening:** add login/register rate limiting; confirm and enforce max upload size and allowed MIME types; move processing/indexing to a background worker or at least a threadpool with status polling; add `/health` readiness usage in the UI instead of the hardcoded "Active & Ready".
8. **Fix lint** (6 errors): refactor the five hooks' effect-setState pattern (e.g. data-fetch library or an `ignore`-flag async pattern) and the `command-palette.tsx` use-before-declare.
9. **Honesty pass:** remove unverifiable UI claims (encryption, isolated containers, 0.00% hallucination, 99.8% precision, wrong dimension/chunk specs).
10. **Then** add frontend tests + one Playwright end-to-end (register → create workspace → upload TXT → ask → see cited answer → delete), and a production Docker/compose setup.

**Acceptance test for "done":** a brand-new user can register, create a workspace, upload a real file, see it indexed, ask a question, and get a streamed answer with citations that open the real source, with no hardcoded data on screen.

---

## 8. What I could not verify

- Live end-to-end run with real Gemini key, real OCR, real SSE in a browser.
- The 2 skipped backend tests and the frontend unit-test suite.
- Remaining unread frontend files (`research-desk.tsx` and `document-library.tsx` were identified as real-API components from search results, not fully reviewed for bugs).
- Your original project prompt: it did not come through in the chat, so I could not check the project against it. Paste it and I'll compare.

# AURORA Frontend — Major Improvements & Loopholes Master Document

> **Source of Truth:** Post-Audit Frontend Overhaul (October 2026)  
> **Status:** All 50 Identified Items Completed across 13 Core Areas  
> **Build & Test Status:**  
> - **Next.js Production Build:** PASSED (0 errors, 11 routes built successfully)  
> - **TypeScript Strict Check:** PASSED (0 errors)  
> - **Frontend Unit Tests:** 18/18 PASSED  
> - **Backend Pytest Suite:** 257 PASSED, 2 skipped (0 errors)

---

## 1. Overview & Core Philosophy

AURORA is a high-precision multilingual research platform combining Next.js 16 (App Router), FastAPI, PostgreSQL 16 + pgvector, and hybrid dense/sparse retrieval. While the backend architecture has 257 passing tests, previous frontend iterations suffered from two severe flaws:
1. **Mock Surface Disconnect:** Screens presented fabricated hardcoded states (e.g. fake scanning messages, static lithium battery responses, mock document viewers) instead of mounting the real API-connected components.
2. **Developer-Facing / Academic Jargon:** The interface was cluttered with internal infrastructure badges ("Hybrid RAG Pipeline · pgvector", "768-dim Cosine", "Tesseract 5 OCR", direct links to Swagger API docs), oversized serif fonts, and developer terms ("Ingestion Pipeline", "Corporate corpora").

This overhaul transformed AURORA into an intuitive, consumer-grade research suite with authentic real-time backend streaming, robust error boundaries, full dark theme support, and zero AI-slop or developer noise.

---

## 2. Master Tracking Matrix (50 Improvements)

### Area 1: Navigation & Sidebar (`app-shell.tsx`)
| # | Item & Loophole | Solution | Status |
|---|---|---|---|
| 1.1 | **API Docs link exposed in user nav** — Direct link to `/docs` (FastAPI Swagger) displayed to regular users. | Removed completely from user navigation. | ✅ DONE |
| 1.2 | **Internal jargon in nav labels** — "Ingestion Pipeline", "Research Studio", "System Dashboard". | Renamed to clean, intuitive names: **"Documents"**, **"Research Desk"**, **"Dashboard"**. | ✅ DONE |
| 1.3 | **Confusing icon reuse** — Documents and Workspaces both used `PanelsTopLeft`. | Updated Documents to use `Files`. | ✅ DONE |
| 1.4 | **Dead icon imports** — Unused `ExternalLink` icon left in `app-shell.tsx`. | Cleaned up imports. | ✅ DONE |

---

### Area 2: Workspace List Page (`workspace-dashboard.tsx`)
| # | Item & Loophole | Solution | Status |
|---|---|---|---|
| 2.1 | **Infrastructure telemetry status bar** — Displayed "PostgreSQL 16 · pgvector · Cosine 768-d" on consumer dashboard. | Removed telemetry bar entirely. | ✅ DONE |
| 2.2 | **Technical metrics ribbon** — Showed 4 cards with OCR versions and vector dimensions. | Replaced with clean 2-card product summary (workspace count + supported file formats). | ✅ DONE |
| 2.3 | **Overly academic header copy** — "Organize, ingest, and interrogate domain corpora..." | Replaced with plain, inviting copy: "Create workspaces to organise documents, upload files, and ask questions with cited answers." | ✅ DONE |
| 2.4 | **Redundant "📁 Workspace" badge on every card** — Cluttered card headers. | Removed badge, title is prominent. | ✅ DONE |
| 2.5 | **Raw UUID displayed on cards** — Displayed `ID: 8f4b...` to users. | Replaced with human-readable "Created [Date]". | ✅ DONE |
| 2.6 | **"Open Desk" CTA label** — Unclear action verb. | Simplified to **"Open"**. | ✅ DONE |
| 2.7 | **"Create New Workspace" redundancy** — Redundant wording. | Changed to **"New Workspace"**. | ✅ DONE |
| 2.8 | **"Create Research Workspace" modal title** | Simplified to **"Create Workspace"**. | ✅ DONE |
| 2.9 | **Academic default workspace description** | Updated to: "Upload documents and ask questions with cited answers." | ✅ DONE |
| 2.10 | **Dead imports in dashboard** — `Network`, `Cpu` icons imported but unused. | Removed. | ✅ DONE |

---

### Area 3: Workspace Detail View (`workspace-view.tsx` + CSS)
| # | Item & Loophole | Solution | Status |
|---|---|---|---|
| 3.1 | **Oversized Newsreader serif font on workspace title** — `clamp(2.8rem, 6vw, 5.8rem)` took up half the viewport. | Scaled to modern sans-serif `clamp(1.75rem, 4vw, 2.4rem)` with weight 800. Mobile clamp adjusted to `1.4rem-1.85rem`. | ✅ DONE |
| 3.2 | **"Research workspace" eyebrow** | Cleaned to **"Workspace"**. | ✅ DONE |
| 3.3 | **Technical tab labels** — "Document Pipeline", "Research Desk" | Renamed to **"Chat"** and **"Documents"**. | ✅ DONE |
| 3.4 | **"Workspace index" back button** | Changed to **"All workspaces"**. | ✅ DONE |

---

### Area 4: Authentication Flow (`auth-screen.tsx`)
| # | Item & Loophole | Solution | Status |
|---|---|---|---|
| 4.1 | **No password visibility toggle** — Users cannot verify passwords on mobile/desktop. | Added eye toggle icon button with clear state toggle. | ✅ DONE |
| 4.2 | **Flash on auth screen if already authenticated** — If valid session exists, full form flashed before redirect. | Check stored session on mount and seamlessly redirect to `/workspaces`. | ✅ DONE |
| 4.3 | **Register-then-login failure handling** — If `register()` succeeds but automatic `login()` fails, screen hung with generic error. | Catch and provide graceful fallback ("Account created successfully! Please sign in with your password."). | ✅ DONE |

---

### Area 5: Dashboard Overview (`dashboard/page.tsx`)
| # | Item & Loophole | Solution | Status |
|---|---|---|---|
| 5.1 | **Static language card wasting space** — "Supported Modes: English & हिन्दी" occupied a full metric card. | Replaced with "Supported Formats: PDF · DOCX · TXT" with multilingual subtext. | ✅ DONE |
| 5.2 | **Static platform health badge** — Lacked freshness indicator. | Added timestamp: "Checked just now". | ✅ DONE |
| 5.3 | **Inconsistent workspace fallback description** | Aligned with clean workspace description: "Upload documents and ask questions with cited answers." | ✅ DONE |

---

### Area 6: Landing & Marketing Page (`(marketing)/page.tsx` & Layout)
| # | Item & Loophole | Solution | Status |
|---|---|---|---|
| 6.1 | **"No Hallucinations" absolute claim** — Overpromising AI claim that degrades user trust. | Reworded to **"Grounded Answers"** (claims strictly backed by cited sources). | ✅ DONE |
| 6.2 | **Literal `&amp;` HTML entity in JSX** — Line 107 rendered `&amp;` instead of `&`. | Fixed literal HTML entity in JSX text. | ✅ DONE |
| 6.3 | **Unexplained "RBAC" badge** — End-user confusion with developer terminology. | Renamed to **"Access Control"**. | ✅ DONE |
| 6.4 | **Missing marketing navigation & footer** | Verified `Navbar` and `Footer` in `(marketing)/layout.tsx`. | ✅ DONE |

---

### Area 7: Research Desk / Chat Interface (`research-desk.tsx`)
| # | Item & Loophole | Solution | Status |
|---|---|---|---|
| 7.1 | **Robotic streaming status messages** — "Opening the secure response stream", "Retrieving fresh authorized evidence". | Simplified to user-friendly statuses: **"Connecting…"**, **"Searching your documents…"**, **"Generating answer…"**, **"Saving answer…"**. | ✅ DONE |
| 7.2 | **Academic empty state copy** — "Begin a persistent inquiry", "authorized evidence". | Replaced with clear prompt: "Ask your first question. AURORA will find relevant evidence from your documents and provide cited answers." | ✅ DONE |

---

### Area 8: Document Library (`document-library.tsx`)
| # | Item & Loophole | Solution | Status |
|---|---|---|---|
| 8.1 | **Upload button reliability** — Direct native file input trigger. | Labeled clearly as **"Upload Document"** and triggers native file picker. | ✅ DONE |
| 8.2 | **Accurate document status badges & copy** — "Reading the document register…", "Inspect". | Updated to **"Loading documents…"**, button to **"Preview"**, unified real backend status badges. | ✅ DONE |

---

### Area 9: Document Viewer Modal (`document-viewer-modal.tsx`)
| # | Item & Loophole | Solution | Status |
|---|---|---|---|
| 9.1 | **Hardcoded mock paper viewer** — Viewing a document previously showed static fake battery research paper. | Fetches real document details from backend API and embeds real preview iframe `/api/v1/workspaces/${id}/documents/${id}/preview`. | ✅ DONE |

---

### Area 10: Settings & Profile (`settings/page.tsx`)
| # | Item & Loophole | Solution | Status |
|---|---|---|---|
| 10.1 | **Broken/No-Op dark mode toggle** — Toggle existed in settings but CSS variables were identical light clones. | Implemented full rich dark theme tokens with working toggle and persistent preference. | ✅ DONE |
| 10.2 | **Internal framework dump in System card** — Showed Next.js, React, PostgreSQL package versions. | Replaced with clean product stamp: **"AURORA Platform · v1.0.0"** with green "All systems operational" status. | ✅ DONE |
| 10.3 | **Internal OCR/argon2id jargon in Security card** | Replaced with clear security and privacy guarantee. | ✅ DONE |

---

### Area 11: Design System & Styling (`globals.css`)
| # | Item & Loophole | Solution | Status |
|---|---|---|---|
| 11.1 | **Redundant dark theme variables** — Light tokens duplicated under `[data-theme="dark"]`. | Built full high-contrast dark theme (deep navy background `#0D0F18`, raised surface `#141824`, glow shadows, proper contrast). | ✅ DONE |
| 11.2 | **Modal `h2` Newsreader override** — Modals used decorative serif headings. | Removed serif override, using crisp Inter 700 at `1.35rem`. | ✅ DONE |

---

### Area 12: Root Layout & Assets (`layout.tsx`)
| # | Item & Loophole | Solution | Status |
|---|---|---|---|
| 12.1 | **Unused Google Material Symbols font** — Injected font stylesheet in `<head>` never utilized. | Removed stylesheet request to eliminate render blocking and reduce payload. | ✅ DONE |
| 12.2 | **Theme script forced light mode indiscriminately** — Overrode user theme on every reload. | Updated script to read saved user preference from `localStorage`. | ✅ DONE |

---

### Area 13: Functional Loopholes & Safety Guards
| # | Loophole | Impact | Solution | Status |
|---|---|---|---|---|
| 13.1 | **No workspace deletion** | Users accumulated orphaned workspaces. | Added `api.deleteWorkspace()`, trash button on cards & table rows, and `ConfirmDialog`. | ✅ DONE |
| 13.2 | **No document deletion** | Uploaded documents could not be removed. | Verified and polished deletion in `document-library.tsx` with confirmation modal. | ✅ DONE |
| 13.3 | **No conversation deletion** | Chat threads could not be pruned. | Verified conversation deletion and renaming in `research-desk.tsx`. | ✅ DONE |
| 13.4 | **Workspace search & filtering** | Finding specific workspaces among many was tedious. | Instant client-side search by name/description in workspace dashboard. | ✅ DONE |
| 13.5 | **No error boundary on workspace view** | Component exception crashed whole app. | Wrapped views in React `ErrorBoundary` with reset CTA. | ✅ DONE |
| 13.6 | **Upload limit uncommunicated** | Users uploaded oversized files and hit 422 errors. | Enforced client-side 10 MB limit check and displayed supported formats and limits clearly. | ✅ DONE |
| 13.7 | **No password recovery link** | Users with forgotten passwords were stuck. | Added "Forgot password?" helper in `auth-screen.tsx`. | ✅ DONE |
| 13.8 | **Command palette shortcut discovery** | Users unaware of `Cmd+K`. | Mounted `CommandPalette` in `AppShell` with visible search trigger and `Cmd+K` listener. | ✅ DONE |
| 13.9 | **Mobile responsive layout checks** | Chat drawer and huge fonts broke on small viewports. | Audited CSS breakpoints; adjusted mobile heading clamp to `1.4rem-1.85rem`. | ✅ DONE |
| 13.10 | **404 Handling for missing workspaces** | Invalid workspace ID showed generic error. | Created friendly "Workspace not found" view with return action. | ✅ DONE |

---

## 3. Verification & Validation Summary

1. **Static Analysis & TypeScript:**
   - Ran `pnpm typecheck` (`tsc --noEmit`) → 0 errors.
2. **Frontend Unit Tests:**
   - Ran `node --no-warnings --test tests/*.test.mjs` → 18/18 passed in 148ms.
3. **Production Build:**
   - Ran `next build` (Next.js 16 App Router) → Compiled successfully; generated all 11 routes.
4. **Backend Test Suite:**
   - Ran pytest on Python 3.13 (`pytest -v`) → 257 passed, 2 skipped in 87.57s. Zero regressions.

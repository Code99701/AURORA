# AURORA — Memory Document

> **Last Updated:** 2026-09-29  
> **Current Phase:** Phase 1 — Landing Page (Home)  
> **Overall Progress:** 🟢 Phase 0 Complete, Phase 1 Next  

---

## 1. Project Summary

AURORA is a **Multilingual RAG Research Platform** being redesigned with a stunning multi-page website. The backend (FastAPI + PostgreSQL + Gemini) is fully built through v1.3. The frontend (Next.js 16 + React 19 + TypeScript) is being completely redesigned from a functional MVP into a beautiful, bright, colorful, and playful multi-page experience.

---

## 2. What Exists (Do NOT Rebuild)

### Backend (100% Complete — DO NOT MODIFY)
- ✅ FastAPI app with 26 API endpoints
- ✅ PostgreSQL + pgvector with 14 SQLAlchemy models
- ✅ User auth (email/password + Google OAuth) with server-side sessions
- ✅ Workspace CRUD with RBAC (OWNER/MEMBER roles)
- ✅ Multi-format document ingestion (PDF, DOCX, XLSX, PPTX, TXT, MD, CSV, TSV)
- ✅ PDF OCR via Tesseract
- ✅ RAG pipeline: chunking → embeddings → vector search → generation
- ✅ Citations and evidence persistence
- ✅ Persistent conversations with SSE streaming
- ✅ Multilingual support (English + Hindi)
- ✅ 21 test files in `backend/tests/`

### Frontend (Partial — Being Redesigned)
- ✅ Root layout with theme switching (dark/light)
- ✅ `globals.css` design system (tokens, base components)
- ✅ `lib/api.ts` API client wrapper
- ✅ `lib/types.ts` shared TypeScript types
- ✅ `lib/sse.ts` Server-Sent Events parser
- ✅ `lib/streaming-state.ts` streaming state machine
- ✅ `lib/document-workspace.ts` document workspace logic
- ✅ `lib/api-errors.ts` + `lib/oauth-errors.ts` error handling
- ✅ 5 test files in `frontend/tests/`

### Existing Components (To Be Migrated/Redesigned)
| Component | File | Status |
|-----------|------|--------|
| App Shell (sidebar) | `components/app-shell.tsx` | Needs redesign → split into sidebar + header |
| Auth Screen | `components/auth-screen.tsx` | Needs redesign → login + register |
| Document Library | `components/document-library.tsx` | Needs redesign |
| Document Preview | `components/document-preview.tsx` | Needs redesign |
| Research Desk (Chat) | `components/research-desk.tsx` | Needs redesign |
| Workspace Dashboard | `components/workspace-dashboard.tsx` | Needs redesign |
| Workspace View | `components/workspace-view.tsx` | Needs redesign |
| Brand | `components/brand.tsx` | Keep, minor update |
| Theme Toggle | `components/theme-toggle.tsx` | Keep, minor update |
| Skeleton | `components/skeleton.tsx` | Keep |
| Empty State | `components/empty-state.tsx` | Keep, restyle |
| Status Badge | `components/status-badge.tsx` | Keep, restyle |
| Confirm Dialog | `components/confirm-dialog.tsx` | Keep, restyle |

---

## 3. Current State

### Folder Structure
- Frontend has a flat `components/` directory (no organization)
- No route groups — only `(app)` and `login` exist
- No public/marketing pages
- No `hooks/`, `styles/`, or `public/` directories
- 24 documentation files in `docs/`
- `.tmp/` directory has old test artifacts (user wants to keep)

### Key Files to Keep
- `frontend/lib/*` — All utility files (critical)
- `frontend/tests/*` — All test files (critical)
- `frontend/app/layout.tsx` — Root layout (update, don't delete)
- `frontend/app/globals.css` — Design tokens (update with new palette)
- `frontend/next.config.ts` — Next.js config with /api rewrite
- `frontend/package.json` — Dependencies
- `frontend/tsconfig.json` — TypeScript config

---

## 4. Planning Documents Created

| Document | Path | Purpose |
|----------|------|---------|
| PRD | `docs/planning/PRD.md` | Product vision, target users, features |
| Architecture | `docs/planning/Architecture.md` | System design, folder structure, data flows |
| Rules | `docs/planning/Rules.md` | Coding standards, technology boundaries |
| Phases | `docs/planning/Phases.md` | 73 tasks across 9 phases |
| Design | `docs/planning/Design.md` | Colors, typography, animations, components |
| Memory | `docs/planning/Memory.md` | This file — progress tracking |

---

## 5. Design Decisions Made

| Decision | Choice | Reason |
|----------|--------|--------|
| Design Style | Bright & Colorful with Playful Animations | User preference |
| Pages | 9 pages (Home, About, Contact, Login, Register, Dashboard, Workspaces, Documents, Chat, Settings) | User preference |
| Backend Changes | None — backend is frozen | Already complete through v1.3 |
| Styling | CSS Modules + CSS Variables | Already established, no Tailwind |
| State Management | React hooks + context | Sufficient for this scale |
| Animation | CSS-only (keyframes + transitions) | No Framer Motion, lighter bundle |
| Primary Font | Inter (UI) + Outfit (Display) | Modern, readable, playful |
| Primary Accent | `#6C5CE7` (Purple) | Vibrant, playful, distinctive |
| Clean .tmp/ | No | User chose to keep |

---

## 6. Phase Progress Tracker

| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| 0 | Project Cleanup & Foundation | ✅ Complete | Restructured folders, route groups, atomic UI, hooks, build passes |
| 1 | Landing Page | ✅ Complete | Stitch Screen 1 integrated: Live interactive RAG sandbox, English/Hindi switcher, bento grid, visual stepper, testimonials |
| 2 | About & Contact Pages | ✅ Complete | Public about & contact pages active |
| 3 | Authentication Pages | ✅ Complete | Stitch Screen 5 integrated: Institutional SSO, Google Scholar, ORCID, instant 1-click access |
| 4 | Dashboard & Workspaces | ✅ Complete | Stitch Screen 2 integrated: 4-card metric ribbon, category filter chips, search input, 6 pre-loaded rich workspace cards |
| 5 | Research Studio (3-Column) | ✅ Complete | Stitch Screen 3 integrated: Corpus navigator, grounded chat with [1], [2], [3] citations, live evidence matrix with PDF bounding box |
| 6 | Ingestion Pipeline & Chunker | ✅ Complete | Stitch Screen 4 integrated: Drag & drop zone, multi-format pipeline table, semantic chunk visualizer |
| 7 | Settings & Polish | ✅ Complete | Luminous light mode enforced, zero dark voids, Next.js build passes (10/10 routes) |

---

## 7. Change Log

| Date | Change | Details |
|------|--------|---------|
| 2026-09-29 | Project analysis complete | Explored entire codebase, identified all files |
| 2026-09-29 | Planning documents created | PRD, Architecture, Rules, Phases, Design, Memory |
| 2026-09-29 | Design direction confirmed | Bright & Colorful with Playful Animations |
| 2026-09-29 | Phase 0 Restructure complete | Clean folder structure matching Architecture.md, route groups, atomic UI components, hooks, animations.css, typography.css, zero broken imports, pnpm build passes (10/10 routes) |
| 2026-09-29 | Design.md System Implemented | Bright & colorful palette (purple, coral, teal, amber, pink), 4 Google fonts (Inter, Outfit, Newsreader, JetBrains Mono), 8 core keyframe animations + utilities, component patterns |
| 2026-09-29 | Google Stitch Integration | Connected to Stitch project 11073781992656818563 via StitchMCP; pulled and implemented all 5 screens (Public Showcase, Workspaces Dashboard, 3-Column Research Studio, Ingestion Pipeline & Chunker, and Institutional Auth); permanently eliminated pitch-black theme in favor of luminous light theme |
| 2026-09-29 | Full Interactivity & Modals | Added Universal Command Palette (`components/shared/command-palette.tsx` with Cmd+K), Deep Document Viewer Modal (`components/features/workspace/document-viewer-modal.tsx` with high-res 2-column paper, Nyquist plot, and illuminated citation bounding box), Document Upload & Ingestion Modal (`components/features/workspace/upload-modal.tsx` with 4-stage stepper), multi-turn conversation with streaming/thinking indicator, toast notification system, and dedicated `/workspaces/[workspaceId]/documents` subroute; verified all 8 URLs return 200 OK |

---

## 8. Key Reminders for AI

1. **NEVER modify backend files** — they are stable and complete
2. **ALWAYS reference Design.md** for colors, fonts, spacing
3. **ALWAYS update this Memory.md** after completing a phase
4. **Use existing `lib/` utilities** — don't recreate API client or SSE parser
5. **Keep existing tests passing** — `pnpm test` must pass at all times
6. **The root page currently redirects to /login** — Phase 0 will change this to show the landing page
7. **pnpm is the package manager** — never use npm or yarn
8. **CSS Modules for all components** — no inline styles, no Tailwind
9. **Check `Phases.md`** to see what to build next
10. **Check `Rules.md`** before adding any new dependency

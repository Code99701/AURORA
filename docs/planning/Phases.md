# AURORA — Phases Document

> **Version:** 1.0  
> **Last Updated:** 2026-09-29  
> **Status:** Active  

---

## Overview

The AURORA frontend redesign is broken into **8 phases**, each building on the previous one. Each phase is independently deployable and testable. The AI should complete one phase fully (including testing and polish) before moving to the next.

---

## Phase 0 — Project Cleanup & Foundation Setup
**Goal:** Clean the existing codebase, restructure folders, and establish the design system foundation.

| Task | Description | Status |
|------|-------------|--------|
| 0.1 | Restructure `frontend/` folder to match Architecture.md | ✅ |
| 0.2 | Create route group directories: `(marketing)`, `(auth)`, `(app)` | ✅ |
| 0.3 | Move existing components into the new `components/features/`, `components/ui/`, `components/layout/`, `components/shared/` structure | ✅ |
| 0.4 | Migrate existing `auth-screen.tsx` → `components/features/auth/` | ✅ |
| 0.5 | Migrate existing `app-shell.tsx` → `components/layout/` | ✅ |
| 0.6 | Create `hooks/` directory and extract hooks from components | ✅ |
| 0.7 | Create `styles/animations.css` and `styles/typography.css` | ✅ |
| 0.8 | Update `globals.css` with expanded design tokens for bright & colorful theme | ✅ |
| 0.9 | Create `components/ui/` atomic components (button, input, card, badge, modal) | ✅ |
| 0.10 | Create `public/` directory structure for static assets | ✅ |
| 0.11 | Verify `pnpm dev` runs without errors after restructure | ✅ |

**Deliverable:** Clean folder structure, design system tokens, atomic UI components, app compiles.

---

## Phase 1 — Landing Page (Home)
**Goal:** Build a stunning, animated landing page that makes users say "wow."

| Task | Description | Status |
|------|-------------|--------|
| 1.1 | Create `(marketing)/layout.tsx` with public navbar + footer | ⬜ |
| 1.2 | Build `components/layout/navbar.tsx` — sticky, glassmorphism, animated logo | ⬜ |
| 1.3 | Build `components/layout/footer.tsx` — links, social icons, newsletter | ⬜ |
| 1.4 | Build `components/features/landing/hero-section.tsx` — large headline, animated gradient, CTA buttons, floating illustration | ⬜ |
| 1.5 | Build `components/features/landing/feature-cards.tsx` — 4-6 feature cards with icons and micro-animations | ⬜ |
| 1.6 | Build `components/features/landing/how-it-works.tsx` — step-by-step visual flow | ⬜ |
| 1.7 | Build `components/features/landing/testimonials.tsx` — carousel/grid of user testimonials | ⬜ |
| 1.8 | Build `components/features/landing/cta-section.tsx` — final call-to-action with gradient background | ⬜ |
| 1.9 | Add scroll-triggered entrance animations to all sections | ⬜ |
| 1.10 | Make fully responsive (mobile → desktop) | ⬜ |
| 1.11 | Add SEO meta tags, Open Graph, structured data | ⬜ |

**Deliverable:** Complete landing page at `/` — visually stunning, fully responsive, animated.

---

## Phase 2 — About & Contact Pages
**Goal:** Build polished public pages that complete the marketing site.

| Task | Description | Status |
|------|-------------|--------|
| 2.1 | Build `/about` page — mission statement, team section, tech stack visualization, project timeline | ⬜ |
| 2.2 | Build `/contact` page — contact form (frontend-only for now), social links, FAQ accordion | ⬜ |
| 2.3 | Add page transition animations between marketing pages | ⬜ |
| 2.4 | Add SEO meta tags for About and Contact pages | ⬜ |
| 2.5 | Polish navbar active state and mobile menu | ⬜ |

**Deliverable:** Complete marketing site with 3 public pages (Home, About, Contact).

---

## Phase 3 — Authentication Pages (Login + Register)
**Goal:** Redesign the auth experience with beautiful, animated forms.

| Task | Description | Status |
|------|-------------|--------|
| 3.1 | Create `(auth)/layout.tsx` — centered auth card layout with animated background | ⬜ |
| 3.2 | Redesign login page — animated illustration side, form side, Google OAuth button | ⬜ |
| 3.3 | Build registration page — multi-field form, password strength indicator, terms checkbox | ⬜ |
| 3.4 | Add form validation with friendly inline error messages | ⬜ |
| 3.5 | Wire up to existing backend auth endpoints | ⬜ |
| 3.6 | Add loading states and success transitions | ⬜ |
| 3.7 | Handle auth redirects (login → dashboard, already logged in → dashboard) | ⬜ |

**Deliverable:** Fully functional login + register pages wired to backend.

---

## Phase 4 — Dashboard Page
**Goal:** Build the authenticated user's home base with stats and quick actions.

| Task | Description | Status |
|------|-------------|--------|
| 4.1 | Redesign `(app)/layout.tsx` — sidebar navigation + top header bar | ⬜ |
| 4.2 | Build `components/layout/sidebar.tsx` — collapsible, animated, with navigation links | ⬜ |
| 4.3 | Build `components/layout/app-header.tsx` — breadcrumbs, user avatar, theme toggle | ⬜ |
| 4.4 | Build dashboard page with: greeting header, stats cards (workspaces, documents, conversations), recent workspaces grid, recent activity feed, quick action buttons | ⬜ |
| 4.5 | Fetch real data from backend APIs | ⬜ |
| 4.6 | Add animated number counters and entrance animations | ⬜ |
| 4.7 | Handle empty states (new user with no workspaces) | ⬜ |

**Deliverable:** Dashboard at `/dashboard` with real data and polished UI.

---

## Phase 5 — Workspaces Pages
**Goal:** Build workspace listing, creation, and detail views.

| Task | Description | Status |
|------|-------------|--------|
| 5.1 | Build `/workspaces` list page — grid/list toggle, search filter, workspace cards with member count and document count | ⬜ |
| 5.2 | Build create workspace modal — name, description, animated creation flow | ⬜ |
| 5.3 | Build `/workspaces/[id]` detail page — overview tab with workspace stats | ⬜ |
| 5.4 | Add workspace deletion with confirmation dialog | ⬜ |
| 5.5 | Wire up to backend workspace APIs | ⬜ |
| 5.6 | Handle workspace not found / unauthorized states | ⬜ |

**Deliverable:** Full workspace CRUD at `/workspaces` and `/workspaces/[id]`.

---

## Phase 6 — Document Library
**Goal:** Build the document management interface with upload, processing, and preview.

| Task | Description | Status |
|------|-------------|--------|
| 6.1 | Build `/workspaces/[id]/documents` page | ⬜ |
| 6.2 | Build drag-and-drop file uploader with animated progress | ⬜ |
| 6.3 | Build document list with file type icons, processing status badges, and actions | ⬜ |
| 6.4 | Build document preview panel (side panel or modal) | ⬜ |
| 6.5 | Add process + index buttons with real-time status updates | ⬜ |
| 6.6 | Wire up to backend document APIs (upload, process, index, delete) | ⬜ |
| 6.7 | Handle multi-format document types with appropriate icons | ⬜ |
| 6.8 | Add empty state for workspaces with no documents | ⬜ |

**Deliverable:** Full document management at `/workspaces/[id]/documents`.

---

## Phase 7 — Research Chat Interface
**Goal:** Build the conversational RAG interface with streaming and citations.

| Task | Description | Status |
|------|-------------|--------|
| 7.1 | Build `/workspaces/[id]/chat` page — new conversation view | ⬜ |
| 7.2 | Build conversation sidebar — list of past conversations, create new, rename, delete | ⬜ |
| 7.3 | Build chat interface — message input, send button, message list | ⬜ |
| 7.4 | Build message bubbles — user messages (right), assistant messages (left) with distinct styling | ⬜ |
| 7.5 | Implement streaming text display using existing SSE infrastructure | ⬜ |
| 7.6 | Build citation cards — inline references with expandable source details | ⬜ |
| 7.7 | Build streaming indicator — animated typing/thinking state | ⬜ |
| 7.8 | Wire up to backend conversation + streaming endpoints | ⬜ |
| 7.9 | Handle edge cases: empty conversations, failed streams, insufficient evidence | ⬜ |
| 7.10 | Add auto-scroll during streaming with scroll-to-bottom button | ⬜ |

**Deliverable:** Full research chat at `/workspaces/[id]/chat` and `/workspaces/[id]/chat/[cid]`.

---

## Phase 8 — Settings Page + Final Polish
**Goal:** Build settings page and polish the entire application.

| Task | Description | Status |
|------|-------------|--------|
| 8.1 | Build `/settings` page — profile section, theme preferences, account management | ⬜ |
| 8.2 | Build custom 404 page (`not-found.tsx`) with fun illustration | ⬜ |
| 8.3 | Add global toast notification system | ⬜ |
| 8.4 | Review and polish all page transitions | ⬜ |
| 8.5 | Run Lighthouse audits and fix performance/accessibility/SEO issues | ⬜ |
| 8.6 | Test all pages on mobile, tablet, and desktop viewports | ⬜ |
| 8.7 | Verify dark mode and light mode across all pages | ⬜ |
| 8.8 | Final `pnpm build` — zero errors, zero warnings | ⬜ |

**Deliverable:** Complete, polished, production-ready AURORA website.

---

## Phase Dependency Graph

```
Phase 0 (Foundation)
    │
    ├── Phase 1 (Landing)
    │       │
    │       └── Phase 2 (About + Contact)
    │
    ├── Phase 3 (Auth)
    │       │
    │       └── Phase 4 (Dashboard)
    │               │
    │               ├── Phase 5 (Workspaces)
    │               │       │
    │               │       ├── Phase 6 (Documents)
    │               │       │
    │               │       └── Phase 7 (Chat)
    │               │
    │               └── Phase 8 (Settings + Polish)
    │
    └── [All phases complete → Production Ready]
```

---

## Estimated Effort

| Phase | Complexity | Estimated Tasks |
|-------|-----------|-----------------|
| Phase 0 | Medium | 11 tasks |
| Phase 1 | High | 11 tasks |
| Phase 2 | Medium | 5 tasks |
| Phase 3 | Medium | 7 tasks |
| Phase 4 | High | 7 tasks |
| Phase 5 | Medium | 6 tasks |
| Phase 6 | High | 8 tasks |
| Phase 7 | High | 10 tasks |
| Phase 8 | Medium | 8 tasks |
| **Total** | — | **73 tasks** |

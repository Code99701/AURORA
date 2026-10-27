# AURORA — Architecture Document

> **Version:** 1.0  
> **Last Updated:** 2026-09-29  
> **Status:** Active  

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser)                         │
│                                                                 │
│   Next.js 16 App Router  ·  React 19  ·  TypeScript             │
│   CSS Modules + CSS Variables  ·  Lucide Icons                  │
│                                                                 │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│   │ Landing  │  │   Auth   │  │   App    │  │  Public  │       │
│   │  Pages   │  │  Pages   │  │  Pages   │  │  Pages   │       │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│        │              │             │              │             │
│        └──────────────┴─────────────┴──────────────┘             │
│                          │                                       │
│                   /api/* rewrite                                 │
└──────────────────────────┼──────────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────┼──────────────────────────────────────┐
│                    BACKEND (FastAPI)                             │
│                                                                 │
│   Python 3.12+  ·  Pydantic  ·  SQLAlchemy  ·  Alembic          │
│                                                                 │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│   │   Auth   │  │   RAG    │  │ Ingestion│  │ Documents│       │
│   │ Service  │  │ Pipeline │  │ Pipeline │  │ Service  │       │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│                          │                                       │
└──────────────────────────┼──────────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────────┐
│                     DATA LAYER                                   │
│                                                                 │
│   PostgreSQL 16 + pgvector  ·  Local File Storage               │
│   Docker Container: aurora-postgres                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Tech Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Frontend Framework** | Next.js (App Router) | 16.3.0 | Server/client rendering, routing, API rewrites |
| **UI Library** | React | 19.2.8 | Component architecture |
| **Language** | TypeScript | 5.9.3 | Type safety |
| **Styling** | CSS Modules + CSS Variables | — | Scoped styles, design tokens, no utility frameworks |
| **Icons** | Lucide React | 1.31.0 | Consistent icon system |
| **Package Manager** | pnpm | 11.19.0 | Fast, disk-efficient package management |
| **Backend Framework** | FastAPI | 0.115.8 | High-performance Python API |
| **ORM** | SQLAlchemy | 2.0.38 | Database abstraction |
| **Migrations** | Alembic | 1.14.1 | Schema migrations |
| **Database** | PostgreSQL + pgvector | 16 | Relational + vector storage |
| **AI Provider** | Gemini | — | Embeddings + generation |
| **Auth** | Server-side sessions | — | HttpOnly cookie, argon2 password hashing |
| **OCR** | Tesseract | 5.x | Scanned PDF text extraction |
| **Containerization** | Docker Compose | — | PostgreSQL container |

---

## 3. Frontend Folder Structure (Redesigned)

```
frontend/
├── app/                          # Next.js App Router
│   ├── (marketing)/              # Route group: public pages (no app shell)
│   │   ├── layout.tsx            # Marketing layout (navbar + footer)
│   │   ├── page.tsx              # Landing / Home page
│   │   ├── about/
│   │   │   └── page.tsx          # About page
│   │   └── contact/
│   │       └── page.tsx          # Contact page
│   │
│   ├── (auth)/                   # Route group: authentication
│   │   ├── layout.tsx            # Auth layout (centered card)
│   │   ├── login/
│   │   │   └── page.tsx          # Login page
│   │   └── register/
│   │       └── page.tsx          # Registration page
│   │
│   ├── (app)/                    # Route group: authenticated app
│   │   ├── layout.tsx            # App shell (sidebar + header)
│   │   ├── dashboard/
│   │   │   └── page.tsx          # Dashboard page
│   │   ├── workspaces/
│   │   │   ├── page.tsx          # Workspaces list
│   │   │   └── [workspaceId]/
│   │   │       ├── page.tsx      # Workspace detail
│   │   │       ├── documents/
│   │   │       │   └── page.tsx  # Document library
│   │   │       └── chat/
│   │   │           ├── page.tsx  # New conversation
│   │   │           └── [conversationId]/
│   │   │               └── page.tsx  # Conversation view
│   │   └── settings/
│   │       └── page.tsx          # Settings / Profile
│   │
│   ├── globals.css               # Design system tokens + base styles
│   ├── layout.tsx                # Root layout (html, body, fonts, theme)
│   └── not-found.tsx             # Custom 404 page
│
├── components/                   # Reusable UI components
│   ├── ui/                       # Atomic design primitives
│   │   ├── button.tsx
│   │   ├── button.module.css
│   │   ├── input.tsx
│   │   ├── input.module.css
│   │   ├── card.tsx
│   │   ├── card.module.css
│   │   ├── badge.tsx
│   │   ├── modal.tsx
│   │   ├── modal.module.css
│   │   ├── skeleton.tsx
│   │   ├── dropdown.tsx
│   │   ├── tabs.tsx
│   │   ├── toast.tsx
│   │   └── tooltip.tsx
│   │
│   ├── layout/                   # Layout components
│   │   ├── navbar.tsx            # Public navigation bar
│   │   ├── navbar.module.css
│   │   ├── footer.tsx            # Public footer
│   │   ├── footer.module.css
│   │   ├── sidebar.tsx           # App sidebar navigation
│   │   ├── sidebar.module.css
│   │   ├── app-header.tsx        # App top bar
│   │   └── app-header.module.css
│   │
│   ├── features/                 # Feature-specific components
│   │   ├── auth/
│   │   │   ├── login-form.tsx
│   │   │   ├── register-form.tsx
│   │   │   └── auth-screen.module.css
│   │   ├── dashboard/
│   │   │   ├── stats-card.tsx
│   │   │   ├── recent-activity.tsx
│   │   │   └── quick-actions.tsx
│   │   ├── workspace/
│   │   │   ├── workspace-card.tsx
│   │   │   ├── workspace-grid.tsx
│   │   │   └── create-workspace-modal.tsx
│   │   ├── documents/
│   │   │   ├── document-uploader.tsx
│   │   │   ├── document-list.tsx
│   │   │   ├── document-preview.tsx
│   │   │   └── processing-status.tsx
│   │   ├── chat/
│   │   │   ├── chat-interface.tsx
│   │   │   ├── message-bubble.tsx
│   │   │   ├── citation-card.tsx
│   │   │   ├── conversation-sidebar.tsx
│   │   │   └── streaming-indicator.tsx
│   │   └── landing/
│   │       ├── hero-section.tsx
│   │       ├── feature-cards.tsx
│   │       ├── how-it-works.tsx
│   │       ├── testimonials.tsx
│   │       └── cta-section.tsx
│   │
│   └── shared/                   # Cross-cutting components
│       ├── brand.tsx             # AURORA logo + wordmark
│       ├── theme-toggle.tsx      # Dark/light switch
│       ├── empty-state.tsx       # Empty state illustrations
│       ├── error-boundary.tsx    # Error handling
│       └── loading-spinner.tsx   # Global loading states
│
├── hooks/                        # Custom React hooks
│   ├── use-auth.ts               # Authentication state
│   ├── use-workspaces.ts         # Workspace data fetching
│   ├── use-documents.ts          # Document operations
│   ├── use-chat.ts               # Chat/streaming operations
│   ├── use-theme.ts              # Theme management
│   └── use-media-query.ts        # Responsive breakpoints
│
├── lib/                          # Utilities and services
│   ├── api.ts                    # API client (fetch wrapper)
│   ├── api-errors.ts             # Error classification
│   ├── types.ts                  # Shared TypeScript types
│   ├── constants.ts              # App-wide constants
│   ├── sse.ts                    # Server-Sent Events parser
│   ├── streaming-state.ts        # Streaming state machine
│   ├── document-workspace.ts     # Document workspace logic
│   ├── oauth-errors.ts           # OAuth error handling
│   └── utils.ts                  # General utility functions
│
├── styles/                       # Additional style modules
│   ├── animations.css            # Keyframe animations library
│   └── typography.css            # Typography scale and classes
│
├── public/                       # Static assets
│   ├── images/                   # Generated/sourced images
│   ├── fonts/                    # Self-hosted fonts (if needed)
│   └── favicon.ico
│
├── tests/                        # Frontend test files
│   ├── api-errors.test.mjs
│   ├── document-workspace.test.mjs
│   ├── oauth-errors.test.mjs
│   ├── sse-parser.test.mjs
│   └── streaming-state.test.mjs
│
├── .env.example
├── eslint.config.mjs
├── next.config.ts
├── package.json
├── pnpm-lock.yaml
├── pnpm-workspace.yaml
├── tsconfig.json
└── next-env.d.ts
```

---

## 4. Backend Folder Structure (Existing — No Changes)

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                   # FastAPI app factory
│   ├── api/
│   │   ├── deps.py               # Dependency injection (auth, DB)
│   │   └── v1/
│   │       ├── router.py         # API router aggregator
│   │       ├── auth.py           # Login, register, session, Google OAuth
│   │       ├── conversations.py  # Chat/conversation CRUD + streaming
│   │       ├── documents.py      # Upload, process, index documents
│   │       ├── health.py         # Health check endpoint
│   │       ├── rag.py            # RAG query + response retrieval
│   │       ├── retrieval.py      # Semantic search endpoint
│   │       └── workspaces.py     # Workspace CRUD + membership
│   ├── auth/                     # Google OAuth integration
│   ├── core/
│   │   ├── config.py             # Pydantic settings (all env vars)
│   │   ├── logging.py            # Structured logging setup
│   │   └── security.py           # Password hashing, session tokens
│   ├── db/                       # Database engine + session factory
│   ├── embeddings/               # Embedding provider abstraction
│   ├── evaluation/               # Multilingual RAG evaluation
│   ├── ingestion/                # Multi-format document ingestion
│   ├── llm/                      # LLM provider abstraction (Gemini)
│   ├── models/                   # SQLAlchemy ORM models (14 tables)
│   ├── ocr/                      # Tesseract OCR abstraction
│   ├── processing/               # Document text/PDF processing
│   ├── rag/                      # Chunking, context building, prompts
│   ├── schemas/                  # Pydantic request/response schemas
│   ├── services/                 # Business logic layer
│   └── storage/                  # File storage abstraction (local)
├── alembic/                      # Database migration scripts
├── alembic.ini
├── requirements.txt
└── tests/                        # pytest test suite (21 test files)
```

---

## 5. Data Flow

### 5.1 Authentication Flow
```
Browser → POST /api/v1/auth/login → FastAPI validates credentials
       → Creates session in PostgreSQL → Sets HttpOnly cookie
       → All subsequent requests include cookie automatically
       → Same-origin /api rewrite keeps cookies first-party
```

### 5.2 Document Processing Flow
```
Upload → Validate (type, size, MIME) → Store binary (local FS)
      → Detect format → Select adapter (PDF/DOCX/XLSX/PPTX/TXT/CSV)
      → Extract content units → OCR scanned pages (PDF only)
      → Create canonical units with provenance metadata
```

### 5.3 RAG Query Flow
```
User Question → Embed query (Gemini) → Vector search (pgvector, cosine)
             → Retrieve top-K chunks → Apply relevance threshold
             → Build bounded context → Generate answer (Gemini)
             → Persist response + citations → Stream via SSE
```

### 5.4 Frontend Routing Flow
```
/ (root)
├── / ─────────────────── Landing page (marketing)
├── /about ────────────── About page (marketing)
├── /contact ──────────── Contact page (marketing)
├── /login ────────────── Login page (auth)
├── /register ─────────── Register page (auth)
├── /dashboard ────────── Dashboard (app, protected)
├── /workspaces ────────── Workspace list (app, protected)
├── /workspaces/[id] ──── Workspace detail (app, protected)
├── /workspaces/[id]/documents ── Document library (app, protected)
├── /workspaces/[id]/chat ─────── New conversation (app, protected)
├── /workspaces/[id]/chat/[cid] ─ Chat view (app, protected)
└── /settings ─────────── Settings (app, protected)
```

---

## 6. API Endpoints (Existing)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/v1/auth/register` | Create account |
| `POST` | `/api/v1/auth/login` | Sign in |
| `POST` | `/api/v1/auth/logout` | Sign out |
| `GET` | `/api/v1/auth/me` | Current user |
| `GET` | `/api/v1/auth/google/login` | Google OAuth redirect |
| `GET` | `/api/v1/auth/google/callback` | Google OAuth callback |
| `POST` | `/api/v1/workspaces` | Create workspace |
| `GET` | `/api/v1/workspaces` | List workspaces |
| `GET` | `/api/v1/workspaces/{id}` | Get workspace |
| `DELETE` | `/api/v1/workspaces/{id}` | Delete workspace |
| `POST` | `/api/v1/workspaces/{id}/documents` | Upload document |
| `GET` | `/api/v1/workspaces/{id}/documents` | List documents |
| `DELETE` | `/api/v1/workspaces/{id}/documents/{did}` | Delete document |
| `POST` | `/api/v1/workspaces/{id}/documents/{did}/process` | Process document |
| `POST` | `/api/v1/workspaces/{id}/documents/{did}/index` | Index document |
| `POST` | `/api/v1/workspaces/{id}/search` | Semantic search |
| `POST` | `/api/v1/workspaces/{id}/rag` | RAG query |
| `GET` | `/api/v1/workspaces/{id}/rag/responses/{rid}` | Get RAG response |
| `POST` | `/api/v1/workspaces/{id}/conversations` | Create conversation |
| `GET` | `/api/v1/workspaces/{id}/conversations` | List conversations |
| `GET` | `/api/v1/workspaces/{id}/conversations/{cid}` | Get conversation |
| `PATCH` | `/api/v1/workspaces/{id}/conversations/{cid}` | Rename conversation |
| `DELETE` | `/api/v1/workspaces/{id}/conversations/{cid}` | Delete conversation |
| `POST` | `.../conversations/{cid}/messages` | Send message (sync) |
| `POST` | `.../conversations/{cid}/messages/stream` | Send message (SSE) |
| `GET` | `/api/v1/health` | Health check |

---

## 7. Key Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **Next.js App Router** | Server components for SEO on public pages, client components for interactivity |
| **CSS Modules (no Tailwind)** | Maximum design control, scoped styles, design tokens via CSS variables |
| **Route Groups** | `(marketing)`, `(auth)`, `(app)` for different layouts without URL impact |
| **No state management library** | React 19 hooks + context sufficient for this scale |
| **Same-origin /api rewrite** | Cookies remain first-party, no CORS complexity |
| **Feature-based components** | Scalable organization, each feature is self-contained |
| **pnpm** | Already configured, faster than npm, strict dependency management |

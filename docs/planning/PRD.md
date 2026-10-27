# AURORA — Product Requirements Document (PRD)

> **Version:** 1.0  
> **Last Updated:** 2026-09-29  
> **Status:** Active  

---

## 1. Product Vision

**AURORA** is a multilingual, AI-powered research workspace that transforms how students, researchers, and knowledge workers interact with documents. Upload any document, ask questions in any language, and receive citation-backed, evidence-grounded answers — all within a beautifully designed, friendly, and approachable interface.

The platform combines **Retrieval-Augmented Generation (RAG)** with a modern multi-page website experience that feels inviting, playful, and premium.

---

## 2. Problem Statement

Researchers and students spend excessive time manually reading, cross-referencing, and extracting insights from large document collections. Existing tools are either:
- **Too technical** — requiring programming knowledge (LangChain, LlamaIndex)
- **Too basic** — simple chatbots that hallucinate without evidence
- **Ugly and utilitarian** — functional but uninspiring interfaces

AURORA solves this by providing a **beautiful, approachable interface** on top of a robust evidence-grounded RAG pipeline with full citation support.

---

## 3. Target Users

| Persona | Description | Pain Points |
|---------|-------------|-------------|
| 🎓 **College Students** | Uploading lecture notes, PDFs, research papers | Need quick, reliable answers for studying |
| 🔬 **Researchers** | Managing multi-document research workflows | Need citation-backed evidence across documents |
| 📝 **Knowledge Workers** | Processing reports, manuals, internal docs | Need multilingual support and organized workspaces |
| 👨‍🏫 **Educators** | Creating materials from multiple sources | Need document organization and searchability |

---

## 4. Core Features

### 4.1 Public Pages (Unauthenticated)

| Page | Purpose | Key Elements |
|------|---------|--------------|
| **Landing / Home** | First impression, product showcase | Hero section, feature cards, animated demos, testimonials, CTA |
| **About** | Team story, mission, technology overview | Team bios, tech stack visualization, project timeline |
| **Contact** | Support, feedback, inquiries | Contact form, social links, FAQ accordion |

### 4.2 Authentication Pages

| Page | Purpose | Key Elements |
|------|---------|--------------|
| **Login** | Email/password + Google OAuth sign-in | Animated illustration, form, social login button |
| **Register** | New account creation | Step indicator, password strength, terms acceptance |

### 4.3 Protected App Pages (Authenticated)

| Page | Purpose | Key Elements |
|------|---------|--------------|
| **Dashboard** | Overview hub after login | Stats cards, recent workspaces, recent activity feed, quick actions |
| **Workspaces List** | Browse/create/manage workspaces | Grid/list toggle, search, workspace cards with previews |
| **Workspace Detail** | Single workspace view | Tabbed interface: Documents, Chat, Search, Settings |
| **Document Library** | Upload, manage, preview documents | Drag-and-drop upload, file browser, processing status, preview panel |
| **Research Chat** | Conversational RAG interface | Chat bubbles, streaming responses, inline citations, conversation sidebar |
| **Settings / Profile** | Account and app preferences | Profile editing, theme toggle, notification preferences, account management |

### 4.4 Existing Backend Features (Already Built)

These backend capabilities are already operational and will be exposed through the new frontend:

- ✅ User authentication (email/password + Google OAuth)
- ✅ Workspace creation and RBAC authorization
- ✅ Multi-format document upload (PDF, DOCX, XLSX, PPTX, TXT, MD, CSV, TSV)
- ✅ Document processing with OCR support (Tesseract for scanned pages)
- ✅ RAG pipeline: chunking → embeddings → vector search → grounded generation
- ✅ Citation and evidence persistence
- ✅ Persistent conversations with streaming SSE
- ✅ Multilingual support (English + Hindi)
- ✅ Dark/light theme support

---

## 5. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| **Performance** | First Contentful Paint < 1.5s, Time to Interactive < 3s |
| **Accessibility** | WCAG 2.1 AA compliance, keyboard navigation, screen reader support |
| **Responsiveness** | Full support for mobile (360px), tablet (768px), desktop (1280px+) |
| **Browser Support** | Chrome 120+, Firefox 120+, Safari 17+, Edge 120+ |
| **SEO** | Proper meta tags, Open Graph, semantic HTML on all public pages |
| **Animation** | 60fps animations, respect `prefers-reduced-motion` |
| **Security** | No secrets in frontend, HttpOnly cookies, CSRF protection via same-origin |

---

## 6. Success Metrics

| Metric | Target |
|--------|--------|
| **Design Quality** | Visually stunning first impression — users say "wow" |
| **Page Count** | 9+ distinct pages with unique layouts |
| **Interactivity** | Every page has micro-animations and hover effects |
| **Lighthouse Score** | Performance > 90, Accessibility > 95, SEO > 95 |
| **Mobile Experience** | Fully functional on all screen sizes |

---

## 7. Out of Scope (v1)

- Real-time collaboration / multi-user editing
- Payment / subscription system
- Mobile native app
- Admin panel / user management dashboard
- Email notifications
- File sharing between users
- Advanced analytics dashboard

---

## 8. Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| PostgreSQL + pgvector | ✅ Running | Docker container `aurora-postgres` |
| FastAPI Backend | ✅ Running | All v1.0–v1.3 APIs operational |
| Gemini API | ✅ Configured | Embeddings + generation |
| Google OAuth | ✅ Configured | Optional social login |
| Tesseract OCR | ✅ Installed | PDF OCR support |

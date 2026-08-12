# AURORA Project Audit

**Audit date:** 13 August 2026  
**Project:** AURORA: Multilingual RAG Platform  
**Repository:** `D:\Jarvis\projects\AURORA`

## Executive conclusion

AURORA has a coherent, technically defensible architecture and a verified academic foundation, but it is still at the **repository/environment foundation stage**. No application code, database, authentication, document processing, RAG pipeline, frontend, or tests exist yet.

The correct next implementation milestone is a small **Backend Foundation v0.1**, but only after explicitly confirming the remaining architecture and scope decisions listed in section J.

### Sources reviewed

Project records:

- [AURORA master context](../data/AURORA_MASTER_CONTEXT.md)
- [Verified project baseline](../data/AURORA_Project_Baseline_and_Requirements.txt)
- [Requirements and scope specification](../data/AURORA_Project_Requirements_and_Scope_Specification.txt)
- [System architecture specification](../data/AURORA_System_Architecture_Specification_v1.0.txt)
- [Learning and development roadmap](../data/AURORA_Learning_and_Development_Roadmap_v1.0.txt)
- [Resource and learning map](../data/AURORA_Resource_and_Learning_Map_v1.0.txt)
- [Implementation progress record](../data/AURORA_Implementation_Progress_Record.txt)

Official academic and SDMS sources:

- [V Semester Capstone Project Topics](<../data/20.V sem capstone Project.pdf>)
- [Academic Scheme for the 2024 Batch](<../data/8_AScheme 2024 Batch  1-8 sem.pdf>)
- [Third Year Academic Calendar 2026-27](<../data/5  Third Year Academic Calendar 2026-27_F 1.pdf>)
- [V Semester Lab Syllabus](<../data/8_B.V sem LAB Syllabus.pdf>)
- [V Semester MAC Syllabus](<../data/8.V sem Syllabus MAC.pdf>)
- [Project Registration SDMS Notice](<../data/Project Registration SDMS notice.pdf>)
- [Tentative V Semester timetable screenshot](<../data/Screenshot 2026-08-09 114847.png>)

## A. Project understanding

### What AURORA is

AURORA is a secure, multilingual, document-grounded research and knowledge-discovery web platform built around Retrieval-Augmented Generation.

It is deliberately broader than “chat with a PDF,” but the first version remains a controlled, single-developer academic product rather than an enterprise multi-tenant SaaS platform.

### Purpose

AURORA should let users:

- Organize authorized documents.
- Retrieve semantically relevant evidence.
- Ask questions in supported languages.
- Receive answers grounded in retrieved evidence.
- Trace answers back to real document locations.
- Demonstrate meaningful cross-language retrieval.

The university-approved foundation is Topic 16: **“Design and Development of Multilingual RAG Chatbot.”**

### Target users

The requirements formally define:

- Authenticated individual users performing document-grounded research.
- Optional administrators with limited protected capabilities.
- Workspace owners and members where collaborative workspaces are implemented.

Specific personas such as students, teachers, or professional researchers are reasonable product audiences, but they are not formally established as exclusive target users.

### Core workflow

```text
Authenticate
→ Select workspace
→ Upload validated document
→ Store and process file
→ Extract and clean text
→ Preserve page/section metadata
→ Chunk text
→ Generate embeddings
→ Store vectors
→ Retrieve only authorized chunks
→ Construct grounded context
→ Generate answer in selected language
→ Validate citation IDs
→ Display answer and original-source citations
```

## B. Requirements

### MUST HAVE

- Secure authentication and logout.
- Dashboard.
- Minimal workspace/ownership boundary.
- Backend-enforced authorization and data isolation.
- Controlled document-format support.
- File type, size, and malformed-input validation.
- Safe storage and processing lifecycle.
- Extraction, cleaning, metadata preservation, and chunking.
- Embedding generation.
- PostgreSQL persistence and pgvector retrieval.
- Authorization-aware retrieval.
- Deterministic two-step RAG.
- Insufficient-evidence behavior.
- Grounded answers.
- Traceable source citations.
- English/Hindi or another explicitly tested multilingual combination.
- At least one real cross-language retrieval scenario.
- Structured errors and safe logging.
- Core success, failure, and authorization tests.
- Reproducible local setup and technical documentation.
- Submission, oral, and demonstration readiness.

### SHOULD HAVE

- Full workspace membership management UI.
- Conversation history and bounded conversational context.
- Cross-document retrieval and analysis.
- Minimal admin functions.
- Stronger document management and deletion.
- Streaming responses.
- Metadata filtering and measured retrieval improvements.
- Usage and latency analytics.
- Repeatable RAG evaluation and an evaluation report/dashboard.
- Provider and storage abstractions.
- Responsive UI, accessibility, dark/light mode, and polished states.

### NICE TO HAVE

- Hybrid retrieval.
- Query rewriting.
- Reranking.
- Citation/evidence verification.
- Agentic RAG or LangGraph.
- Research-gap detection.
- Provider-switching UI.
- AI cost dashboard.
- Full audit-log subsystem.
- GraphRAG.

None should begin until the complete core workflow passes its tests.

## C. Intended architecture

| Area | Intended design |
|---|---|
| Frontend | Next.js App Router, TypeScript, Tailwind CSS and selected shadcn/ui components. It renders state and calls the backend; it never authorizes resources. |
| Backend | One FastAPI modular monolith with thin route handlers, application services, domain rules, repositories, and infrastructure adapters. |
| Database | PostgreSQL as the system of record with pgvector for chunk embeddings and similarity search. |
| Authentication | Opaque high-entropy server-side sessions, hashed session tokens, secure HttpOnly cookies, expiration and logout invalidation. |
| Authorization | System roles `USER/ADMIN` and workspace roles `OWNER/MEMBER`; every protected resource is checked server-side. |
| Document pipeline | Upload → validate → store → extract → clean → enrich metadata → chunk → embed → vector insert → ready/failed. |
| RAG pipeline | Authenticate → authorize → embed query → filtered retrieval → context construction → grounded generation → citation validation. |
| AI layer | One Gemini adapter initially, with separate interfaces for generation and embeddings. Exact models remain configurable. |
| Citations | Persistent relationship from assistant message → citation → chunk → document, including page/section information. Model-generated IDs must be validated against retrieved evidence. |
| Evaluation | Controlled English, Hindi, cross-language, and unanswerable cases measuring retrieval relevance, grounding, answer relevance, citation accuracy, and latency. |
| Storage | Local filesystem adapter during development; object storage only when public deployment requires it. |
| Background work | Simple in-process processing initially, with the limitation that it is not durable across restarts. |
| Deployment | Local-first. Optional Vercel/Render/Neon/R2 demonstration topology only after the core is stable. |

The strongest architectural rule is:

> Authorization and workspace filtering occur before retrieved content reaches the LLM.

## D. Current implementation state

### Git

- Repository: `D:\Jarvis\projects\AURORA`
- Branch: `main`
- Remote: `https://github.com/Code99701/AURORA.git`
- Local branch tracks `origin/main`.
- Working tree was clean at the time of the audit.
- Cached local remote-tracking state pointed to the same commit as `main`.
- No live remote fetch was required for the audit.

Commits:

1. `246212c chore: initialize AURORA project`
2. `76cc578 chore: configure Python environment ignore`

Only these files were tracked before this audit document was created:

- `.env.example`
- `.gitignore`
- `README.md`

Therefore, GitHub contained three project files rather than the empty directory structure. Git cannot track empty directories.

### Local filesystem

Locally present:

- `backend/`
  - `aurora-env/`
- `frontend/` — empty
- `docs/`
  - `architecture/` — empty
  - `api/` — empty
  - `database/` — empty
  - `security/` — empty
  - `rag/` — empty
  - `testing/` — empty
  - `decisions/` — empty
- `learning/`
  - `exercises/` — empty
  - `notes/` — empty
  - `viva/` — empty
- `scripts/` — empty
- `tests/` — empty
- `data/` — 14 source artifacts, ignored by Git

### Environment and tools

Verified:

- AURORA Python: `3.13.7`
- Interpreter: `D:\Jarvis\projects\AURORA\backend\aurora-env\Scripts\python.exe`
- Virtual environment is isolated from system packages.
- Installed inside the environment: only `pip 25.2`.
- Git: `2.53.0.windows.2`
- Node.js: `24.17.0`
- VS Code: `1.123.0`
- Docker CLI: `29.6.1`
- PostgreSQL/`psql`: not found on PATH.
- No database container or Compose configuration exists.
- No project dependency manifest exists.
- No frontend package manifest exists.

The normal `npm` wrapper could not be fully verified inside the audit sandbox because it redirected to a user-level npm prefix that was not readable there. The directly installed npm CLI reported `11.13.0`, rather than the progress record’s `11.7.0`. Package-manager health should be rechecked before frontend scaffolding.

### Configured correctly

- `backend/aurora-env/` is ignored.
- `.env` variants are ignored while `.env.example` remains tracked.
- API/database/session placeholders exist.
- Runtime uploads, storage, local databases, caches, and secrets are ignored.
- No secret was found in tracked files.

### Quality issues in existing files

The README is not correctly rendered Markdown:

- Heading, list, and bold markers are escaped.
- It contains excessive blank lines.
- Its final code fence is not closed.

It is therefore not accurately “complete,” despite the progress record saying it is.

### Missing implementation

There is currently no:

- FastAPI application.
- Dependency declaration or lock strategy.
- Health endpoint.
- Configuration/settings code.
- API route.
- Database connection or migration.
- Authentication or session system.
- Workspace or RBAC model.
- Document parser.
- Upload endpoint.
- Chunker.
- Embedding adapter.
- pgvector table or retriever.
- RAG or citation code.
- Frontend.
- Automated test.
- CI/CD configuration.
- Deployment configuration.

## E. Document conflicts and discrepancies

| Conflict | Audit finding |
|---|---|
| Architecture approval status | The architecture begins as “draft for approval/in progress” and ends with an approval gate, although its ADRs say accepted and the progress record calls architecture complete. It needs explicit formal approval before implementation. |
| Workspace/RBAC priority | Requirements call workspaces and minimal RBAC SHOULD HAVE, but separately make workspace isolation mandatory. Architecture makes a minimal workspace boundary mandatory. Recommended interpretation: the security boundary is MUST HAVE; collaboration/admin UI is SHOULD HAVE. This still needs approval. |
| Timetable authority | The only timetable artifact is a polished derivative screenshot labelled “Tentative Timetable,” not the original official notice/PDF. It indicates Tuesday 10:00–12:00 and 75% attendance, but the baseline overstates these as fully verified official facts. Add the original notice before treating them as authoritative. |
| Mentor status | The progress record says “Faculty Guide entered: Minakshi Poonia.” Earlier documents say mentor assignment is open. Entering a name is not evidence of SDMS mentor approval. Current approved mentor status remains unverified. |
| Repository structure | The progress record says the structure is complete, but Git contains no directories because they are empty. The structure exists locally only. |
| README status | Progress calls it complete; the actual file is malformed Markdown with an unclosed fence. |
| Tool versions | Progress records npm `11.7.0`; the current direct installation reports `11.13.0`. |
| Progress record paths | Several paths were damaged to forms such as `D:` and `D:-env.exe`. The actual filesystem must be used instead. |
| Development calendar | The resource plan places “full frontend integration” after the 2–4 November Expo. The calendar describes the Expo as project evaluation/demonstration, so a usable demonstration should exist before it. |
| Testing order | Some roadmap sequences place testing/security hardening very late, while the requirements make security and core tests mandatory. Tests and security need to be built continuously. |
| `data/` meaning | `data/` currently contains irreplaceable project source material, while the architecture also suggests `data/uploads`. Runtime uploads should instead use the already ignored `storage/` boundary to avoid mixing source documents with user content. |
| University full-stack syllabus vs project stack | The lab syllabus teaches React/Vite, Express, MongoDB/MySQL and JWT. AURORA uses Next.js, FastAPI, PostgreSQL and server sessions. This is not a genuine academic conflict: the syllabus teaches concepts and experiments; it does not mandate the Cornerstone implementation stack. |

## F. Technology review

| Technology | Decision | Timing and concern |
|---|---|---|
| Python 3.13.7 | Use | Suitable now. Current FastAPI, SQLAlchemy and Google Gen AI packages support Python 3.13. |
| FastAPI + Pydantic | Use now | Correct first backend stack. Keep routes thin and use current Pydantic v2 patterns. |
| SQLAlchemy + Alembic | Use shortly | Introduce after the API/configuration skeleton, when persistent entities begin. Avoid legacy SQLAlchemy query tutorials. |
| PostgreSQL 18 + pgvector | Use | Strong fit for relational ownership plus vectors. PostgreSQL 18 is current while 19 remains beta; pgvector supports PostgreSQL 13+. |
| Docker | Postpone to database phase | Docker is installed and is preferable to native Windows pgvector compilation. It is unnecessary for the first health endpoint. |
| Next.js + TypeScript | Use later | Node 24 is LTS and exceeds Next.js’s minimum Node 20.9 requirement. Verify the user-level package manager before scaffolding. |
| Tailwind + shadcn/ui | Use during frontend phase | Current Tailwind v4 and shadcn tooling are compatible. Avoid old Tailwind v3/shadcn commands. |
| Motion, Lucide, Recharts | Postpone | They provide polish, icons, and charts rather than core functionality. The current Motion package is `motion`, imported from `motion/react`. |
| Server-side sessions + Argon2id | Use in security phase | Better fit than JWT for simple revocation/logout. Deployment topology must determine SameSite, Secure-cookie, CORS, and CSRF behavior. |
| Direct two-step RAG | Use | Best learning and viva choice. Do not add LangChain, LlamaIndex, or LangGraph until direct retrieval and evaluation expose a real problem. |
| Gemini generation | Use behind one adapter; model open | `gemini-3.1-flash-lite` exists, but current pricing identifies `gemini-3.5-flash-lite` as the most cost-efficient GA model. Freeze nothing until AURORA evaluates quality, latency, quotas, and cost. |
| Gemini embeddings | Evaluate before freezing | Both `gemini-embedding-001` and `gemini-embedding-2` are stable, but their vector spaces are incompatible; switching requires re-embedding all data. Test both on a small bilingual set first. |
| Embedding dimensions | Decide before schema/index freeze | pgvector HNSW indexes on `vector` support up to 2,000 dimensions, while Gemini defaults can be 3,072. Prefer a tested 768- or 1,536-dimensional configuration if later HNSW is desired, or consciously use another pgvector type. |
| Local file storage | Use now | Store runtime content under a dedicated `storage/` tree, not the existing project-source `data/` folder. |
| R2/Neon/Render/Vercel | Postpone | Free tiers remain candidates, not dependencies. Render is ephemeral and sleeps when idle; Vercel Hobby is personal/non-commercial. |

Current official references used for compatibility and pricing verification:

- [FastAPI package metadata](https://pypi.org/project/fastapi/)
- [SQLAlchemy package metadata](https://pypi.org/project/SQLAlchemy/)
- [Google Gen AI Python SDK](https://pypi.org/project/google-genai/)
- [Next.js installation requirements](https://nextjs.org/docs/app/getting-started/installation)
- [Node.js release status](https://nodejs.org/en/about/previous-releases)
- [PostgreSQL 18 documentation](https://www.postgresql.org/docs/18/index.html)
- [pgvector documentation](https://github.com/pgvector/pgvector)
- [Gemini embeddings](https://ai.google.dev/gemini-api/docs/embeddings)
- [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Motion installation](https://motion.dev/docs/react-installation)
- [shadcn/ui Next.js setup](https://ui.shadcn.com/docs/installation/next)
- [Render free-tier limitations](https://render.com/docs/free)
- [Vercel Hobby plan](https://vercel.com/docs/plans/hobby)
- [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- [Neon pricing](https://neon.com/pricing)

One privacy concern deserves emphasis: Gemini’s free tier indicates submitted content may be used to improve Google products. Use non-sensitive demonstration documents unless the selected service tier and data terms are acceptable.

## G. Single next development milestone

### Backend Foundation v0.1

The next implementation milestone should be:

```text
Reproducible FastAPI application
→ typed configuration
→ /api/v1/health endpoint
→ structured errors
→ initial security/CORS configuration boundary
→ automated API tests
→ documented run command
```

Exit criteria:

- Runs using `backend/aurora-env`.
- Uses one agreed dependency manifest and version strategy.
- Starts without secrets.
- Health endpoint returns a typed response.
- Invalid routes and errors do not expose internals.
- Tests pass through the same application entry point.
- README explains setup and execution.
- No database, authentication, AI provider, or frontend is added prematurely.
- The developer can explain request → route → validation → response → test.

## H. Phased development plan

### Phase 0 — Approval and repository hygiene

- Resolve the decisions in section J.
- Repair README.
- Decide the dependency manifest and naming conventions.
- Confirm package-manager health.
- Keep project documentation synchronized with Git.

### Phase 1 — Backend Foundation v0.1

- FastAPI, settings, health endpoint, errors, logging foundation, and pytest.
- Learn HTTP, request/response models, dependency injection, and OpenAPI.

### Phase 2 — Database and security foundation

- Dockerized PostgreSQL/pgvector.
- SQLAlchemy and Alembic.
- Users, sessions, workspaces, and membership.
- Argon2id, login/logout, protected endpoints, and negative authorization tests.

### Phase 3 — Document system

- Begin with PDF, TXT, and Markdown if approved.
- File allowlist, MIME/size validation, checksum, and safe storage.
- Extraction, cleaning, page/section metadata, chunking, and processing states.
- Valid, unsupported, malformed, and oversized-file tests.

### Phase 4 — Embedding and retrieval

- Small English/Hindi embedding experiment.
- Freeze provider, dimensions, and normalization behavior.
- Store chunk vectors.
- Implement exact similarity search with mandatory workspace filtering.
- Measure known-query retrieval before adding HNSW.

### Phase 5 — Basic RAG and citations

- Context builder and context limits.
- Grounding and insufficient-evidence policy.
- Generation adapter.
- Evidence IDs, citation validation, and persistent citation mapping.
- Provider-failure and invented-citation tests.

### Phase 6 — Meaningful multilingual RAG

- English query → Hindi evidence.
- Hindi query → English evidence.
- Selected answer language.
- Original-source citation preservation.
- Controlled bilingual evaluation cases.

### Phase 7 — Frontend integration

- Next.js login, dashboard, document states, upload, chat, and citations.
- Accessible loading, error, and empty states.
- No analytics, Motion, or elaborate admin interface until the workflow works.

### Phase 8 — Hardening and academic delivery

- End-to-end and authorization tests.
- Evaluation dataset and actual metrics.
- Demo rehearsal with a local/offline fallback plan.
- Documentation, screenshots, SDMS submissions, and viva preparation.

The existing 340–515 hour estimate cannot fit before the 2 November Expo at 12–16 hours per week. The pre-Expo scope must therefore be restricted to the minimum path through phases 1–7, with virtually all SHOULD HAVE and NICE TO HAVE features deferred.

## I. Risks

### Technical risks

- Extraction quality and page-level citation mapping.
- Poor multilingual retrieval despite successful API calls.
- Embedding-model migration forcing full re-indexing.
- 3,072-dimensional embeddings limiting later pgvector HNSW choices.
- In-process document jobs being lost on restart.
- Windows-native PostgreSQL/pgvector complexity.
- External API latency, rate limits, and model changes.

### Scope risks

- The nominal MUST-HAVE scope is already large for one beginner.
- “Research platform” language may encourage premature analytics, agents, or GraphRAG.
- Workspaces, RBAC, analytics, evaluation, and UI polish can become separate projects.
- The current full learning plan exceeds the available pre-Expo time.

### Beginner-learning risks

- Too many technologies being introduced at once.
- Copying outdated tutorials for Pydantic v1, SQLAlchemy 1.x, Create React App, Tailwind v3, or deprecated Gemini SDKs.
- Building large disconnected mini-projects rather than learning inside AURORA.
- Deferring understanding or tests until after implementation.

### Budget risks

- Free-tier limits and terms may change.
- Repeated embedding and generation calls can consume quota.
- Public deployment may require persistent storage and a database.
- Free services can cold-start or expire.
- Paid provider use must be capped and measured.

### Security risks

- Broken object-level authorization or cross-workspace retrieval.
- Malicious or resource-exhausting uploads.
- Prompt injection embedded inside documents.
- Sensitive documents being sent to a free AI tier.
- Cookie, CORS, or CSRF mistakes in split frontend/backend deployment.
- Secrets or document content entering logs.
- Treating frontend visibility as authorization.

### Academic and demonstration risks

- Original official timetable evidence is missing.
- Exact SDMS category, mentor approval, milestone dates, and rubric remain unresolved.
- The existing calendar schedules the product UI after the Expo.
- Cloud cold starts or campus-network failures could break a demo.
- The project sources and architecture are ignored by Git and therefore lack version history.
- Empty directories create the impression that GitHub contains more structure than it does.
- The README currently presents poorly on GitHub.

## J. Stop point and recommendation

Do **not** install packages or create implementation code until these decisions are approved:

1. Minimal workspace isolation is MUST HAVE; collaboration/admin UI remains SHOULD HAVE.
2. Initial languages are English and Hindi.
3. Initial formats are PDF, TXT, and Markdown; DOCX is postponed.
4. Direct two-step RAG, server-side sessions, PostgreSQL/pgvector, and local `storage/` remain approved.
5. Gemini generation and embedding model versions stay open until small measured experiments.
6. The next milestone is **Backend Foundation v0.1** with tests and documentation, not database, authentication, or frontend work.

Once those decisions are approved, implementation should begin with that one milestone only.

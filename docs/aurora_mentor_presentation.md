# AURORA Mentor Presentation
## Presentation-ready content for 15 slides

### Slide 1: Title

**AURORA**

**Multilingual Retrieval-Augmented Generation Chatbot**

V Semester Cornerstone Project | Topic 16

### Slide 2: Introduction

- AURORA is a secure research-assistance platform.
- Users upload documents into isolated workspaces.
- The system retrieves relevant evidence before generating an answer.
- Answers remain connected to source citations.

### Slide 3: Problem

- Important knowledge is distributed across many documents.
- Keyword-only lookup can miss semantically related content.
- Generic AI answers may be unsupported or difficult to verify.
- Users need multilingual interaction and source traceability.

### Slide 4: Proposed Solution

- AURORA combines document intelligence, vector retrieval, and Gemini.
- Documents are converted into one canonical representation.
- Questions retrieve authorized evidence from PostgreSQL + pgvector.
- Gemini generates a grounded answer from that evidence.
- The server persists citations for source inspection.

### Slide 5: Objectives

- Build a multilingual document-grounded assistant.
- Support secure workspace-based data isolation.
- Ingest multiple document formats through one pipeline.
- Retrieve semantically relevant evidence.
- Generate answers with durable source references.
- Provide a testable and understandable architecture.

### Slide 6: Scope

**Current scope**

- PDF, TXT, Markdown, CSV, TSV, DOCX, XLSX, PPTX.
- English/Hindi multilingual flow.
- Authentication, workspaces, documents, RAG, citations, conversations.
- Synchronous and SSE-streamed conversation responses.

**Outside current scope**

- Claim-level citation verification.
- Reranking, hybrid search, agents, and GraphRAG.
- Visual interpretation and legacy Office formats.
- Cloud storage and production deployment.

### Slide 7: System Design

```text
Next.js frontend
        |
FastAPI modular backend
        |
PostgreSQL + pgvector ---- private local file storage
        |
Gemini embeddings and generation
```

- Frontend: Next.js, React, TypeScript.
- Backend: FastAPI, Python, SQLAlchemy.
- Data: PostgreSQL, pgvector, Alembic.
- Security: server-side sessions and workspace authorization.

### Slide 8: Working / Data Flow

```text
User login
  -> authorized workspace
  -> upload and validate
  -> extract and canonicalize
  -> chunk and embed
  -> store vectors
  -> ask question
  -> retrieve authorized evidence
  -> construct context
  -> Gemini answer
  -> persist and display citations
```

### Slide 9: RAG Pipeline

1. Embed the user query with `RETRIEVAL_QUERY`.
2. Search indexed chunks with exact cosine distance.
3. Filter by workspace and indexed status.
4. Remove duplicates and diversify documents.
5. Apply relevance threshold and context budget.
6. Ask Gemini to answer only from evidence.
7. Persist the answer and ordered citations.

### Slide 10: Multilingual Capability

- Source text remains in its original language.
- Document and query embeddings share a semantic vector space.
- The application does not translate source documents.
- Users can select an answer language.
- The repository directly evaluates English and Hindi behavior.
- Broader language quality is future evaluation work.

### Slide 11: Technology Stack

- **Frontend:** Next.js 16, React 19, TypeScript.
- **Backend:** FastAPI and Python.
- **Database:** PostgreSQL with pgvector.
- **ORM/migrations:** SQLAlchemy and Alembic.
- **AI:** Gemini embeddings and generation adapters.
- **Parsing/OCR:** format adapters, python-docx, openpyxl, python-pptx, Tesseract for selected PDF OCR.
- **Transport:** JSON APIs and Server-Sent Events.

### Slide 12: Security and Reliability

- HttpOnly opaque database sessions.
- Optional Google OpenID Connect without storing Google tokens.
- OWNER/MEMBER workspace authorization.
- Workspace filters applied inside retrieval SQL.
- Private path-safe local storage.
- Bounded file, archive, extraction, and context limits.
- Transactional ingestion, indexing, citation persistence, and stream cleanup.
- Safe provider errors and controlled insufficient-evidence responses.

### Slide 13: Deliverables

- Working AURORA frontend and FastAPI backend.
- Multi-format canonical document ingestion.
- Chunking, embeddings, pgvector indexing, and semantic retrieval.
- Grounded Gemini RAG generation.
- Durable citations and evidence lookup.
- Persistent conversations and streamed responses.
- Automated backend and frontend verification suites.
- Milestone 2 system design and working explanation.

### Slide 14: Limitations and Future Scope

- Similarity threshold is a baseline, not calibrated confidence.
- Citations identify evidence chunks, not individual claims.
- Evaluation is limited in size and directly verified language coverage.
- No reranking, hybrid search, query rewriting, or GraphRAG.
- Visual-only content is not semantically interpreted.
- Future work: larger evaluation sets, claim verification, broader languages, cloud storage, approximate indexes, and scalable background processing.

### Slide 15: Conclusion

- AURORA connects uploaded documents to grounded multilingual answers.
- Canonical representation keeps multiple formats on one pipeline.
- Workspace authorization protects the evidence boundary.
- pgvector enables semantic retrieval from PostgreSQL.
- Citations make the generated result inspectable.
- The current implementation provides a clear foundation for future evaluation and scale.

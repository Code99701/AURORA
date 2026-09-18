# Document Processing Foundation v0.6

Document Processing v0.6 turns a securely stored PDF into deterministic, page-aware text that later milestones can chunk while preserving source provenance. It does not use an LLM and does not implement OCR, chunks, embeddings, retrieval, or RAG.

## Why extraction exists

The v0.5 document record identifies a private source file, but retrieval cannot operate directly on PDF binary data. Extraction creates a structured text boundary between storage and the future RAG data pipeline.

The implemented flow is:

```text
Document
   ↓
FileStorage
   ↓
pypdf PDF extractor
   ↓
Raw page text
   ↓
Deterministic cleaner
   ↓
ExtractedPage rows
   ↓
Future chunking
```

## PDF extraction

`pypdf` reads the binary stream returned by the existing `FileStorage` interface. The processing API never accepts a filesystem path or storage key. It first authenticates the session, authorizes workspace membership, and resolves the document using both its UUID and the authorized workspace UUID.

The extractor iterates the PDF’s page objects in source order. Every source page receives a one-based page number. A page with no extracted text is retained as an empty page when at least one other page contains usable text. This preserves true page numbering for future citations.

Corrupt, unreadable, and unsupported encrypted PDFs fail with the safe `PDF_EXTRACTION_ERROR` code. Provider paths, credentials, parser exceptions, and stack traces are not returned.

## Page-aware representation

`extracted_pages` contains:

- an internal primary key;
- the parent `document_id`;
- one-based `page_number`;
- cleaned page text;
- character count;
- creation and update timestamps.

The `(document_id, page_number)` pair is unique. Deleting a document cascades to its extracted pages. Workspace ownership is not duplicated: authorization is inherited through `ExtractedPage → Document → Workspace`.

This establishes the provenance chain:

```text
Workspace → Document → Page → Extracted text
```

Future chunks will point back to these pages so retrieval results and citations can identify the original source location.

## Deterministic text cleaning

Cleaning intentionally makes only conservative, repeatable changes:

- normalizes CRLF/CR line endings;
- removes obvious non-printing control characters;
- collapses repeated horizontal whitespace;
- joins line breaks within a paragraph using a single space;
- collapses repeated blank lines to one paragraph separator;
- trims surrounding whitespace.

Cleaning does not summarize, paraphrase, translate, classify, or otherwise reinterpret source content. Each page is cleaned independently, so page boundaries cannot be lost.

## Processing lifecycle

The synchronous v0.6 trigger uses the existing document lifecycle:

```text
UPLOADED (or previous terminal state)
   ↓
PROCESSING
   ├─ success → PROCESSED
   └─ failure → FAILED
```

`PROCESSED` is committed only after extracted page rows and document metadata are persisted successfully. Document detail responses expose:

- `status`;
- `page_count`;
- a safe `processing_error` code, when failed;
- `processed_at`, when successful.

They do not expose extracted text, storage internals, or raw exceptions.

## Idempotent reprocessing

The service deletes any previous extracted pages when a new processing attempt enters `PROCESSING`. A successful attempt writes exactly one replacement row for each source page. The uniqueness constraint prevents duplicate page numbers.

If the attempt later fails, the document is `FAILED` and no stale page set remains. This simple replacement strategy is suitable for the current controlled synchronous workload; no queue or distributed transaction is introduced.

## Failure handling

Safe terminal codes are:

- `STORAGE_READ_ERROR`: the stored object could not be opened;
- `PDF_EXTRACTION_ERROR`: the PDF was corrupt, unreadable, or unsupported;
- `NO_EXTRACTABLE_TEXT`: the document had no usable text;
- `EXTRACTED_CONTENT_PERSISTENCE_ERROR`: page rows could not be committed;
- `PROCESSING_STATE_ERROR`: processing could not enter its initial state.

An empty or image-only document is not treated as successfully processed. It becomes `FAILED` with `NO_EXTRACTABLE_TEXT`, and the response explains that OCR is unavailable. The system never fabricates extracted content.

## API trigger

An authorized workspace member starts synchronous processing with:

```http
POST /api/v1/workspaces/{workspace_id}/documents/{document_id}/process
```

The request body is empty. The client supplies neither a path nor extraction options. The response is the safe document metadata representation with the resulting status.

Synchronous processing is intentional for v0.6: it keeps status transitions observable and understandable without Redis, Celery, Kafka, or a worker system. A future deployment can add durable processing only if measured workload requires it.

## Security boundary

```text
authenticated identity
  → workspace membership
  → document filtered by workspace
  → FileStorage open
  → PDF extraction
```

Knowing a document UUID does not grant access. Cross-workspace and non-member processing receive the existing concealed 404 policy. Extracted text is untrusted user data; later RAG stages must treat it as source evidence, never as system instructions.

## Why OCR is deferred

OCR introduces large native dependencies, additional resource limits, language accuracy questions, and new security/testing surfaces. v0.6 supports text-based PDFs only. Scanned/image-only PDFs fail explicitly rather than producing misleading empty success.

## Why chunking is deferred

Chunk size, overlap, token accounting, provenance metadata, and embedding constraints deserve a separate tested boundary. v0.6 ends with clean page rows. No chunk table, tokenizer, vector, pgvector write, or retrieval logic is included.

## Connection to v0.7

RAG Data Pipeline Foundation v0.7 will begin from the persisted page rows:

```text
ExtractedPage
  → deterministic chunks
  → document/page metadata
  → embedding preparation
  → pgvector integration
  → authorized semantic retrieval
```

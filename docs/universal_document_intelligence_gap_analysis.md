# AURORA Universal Document Intelligence - Pre-Implementation Gap Analysis

**Audit baseline:** AURORA v1.4.1  
**Audit date:** 26 August 2026  
**Gate:** This analysis was completed before universal-ingestion hardening code changes.

## A. What is already correct

- `FileStorage` is the only binary boundary. Generated object keys, root
  containment, atomic local writes, cleanup, authenticated access, and
  concealed cross-workspace lookups are correct and should remain.
- Upload validation currently enforces the truthful PDF-only contract using
  normalized filenames, extension, declared MIME type, bounded reads, PDF
  signature, checksum, and maximum size.
- `AdapterRegistry`, `FormatAdapter`, `CanonicalDocument`, `ContentUnit`, and
  `IngestionRun` establish the right modular-monolith seam for future formats.
- The PDF adapter prefers native extraction and selectively renders/OCRs only
  pages that appear insufficient. Rendered pixel, page, OCR page, timeout, and
  extracted-character limits are present.
- Tesseract is behind a provider-neutral OCR protocol and has safe public error
  mapping. English and Hindi data are available locally.
- Staged canonical activation prevents a failed replacement from deleting the
  last valid page/index representation. The legacy `ExtractedPage` dual-write
  correctly preserves citation and preview compatibility.
- Indexing is canonical-first with a legacy fallback, deterministic page-local
  chunking, embedding validation, pgvector storage, and workspace-scoped SQL.
- Retrieval, RAG context construction, provider separation, prompt-injection
  boundaries, persistent conversations/SSE, and server-controlled citations
  are already security-conscious.
- Existing tests cover auth, Google OAuth, RBAC, storage, native/scanned/mixed/
  vector PDFs, migration safety, indexing, multilingual retrieval, RAG,
  citations, conversations, streaming, and frontend lifecycle behavior.

## B. What is missing

- Explicit canonical unit outcome (`USABLE`, `SKIPPED`, `FAILED`), canonical
  content type, parent/section relationship, and a stable place for structural
  hierarchy are missing.
- Document/run outcomes do not distinguish complete success from partial
  success. Run diagnostics do not persist native/OCR/skipped/failed counts,
  confidence statistics, duration, failure stage, chunks created, or resource
  limit events.
- There is no reusable adapter compliance harness. Current PDF tests are good
  examples but not a standard contract future adapters can inherit.
- PDF tests do not systematically cover rotated pages, differing page sizes,
  decorative/unreadable pages inside otherwise useful documents, per-page
  render/OCR failure, exact resource boundaries, repeated metadata, or
  concurrent processing.
- Retrieval has exact workspace isolation and chunk deduplication, but no
  candidate diversity step to prevent one document from consuming the entire
  multi-document evidence budget.
- RAG evidence now carries optional canonical provenance internally, but
  `RetrievedChunk`, public search, and context serialization remain primarily
  page-oriented.
- The UI has no `Partially processed` state or safe summary such as usable and
  skipped unit counts.

## C. What is fragile

- Any OCR error, low-quality OCR result, per-page render error, or per-page
  resource limit aborts the whole PDF, even if other pages contain reliable
  evidence. Decorative graphic pages are therefore capable of destroying a
  useful document result.
- PDFium is opened before it is known to be needed, so a renderer problem can
  reject a fully native-text PDF.
- Native quality is based mostly on printable character count and can accept
  repeated/gibberish text or miss structurally useful short text.
- Page classification uses lightweight PDF content-operator signals. It is
  useful routing evidence, not a complete layout/content detector.
- The processing version calculation and initial state transition lack a row
  lock; two simultaneous process requests can race on run version and state.
- Reprocessing is safe after extraction starts, but it is not idempotent and
  does unnecessary work when duplicate requests arrive concurrently.
- Retrieval asks PostgreSQL for only `top_k` rows. If one document dominates
  those rows, later evidence selection cannot recover other relevant sources.
- OCR provider discovery/configuration is repeated per page and uses
  `pytesseract`'s process-global executable setting.

## D. What should be generalized now

1. Enrich the canonical contract additively with unit content type, unit
   outcome, parent identity, structural metadata, and extraction issue code.
2. Add document/run outcome and safe diagnostic summaries without storing or
   logging extracted text.
3. Make PDF page handling fault-isolated: preserve usable native/OCR units,
   record blank/skipped/failed units, and return partial success when warranted.
4. Lazily initialize rendering and preserve fatal handling for document-wide
   corruption/protection and configured global safety limits.
5. Add a database-backed processing concurrency guard.
6. Define adapter capabilities and a reusable compliance assertion/matrix.
7. Carry canonical locator and extraction method through retrieval/context
   while retaining `page_number` during the compatibility phase.
8. Fetch a bounded candidate pool and select relevant evidence with
   deterministic per-document diversity and duplicate suppression.
9. Add frontend partial-state language and actionable safe summaries.

## E. What should remain deferred

- No new format adapter should be claimed in this hardening increment because
  the brief does not select an approved next-format milestone.
- DOC/DOCX, PPT/PPTX, XLS/XLSX, CSV, text/code, HTML, JSON/XML, image, SVG,
  archive, audio, and video adapters remain design targets, not implemented
  support.
- Legacy Office conversion, archives, media transcription, visual embeddings,
  OCR region highlighting, table reconstruction, chart interpretation,
  handwriting recognition, hybrid search, reranking, and advanced agents remain
  deferred.
- Redis, Celery, Kafka, microservices, GPU infrastructure, and distributed job
  execution are not justified by the current repository.
- Full removal of `ExtractedPage` and non-null `page_number` is a later contract
  migration after non-page adapters exist and downstream consumers dual-read
  generic locators.

## F. Proposed implementation sequence

1. Add an expand-only migration for canonical outcomes, hierarchy, diagnostics,
   and partial document status; backfill legacy/current rows.
2. Extend the adapter capability/canonical result contracts.
3. Build reusable compliance helpers plus generated variability fixtures.
4. Refactor PDF extraction into page-isolated outcomes with lazy rendering,
   selective OCR, richer quality metrics, and safe partial success.
5. Guard concurrent document processing and persist sanitized run diagnostics.
6. Allow partial documents to index only usable canonical units while keeping
   old page/citation links.
7. add bounded multi-document candidate diversity and generic provenance to
   retrieval context.
8. Update frontend partial state/summary without redesigning the workspace.
9. Run migration, full backend regression, frontend tests/typecheck/lint/build,
   generated compliance matrix, and privacy-safe multi-document acceptance.
10. Document only formats and behavior actually verified.

## G. Proposed automated test matrix

### Adapter contract

- registered identity/capabilities;
- deterministic ordered units and unique ordinals;
- versioned safe locators;
- content type/outcome/extraction method consistency;
- no direct storage path dependency;
- bounded reads and sanitized errors;
- empty documents never become usable;
- partial results contain at least one usable unit and explicit issue units.

### PDF content and structure

- native, scanned/image, vector-outline, and mixed pages;
- native text plus embedded image;
- blank and decorative pages inside a useful document;
- English, Hindi, mixed Unicode, short semantic text, and low-quality text;
- one/multiple/many pages, portrait/landscape, rotated pages, and different
  page sizes;
- programmatic tables, columns, headings, lists, headers/footers, and forms at
  extraction/provenance level (not semantic layout reconstruction claims).

### Failure, quality, and resource behavior

- one page OCR failure, timeout, low confidence, or render failure with other
  usable pages;
- all pages unusable;
- malformed, encrypted, zero-page, and partially unreadable PDFs;
- page, pixel, total pixel, OCR page, character, and file-size limits;
- renderer unavailable for native-only versus OCR-required documents;
- repeated processing and two concurrent process requests.

### Downstream/security

- only usable units create chunks;
- partial document indexing and authoritative locator/page citations;
- multi-document candidate diversity, duplicate suppression, contradictions in
  context, and workspace isolation;
- MIME/extension/signature mismatch, path traversal, malicious metadata, and
  provider/parser error sanitization;
- auth, OAuth, RBAC, conversations, SSE, multilingual retrieval, preview, and
  deletion regressions.

## H. Migration and schema implications

Use one additive migration after `f4a1c2d3e5b6`:

- expand `documents.status` to include `PARTIALLY_PROCESSED`;
- add a sanitized JSON processing summary to `documents`;
- add `outcome`, `failure_stage`, `duration_ms`, and JSON diagnostics to
  `ingestion_runs`;
- add `content_type`, `status`, `issue_code`, and nullable self-referencing
  `parent_unit_id` to `content_units`;
- backfill existing units as `USABLE` when text is non-empty and `SKIPPED` when
  empty, with `text/plain` content type;
- backfill active runs as `COMPLETE` and safe count diagnostics;
- preserve all existing tables, page/chunk foreign keys, vectors, citations,
  and storage data;
- provide downgrade that removes only these additive fields and restores the
  old document status constraint after converting partial rows to `PROCESSED`.

This remains an expand/dual-read/dual-write step. It does not contract the
legacy PDF page model or pretend that unimplemented formats are supported.


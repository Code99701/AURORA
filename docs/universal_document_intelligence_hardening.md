# AURORA Universal Document Intelligence / Ingestion Hardening

**Implementation date:** 2 September 2026  
**Migration:** `a5b7c9d1e3f5`  
**Pre-implementation audit:** `docs/universal_document_intelligence_gap_analysis.md`

## Outcome

AURORA now has a format-neutral canonical ingestion and indexing seam, a
fault-isolated PDF adapter, explicit partial-success behavior, sanitized
diagnostics, automatic upload-to-index UI flow, and multi-document evidence
diversification. The implementation deliberately supports **PDF only** in this
milestone. It does not advertise formats for which no adapter exists.

The user-facing flow in the workspace is now:

```text
UPLOAD PDF -> AUTOMATIC PROCESSING -> AUTOMATIC INDEXING -> ASK -> CITED ANSWER
```

Manual Process/Index actions remain as retry controls after a failure; users do
not choose native extraction, OCR, parser, or rendering modes.

## 1. Canonical contract

Every registered adapter declares an identity, version, source format,
extensions, media types, unit kinds, partial-result support, native-extraction
support, and OCR-fallback support. Its result is a `CanonicalDocument` with:

- ordered, stable content-unit ordinals;
- unit kind and MIME-style content type;
- normalized text;
- a versioned format-appropriate locator;
- extraction method, language, confidence, and structural metadata;
- `USABLE`, `SKIPPED`, or `FAILED` unit outcome;
- an optional safe issue code and parent-unit relationship;
- `COMPLETE` or `PARTIAL` document outcome;
- sanitized aggregate diagnostics without extracted document text.

`IngestionRun` remains the version/run identity. Only one run is active for a
document, and activation is atomic. A failed replacement preserves the last
valid active run, page view, chunks, and citations.

## 2. PDF processing strategy

The PDF adapter performs bounded validation and opens the tolerant native parser
first. It rejects document-wide conditions such as malformed structure,
encryption, an invalid signature, excessive file size, excessive page count,
or excessive extracted characters with specific safe errors.

Each page is then handled independently:

1. Inspect lightweight PDF content signals and page geometry.
2. Attempt normalized native text extraction.
3. Accept native text only when printable, alphanumeric, replacement-character,
   and repeated-run checks are satisfactory.
4. Mark truly blank pages as `SKIPPED`; a blank page does not make an otherwise
   useful document partial.
5. Lazily open PDFium only if a page actually needs visual recovery.
6. Enforce per-page pixels, total rendered pixels, OCR-page count, and per-page
   OCR timeout before accepting OCR output.
7. Accept OCR only when text and confidence checks pass.
8. Record an unreadable/render-failed/OCR-failed page as a failed canonical unit
   and continue processing later pages.

If at least one unit is usable, the result activates as `PROCESSED` or
`PARTIALLY_PROCESSED`. If no unit is usable, the request fails with the first
actionable cause (for example `OCR_TIMEOUT`) or `NO_EXTRACTABLE_TEXT`.

Native-only PDFs do not depend on PDFium availability. OCR is selective rather
than unconditional. Rotation, page dimensions, extraction classification,
quality metrics, OCR regions, rendering DPI, and confidence are preserved as
non-secret structural metadata.

## 3. Lifecycle and concurrency

Document processing obtains a database row lock before starting a new version.
A request arriving while the document is already `PROCESSING` receives
`DOCUMENT_PROCESSING_IN_PROGRESS` instead of racing the version counter or
creating a duplicate run.

The lifecycle distinguishes:

| Condition | Document state | Unit/run detail |
| --- | --- | --- |
| All useful units recovered | `PROCESSED` | run outcome `COMPLETE` |
| Useful evidence plus unrecoverable units | `PARTIALLY_PROCESSED` | run outcome `PARTIAL` |
| No useful content | `FAILED` | actionable failure code/stage |
| Unsupported upload | request rejected | `UNSUPPORTED_FILE_TYPE`/validation response |
| Password-protected PDF | `FAILED` | `ENCRYPTED_PDF`, validation stage |
| Embedding/index failure | processing result retained | indexing status `FAILED` |

The document summary exposes safe counts to authorized clients. It never
contains extracted text, storage paths, credentials, or provider secrets.

## 4. Canonical-first indexing

Indexing now reads `USABLE` units from the active canonical run directly. The
legacy `ExtractedPage` table is only a compatibility view for PDF preview and
old page-aware consumers. A canonical unit without a page can create chunks
without an `extracted_page_id` or `page_number`; its authoritative locator is
available through `content_unit_id`.

Legacy documents without an active canonical run retain a page-based fallback.
Chunk fingerprints include the ingestion version, unit ordinal, extraction
method, canonical locator, normalized content, chunking settings, and embedding
provider identity. Failed or skipped units never create chunks.

## 5. Multi-document retrieval and RAG

Workspace authorization remains inside the retrieval SQL query. Retrieval now
requests a bounded candidate pool, removes normalized duplicate content only
within the same document, and selects candidates round-robin by each document's
best rank. This prevents one verbose source from consuming the entire evidence
budget while preserving the globally strongest first result.

RAG applies the configured similarity threshold and character budget after
selection. Each untrusted evidence block carries document identity, chunk
identity, optional page, generic locator, extraction method, similarity, and
escaped document text. The configured LLM still receives retrieved evidence,
not whole documents. Provider abstractions for embeddings, OCR, and generation
remain independent.

Citations continue to be persisted from server-authorized chunks and resolved
inside the workspace boundary. PDF citations remain page-aware. Future non-page
adapters can use canonical locators without a schema redesign.

## 6. Observability

Sanitized ingestion diagnostics include:

- detected page and unit counts;
- usable, skipped, and failed unit counts;
- extraction-method counts;
- issue/resource-limit counts;
- OCR candidate count and rendered pixel count;
- average accepted OCR confidence;
- adapter identity/version and run outcome;
- failure stage and failure code;
- processing duration.

Indexing diagnostics add chunk count, embedding provider/model identity,
outcome, failure code when applicable, and duration. Structured application
logs include identifiers and counts, never extracted content.

## 7. Automated compliance coverage

`backend/tests/adapter_compliance.py` is the reusable minimum contract for this
and future adapters. The PDF suite uses deterministic generated documents for:

- native, image-only, vector-outline, mixed, blank, encrypted, and malformed
  PDFs;
- selective OCR, low-confidence/no-text OCR, OCR timeout, and rendered-pixel
  bounds;
- mixed native plus failed OCR with a partial result;
- native extraction while the renderer is unavailable;
- rotated-page geometry and provenance;
- canonical unit ordering, outcome, locator, status, content type, and
  diagnostic invariants;
- partial persistence, usable-unit-only indexing, concurrent-state rejection,
  and atomic failed reprocessing;
- canonical section indexing with no legacy page;
- multi-document selection and within-document duplicate suppression.

Existing suites continue to cover signature/MIME/extension validation, path
safety, upload limits, RBAC and concealed cross-workspace access, migrations,
pgvector retrieval, multilingual behavior, Gemini provider boundaries,
citations, conversations, streaming, Google OAuth, and frontend behavior.

## 8. Security and resource boundaries

The hardening preserves generated storage keys, root containment, authenticated
download/preview, workspace-scoped retrieval, bounded file reads, maximum page
and content sizes, render pixel limits, OCR page/time limits, fixed embedding
dimension, and sanitized provider/parser errors. It does not execute uploaded
content and adds no archive extraction or legacy Office conversion surface.

Partial success never bypasses a global safety limit. It only prevents a local
page failure from discarding already trustworthy evidence.

## 9. Actually supported formats

| Format | Upload | Native extraction | OCR fallback | Partial units | Preview |
| --- | --- | --- | --- | --- | --- |
| PDF (`.pdf`, `application/pdf`) | Supported | Supported | Local Tesseract, selective | Supported | Supported |

No DOC/DOCX, PPT/PPTX, XLS/XLSX, CSV, TXT/Markdown, HTML, JSON/XML, image,
archive, audio, or video adapter is implemented in this milestone. Their future
adapters can target the canonical contract and compliance suite without changing
indexing, retrieval, RAG, or citations.

## 10. Known limitations and deferred work

- Processing and indexing are synchronous HTTP operations. The schema and
  lifecycle are prepared for jobs/progress/cancellation, but no queue or worker
  infrastructure is introduced.
- PDF content signals are routing heuristics, not semantic layout analysis.
- OCR does not currently deskew, denoise, detect handwriting, reconstruct
  tables, interpret charts, or produce visual embeddings.
- Native/OCR text reading order for complex columns and diagrams depends on the
  underlying parser/OCR engine.
- English and Hindi Tesseract data are configured by default; other languages
  require installed language data and configuration.
- Retrieval uses exact pgvector cosine distance plus deterministic diversity;
  hybrid lexical search and reranking remain deferred.
- Partial failed pages remain visible in the compatibility page register with
  empty text but cannot create chunks or evidence.

## 11. Configuration

Existing ingestion limits remain in `.env.example`. The only new retrieval
setting is:

```dotenv
RETRIEVAL_CANDIDATE_MULTIPLIER=4
```

It is validated from 1 through 10. The internal candidate query is additionally
capped at 100 rows.

## 12. Verification record

- Backend: **204 passed, 2 skipped** across the complete collected suite. The
  one Docker restart
  test initially blocked by sandbox permissions was rerun separately and
  passed, so every backend test passed. The two skips are explicit live-provider
  tests.
- Focused hardening/RAG run: **86 passed, 1 skipped**.
- Frontend: **15 passed**, TypeScript clean, ESLint clean.
- Next.js 16.3 production build: successful.
- Clean-database Alembic upgrade through `a5b7c9d1e3f5`: successful.

## 13. Operations

Apply the additive migration before running the updated application:

```powershell
cd D:\Jarvis\projects\AURORA\backend
.\aurora-env\Scripts\Activate.ps1
alembic upgrade head
```

Then start FastAPI and the Next.js frontend using the existing project run
instructions. Uploading a PDF from the workspace starts processing and indexing
automatically.

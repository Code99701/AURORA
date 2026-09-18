# AURORA v1.4.1 — Canonical Ingestion Core and Robust PDF/OCR

**Status:** Implemented and verified locally  
**Scope:** PDF only; canonical ingestion foundation for later adapters  
**Migration:** `f4a1c2d3e5b6_add_canonical_ingestion_core.py`

## 1. Outcome

v1.4.1 fixes PDFs that are visually readable but have no usable PDF text
layer. AURORA still attempts native `pypdf` extraction first. Only pages whose
native text is insufficient are rendered with `pypdfium2` and sent to the local
OCR boundary. The result is stored as versioned canonical content while the
existing `ExtractedPage`, page-aware chunk, citation, and preview contracts
remain available.

The existing authentication, Google OAuth, workspace RBAC, `FileStorage`,
pgvector retrieval, RAG, citations, conversations, SSE streaming, multilingual
behavior, and PDF preview architecture were retained.

## 2. Processing flow

```text
Authorized PDF upload
  -> existing filename/MIME/signature/size validation
  -> existing FileStorage binary boundary
  -> AdapterRegistry resolves the allowlisted PDF adapter
  -> bounded pypdf parse and per-page native extraction
  -> text quality and page-signal assessment
       -> usable native text: canonical NATIVE page unit
       -> genuinely blank page: canonical BLANK page unit
       -> insufficient/image/vector/mixed page: bounded PDFium render
          -> local OCR provider
          -> OCR quality gate
          -> canonical OCR page unit
  -> stage IngestionRun and ContentUnit rows
  -> atomically activate the staged run
  -> dual-write the ExtractedPage compatibility view
  -> index canonical units with page-compatible chunks
  -> authorized pgvector retrieval and server-controlled citations
```

Adapters receive only a binary stream opened through `FileStorage`. They do not
know the local filesystem root or storage key and never build a path to an
uploaded object.

## 3. Provider-neutral contracts

### 3.1 Format adapter

`FormatAdapter` exposes identity fields and one operation:

```python
class FormatAdapter(Protocol):
    adapter_id: str
    adapter_version: str
    source_format: str

    def extract(
        self, source: BinaryIO, context: ExtractionContext
    ) -> CanonicalDocument: ...
```

`AdapterRegistry` is an explicit allowlist. v1.4.1 registers only
`PDFAdapter`; it does not imply support for Office, archives, images, audio, or
video.

### 3.2 OCR provider

`OCRProvider.recognize(image, timeout_seconds)` returns text, normalized
confidence, language, and optional regions. The PDF adapter depends only on
this protocol. `TesseractOCRProvider` is the local implementation.

### 3.3 Canonical document and content units

A `CanonicalDocument` records adapter identity, source format, optional page
count, warnings, and ordered `ContentUnitDraft` records. Persisted
`ContentUnit` fields include:

- document and ingestion-run identity;
- deterministic ordinal and unit kind;
- normalized text and character count;
- language and confidence when known;
- extraction method (`NATIVE`, `OCR`, `BLANK`, or legacy backfill value);
- versioned JSON provenance locator;
- adapter metadata, including page classification, OCR regions, and render DPI.

PDF provenance currently uses:

```json
{"v": 1, "type": "pdf_page", "page": 7}
```

The locator is authoritative canonical provenance. `page_number` remains in the
existing compatibility/citation path for v1.4.1.

## 4. Per-page PDF strategy

1. Validate the bounded binary and `%PDF-` signature again at the adapter
   boundary.
2. Parse with `PdfReader(strict=False)` and reject encrypted PDFs.
3. Inspect page content operators and image XObjects.
4. Extract and normalize native text.
5. Accept native text only when its printable ratio and semantic content pass
   the configured quality gate. Short legitimate titles/page labels are kept
   when represented by real text operators.
6. Treat actual empty/whitespace-only pages as blank units.
7. Classify remaining pages as image-only, vector-outline, or mixed and render
   only those pages at bounded DPI.
8. Run local English/Hindi OCR and accept it only when it contains semantic
   text, has an acceptable printable ratio, meets the character threshold, and
   meets the confidence threshold.

A document succeeds only if at least one canonical unit has usable text. A few
low-quality OCR characters cannot make the document `PROCESSED`.

## 5. Atomic activation and reprocessing

Each attempt receives a monotonically increasing `IngestionRun.version` and
moves through `PROCESSING -> STAGED -> ACTIVE` or `FAILED`. A partial unique
index permits only one active run per document.

Canonical units are committed in the staged run before activation. Activation
then supersedes the prior active run, replaces the compatible `ExtractedPage`
view, resets the old index, and marks the document processed in one database
transaction. If this transaction fails, it rolls back as a unit.

The previous pages, chunks, index metadata, and active run are not deleted
before a replacement has been staged successfully. A failed reprocessing
attempt records a failed run and restores the previous valid document state.
This prevents an OCR outage or malformed replacement from destroying the last
known-good research representation.

## 6. Expand, backfill, dual-write, switch

The migration is additive:

- adds nullable `documents.processing_stage`;
- creates `ingestion_runs` and `content_units`;
- adds nullable `content_unit_id` links to `extracted_pages` and
  `document_chunks`;
- backfills each previously processed document into one active legacy run;
- creates page locators and connects old pages/chunks to their canonical units;
- keeps `extracted_pages`, `extracted_page_id`, and `page_number` intact.

New processing writes canonical units and the old page view. New indexing reads
the active canonical run first and falls back to old `ExtractedPage` rows when
canonical data is absent. Existing citation traversal therefore remains valid.
The downgrade removes only the additive canonical structures and leaves the
legacy page/citation foundation in place.

## 7. Security and resource limits

Defaults are configurable in `.env`:

| Control | Default |
|---|---:|
| Upload/adapter file limit | 10 MiB |
| PDF pages | 250 |
| Render DPI | 300 |
| Pixels per rendered page | 40,000,000 |
| Total rendered pixels | 900,000,000 |
| OCR pages per document | 100 |
| OCR timeout per page | 30 seconds |
| Maximum extracted text | 5,000,000 characters |
| Native minimum text | 8 characters |
| OCR minimum text | 12 characters |
| Minimum printable ratio | 0.85 |
| Minimum OCR confidence | 0.25 |

Additional controls:

- upload extension, declared MIME type, and PDF signature must agree;
- object keys remain generated server-side and constrained by `FileStorage`;
- encrypted, malformed, over-page, over-pixel, and over-character documents
  fail with safe codes;
- rendering is in memory and page images are closed in `finally` paths;
- uploaded content is parsed/rendered only and is never executed;
- public errors exclude filesystem paths, parser/OCR internals, stack traces,
  credentials, and provider payloads.

Representative errors include `ENCRYPTED_PDF`, `PDF_EXTRACTION_ERROR`,
`PDF_RENDER_ERROR`, `PDF_PAGE_LIMIT`, `PDF_RENDER_RESOURCE_LIMIT`,
`OCR_PAGE_LIMIT`, `OCR_TIMEOUT`, `OCR_ENGINE_UNAVAILABLE`,
`OCR_LANGUAGE_UNAVAILABLE`, `OCR_NO_USABLE_TEXT`, and
`NO_EXTRACTABLE_TEXT`.

## 8. Local OCR runtime

Python dependencies are pinned in `backend/requirements.txt`:

- `pypdfium2==5.13.0`
- `Pillow==12.3.0`
- `pytesseract==0.3.13`

`pytesseract` is a bridge, not the OCR engine. Install Tesseract 5 separately
and ensure `eng.traineddata` and `hin.traineddata` are available. Configure an
explicit executable when it is not on `PATH`:

```text
TESSERACT_EXECUTABLE=C:\Program Files\Tesseract-OCR\tesseract.exe
OCR_LANGUAGES=eng+hin
```

On this development machine, the official Windows binary and official
English/Hindi fast models were extracted into the Git-ignored
`backend/.runtime/tesseract/` directory. AURORA checks the explicit setting,
`PATH`, the normal Windows installation path, and then this project-local
development path.

## 9. Zero-source research behavior

The research textarea stays enabled when the workspace has no indexed source,
so a user may prepare a question. Sending it reaches the backend, which checks
for an authorized `PROCESSED + INDEXED` document before invoking embedding or
generation providers. If none exists, search, one-shot RAG, and SSE preflight
return HTTP 409 with:

```json
{
  "code": "NO_RESEARCH_READY_SOURCES",
  "message": "Process and index a workspace document before asking a grounded question"
}
```

The frontend renders that actionable message. Indexed workspaces that merely
lack sufficiently relevant evidence retain the existing deterministic
insufficient-evidence behavior.

## 10. Test strategy and results

Deterministic tests cover searchable, scanned, vector-outline, mixed,
blank/whitespace, malformed, encrypted, low-quality OCR, OCR timeout, render
limits, provenance, canonical persistence, reprocessing, atomic failure,
migration upgrade/downgrade/re-upgrade, zero-source provider suppression, and
legacy page/citation behavior. The full regression suite also covers auth,
OAuth, RBAC/workspace isolation, multilingual retrieval, conversations, SSE,
citations, storage, and database persistence.

Manual `intern.pdf` acceptance used local deterministic embedding/generation
providers so private OCR text did not leave the machine. It verified:

- 13 of 13 pages recovered by real Tesseract OCR;
- 13 canonical page units, all with OCR extraction metadata;
- 21 page-linked vector chunks stored in pgvector;
- retrieval returned eight authorized chunks;
- RAG persisted a grounded answer and server-controlled citations;
- citation resolution returned OCR locator page 7;
- the cited chunk's canonical locator also resolved to page 7;
- authorized preview returned the original 2,022,871-byte PDF;
- frontend citation handling opens the document inspector with `#page=7`.

No document text was sent to Gemini during this manual acceptance run. A live
Gemini acceptance run requires the document owner's explicit approval to send
the extracted content to that external provider.

## 11. Known limitations and deferred work

- v1.4.1 is synchronous; very large allowed OCR jobs can occupy an API worker.
- OCR quality depends on scan resolution, orientation, typography, language
  data, and document complexity; handwriting is not a target.
- Region metadata is stored but citations remain page-level in the current UI.
- Only PDF is registered. DOC/DOCX, PPT/PPTX, XLS/XLSX, archives, PSD, audio,
  video, media embeddings, hybrid retrieval, reranking, and distributed job
  infrastructure are explicitly deferred.
- Legacy rows remain by design until a later, measured contract migration.

## 12. Next recommended milestone

**AURORA v1.5 — Asynchronous Ingestion Operations and Observability.**

Before adding more formats, move bounded processing behind a durable local job
contract, add progress/cancellation/metrics, and exercise retry/idempotency on
the canonical run model. This should remain inside the modular monolith; it
does not require Redis, Celery, Kafka, or microservices in the first iteration.


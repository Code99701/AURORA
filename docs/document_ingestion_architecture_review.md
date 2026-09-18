# AURORA — Document Ingestion Architecture Review

**Status:** Architecture review and implementation plan  
**Implementation status:** No implementation performed  
**Concrete failure case:** intern.pdf  
**Recommended next milestone:** AURORA v1.4.1 — Canonical Ingestion Core and Robust PDF/OCR

---

## Executive summary

The failure observed with intern.pdf is caused by a real limitation in AURORA's current ingestion layer, not by a corrupt file.

The attached file is a valid, unencrypted, 13-page PDF created by Microsoft Print to PDF. It is visually readable because a PDF renderer can draw its content. However, the visible letters are represented predominantly as vector paths rather than PDF text objects. The file has no usable font resources or PDF text-showing operations, and both pypdf and pdfplumber return zero characters from every page. A native text extractor therefore has no Unicode text to recover.

AURORA currently has only one PDF extraction strategy: pypdf page.extract_text(). If every extracted page is empty, processing ends with NO_EXTRACTABLE_TEXT. There is no page classification, extraction-quality assessment, rendering fallback, or OCR provider. The result shown in the UI—FAILED and NOT INDEXED—is therefore consistent with the current implementation, but it is not sufficient for a production-quality research platform.

The recommended solution is not an isolated OCR patch inside the existing RAG service. AURORA should introduce a provider-neutral ingestion layer in which:

1. A file is securely validated and identified.
2. A registered format adapter converts it to a common canonical representation.
3. Extraction quality is measured.
4. Format-specific fallback strategies run where appropriate.
5. Canonical content is normalized and stored with generic provenance.
6. Format-aware chunking prepares evidence for the existing embedding and pgvector pipeline.
7. Existing authorization, retrieval, generation, conversations, streaming, and server-controlled citations remain in place.

For PDFs, native extraction should run first because it is faster and generally more accurate than OCR. Pages with insufficient native text should be classified and rendered for OCR. OCR output must retain page and region provenance and must pass its own quality checks before the document becomes processable.

This review recommends an incremental migration. Existing PDF page rows and citations should remain readable while new canonical content tables and generic locators are introduced. AURORA should first solve robust PDF ingestion and generic provenance, then add core Office, text, spreadsheet, presentation, structured-data, and image adapters. Legacy Office formats, RAR, PSD, audio, and video should be explicitly deferred until the core ingestion platform is stable.

---

## Review constraints

This document is an architecture review only. During its preparation:

- No application files were modified.
- No application behavior was refactored.
- No dependencies were installed.
- No OCR implementation was added.
- No database migration was created or executed.
- No database data was changed.
- No commit or push was performed.

The only new artifact is this Markdown review document.

---

## 1. Current document ingestion architecture

### 1.1 Upload and validation

The current upload service accepts only PDF documents. It validates:

- A normalized display filename.
- A .pdf filename suffix.
- A declared MIME type of application/pdf or application/x-pdf.
- A maximum upload size configured through DOCUMENT_MAX_SIZE_BYTES, currently 10 MB.
- A leading PDF signature of %PDF-.
- A SHA-256 checksum.

The original binary is saved through the FileStorage protocol. The generated object key follows the pattern:

    workspaces/{workspace_id}/documents/{document_id}/original

The database records the workspace, uploader, filename, storage provider, storage key, content type, file size, checksum, processing status, and indexing status.

### 1.2 Processing

Processing is currently PDF-specific:

    Stored PDF
        ↓
    pypdf.PdfReader
        ↓
    page.extract_text() for every page
        ↓
    text cleanup
        ↓
    one ExtractedPage row per PDF page

When processing begins, AURORA:

- Sets the document to PROCESSING.
- Clears its previous processing error and processed timestamp.
- Resets its indexing status and indexing metadata.
- Deletes existing ExtractedPage rows.
- Opens the original through FileStorage.
- Calls the PDF extractor.
- Normalizes whitespace and control characters.

If all pages contain empty text after normalization, processing terminates with:

- Document status: FAILED
- Processing error: NO_EXTRACTABLE_TEXT
- Indexing status: NOT_INDEXED
- Public message: PDF contains no extractable text; OCR is not supported

If at least one page contains text, all page rows are persisted, including empty pages, and the document becomes PROCESSED.

### 1.3 Indexing

Indexing is a separate manual operation. It requires the document to be PROCESSED.

The current indexer:

- Reads ExtractedPage records in page order.
- Splits each page into deterministic character windows.
- Never combines text from different pages.
- Generates Gemini embeddings.
- Validates a fixed embedding dimension of 768.
- Replaces the document's previous DocumentChunk rows.
- Stores vectors in PostgreSQL through pgvector.
- Marks the document INDEXED.

The indexing fingerprint includes chunk sizes, embedding provider, embedding model, embedding dimension, page numbers, and page text.

### 1.4 Retrieval and RAG

Retrieval:

- Creates an embedding for the user's query.
- Searches DocumentChunk vectors.
- Filters documents by the authorized workspace.
- Includes only documents with indexing status INDEXED.
- Returns filename, page number, chunk text, and similarity.

Generation only runs when relevant authorized evidence remains after the similarity and context limits. When no relevant evidence exists, AURORA returns a deterministic insufficient-evidence response instead of invoking the language model.

Persistent citations connect:

    RAG response
        ↓
    RAGCitation
        ↓
    DocumentChunk
        ↓
    ExtractedPage
        ↓
    Document

This is a secure and useful foundation, but ExtractedPage and page_number make it inherently PDF-oriented.

### 1.5 Frontend behavior

The document interface correctly shows processing and indexing as separate states. The research interface computes the number of indexed sources. When that number is zero:

- A warning explains that there are no research-ready sources.
- A Review sources action is presented.
- The question textarea is disabled.
- The Send button is disabled.

This prevents unsupported generation, but it also prevents users from preparing a question and can make the research screen feel non-interactive.

---

## 2. Exact diagnosis of the attached PDF failure

### 2.1 File facts

Inspection of intern.pdf established:

- File size: 2,022,871 bytes, approximately 1.9 MB.
- Page count: 13.
- Encryption: none.
- Producer: Microsoft: Print To PDF.
- Title: Embark on a Global Research Journey with Globalink Internship.
- pypdf extracted characters: zero on every page.
- pdfplumber extracted characters: zero on every page.
- PDF font resources: zero on every page.
- PDF text operators such as BT, ET, Tf, Tj, and TJ: absent on every page.
- Raster images: present on the first pages.
- Vector drawing operations: present in very large quantities throughout the document.

### 2.2 What kind of PDF this is

This is not a conventional searchable PDF, and it is not simply a collection of full-page scanned images.

The visible page content was flattened during printing. Letters that originally existed as browser or application text were converted into geometric outlines. A PDF renderer sees those outlines and paints them on screen, so the document looks normal to a person. A text extractor searches for semantic text objects, fonts, character maps, and text-showing instructions. Those structures do not exist in this file.

The most accurate classification is:

> A flattened, vector-outlined PDF containing visually readable glyph shapes but no semantic text layer, with some embedded raster images.

### 2.3 Why AURORA fails

AURORA currently calls pypdf page.extract_text(). That API can extract text only when the PDF contains recoverable character information. It is not an OCR engine and cannot infer that a group of Bezier curves represents the letter A.

Every page therefore returns an empty string. The processing service cleans those empty strings, finds that no page contains usable text, and emits NO_EXTRACTABLE_TEXT.

The upload is not rejected because it is structurally a PDF and has the expected signature. The preview succeeds because the browser renders vector graphics. Processing fails because rendering and semantic extraction are different operations.

### 2.4 Would OCR solve it?

Rendering each affected page into pixels and passing the image to OCR is the correct recovery path. It should recover a substantial portion of the visible content because the letters are visible after rendering.

OCR is not guaranteed to be perfect. The document includes:

- Small website text.
- Light grey text.
- Multi-column layout.
- Images and navigation elements.
- Decorative elements.

Therefore, OCR results must be evaluated for coverage and quality. AURORA should not mark a document ready merely because the OCR engine returned a few characters.

---

## 3. Current architectural weaknesses

### 3.1 Single extraction strategy

The processing result depends entirely on pypdf native extraction. Real-world PDFs may contain:

- Normal text layers.
- Scanned images.
- Vector-outlined text.
- Broken or unusual character maps.
- Mixed native and scanned pages.
- Text embedded inside images.

A single strategy cannot handle all of these reliably.

### 3.2 Document-level rather than page-level assessment

If one page contains usable text and twelve pages are image-only, the current document passes processing. Empty pages are preserved, but no attempt is made to recover their visible content. A mixed PDF can therefore become PROCESSED while most evidence remains missing.

### 3.3 No extraction-quality model

The current decision is binary: any non-empty cleaned text is considered success. It does not detect:

- Mojibake.
- Replacement-character-heavy output.
- Repeated garbage.
- Very low coverage.
- Text with no plausible words.
- Pages whose visible content is much greater than extracted content.

### 3.4 Page-only canonical model

ExtractedPage requires a positive page number. This cannot naturally represent:

- A DOCX paragraph.
- An XLSX cell range.
- A PPTX slide shape.
- A CSV row range.
- A code symbol and line range.
- An audio timestamp.

### 3.5 Destructive reprocessing start

Existing extracted pages and indexing metadata are cleared before replacement extraction succeeds. If reprocessing fails, the last known-good searchable representation is lost. New ingestion must be staged and activated atomically.

### 3.6 Limited status history

The document stores current status and an error code but no durable processing-attempt history. It cannot explain:

- Which adapter ran.
- Which extractor version ran.
- Whether native extraction was tried.
- Which pages required OCR.
- How long stages took.
- What resource limit was reached.

### 3.7 Synchronous processing

Native PDF extraction is usually fast enough for an HTTP request. OCR, Office parsing, archives, and media can take much longer. A synchronous-only design risks timeouts and poor retry behavior.

### 3.8 Frontend readiness derived from document list

The frontend counts indexed documents from a list response. This is useful for presentation but should not be the authoritative enforcement mechanism. Readiness can change between rendering and submission, and a client can bypass UI controls.

---

## 4. Proposed multi-format ingestion architecture

The proposed architecture separates file interpretation from RAG:

    Authorized upload
        ↓
    Bounded immutable storage
        ↓
    Security validation
        ↓
    File identification
        ↓
    Registered format adapter
        ↓
    Canonical document
        ↓
    Normalization and quality validation
        ↓
    Atomic activation
        ↓
    Format-aware chunking
        ↓
    Existing embedding abstraction
        ↓
    Existing pgvector index
        ↓
    Existing authorized retrieval
        ↓
    Existing grounded generation
        ↓
    Generic server-controlled citations

### 4.1 Components

**UploadValidator**

Performs bounded reading, checksum calculation, initial signature checks, filename normalization, size enforcement, and denylist checks.

**FileIdentifier**

Combines declared MIME, extension, binary signature, container structure, and parser probes. It returns a detected format with confidence and warnings.

**AdapterRegistry**

Maps supported detected formats to explicit adapter factories. It is the only component responsible for selecting a format implementation.

**IngestionOrchestrator**

Coordinates stages, resource budgets, storage access, temporary artifacts, extraction, quality assessment, normalization, persistence, and activation.

**FormatAdapter**

Understands one format family and produces a CanonicalDocument. It does not know about workspaces, SQLAlchemy, Gemini, pgvector, or frontend components.

**QualityAssessor**

Evaluates adapter output and decides whether it is usable, needs fallback, or must fail.

**ChunkStrategyRegistry**

Selects chunking behavior from canonical unit kind rather than original file extension.

### 4.2 Design principles

- Explicit allowlist rather than universal file acceptance.
- Content verification rather than trusting extension.
- Immutable original binary.
- Provider-neutral storage.
- Versioned extraction results.
- Atomic replacement of active content.
- Generic provenance.
- Existing authorization and citation ownership preserved.
- No execution of uploaded content.

---

## 5. Proposed canonical content representation

### 5.1 CanonicalDocument

A CanonicalDocument should contain:

- Document identity.
- Detected format and MIME.
- Adapter ID and adapter version.
- Extraction timestamp.
- Title and safe metadata.
- Language hints.
- Ordered content units.
- Extraction warnings.
- Quality metrics.
- References to safe derivatives when needed.

### 5.2 ContentUnit

Each ContentUnit should contain:

- Stable ID.
- Document ID.
- Ingestion run ID.
- Ordinal position.
- Unit kind.
- Normalized text.
- Optional structured payload.
- Language.
- Structural path.
- Generic provenance locator.
- Extraction method.
- Confidence.
- Character count.
- Safe adapter metadata.

Suggested kinds include heading, paragraph, list_item, table_rows, sheet_range, slide_text, code_symbol, transcript_segment, OCR_region, image_caption, and metadata.

### 5.3 Structured content

Plain text remains necessary for embeddings, but structure should not be discarded. For example, an XLSX table unit can contain:

- A text rendering suitable for embeddings.
- A JSON representation of headers and rows.
- The worksheet and range locator.
- Formula/cached-value metadata.

The JSON payload should be bounded and schema-versioned. It should not become an unlimited dumping ground for raw parser objects.

### 5.4 Generic provenance locators

Locators should be server-generated, versioned JSON:

    PDF:
    {"v":1,"type":"pdf_page","page":7,"regions":[...]}

    DOCX:
    {"v":1,"type":"docx_paragraph","section":2,"paragraph":14}

    PPTX:
    {"v":1,"type":"pptx_slide","slide":12,"shape":4}

    XLSX:
    {"v":1,"type":"xlsx_range","sheet":"Sales","range":"B14:F27"}

    CSV:
    {"v":1,"type":"csv_rows","start_row":20,"end_row":35}

    Code:
    {"v":1,"type":"code_lines","path":"app/main.py","symbol":"process","start_line":42,"end_line":78}

    Audio/video:
    {"v":1,"type":"media_time","start_ms":763000,"end_ms":808000}

The application should validate locator schemas before persistence.

---

## 6. Proposed extractor interface

A conceptual interface is:

    FormatAdapter
    - adapter_id
    - adapter_version
    - supported_formats
    - probe(descriptor, source) -> ProbeResult
    - extract(source, context) -> CanonicalDocument

### 6.1 FileDescriptor

Contains:

- Original filename.
- Extension.
- Declared MIME.
- Detected signature.
- File size.
- Checksum.
- Container observations.

### 6.2 ProbeResult

Contains:

- Supported or unsupported.
- Detected format.
- Confidence.
- Mismatch warnings.
- Encryption/password state.
- Preliminary resource facts such as page, sheet, slide, or member count.

### 6.3 ExtractionContext

Contains:

- Cancellation/deadline.
- Resource budget.
- Secure temporary-artifact manager.
- OCR provider.
- Allowed OCR languages.
- Maximum extracted characters and units.
- Feature flags.
- Audit correlation ID.

### 6.4 SeekableSource

FileStorage.open returns a BinaryIO stream. Some parsers require seek and tell; some require a filesystem path. A SeekableSource wrapper should:

- Accept a storage stream.
- Preserve provider neutrality.
- Spool only when required.
- Enforce maximum bytes.
- Create private random temporary paths.
- Clean up in all success and error paths.

Adapters must never derive or access LocalFileStorage paths themselves.

---

## 7. Format adapter registry design

### 7.1 Explicit registration

Adapters should be registered at application startup:

    PDF → PdfAdapter
    DOCX → DocxAdapter
    XLSX → XlsxAdapter
    CSV → DelimitedTextAdapter
    PPTX → PptxAdapter

This is configuration, not a giant conditional inside the RAG service.

### 7.2 Selection rules

1. Reject executable/system signatures before normal classification.
2. Compare filename extension and declared MIME with binary observations.
3. Inspect container structure when applicable.
4. Ask candidate adapters to probe safely.
5. Select one highest-confidence allowed adapter.
6. Reject ambiguous or conflicting identification.

OOXML formats are all ZIP-based. The registry should inspect content types and package paths to distinguish DOCX, XLSX, and PPTX.

### 7.3 Safety

- No dynamic Python import based on user data.
- No shell command assembled from a filename.
- No generic fallback that sends unknown binaries to multiple parsers.
- No adapter for EXE, DLL, SYS, or unknown proprietary binary data.
- Parser failures return safe application error codes.

---

## 8. PDF and OCR architecture

### 8.1 Native-first pipeline

Native extraction should always be attempted first because it is:

- Faster.
- More accurate for searchable PDFs.
- Better at preserving exact characters.
- Less CPU-intensive.
- Better for multilingual Unicode text.

### 8.2 Per-page classification

Each page should be classified as:

- NATIVE_TEXT
- IMAGE_ONLY
- VECTOR_OUTLINE_TEXT
- MIXED
- BLANK
- EXTRACTION_ERROR

Classification signals include:

- Font resources.
- Text operators.
- Extracted character count.
- Printable ratio.
- Replacement-character ratio.
- Raster-image coverage.
- Vector-paint complexity.
- Page area and text density.

### 8.3 Quality assessment

Native text is sufficient only when it passes configurable thresholds. A practical assessor should measure:

- Characters per page.
- Percentage of substantive pages containing text.
- Plausible words and line structure.
- Excessive repetition.
- Unicode corruption.
- Control/replacement characters.
- Visible-content indicators versus extracted coverage.

No single metric should decide success.

### 8.4 OCR fallback

Only insufficient pages should be rendered. A searchable 200-page PDF with two scanned appendices should OCR those two pages, not all 200.

Recommended flow:

    Page
      ↓
    native extraction
      ↓
    quality gate
      ├── sufficient → native content unit
      ├── blank → blank page record
      └── insufficient → render at bounded DPI
                              ↓
                         preprocess if needed
                              ↓
                             OCR
                              ↓
                         OCR quality gate

Use pypdfium2 for rendering and local Tesseract through pytesseract. Start with English, Hindi/Devanagari, and orientation data.

### 8.5 OCR provenance

OCR should preserve:

- Page number.
- OCR block/line/word coordinates.
- Confidence.
- Language.
- Rendering DPI.
- OCR engine and model/data version.
- Preprocessing steps.

Coordinates should be normalized to page dimensions so they remain usable across preview resolutions.

### 8.6 Native/OCR merging

For mixed pages:

- Retain high-quality native text.
- OCR regions not covered by native text.
- Deduplicate overlapping text.
- Never concatenate full native and full OCR output blindly.
- Record extraction method per content unit.

### 8.7 OCR failure

Useful failure codes:

- PDF_PARSE_ERROR
- OCR_ENGINE_UNAVAILABLE
- OCR_LANGUAGE_UNAVAILABLE
- OCR_TIMEOUT
- OCR_RESOURCE_LIMIT
- OCR_NO_USABLE_TEXT
- EXTRACTION_QUALITY_FAILED

NATIVE_TEXT_INSUFFICIENT is a stage result, not terminal failure when OCR remains available.

### 8.8 Status UX

The UI should display:

- Inspecting PDF
- Extracting native text
- Native text unavailable; OCR required
- Running OCR, page X of Y
- Validating recognized text
- Ready to index

The final failure should explain whether the file needs a missing language pack, exceeded a limit, timed out, or simply contained no recognizable text.

---

## 9. DOC and DOCX architecture

### 9.1 DOCX

Use python-docx for:

- Paragraphs in document order.
- Heading styles and hierarchy.
- Lists.
- Section boundaries.
- Tables and nested tables.
- Headers and footers where useful.
- Embedded image references.

DOCX page numbers should not be fabricated. DOCX stores document structure, while actual pagination depends on fonts, printer settings, and a layout engine. Provenance should therefore use section, heading path, paragraph index, table index, row, and cell.

Images may be passed to the image OCR pipeline later, linked back to the containing paragraph or section.

### 9.2 DOC

Legacy DOC is a compound binary format and is not supported by python-docx. Future support should use an isolated conversion process:

    DOC
      ↓
    sandboxed LibreOffice conversion
      ↓
    DOCX or PDF derivative
      ↓
    normal adapter

The converter must:

- Have no network access.
- Run with a private temporary profile.
- Disable macros.
- Use strict time and memory limits.
- Receive a server-generated path.
- Produce only an allowlisted derivative.

DOC support should be deferred until DOCX is stable.

---

## 10. XLS, XLSX, CSV, and TSV architecture

### 10.1 XLSX

Use openpyxl read-only mode where possible. Preserve:

- Workbook and sheet names.
- Sheet order.
- Used ranges.
- Row and column coordinates.
- Cell values and types.
- Formula text.
- Cached formula results when present.
- Merged-cell relationships.
- Table names and ranges.
- Hidden rows, columns, and sheets as metadata.

Openpyxl does not calculate Excel formulas. AURORA must distinguish a formula from a cached value and never claim it recalculated the workbook.

### 10.2 Canonical table representation

A worksheet range can become:

- One heading/metadata unit describing the sheet.
- Table-row units containing repeated headers.
- Provenance such as Sales!B14:F27.
- Structured JSON containing headers and cell values.
- Text optimized for embedding.

Sparse sheets should not be expanded into enormous empty matrices.

### 10.3 CSV and TSV

Use the Python standard library with:

- BOM detection.
- UTF-8 first, bounded encoding fallback.
- Dialect/delimiter sniffing.
- Maximum field length.
- Maximum rows and columns.
- Header inference with warnings.
- Row-range provenance.

CSV formulas beginning with characters such as = should be treated as text. If AURORA later exports CSV, it must prevent spreadsheet-formula injection.

### 10.4 XLS

Evaluate xlrd for legacy XLS after XLSX and CSV are stable. Treat XLS as a distinct adapter because its binary structure and parser risks differ from XLSX.

---

## 11. PPT and PPTX architecture

### 11.1 PPTX

Use python-pptx to preserve:

- Slide number.
- Slide title.
- Text frames.
- Bullets.
- Tables.
- Speaker notes.
- Image references.
- Chart titles and labels where accessible.

Reading order should consider grouped shapes and their top/left coordinates. Package order alone may not match the visual order.

### 11.2 Visual content

Phase-one PPTX support should extract text, tables, and notes. Later:

- OCR embedded slide images.
- Extract chart data where available.
- Render a slide for visual fallback.
- Record warnings for SmartArt or unsupported objects.

The system should never silently claim complete extraction when unsupported visual content exists.

### 11.3 PPT

Legacy PPT should use the same controlled conversion approach proposed for DOC and remain deferred initially.

---

## 12. Image architecture

### 12.1 Initial support

Prioritize:

- JPEG/JPG
- PNG
- Bounded GIF handling
- TIFF only after validation

### 12.2 Processing

    image validation
      ↓
    dimension and pixel limits
      ↓
    EXIF/metadata extraction
      ↓
    orientation correction
      ↓
    OCR
      ↓
    region-level canonical units

Pillow decompression-bomb warnings should become hard application failures. Animated images need frame-count and total-pixel limits.

### 12.3 SVG

SVG is XML capable of scripts, external references, and active behavior. AURORA must:

- Never render uploaded SVG directly in the browser.
- Disable scripts and external resources.
- Extract safe text nodes.
- Reject entities and remote references.
- Rasterize only through a hardened, no-network process if needed.

### 12.4 PSD

PSD parsing adds layers, masks, embedded resources, high memory usage, and limited research value. PSD should remain deferred until concrete user demand exists.

---

## 13. HTML, JSON, and XML architecture

### 13.1 HTML

Uploaded HTML should be treated as an offline document:

- Do not fetch URLs.
- Remove scripts, styles, forms, and event handlers.
- Ignore or down-weight navigation and boilerplate.
- Preserve headings, paragraphs, lists, tables, and link text.
- Record DOM-path or heading-path provenance.
- Never serve the original HTML unsanitized.

### 13.2 JSON

JSON extraction should preserve structure:

- JSON Pointer paths.
- Object keys.
- Bounded array ranges.
- Primitive value types.
- Nested context.

Apply limits for bytes, nesting depth, key count, array count, and extracted characters.

### 13.3 XML

XML parsing must disable:

- DTD loading.
- External entities.
- Entity expansion.
- Filesystem resolution.
- Network resolution.
- Huge-tree mode.

Content units should retain safe XPath-like locations. Large XML should use incremental parsing.

---

## 14. Source-code ingestion architecture

### 14.1 Baseline

Code is text evidence, never executable input. Baseline support should preserve:

- Relative filename/path.
- Language.
- Line numbers.
- Comments and docstrings.
- Imports as text.
- Function/class declarations.

No compilation, imports, package installation, or project execution should occur.

### 14.2 Chunking

Initial chunks can use:

- Blank-line boundaries.
- Declaration boundaries.
- Bounded line ranges.

Later, Tree-sitter can identify symbols and nested structures. Every chunk should cite exact line ranges and, where possible, its symbol name.

### 14.3 Supported extensions

Start with a small allowlist such as PY, JS, TS, JAVA, C, H, CPP, SQL, HTML, CSS, and shell text. Expand only with tests and an explicit language mapping.

---

## 15. Audio architecture

Audio ingestion should eventually:

1. Validate the container and codec.
2. Inspect duration through ffprobe.
3. Reject excessive duration or unsupported codecs.
4. Normalize audio through isolated FFmpeg.
5. Transcribe with a local or configured provider.
6. Produce sentence/segment units with timestamps.
7. Store language and transcription confidence.
8. Chunk without losing time boundaries.

Local faster-whisper avoids per-request cloud fees but adds model downloads, CPU/memory load, and deployment complexity. Audio should be deferred until document ingestion is stable.

---

## 16. Video architecture

Video is a compound ingestion problem:

- Container and codec validation.
- Audio extraction.
- Speech transcription.
- Optional frame sampling.
- OCR of selected frames.
- Optional visual understanding.

Initial video support should transcribe audio and preserve timestamps. It should not attempt dense frame analysis. Enforce duration, resolution, frame count, bitrate, extracted-audio size, and processing-time limits.

Visual/frame analysis should be a later opt-in capability because it increases cost, privacy exposure, and processing time.

---

## 17. Archive architecture

### 17.1 ZIP

ZIP support should be explicit and restricted:

- Inspect central directory before extraction.
- Reject absolute paths and traversal.
- Reject symbolic links and device paths.
- Set member-count limits.
- Set per-member and total expanded-size limits.
- Set a compression-ratio limit.
- Reject encrypted entries initially.
- Disable nested archives initially.
- Process only allowlisted member types.

Do not flatten an archive into one text document. Create child artifacts or documents with archive-entry provenance:

    archive.zip → reports/2026/sales.xlsx → Sales!B14:F27

### 17.2 RAR

RAR often needs a separate native runtime and creates additional deployment and licensing considerations. Defer it until ZIP is proven safe and useful.

---

## 18. Security threat model

| Threat | Impact | Required controls |
|---|---|---|
| Extension spoofing | Wrong parser or unsafe handling | Signature, MIME, container, and parser validation |
| Executable disguised as document | Code-execution risk | Early executable signature rejection; no executable adapter |
| Corrupt parser input | Crash or vulnerability | Pinned patched libraries, safe errors, parser isolation |
| CPU/memory exhaustion | Denial of service | Per-format budgets, timeouts, process limits |
| Image/PDF decompression bomb | Excessive memory/disk | Page, pixel, DPI, object, and rendered-byte ceilings |
| ZIP traversal | Files written outside temp root | Normalize and validate every member path |
| ZIP bomb | Disk/memory exhaustion | Member, total-size, and ratio limits |
| Recursive archives | Exponential work | Disable initially; later use strict depth |
| XML entity attack | File/network disclosure | No entities, DTD, filesystem, or network resolution |
| Office macro/OLE content | Code execution | Never execute; ignore or reject active content |
| External links | SSRF and data leakage | Never fetch during ingestion |
| Malicious media codec | Native parser exploit | Patched FFmpeg, sandbox, no network, limits |
| Temporary-file leakage | Cross-user exposure | Private random temp directories and guaranteed cleanup |
| Prompt injection in documents | Model instruction manipulation | Treat evidence as untrusted data; delimit and quote it |
| Forged evidence IDs | Cross-workspace leakage | Server-generated citations and authorized resolution |
| Provider data exposure | Privacy/cost risk | Send only bounded required text under explicit provider policy |
| Secret leakage | Credential compromise | No secrets or content in client-visible errors/logs |

Uploaded content must never be able to change AURORA's system instructions, invoke tools, request secrets, or override workspace authorization.

---

## 19. Provenance and citation architecture

### 19.1 Preserve existing citation ownership

Continue:

    RAGResponse → RAGCitation → DocumentChunk

Add:

    DocumentChunk → ChunkProvenance → ContentUnit → Document

ChunkProvenance should record:

- Content unit.
- Start/end character offsets.
- Position within the chunk.
- Primary/secondary source role.

### 19.2 API evolution

Existing PDF responses can continue exposing page_number. Add:

- locator
- locator_label
- source_format
- extraction_method

Example:

    {
      "filename": "Sales.xlsx",
      "locator": {
        "v": 1,
        "type": "xlsx_range",
        "sheet": "Sales",
        "range": "B14:F27"
      },
      "locator_label": "Sales!B14:F27",
      "page_number": null
    }

### 19.3 Source opening

The authoritative citation endpoint should translate a locator into a UI action:

- PDF: open page.
- PPTX: inspect slide.
- XLSX: display sheet/range.
- DOCX: display heading/paragraph context.
- Code: display line range.
- Media: seek to timestamp.

The client receives only server-resolved citation data.

---

## 20. Storage and Cloudflare R2 compatibility

Keep FileStorage unchanged as the primary binary boundary.

### 20.1 Source handling

The orchestrator obtains a BinaryIO through FileStorage.open. When an adapter needs:

- Seek support: wrap or spool the stream.
- A filesystem path: write a bounded private temporary copy.
- Multiple passes: spool once rather than downloading repeatedly.

### 20.2 Derivatives

Optional derivatives can use server-generated keys:

    workspaces/{workspace}/documents/{document}/derivatives/{run}/{artifact}

Possible artifacts:

- Preview thumbnails.
- OCR page renderings.
- Sanitized HTML.
- Normalized audio.
- Conversion output.

Most OCR renderings should be temporary. Persist only artifacts required for navigation or auditing.

### 20.3 R2

An R2 implementation should satisfy the same save, open, delete, and exists contract. Adapters must not know:

- Bucket names.
- R2 credentials.
- Signed URL logic.
- Local filesystem paths.

Tests should include a non-seekable storage stream to expose accidental local-file assumptions.

---

## 21. Chunking implications

### 21.1 Strategy registry

Select a strategy by canonical unit kind:

- Prose: headings, paragraphs, and sentence boundaries.
- PDF: page-bounded prose.
- DOCX: heading sections and paragraphs.
- Tables: row groups with repeated headers.
- Slides: slide or logical region.
- Images: OCR regions and nearby lines.
- Code: symbols and line ranges.
- Media: timestamped sentence windows.
- JSON/XML: bounded structural subtrees.

### 21.2 Provenance preservation

A chunk should not cross provenance boundaries unless the chunk-to-unit relationship can cite every included unit. Avoid joining unrelated spreadsheet ranges or slides merely to reach a target character count.

### 21.3 Determinism

Chunking fingerprints should include:

- Canonical version.
- Adapter version.
- Normalizer version.
- Strategy ID/version.
- Chunk limits.
- Embedding provider/model/dimension.

This permits reliable reindexing and no-op detection.

---

## 22. Embedding and retrieval implications

The existing embedding abstraction, pgvector table, workspace filters, similarity threshold, and RAG preparation can remain.

Changes:

- Read canonical chunks rather than ExtractedPage directly.
- Store source format and unit kind.
- Preserve generic provenance links.
- Continue indexing text only initially.
- Avoid embedding empty metadata and decorative UI text.
- Batch embeddings within provider limits.
- Include only active successful ingestion runs.

OCR text and transcripts can use the existing text embedding model. Visual embeddings are not required for the initial design.

Retrieval may later add metadata filters, but a separate vector database, reranker, or hybrid search system is unnecessary for the ingestion milestone.

---

## 23. Frontend and UX implications

### 23.1 Zero-source composer

Recommended:

- Allow typing when no sources are ready.
- Preserve the typed draft.
- Keep an explanatory banner visible.
- Permit submission.
- Ask the backend for authoritative readiness.
- Return NO_RESEARCH_READY_SOURCES before embedding or generation.
- Show Review sources and Process/Retry actions.

The UI remains useful while the backend remains secure.

### 23.2 Backend enforcement

Before creating a query embedding, the backend should check whether the workspace contains at least one indexed document/chunk. If none exists:

- Return HTTP 409.
- Use a stable error code.
- Do not call the embedding provider.
- Do not call the generation provider.
- Do not create a misleading grounded answer.

If indexed evidence exists but the query retrieves nothing relevant, retain the existing deterministic insufficient-evidence behavior.

### 23.3 Document status

Replace ambiguous terminal states with stage-aware details:

- Uploaded
- Validating
- Extracting native text
- OCR required
- OCR in progress
- Normalizing
- Processed
- Indexing
- Ready
- Failed with actionable reason

### 23.4 Inspection UI

For OCR documents, show:

- Pages successfully recognized.
- Pages with low confidence.
- OCR language.
- Retry with another language, if supported.
- Preview and extracted text side by side where practical.

---

## 24. Dependencies required

### 24.1 Phase-one PDF/OCR

- Existing pypdf for native extraction.
- pypdfium2 for PDF page rendering.
- Pillow for image handling.
- pytesseract Python wrapper.
- Tesseract native engine.
- English, Hindi/Devanagari, and orientation trained data.

### 24.2 Core adapters

- python-docx for DOCX.
- openpyxl for XLSX.
- python-pptx for PPTX.
- beautifulsoup4 for HTML content traversal.
- lxml for robust HTML/XML parsing where configured safely.
- defusedxml for hostile XML defenses.
- charset-normalizer for bounded text-encoding fallback.
- Python standard-library csv, json, zipfile, and XML support where adequate.

### 24.3 Later dependencies

- xlrd for XLS evaluation.
- A selected RTF parser.
- tree-sitter and explicit language grammars.
- psd-tools.
- LibreOffice.
- FFmpeg.
- faster-whisper.
- RAR tooling.

Exact versions should be selected only after a compatibility, security, licensing, and deployment spike. Dependencies with native binaries need documented Windows and production installation procedures.

---

## 25. Budget impact

### 25.1 Low-cost areas

- Native PDF extraction.
- DOCX/PPTX/XLSX parsing.
- TXT, Markdown, CSV, JSON, XML, and HTML parsing.
- PostgreSQL canonical metadata.

These are local and have no per-document provider fee.

### 25.2 OCR

Local Tesseract has no per-page API fee. Costs are:

- CPU time.
- Temporary disk.
- Native runtime installation.
- Language model storage.
- More extracted text sent for embeddings.

### 25.3 Media

Audio and video create the largest costs:

- FFmpeg processing.
- Speech model downloads.
- CPU and memory usage.
- Long-running jobs.
- Optional cloud transcription or visual-analysis fees.

### 25.4 Infrastructure

No Redis, Kafka, Celery, microservices, or GPU infrastructure is required. If durable jobs become necessary, use:

- PostgreSQL job rows.
- Transactional claiming.
- One worker process using the same backend code.
- The existing Docker Compose environment.

---

## 26. Testing strategy

### 26.1 PDF regression

Use:

- A normal searchable PDF.
- A scanned PDF.
- A vector-outline PDF.
- A mixed native/scanned PDF.
- A blank PDF.
- An encrypted PDF.
- A malformed PDF.

The supplied intern.pdf should remain a manual/local acceptance case identified by checksum. CI should use a small project-owned synthetic outline PDF to avoid redistributing third-party content.

### 26.2 Golden canonical tests

Each adapter should have golden expected:

- Content unit order.
- Text.
- Structured data.
- Locator.
- Extraction method.
- Warning codes.

Avoid brittle whole-document OCR snapshots. Assert known phrases, minimum coverage, and provenance.

### 26.3 Security tests

Include:

- MIME/extension mismatch.
- Executable renamed as PDF.
- Fake PDF header.
- Corrupt OOXML.
- XML external entity.
- Excessive nesting.
- Huge CSV field.
- Spreadsheet row bomb.
- Image decompression bomb.
- ZIP traversal.
- ZIP high compression ratio.
- ZIP excessive members.
- Nested archive.
- Parser timeout.
- Temp-file cleanup.

### 26.4 End-to-end tests

Verify:

- Upload → process → index → retrieve → answer.
- Local and simulated R2 streams.
- Workspace isolation.
- Citation resolution.
- PDF page opening.
- Spreadsheet range citation.
- Slide citation.
- Code line citation.
- Zero-source rejection before provider calls.
- English/Hindi OCR.

### 26.5 Performance tests

Measure:

- Processing wall time.
- Peak memory.
- Rendered bytes.
- OCR time/page.
- Extracted characters.
- Embedding batch sizes.
- Database unit/chunk counts.

---

## 27. Migration and backward-compatibility strategy

Use expand, dual-read, backfill, switch, and contract phases.

### 27.1 Expand

Add:

- ingestion_runs
- content_units
- chunk_provenance
- nullable content_unit references
- generic locator response fields

Do not initially remove ExtractedPage or page_number.

### 27.2 Dual write/read

New PDF processing writes canonical PDF page units and temporary compatible page data. The indexer:

- Prefers active canonical content.
- Falls back to ExtractedPage for legacy documents.

### 27.3 Backfill

Convert existing ExtractedPage rows into canonical units:

- kind: page/prose
- extraction method: native_pdf
- locator: pdf_page
- page number retained

No original documents need immediate reprocessing.

### 27.4 Switch

After frontend and API consumers accept generic locators:

- New adapters use only canonical units.
- New chunks use chunk provenance.
- Citation UI renders locator labels.

### 27.5 Contract

Only after tests and data verification:

- Make legacy page links optional.
- Remove page-only constraints.
- Eventually retire ExtractedPage if it no longer provides value.

### 27.6 Atomic activation

Never delete the active content before replacement succeeds. Each run writes staged units. A transaction then:

1. Marks the new run active.
2. Marks the previous run inactive.
3. Invalidates/replaces the index.

Failure leaves the old active content searchable.

---

## 28. Implementation phases

### Phase 1 — AURORA v1.4.1

Canonical ingestion core and robust PDF/OCR:

- Canonical contracts.
- Adapter registry.
- Ingestion runs.
- Generic provenance foundation.
- PDF adapter.
- Quality assessor.
- Page renderer.
- Tesseract OCR.
- Atomic activation.
- intern.pdf regression.
- Stage-aware UI.
- Zero-source backend/UX behavior.

### Phase 2 — AURORA v1.4.2

Core business/research formats:

- TXT.
- Markdown.
- DOCX.
- CSV/TSV.
- XLSX.
- PPTX.
- Format-aware chunks.
- Generic citation labels.

### Phase 3 — AURORA v1.4.3

Structured/web/image ingestion:

- HTML.
- JSON.
- XML.
- JPEG/PNG OCR.
- SVG safety.
- Parser hardening.
- Extraction diagnostics.

### Phase 4 — AURORA v1.4.4

Advanced text and deployment:

- Code-aware ingestion.
- ZIP.
- RTF/XLS evaluation.
- PostgreSQL worker if required.
- R2 verification.
- Performance and adversarial testing.

### Phase 5 — AURORA v1.5

Media and legacy conversion:

- Audio.
- Video transcription.
- Limited frame OCR.
- DOC/PPT conversion.
- Demand-based PSD/RAR evaluation.

---

## 29. MUST HAVE

1. Canonical document and content-unit contracts.
2. Generic provenance locators.
3. Explicit format adapter registry.
4. Provider-neutral FileStorage access.
5. Native-first PDF extraction.
6. Per-page extraction-quality assessment.
7. Automatic bounded OCR fallback.
8. intern.pdf regression coverage.
9. Atomic ingestion activation.
10. Preservation of last known-good content.
11. Strict resource and security limits.
12. Stage-specific processing errors.
13. Server-controlled citations.
14. Backend readiness check before embedding/generation.
15. Clear actionable frontend status.
16. Initial PDF, TXT, Markdown, DOCX, CSV, XLSX, and PPTX support.

---

## 30. SHOULD HAVE

1. HTML, JSON, and XML adapters.
2. JPEG and PNG OCR.
3. Hindi/Devanagari OCR support.
4. OCR confidence and region metadata.
5. Ingestion-run history and metrics.
6. Generic citation navigation.
7. PostgreSQL-backed worker when HTTP execution becomes insufficient.
8. Non-seekable/R2 storage tests.
9. XLS and RTF after evaluation.
10. Restricted ZIP ingestion.
11. Code line-aware ingestion.
12. Adapter and chunk strategy versioning.

---

## 31. NICE TO HAVE

1. Layout-aware OCR.
2. Scanned-table reconstruction.
3. OCR language auto-detection.
4. Tree-sitter symbol chunks.
5. Slide image OCR.
6. Spreadsheet chart summaries.
7. Safe optional visual analysis.
8. User-selectable OCR language/reprocessing.
9. Developer extraction diagnostics.
10. Quality dashboards and evaluation corpora.
11. Search filters by source type and locator.

---

## 32. Explicitly deferred capabilities

- Legacy DOC and PPT conversion.
- RAR ingestion.
- PSD layer extraction.
- Audio transcription.
- Video transcription and frame analysis.
- Recursive archives.
- Encrypted archives.
- Cloud OCR by default.
- Visual embeddings.
- Spreadsheet formula calculation.
- Macro execution.
- Embedded OLE execution.
- Executable/system formats.
- Unknown proprietary binaries.
- GPU infrastructure.
- Redis, Kafka, Celery, and microservices.
- Generic try-every-parser behavior.

Deferred means the architecture should leave an extension point, not that these capabilities are promised in the next milestone.

---

## 33. Risks and tradeoffs

### 33.1 OCR accuracy

OCR can miss small text, confuse characters, and produce incorrect reading order. Confidence, known-text tests, language data, and quality gates reduce but do not eliminate this risk.

### 33.2 Resource use

Rendering and OCR consume more CPU and memory than native extraction. Page/DPI/time limits and selective per-page OCR are essential.

### 33.3 Windows installation

Tesseract is a native runtime and needs documented installation and language-data setup. pypdfium2 wheels reduce PDF rendering friction, but production compatibility still requires testing.

### 33.4 Dependency exposure

Every parser increases supply-chain and malformed-file risk. Add formats incrementally, pin versions, monitor advisories, and isolate native subprocesses.

### 33.5 Schema complexity

Generic provenance is more complex than page_number, but avoiding it would create false citations or force every future format into an inaccurate page model.

### 33.6 Storage growth

Canonical units, structured payloads, OCR coordinates, and derivatives increase storage. Apply retention policies and avoid persisting unnecessary page renderings.

### 33.7 Strict limits

Security limits will reject some legitimate large documents. Limits should be configurable and visible, but never absent.

### 33.8 Background execution

Synchronous processing is simple for development. Durable OCR/media work eventually needs a worker. PostgreSQL-backed jobs keep the architecture small but still introduce deployment and retry considerations.

### 33.9 Legacy formats

DOC/PPT conversion through LibreOffice improves compatibility but adds a large native dependency and parser attack surface. Deferring them is an intentional safety and scope decision.

### 33.10 Evidence quality

Successful parsing does not guarantee useful retrieval. Extraction evaluation, chunking evaluation, and end-to-end RAG evaluation must remain separate quality gates.

---

## Recommended next milestone sequence

### 1. AURORA v1.4.1 — Canonical Ingestion Core and Robust PDF/OCR

This should be the immediate next milestone. It directly resolves the demonstrated intern.pdf limitation and creates the canonical/provenance foundation required by every later adapter.

### 2. AURORA v1.4.2 — Core Document, Spreadsheet, and Presentation Adapters

Add TXT, Markdown, DOCX, CSV/TSV, XLSX, and PPTX using the established adapter contract.

### 3. AURORA v1.4.3 — Structured Web Data, Images, and Generic Citation UX

Add HTML, JSON, XML, JPEG/PNG OCR, safe SVG handling, and frontend rendering for generic locators.

### 4. AURORA v1.4.4 — Code, Archives, R2, and Processing Hardening

Add code-aware ingestion, restricted ZIP, R2 stream verification, optional PostgreSQL worker, and adversarial/performance testing.

### 5. AURORA v1.5 — Media and Controlled Legacy Conversion

Only after the core platform is stable, evaluate audio, video, DOC/PPT conversion, PSD, and RAR according to real user demand.

---

## Final recommendation

Do not add isolated OCR logic directly to the current processing service and do not begin implementing every file type simultaneously.

Approve v1.4.1 as a focused milestone with two inseparable goals:

1. Make real-world PDF ingestion robust through native extraction, per-page quality assessment, rendering, and OCR fallback.
2. Establish canonical content and generic provenance so every future adapter can feed the existing authorized RAG and citation architecture without making RAG aware of file formats.

This approach fixes the immediate failure, preserves AURORA's strongest existing security and RAG foundations, and avoids turning the project into an unmaintainable collection of format-specific conditionals.

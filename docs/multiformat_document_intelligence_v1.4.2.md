# AURORA v1.4.2 — Core Multi-Format Document Intelligence

**Implementation date:** 2 September 2026  
**Database migration:** none; the v1.4.1 canonical schema is reused  
**Previous canonical migration head:** `a5b7c9d1e3f5`

## 1. Outcome

AURORA now supports PDF plus seven new source formats through one ingestion,
indexing, authorized retrieval, RAG, and citation architecture:

```text
PDF + TXT + Markdown + CSV + TSV + DOCX + XLSX + PPTX
    -> extension/MIME/signature validation
    -> allowlisted format adapter
    -> CanonicalDocument and ordered ContentUnit records
    -> one canonical-first chunking and embedding path
    -> one workspace-authorized retrieval path
    -> one grounded RAG path
    -> server-persisted citations with format-native locators
```

Retrieval and RAG contain no adapter-specific branches. They consume usable
canonical units and their generic versioned locators. `ExtractedPage` continues
only as the compatibility view for PDF pages.

## 2. Supported-format matrix

| Format | Accepted extension | Canonical MIME | Primary units | Native provenance | Partial units |
| --- | --- | --- | --- | --- | --- |
| PDF | `.pdf` | `application/pdf` | page | page number and geometry | yes, per page |
| TXT | `.txt` | `text/plain` | text block | line and character range | no |
| Markdown | `.md`, `.markdown` | `text/markdown` | heading section | heading path, line and character range | no |
| CSV | `.csv` | `text/csv` | row group | logical row range | no |
| TSV | `.tsv` | `text/tab-separated-values` | row group | logical row range | no |
| DOCX | `.docx` | Office Open XML Word MIME | heading, paragraph, table, header, footer | structural index, heading path, section | yes, per structural item |
| XLSX | `.xlsx` | Office Open XML Excel MIME | worksheet range | sheet order/name and cell range | yes, per worksheet |
| PPTX | `.pptx` | Office Open XML PowerPoint MIME | slide | slide number and shape order | yes, per slide |

TXT, Markdown, CSV, and TSV can also arrive with safe declared text MIME
aliases where the extension still identifies one unambiguous allowlisted
adapter. Stored metadata uses the canonical MIME listed above.

Not supported in v1.4.2: DOC, PPT, XLS, RTF, HTML, JSON, XML, images, archives,
source-code-aware ingestion, audio, video, OCR of standalone images, embedded
visual understanding, legacy Office conversion, hybrid retrieval, reranking,
GraphRAG, and agentic RAG.

## 3. Adapter boundary and canonical behavior

`AdapterRegistry.resolve_document()` requires one adapter whose declared
extension and validated canonical MIME both match. The processing service then
calls that adapter and persists its result through the existing v1.4.1 staging
and atomic activation path.

Every adapter declares:

- stable adapter ID and version;
- source format, extensions, media types, and unit kinds;
- native extraction, OCR, and partial-result capabilities;
- ordered zero-based unit ordinals;
- normalized text and content type;
- versioned generic locator (`v: 1`);
- extraction method, outcome, safe issue code, and optional parent ordinal;
- bounded structural metadata and sanitized aggregate diagnostics.

Only `USABLE` units create chunks. `SKIPPED` units preserve a meaningful empty
structure such as an empty worksheet or slide. `FAILED` units preserve a local,
recoverable extraction failure without adding untrusted text to diagnostics.
A document becomes `PARTIALLY_PROCESSED` only when usable content and failed
units coexist.

## 4. Format-specific behavior

### TXT

The text adapter accepts UTF-8 and UTF-8 BOM, normalizes mixed newlines, removes
empty blocks, replaces malformed UTF-8 deterministically with a warning, and
splits very long blocks at the configured field limit. Locators use source line
ranges plus normalized character offsets. Content is never executed and URLs
are never fetched.

### Markdown

Markdown units follow heading sections and preserve nested heading paths and
parent relationships. Metadata records heading level, link count, and whether
a fenced code block is present. Formatting-only HTML comments do not become
retrieval evidence. Lists, quotes, tables, links, inline formatting, and code
remain inert source text; none are executed or remotely resolved.

### CSV and TSV

Parsing uses Python's bounded standard CSV parser in strict mode. CSV safely
sniffs comma, tab, semicolon, or pipe delimiters; TSV fixes the delimiter to a
tab. BOM, quoted and escaped fields, multiline fields, headers, missing
headers, Unicode, empty rows, and inconsistent row widths are represented
deterministically. Non-empty rows are grouped using stable source row ranges.

Values beginning with `=`, `+`, `-`, or `@` are preserved as untrusted text and
counted in diagnostics. AURORA never evaluates or rewrites them as formulas.

### DOCX

`python-docx` reads paragraphs and tables in document order. Heading styles
produce hierarchy and parent ordinals; list styles/numbering are metadata.
Tables become readable row/column text rather than an opaque flattened string,
and nested tables are recursively represented within the configured cell
budget. Deduplicated headers and footers use section locators. Inline image
count is metadata only; image pixels and unsupported embedded objects are not
interpreted. No page number is fabricated because DOCX pagination is not
authoritative without a layout engine.

### XLSX

`openpyxl` reads workbooks in read-only mode twice: once for formulas and once
for genuinely available cached values. AURORA never recalculates formulas and
records `formula_calculation_performed: false`. Worksheet units retain sheet
name/order, cell range, cell coordinates, values, and cell-type counts.

Bounded direct OOXML metadata inspection records declared used ranges, merged
ranges, hidden rows/columns, hidden sheet state, defined table ranges, and
external-link count without following external links. Empty sheets are
`SKIPPED`. Huge declared worksheet rectangles fail the global cell budget
before cells are materialized.

### PPTX

`python-pptx` creates one canonical unit per slide in presentation order. Text
boxes retain shape and paragraph order; list indentation, tables, slide title,
and safely available speaker notes are represented. Image, chart, table, and
shape counts are metadata. Empty or visual-only slides are `SKIPPED`, and
`visual_content_interpreted` is explicitly false. No chart/image semantics are
invented and no PDF-style page provenance is created.

## 5. Provenance and user-facing citations

Representative locators are:

```json
{"v": 1, "type": "text_range", "line_start": 1, "line_end": 12}
{"v": 1, "type": "markdown_section", "heading_path": ["Study", "Results"], "line_start": 8, "line_end": 20}
{"v": 1, "type": "delimited_rows", "row_start": 2, "row_end": 51}
{"v": 1, "type": "docx_paragraph", "paragraph": 9, "heading_path": ["Results"]}
{"v": 1, "type": "docx_table", "table": 2, "heading_path": ["Appendix"]}
{"v": 1, "type": "xlsx_range", "sheet": "Research", "sheet_order": 1, "range": "A1:C40"}
{"v": 1, "type": "pptx_slide", "slide": 5}
```

The UI renders these as human labels such as `Lines 1–12`,
`Study › Results`, `Rows 2–51`, `Results · paragraph 9`, `Table 2`,
`Research · A1:C40`, and `Slide 5`. PDF citations remain `Page N`.

## 6. Validation and hostile-input controls

Upload validation combines normalized filename, declared MIME, extension, file
size, and a lightweight signature/container check. It does not try arbitrary
parsers until one succeeds.

Office Open XML packages are inspected before their parser is called:

- ZIP entry and total uncompressed-size limits;
- required `[Content_Types].xml` and format-specific core member;
- no absolute or parent-traversal member paths;
- no encrypted members;
- bounded aggregate expansion ratio;
- rejection of `vbaProject.bin` active content;
- rejection of XML DTD/entity declarations;
- no extraction to the filesystem;
- no macros, OLE programs, subprocess conversion, or remote fetching.

Excel external links are counted but never followed. Formula text is never
calculated. Text and Markdown URLs are never fetched. Parser exceptions, local
paths, credentials, traces, and extracted text do not enter user diagnostics.

## 7. Resource limits

All limits are centralized in `Settings` and `ExtractionLimits` and documented
in `.env.example`:

| Setting | Default | Purpose |
| --- | ---: | --- |
| `DOCUMENT_MAX_SIZE_BYTES` | 10 MiB | upload and stored-file read ceiling |
| `EXTRACTION_MAX_CHARACTERS` | 5,000,000 | canonical extracted-text ceiling |
| `INGESTION_MAX_UNITS` | 10,000 | canonical unit ceiling |
| `TABULAR_MAX_ROWS` | 50,000 | per delimited source/worksheet row bound |
| `TABULAR_MAX_COLUMNS` | 500 | tabular width bound |
| `TABULAR_MAX_CELLS` | 250,000 | document table/cell budget |
| `TABULAR_MAX_FIELD_CHARACTERS` | 100,000 | individual field/cell/block bound |
| `TABULAR_ROWS_PER_UNIT` | 50 | row-group unit size |
| `OOXML_MAX_ARCHIVE_ENTRIES` | 10,000 | package member bound |
| `OOXML_MAX_UNCOMPRESSED_BYTES` | 100 MiB | package expansion bound |
| `DOCX_MAX_PARAGRAPHS` | 20,000 | Word paragraph bound |
| `XLSX_MAX_SHEETS` | 250 | workbook sheet bound |
| `PPTX_MAX_SLIDES` | 1,000 | presentation slide bound |

Existing PDF page, render-pixel, OCR-page, OCR-time, and quality bounds remain
unchanged. Global resource failures fail the document rather than returning a
misleading partial result.

## 8. Dependencies

Three direct parser dependencies were added and pinned according to repository
practice:

- `python-docx==1.2.0`
- `openpyxl==3.1.5`
- `python-pptx==1.0.2`

TXT, Markdown, CSV, and TSV use Python's standard library and the existing text
normalization utilities. No queue, cache, broker, conversion service, search
engine, or second database was introduced.

## 9. Frontend behavior

The file picker advertises only PDF, TXT, Markdown, CSV, TSV, DOCX, XLSX, and
PPTX. The normal user flow remains upload -> automatic processing -> automatic
indexing. Manual Process/Index controls remain recovery actions.

The source register displays format-aware structure (pages, sheets, slides, or
canonical units). PDF retains the authorized inline preview. Other formats show
safe metadata, native status, and an authorized download action rather than
calling the PDF preview endpoint.

## 10. Automated verification

The reusable compliance assertions now validate adapter capability identity,
ordered canonical output, outcomes, locators, content types, normalized text,
diagnostic counts, absence of local paths/traces/credentials, and no extracted
text leakage.

Deterministic generated fixtures cover:

- UTF-8/BOM, Unicode, invalid UTF-8, mixed newlines, empty content, and Markdown hierarchy;
- quoted/multiline fields, headers, formula-like text, malformed CSV, and row bounds;
- DOCX headings, paragraphs, lists, tables, headers, Unicode, and local partial failure;
- XLSX formulas, cached-value distinction, types, merged ranges, hidden structure,
  defined tables, empty/failed sheets, and bounds;
- PPTX titles, text, tables, notes, empty slides, and local partial failure;
- malformed and active-content Office packages;
- PDF regression and the existing canonical/indexing contract;
- all eight formats uploaded, processed, indexed, retrieved, and cited together
  in one authorized workspace with deterministic local providers.

No external Gemini request or private user document is required by this test.

Final verification on 2 September 2026:

- backend: **246 passed, 2 skipped**; the two skips are explicit opt-in live
  provider tests;
- heterogeneous adapter/integration module: **41 passed** as part of the full
  suite (including the eight-format workspace flow);
- frontend: **18 passed**;
- TypeScript: clean (`tsc --noEmit`);
- ESLint: clean;
- Next.js optimized production build: successful;
- Python compile check: clean;
- development database revision: `a5b7c9d1e3f5 (head)`;
- Alembic declared head: `a5b7c9d1e3f5 (head)`.

## 11. Migration status

No schema change was required. Format-neutral content units, JSON locators,
nullable page relationships, active ingestion runs, canonical chunk links, and
generic RAG citations already represent all v1.4.2 formats. Creating
format-specific chunk or index tables would have weakened that architecture.

## 12. Known limitations and deferred work

- Processing and indexing remain synchronous HTTP work; async ingestion,
  progress, cancellation, and worker infrastructure are the next operational
  concern.
- DOCX pagination is intentionally absent, and complex floating-layout reading
  order depends on `python-docx` capabilities.
- XLSX formulas are never recalculated; cached values appear only when genuinely
  present in the package. Rich styling and visual spreadsheet layout are not
  retrieval evidence.
- PPTX image/chart meaning is not interpreted. Visual-only slides are preserved
  as skipped structural units and metadata.
- CSV header/delimiter inference is deterministic but heuristic.
- Invalid UTF-8 text is replacement-normalized with an explicit warning rather
  than guessed as an arbitrary legacy encoding.
- Standalone images/OCR, more OCR languages, HTML/JSON/XML, code-aware parsing,
  legacy Office conversion, archives, advanced previews, hybrid retrieval,
  reranking, query rewriting, GraphRAG, and agentic RAG remain deferred.

## 13. Recommended next milestone

The next coherent milestone is **v1.4.3 — asynchronous ingestion execution,
progress, cancellation, retry policy, and ingestion observability**. It should
move the now-proven multi-format adapters behind a durable job boundary without
changing the canonical, indexing, retrieval, RAG, or citation contracts.

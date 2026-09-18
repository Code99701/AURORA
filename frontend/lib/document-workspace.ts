import type { Document, RAGSource } from "@/lib/types";

export const SUPPORTED_DOCUMENT_ACCEPT = [
  "application/pdf",
  "text/plain",
  "text/markdown",
  "text/csv",
  "text/tab-separated-values",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  ".pdf",
  ".txt",
  ".md",
  ".markdown",
  ".csv",
  ".tsv",
  ".docx",
  ".xlsx",
  ".pptx",
].join(",");

const formatNames: Record<string, string> = {
  "application/pdf": "PDF",
  "text/plain": "TXT",
  "text/markdown": "Markdown",
  "text/csv": "CSV",
  "text/tab-separated-values": "TSV",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "XLSX",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": "PPTX",
};

export function documentFormatName(document: Pick<Document, "content_type">) {
  return formatNames[document.content_type] || "Document";
}

function countLabel(value: unknown, singular: string, plural = `${singular}s`) {
  return typeof value === "number"
    ? `${value} ${value === 1 ? singular : plural}`
    : null;
}

export function documentStructureSummary(document: Document) {
  if (document.content_type === "application/pdf") {
    return countLabel(document.page_count, "page") || "Pages pending";
  }
  const summary = document.processing_summary || {};
  if (document.content_type.endsWith("presentationml.presentation")) {
    return countLabel(summary.slide_count, "slide") || "Slides pending";
  }
  if (document.content_type.endsWith("spreadsheetml.sheet")) {
    return countLabel(summary.sheet_count, "sheet") || "Sheets pending";
  }
  return countLabel(summary.usable_unit_count, "content unit") || "Processing pending";
}

function numberAt(locator: Record<string, unknown>, key: string) {
  const value = locator[key];
  return typeof value === "number" ? value : null;
}

function stringAt(locator: Record<string, unknown>, key: string) {
  const value = locator[key];
  return typeof value === "string" && value ? value : null;
}

export function formatSourceLocation(source: RAGSource) {
  if (source.page_number !== null) return `Page ${source.page_number}`;
  const locator = source.locator;
  if (!locator || typeof locator.type !== "string") return "Source location";
  const lineStart = numberAt(locator, "line_start");
  const lineEnd = numberAt(locator, "line_end");
  const rowStart = numberAt(locator, "row_start");
  const rowEnd = numberAt(locator, "row_end");
  const headingPath = Array.isArray(locator.heading_path)
    ? locator.heading_path.filter((item): item is string => typeof item === "string")
    : [];
  if (locator.type === "text_range") {
    return lineStart === lineEnd ? `Line ${lineStart}` : `Lines ${lineStart}–${lineEnd}`;
  }
  if (locator.type === "markdown_section") {
    return headingPath.length ? headingPath.join(" › ") : `Lines ${lineStart}–${lineEnd}`;
  }
  if (locator.type === "delimited_rows") {
    return rowStart === rowEnd ? `Row ${rowStart}` : `Rows ${rowStart}–${rowEnd}`;
  }
  if (locator.type === "docx_paragraph") {
    const paragraph = numberAt(locator, "paragraph");
    return headingPath.length
      ? `${headingPath.join(" › ")} · paragraph ${paragraph}`
      : `Paragraph ${paragraph}`;
  }
  if (locator.type === "docx_table") return `Table ${numberAt(locator, "table")}`;
  if (locator.type === "docx_header" || locator.type === "docx_footer") {
    return `${locator.type === "docx_header" ? "Header" : "Footer"} · section ${numberAt(locator, "section")}`;
  }
  if (locator.type === "xlsx_range") {
    return `${stringAt(locator, "sheet") || "Worksheet"} · ${stringAt(locator, "range") || "used range"}`;
  }
  if (locator.type === "xlsx_sheet") return stringAt(locator, "sheet") || "Worksheet";
  if (locator.type === "pptx_slide") return `Slide ${numberAt(locator, "slide")}`;
  return locator.type.replaceAll("_", " ");
}

export type DocumentFilter = "all" | "ready" | "needs_action" | "failed";
export type DocumentSort = "newest" | "name";

function matchesFilter(document: Document, filter: DocumentFilter) {
  if (filter === "ready") return document.indexing_status === "INDEXED";
  if (filter === "failed") {
    return document.status === "FAILED" || document.indexing_status === "FAILED";
  }
  if (filter === "needs_action") {
    return document.status === "UPLOADED"
      || document.status === "FAILED"
      || (["PROCESSED", "PARTIALLY_PROCESSED"].includes(document.status)
        && document.indexing_status !== "INDEXED");
  }
  return true;
}

const processingIssueMessages: Record<string, string> = {
  NO_EXTRACTABLE_TEXT: "No usable text was found in this source.",
  ENCRYPTED_PDF: "This PDF is password protected. Remove the password, then upload it again.",
  PDF_PAGE_LIMIT: "This PDF exceeds the configured page limit. Split it into smaller sources.",
  DOCUMENT_SIZE_LIMIT: "This source exceeds the configured processing size limit.",
  DOCUMENT_EXTRACTION_ERROR: "This document is damaged or cannot be read safely. Export a fresh copy and retry.",
  DOCX_PARSE_ERROR: "This Word document is damaged or cannot be read safely.",
  XLSX_PARSE_ERROR: "This Excel workbook is damaged or cannot be read safely.",
  PPTX_PARSE_ERROR: "This PowerPoint presentation is damaged or cannot be read safely.",
  DELIMITED_TEXT_PARSE_ERROR: "This CSV or TSV source is malformed and could not be read safely.",
  TABULAR_ROW_LIMIT: "This tabular source exceeds the configured row limit.",
  TABULAR_COLUMN_LIMIT: "This tabular source exceeds the configured column limit.",
  TABULAR_CELL_LIMIT: "This document exceeds the configured table-cell limit.",
  TABULAR_FIELD_LIMIT: "A field in this document exceeds the configured text limit.",
  DOCX_PARAGRAPH_LIMIT: "This Word document exceeds the configured paragraph limit.",
  PPTX_SLIDE_LIMIT: "This presentation exceeds the configured slide limit.",
  XLSX_SHEET_LIMIT: "This workbook exceeds the configured worksheet limit.",
  CONTENT_UNIT_LIMIT: "This source produces more structural units than the safe processing limit.",
  EXTRACTED_CONTENT_LIMIT: "This source contains more extractable text than the safe processing limit.",
  PDF_EXTRACTION_ERROR: "This PDF is damaged or cannot be read safely. Export a fresh copy and retry.",
  PDF_PAGE_EXTRACTION_ERROR: "One or more PDF pages could not be read.",
  PDF_RENDER_ERROR: "One or more visual pages could not be rendered safely.",
  PDF_RENDER_RESOURCE_LIMIT: "This PDF needs more rendering resources than the safe limit allows.",
  OCR_TIMEOUT: "Text recognition timed out. Retry, or upload a clearer scan.",
  OCR_NO_USABLE_TEXT: "Text recognition could not recover trustworthy text.",
  OCR_ENGINE_UNAVAILABLE: "Text recognition is unavailable on the server. Check the OCR installation.",
  OCR_LANGUAGE_UNAVAILABLE: "The required OCR language data is unavailable on the server.",
  EMBEDDING_PROVIDER_ERROR: "The extracted evidence could not be indexed. Check the embedding provider and retry.",
  NO_INDEXABLE_TEXT: "No usable extracted evidence was available for indexing.",
};

export function documentIssueMessage(document: Document) {
  const code = document.processing_error || document.indexing_error;
  return code ? (processingIssueMessages[code] || "This source could not complete processing. Retry or review the server diagnostics.") : "";
}

export function partialProcessingMessage(document: Document) {
  if (document.status !== "PARTIALLY_PROCESSED") return "";
  const failed = document.processing_summary.failed_unit_count;
  const usable = document.processing_summary.usable_unit_count;
  return `${typeof usable === "number" ? usable : "Some"} content units are usable; ${typeof failed === "number" ? failed : "some"} could not be recovered.`;
}

export function filterAndSortDocuments(
  documents: Document[],
  query: string,
  filter: DocumentFilter,
  sort: DocumentSort,
) {
  const normalizedQuery = query.trim().toLocaleLowerCase();
  return documents
    .filter((document) => !normalizedQuery
      || document.original_filename.toLocaleLowerCase().includes(normalizedQuery))
    .filter((document) => matchesFilter(document, filter))
    .sort((left, right) => sort === "name"
      ? left.original_filename.localeCompare(right.original_filename)
      : new Date(right.created_at).getTime() - new Date(left.created_at).getTime());
}

export function clampDocumentPage(page: number, pageCount: number | null) {
  const normalized = Number.isFinite(page) ? Math.trunc(page) : 1;
  return Math.min(Math.max(normalized, 1), Math.max(pageCount || 1, 1));
}

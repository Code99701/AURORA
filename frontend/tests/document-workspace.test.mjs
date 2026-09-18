import assert from "node:assert/strict";
import test from "node:test";

import {
  clampDocumentPage,
  documentFormatName,
  documentStructureSummary,
  filterAndSortDocuments,
  formatSourceLocation,
  SUPPORTED_DOCUMENT_ACCEPT,
} from "../lib/document-workspace.ts";

function source(overrides) {
  return {
    id: crypto.randomUUID(),
    workspace_id: crypto.randomUUID(),
    uploaded_by: 1,
    original_filename: "Source.pdf",
    content_type: "application/pdf",
    file_size: 1200,
    checksum: "a".repeat(64),
    status: "PROCESSED",
    page_count: 4,
    processing_error: null,
    processed_at: "2026-08-20T10:00:00Z",
    indexing_status: "INDEXED",
    indexing_error: null,
    indexed_at: "2026-08-20T10:01:00Z",
    embedding_model: "test",
    embedding_dimension: 768,
    created_at: "2026-08-20T09:00:00Z",
    updated_at: "2026-08-20T10:01:00Z",
    ...overrides,
  };
}

test("filters the source register without mixing lifecycle meanings", () => {
  const ready = source({ original_filename: "Ready Paper.pdf" });
  const uploaded = source({ original_filename: "New Notes.pdf", status: "UPLOADED", indexing_status: "NOT_INDEXED" });
  const failed = source({ original_filename: "Failed Scan.pdf", status: "FAILED", indexing_status: "FAILED" });

  assert.deepEqual(filterAndSortDocuments([ready, uploaded, failed], "paper", "all", "newest"), [ready]);
  assert.deepEqual(filterAndSortDocuments([ready, uploaded, failed], "", "ready", "newest"), [ready]);
  assert.deepEqual(new Set(filterAndSortDocuments([ready, uploaded, failed], "", "needs_action", "newest")), new Set([uploaded, failed]));
  assert.deepEqual(filterAndSortDocuments([ready, uploaded, failed], "", "failed", "newest"), [failed]);
});

test("sorts filenames and clamps citation pages to document bounds", () => {
  const beta = source({ original_filename: "Beta.pdf" });
  const alpha = source({ original_filename: "Alpha.pdf" });

  assert.deepEqual(filterAndSortDocuments([beta, alpha], "", "all", "name"), [alpha, beta]);
  assert.equal(clampDocumentPage(-4, 9), 1);
  assert.equal(clampDocumentPage(7, 9), 7);
  assert.equal(clampDocumentPage(99, 9), 9);
  assert.equal(clampDocumentPage(Number.NaN, null), 1);
});

test("reports format-aware document structure without fabricating pages", () => {
  assert.equal(documentFormatName(source({ content_type: "text/markdown" })), "Markdown");
  assert.equal(documentStructureSummary(source({ page_count: 4 })), "4 pages");
  assert.equal(documentStructureSummary(source({
    content_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    page_count: null,
    processing_summary: { sheet_count: 3 },
  })), "3 sheets");
  assert.equal(documentStructureSummary(source({
    content_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    page_count: null,
    processing_summary: { slide_count: 1 },
  })), "1 slide");
  assert.equal(documentStructureSummary(source({
    content_type: "text/plain",
    page_count: null,
    processing_summary: { usable_unit_count: 2 },
  })), "2 content units");
});

test("formats native citation locators for human readers", () => {
  const citation = (locator, page_number = null) => ({ locator, page_number });
  assert.equal(formatSourceLocation(citation({ type: "pdf_page", page: 7 }, 7)), "Page 7");
  assert.equal(formatSourceLocation(citation({ type: "text_range", line_start: 3, line_end: 8 })), "Lines 3–8");
  assert.equal(formatSourceLocation(citation({ type: "markdown_section", heading_path: ["Study", "Findings"] })), "Study › Findings");
  assert.equal(formatSourceLocation(citation({ type: "delimited_rows", row_start: 2, row_end: 12 })), "Rows 2–12");
  assert.equal(formatSourceLocation(citation({ type: "docx_paragraph", paragraph: 9, heading_path: ["Results"] })), "Results · paragraph 9");
  assert.equal(formatSourceLocation(citation({ type: "docx_table", table: 2 })), "Table 2");
  assert.equal(formatSourceLocation(citation({ type: "xlsx_range", sheet: "Research", range: "A1:C4" })), "Research · A1:C4");
  assert.equal(formatSourceLocation(citation({ type: "pptx_slide", slide: 5 })), "Slide 5");
});

test("advertises exactly the v1.4.2 upload families", () => {
  for (const extension of [".pdf", ".txt", ".md", ".markdown", ".csv", ".tsv", ".docx", ".xlsx", ".pptx"]) {
    assert.ok(SUPPORTED_DOCUMENT_ACCEPT.includes(extension));
  }
  assert.equal(SUPPORTED_DOCUMENT_ACCEPT.includes(".png"), false);
  assert.equal(SUPPORTED_DOCUMENT_ACCEPT.includes(".doc,"), false);
});

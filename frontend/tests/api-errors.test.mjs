import assert from "node:assert/strict";
import test from "node:test";

import {
  GENERIC_API_ERROR_MESSAGE,
  formatUploadApiError,
} from "../lib/api-errors.ts";

test("turns an upstream proxy failure into an actionable upload error", () => {
  assert.equal(
    formatUploadApiError(GENERIC_API_ERROR_MESSAGE, 500),
    "Source upload failed: the backend service did not return a usable response. Confirm it is running and try again.",
  );
});

test("preserves safe backend upload details", () => {
  assert.equal(
    formatUploadApiError("Document storage is unavailable", 503),
    "Source upload failed: Document storage is unavailable",
  );
  assert.equal(
    formatUploadApiError("Document exceeds the 10485760-byte upload limit", 422),
    "Source upload failed: Document exceeds the 10485760-byte upload limit",
  );
});

test("normalizes a proxy-level payload limit response", () => {
  assert.equal(
    formatUploadApiError(GENERIC_API_ERROR_MESSAGE, 413),
    "Source upload failed: the file exceeds the configured upload limit.",
  );
  assert.equal(
    formatUploadApiError("Request Entity Too Large", 413),
    "Source upload failed: the file exceeds the configured upload limit.",
  );
});

import assert from "node:assert/strict";
import test from "node:test";

import { SSEParser } from "../lib/sse.ts";

test("parses fragmented streaming frames without losing deltas", () => {
  const parser = new SSEParser();
  assert.deepEqual(parser.push("event: state\r\ndata: {\"phase\":\"stream"), []);
  assert.deepEqual(parser.push("ing\"}\r\n\r\nevent: text_delta\ndata: {\"text\":\"Aur"), [
    { event: "state", data: '{"phase":"streaming"}' },
  ]);
  assert.deepEqual(parser.push("ora\"}\n\n"), [
    { event: "text_delta", data: '{"text":"Aurora"}' },
  ]);
});

test("joins multiline data and ignores comments", () => {
  const parser = new SSEParser();
  assert.deepEqual(parser.push(": keepalive\nevent: custom\ndata: first\ndata: second\n\n"), [
    { event: "custom", data: "first\nsecond" },
  ]);
});

test("flushes a final complete frame without a trailing separator", () => {
  const parser = new SSEParser();
  parser.push("event: complete\ndata: {\"ok\":true}");
  assert.deepEqual(parser.finish(), [
    { event: "complete", data: '{"ok":true}' },
  ]);
});

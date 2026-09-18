import assert from "node:assert/strict";
import test from "node:test";

import {
  advanceStreamingState,
  canStartStreaming,
  isNearStreamBottom,
} from "../lib/streaming-state.ts";

test("models the successful streaming lifecycle", () => {
  let state = "submitting";
  state = advanceStreamingState(state, { type: "phase", phase: "retrieving" });
  state = advanceStreamingState(state, { type: "phase", phase: "streaming" });
  state = advanceStreamingState(state, { type: "phase", phase: "finalizing" });
  state = advanceStreamingState(state, { type: "complete" });
  assert.equal(state, "idle");
});

test("supports deterministic insufficient evidence without a streaming phase", () => {
  let state = advanceStreamingState("submitting", { type: "phase", phase: "retrieving" });
  state = advanceStreamingState(state, { type: "phase", phase: "finalizing" });
  assert.equal(advanceStreamingState(state, { type: "complete" }), "idle");
});

test("rejects malformed transitions and exposes failure state", () => {
  assert.equal(
    advanceStreamingState("submitting", { type: "phase", phase: "finalizing" }),
    "error",
  );
  assert.equal(advanceStreamingState("streaming", { type: "error" }), "error");
});

test("prevents blank and duplicate submissions", () => {
  assert.equal(canStartStreaming(false, "conversation-id", "question"), true);
  assert.equal(canStartStreaming(true, "conversation-id", "question"), false);
  assert.equal(canStartStreaming(false, null, "question"), false);
  assert.equal(canStartStreaming(false, "conversation-id", "   "), false);
});

test("auto-follow only remains active near the bottom", () => {
  assert.equal(isNearStreamBottom(1000, 620, 300), true);
  assert.equal(isNearStreamBottom(1000, 300, 300), false);
});

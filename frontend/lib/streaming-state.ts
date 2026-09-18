type StreamingPhaseState = "submitting" | "retrieving" | "streaming" | "finalizing";

export type StreamingState = "idle" | StreamingPhaseState | "error";

export function canStartStreaming(
  activeRequest: boolean,
  conversationId: string | null,
  content: string,
) {
  return !activeRequest && Boolean(conversationId) && Boolean(content.trim());
}

export function isNearStreamBottom(
  scrollHeight: number,
  scrollTop: number,
  clientHeight: number,
  threshold = 96,
) {
  return scrollHeight - scrollTop - clientHeight < threshold;
}

export function advanceStreamingState(
  current: StreamingState,
  event:
    | { type: "phase"; phase: Exclude<StreamingPhaseState, "submitting"> }
    | { type: "complete" }
    | { type: "error" },
): StreamingState {
  if (event.type === "error") return "error";
  if (event.type === "complete") return current === "finalizing" ? "idle" : "error";
  const allowed: Record<Exclude<StreamingPhaseState, "submitting">, StreamingState[]> = {
    retrieving: ["submitting"],
    streaming: ["retrieving"],
    finalizing: ["retrieving", "streaming"],
  };
  return allowed[event.phase].includes(current) ? event.phase : "error";
}

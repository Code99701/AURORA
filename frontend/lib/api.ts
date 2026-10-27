import { SSEParser } from "@/lib/sse";
import { GENERIC_API_ERROR_MESSAGE } from "@/lib/api-errors";
import type { Conversation, ConversationMessage, ConversationStreamEvent, ConversationTurn, Document, RAGResponse, User, Workspace } from "@/lib/types";

const API_ROOT = "/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function codeFromPayload(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object" || !("detail" in payload)) return undefined;
  const detail = (payload as { detail: unknown }).detail;
  if (!detail || typeof detail !== "object" || !("code" in detail)) return undefined;
  const code = (detail as { code: unknown }).code;
  return typeof code === "string" ? code : undefined;
}

type StreamErrorPayload = {
  code?: string;
  message?: string;
  retryable?: boolean;
};

function messageFromPayload(payload: unknown): string {
  if (!payload || typeof payload !== "object" || !("detail" in payload)) {
    return GENERIC_API_ERROR_MESSAGE;
  }
  const detail = (payload as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item && typeof (item as { msg: unknown }).msg === "string") {
          const loc = (item as { loc?: unknown[] }).loc;
          const field = Array.isArray(loc) && loc.length > 1 ? String(loc[loc.length - 1]) : "";
          const msg = (item as { msg: string }).msg.replace(/^Value error,\s*/i, "");
          return field ? `${field}: ${msg}` : msg;
        }
        return null;
      })
      .filter(Boolean);
    if (messages.length > 0) return messages.join(". ");
  }
  if (detail && typeof detail === "object" && "message" in detail) {
    if ("code" in detail && (detail as { code: unknown }).code === "RAG_RETRIEVAL_ERROR") {
      return "AURORA could not retrieve evidence. Confirm that this workspace has an indexed document, then try again.";
    }
    const message = (detail as { message: unknown }).message;
    if (typeof message === "string") return message;
  }
  return "Please review the form and try again.";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      // A safe fallback is returned below.
    }
    throw new ApiError(messageFromPayload(payload), response.status, codeFromPayload(payload));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function requestBlob(path: string, signal?: AbortSignal): Promise<Blob> {
  const response = await fetch(`${API_ROOT}${path}`, {
    credentials: "include",
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    let payload: unknown = null;
    try { payload = await response.json(); } catch { /* safe fallback below */ }
    throw new ApiError(messageFromPayload(payload), response.status, codeFromPayload(payload));
  }
  return response.blob();
}

async function streamConversationMessage(
  workspaceId: string,
  conversationId: string,
  content: string,
  answerLanguage: string | null,
  onEvent: (event: ConversationStreamEvent) => void,
  signal?: AbortSignal,
): Promise<ConversationTurn> {
  const response = await fetch(
    `${API_ROOT}/workspaces/${workspaceId}/conversations/${conversationId}/messages/stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({
        content,
        top_k: 5,
        answer_language: answerLanguage || null,
      }),
      credentials: "include",
      cache: "no-store",
      signal,
    },
  );
  if (!response.ok) {
    let payload: unknown = null;
    try { payload = await response.json(); } catch { /* safe fallback below */ }
    throw new ApiError(messageFromPayload(payload), response.status, codeFromPayload(payload));
  }
  if (!response.body) throw new ApiError("AURORA did not return a readable stream.", 502);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SSEParser();
  let completed: ConversationTurn | null = null;

  const processFrames = (frames: ReturnType<SSEParser["push"]>) => {
    for (const frame of frames) {
      let payload: unknown;
      try {
        payload = JSON.parse(frame.data);
      } catch {
        throw new ApiError("AURORA returned a malformed stream.", 502);
      }
      if (frame.event === "state") {
        const phase = (payload as { phase?: unknown }).phase;
        if (phase === "retrieving" || phase === "streaming" || phase === "finalizing") {
          onEvent({ event: "state", phase });
        } else {
          throw new ApiError("AURORA returned an unknown stream state.", 502);
        }
      } else if (frame.event === "text_delta") {
        const text = (payload as { text?: unknown }).text;
        if (typeof text !== "string") throw new ApiError("AURORA returned an invalid text update.", 502);
        onEvent({ event: "text_delta", text });
      } else if (frame.event === "complete") {
        completed = payload as ConversationTurn;
        onEvent({ event: "complete", turn: completed });
      } else if (frame.event === "error") {
        const error = payload as StreamErrorPayload;
        throw new ApiError(
          typeof error.message === "string" ? error.message : "AURORA could not complete this streamed response.",
          502,
          error.code,
        );
      }
    }
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      processFrames(parser.push(decoder.decode(value, { stream: true })));
    }
    processFrames(parser.push(decoder.decode()));
    processFrames(parser.finish());
  } catch (error) {
    await reader.cancel().catch(() => undefined);
    throw error;
  } finally {
    reader.releaseLock();
  }
  if (!completed) throw new ApiError("The response stream ended before it was saved.", 502);
  return completed;
}

export const api = {
  health: () => request<{ status: string; app_name: string; version: string }>("/health"),
  me: () => request<User>("/auth/me"),
  authProviders: () =>
    request<{ google: { enabled: boolean } }>("/auth/providers"),
  login: (email: string, password: string) =>
    request<{ status: string; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  register: (email: string, password: string, displayName: string) =>
    request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name: displayName }),
    }),
  logout: () => request<{ status: string }>("/auth/logout", { method: "POST" }),
  workspaces: () => request<{ items: Workspace[]; total: number }>("/workspaces"),
  workspace: (workspaceId: string) => request<Workspace>(`/workspaces/${workspaceId}`),
  createWorkspace: (name: string, description: string) =>
    request<Workspace>("/workspaces", {
      method: "POST",
      body: JSON.stringify({ name, description: description || null }),
    }),
  deleteWorkspace: (workspaceId: string) =>
    request<void>(`/workspaces/${workspaceId}`, {
      method: "DELETE",
    }),
  documents: (workspaceId: string) =>
    request<{ items: Document[]; total: number }>(`/workspaces/${workspaceId}/documents`),
  document: (workspaceId: string, documentId: string) =>
    request<Document>(`/workspaces/${workspaceId}/documents/${documentId}`),
  documentPreview: (workspaceId: string, documentId: string, signal?: AbortSignal) =>
    requestBlob(`/workspaces/${workspaceId}/documents/${documentId}/preview`, signal),
  uploadDocument: (workspaceId: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<Document>(`/workspaces/${workspaceId}/documents`, {
      method: "POST",
      body,
    });
  },
  processDocument: (workspaceId: string, documentId: string) =>
    request<Document>(`/workspaces/${workspaceId}/documents/${documentId}/process`, {
      method: "POST",
    }),
  indexDocument: (workspaceId: string, documentId: string) =>
    request<Document>(`/workspaces/${workspaceId}/documents/${documentId}/index`, {
      method: "POST",
    }),
  deleteDocument: (workspaceId: string, documentId: string) =>
    request<void>(`/workspaces/${workspaceId}/documents/${documentId}`, {
      method: "DELETE",
    }),
  citationSource: (workspaceId: string, citationId: string) =>
    request<RAGResponse["sources"][number]>(`/workspaces/${workspaceId}/rag/citations/${citationId}`),
  rag: (workspaceId: string, query: string, answerLanguage: string | null) =>
    request<RAGResponse>(`/workspaces/${workspaceId}/rag`, {
      method: "POST",
      body: JSON.stringify({
        query,
        top_k: 5,
        answer_language: answerLanguage || null,
      }),
    }),
  conversations: (workspaceId: string) =>
    request<{ items: Conversation[]; total: number }>(`/workspaces/${workspaceId}/conversations`),
  conversation: (workspaceId: string, conversationId: string) =>
    request<Conversation>(`/workspaces/${workspaceId}/conversations/${conversationId}`),
  createConversation: (workspaceId: string) =>
    request<Conversation>(`/workspaces/${workspaceId}/conversations`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  renameConversation: (workspaceId: string, conversationId: string, title: string) =>
    request<Conversation>(`/workspaces/${workspaceId}/conversations/${conversationId}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  deleteConversation: (workspaceId: string, conversationId: string) =>
    request<void>(`/workspaces/${workspaceId}/conversations/${conversationId}`, {
      method: "DELETE",
    }),
  conversationMessages: (workspaceId: string, conversationId: string) =>
    request<{ items: ConversationMessage[]; total: number }>(`/workspaces/${workspaceId}/conversations/${conversationId}/messages`),
  sendConversationMessage: (workspaceId: string, conversationId: string, content: string, answerLanguage: string | null) =>
    request<ConversationTurn>(`/workspaces/${workspaceId}/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content, top_k: 5, answer_language: answerLanguage || null }),
    }),
  streamConversationMessage,
};

export type User = {
  id: number;
  email: string;
  display_name: string;
  system_role: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type Workspace = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  created_by: number;
};

export type DocumentStatus = "UPLOADED" | "PROCESSING" | "PROCESSED" | "PARTIALLY_PROCESSED" | "FAILED";
export type IndexingStatus = "NOT_INDEXED" | "INDEXING" | "INDEXED" | "FAILED";

export type Document = {
  id: string;
  workspace_id: string;
  uploaded_by: number;
  original_filename: string;
  content_type: string;
  file_size: number;
  checksum: string;
  status: DocumentStatus;
  page_count: number | null;
  processing_error: string | null;
  processing_stage: string | null;
  processing_summary: Record<string, unknown>;
  processed_at: string | null;
  indexing_status: IndexingStatus;
  indexing_error: string | null;
  indexed_at: string | null;
  embedding_model: string | null;
  embedding_dimension: number | null;
  created_at: string;
  updated_at: string;
};

export type RAGSource = {
  citation_id: string;
  position: number;
  document_id: string;
  chunk_id: string;
  filename: string;
  page_number: number | null;
  similarity: number;
  locator?: Record<string, unknown> | null;
  extraction_method?: string | null;
};

export type RAGResponse = {
  response_id: string;
  answer: string;
  sources: RAGSource[];
  insufficient_evidence: boolean;
  model: string | null;
};

export type Conversation = {
  id: string;
  workspace_id: string;
  user_id: number;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ConversationMessage = {
  id: string;
  conversation_id: string;
  role: "USER" | "ASSISTANT";
  content: string;
  created_at: string;
  response_id: string | null;
  sources: RAGSource[];
  insufficient_evidence: boolean;
  model: string | null;
  latency_ms: number | null;
};

export type ConversationTurn = {
  conversation: Conversation;
  user_message: ConversationMessage;
  assistant_message: ConversationMessage;
};

export type StreamingPhase =
  | "submitting"
  | "retrieving"
  | "streaming"
  | "finalizing";

export type ConversationStreamEvent =
  | { event: "state"; phase: Exclude<StreamingPhase, "submitting"> }
  | { event: "text_delta"; text: string }
  | { event: "complete"; turn: ConversationTurn };

"use client";

import {
  AlertTriangle,
  ArrowDown,
  Bookmark,
  Check,
  ChevronDown,
  Copy,
  Download,
  FileSearch,
  FileText,
  Globe,
  Layers,
  LoaderCircle,
  Paperclip,
  Pencil,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  Square,
  Trash2,
} from "lucide-react";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Conversation, ConversationMessage, RAGSource, StreamingPhase } from "@/lib/types";
import { advanceStreamingState, canStartStreaming, isNearStreamBottom } from "@/lib/streaming-state";
import { formatSourceLocation, SUPPORTED_DOCUMENT_ACCEPT } from "@/lib/document-workspace";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import { ChatMarkdown } from "./chat-markdown";
import { SourceViewerPanel } from "./source-viewer-panel";
import styles from "./research-desk.module.css";

const LANGUAGES = [
  { value: "", label: "Match question" },
  { value: "English", label: "English" },
  { value: "Hindi", label: "हिन्दी" },
];

function formatConversationDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date(value));
}

function confidence(similarity: number) {
  return `${Math.max(0, Math.min(100, similarity * 100)).toFixed(0)}% match`;
}

function streamingStatus(state: "idle" | StreamingPhase | "error") {
  if (state === "submitting") return "Connecting…";
  if (state === "retrieving") return "Searching your documents…";
  if (state === "streaming") return "Generating answer…";
  if (state === "finalizing") return "Saving answer…";
  return "";
}

function Evidence({
  sources,
  onOpenSource,
}: {
  sources: RAGSource[];
  onOpenSource: (source: RAGSource) => void;
}) {
  const [showAll, setShowAll] = useState(false);

  const grouped = useMemo(() => {
    const map = new Map<string, { filename: string; sources: RAGSource[] }>();
    for (const src of sources) {
      const key = src.document_id || src.filename;
      if (!map.has(key)) {
        map.set(key, { filename: src.filename, sources: [] });
      }
      map.get(key)!.sources.push(src);
    }
    return Array.from(map.values());
  }, [sources]);

  const displayedSources = showAll ? sources : sources.slice(0, 3);
  const totalCount = sources.length;

  return (
    <div className={styles.sourcesContainer} aria-label="Evidence sources">
      <div className={styles.sourcesHeader}>
        <span className={styles.sourcesLabel}>Sources ({totalCount})</span>
        {totalCount > 3 && (
          <button
            type="button"
            className={styles.toggleSourcesBtn}
            onClick={() => setShowAll(!showAll)}
          >
            {showAll ? "Show less" : `Show all ${totalCount} sources`}
          </button>
        )}
      </div>

      <div className={styles.groupedSourcesList}>
        {grouped.map((group) => {
          const groupSources = showAll
            ? group.sources
            : group.sources.filter((s) => displayedSources.includes(s));
          if (groupSources.length === 0) return null;

          return (
            <div key={group.filename} className={styles.docSourceRow}>
              <span className={styles.docSourceFilename} title={group.filename}>
                <FileText size={13} className={styles.docSourceIcon} />
                <span>{group.filename}</span>
              </span>
              <div className={styles.pageChipsWrap}>
                {groupSources.map((source) => {
                  const isPptx =
                    source.locator?.type === "pptx_slide" ||
                    /\.(pptx?|odp)$/i.test(source.filename || "");
                  const pageLabel = isPptx
                    ? `Slide ${source.page_number || 1}`
                    : `p. ${source.page_number || 1}`;

                  return (
                    <button
                      key={source.citation_id || source.position}
                      type="button"
                      className={styles.pageChip}
                      onClick={() => onOpenSource(source)}
                      aria-label={`Open ${source.filename}, ${pageLabel}`}
                      title={`Open ${source.filename} at ${pageLabel} (${confidence(source.similarity)})`}
                    >
                      <span className={styles.pageChipPos}>[{source.position}]</span>
                      <span>{pageLabel}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TurnActions({
  content,
  onRegenerate,
  onSave,
  isSaved,
  onExport,
  isLatest = false,
}: {
  content: string;
  onRegenerate: () => void;
  onSave: () => void;
  isSaved: boolean;
  onExport: () => void;
  isLatest?: boolean;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  return (
    <div
      className={`${styles.turnActions} ${isLatest ? styles.latestActions : ""}`}
      aria-label="Answer actions"
    >
      <button
        type="button"
        className={styles.actionBtn}
        onClick={handleCopy}
        aria-label="Copy answer to clipboard"
      >
        {copied ? <Check size={13} className={styles.checkIcon} /> : <Copy size={13} />}
        <span>{copied ? "Copied" : "Copy"}</span>
      </button>

      <button
        type="button"
        className={styles.actionBtn}
        onClick={onRegenerate}
        aria-label="Regenerate this response"
      >
        <RefreshCw size={13} />
        <span>Regenerate</span>
      </button>

      <button
        type="button"
        className={`${styles.actionBtn} ${isSaved ? styles.savedAction : ""}`}
        onClick={onSave}
        aria-label="Save answer"
      >
        <Bookmark size={13} />
        <span>{isSaved ? "Saved" : "Save"}</span>
      </button>

      <button
        type="button"
        className={styles.actionBtn}
        onClick={onExport}
        aria-label="Export response as Markdown"
      >
        <Download size={13} />
        <span>Export</span>
      </button>
    </div>
  );
}


export function ResearchDesk({
  workspaceId,
  initialConversationId,
  onOpenSource,
  onOpenDocuments,
}: {
  workspaceId: string;
  initialConversationId?: string;
  onOpenSource: (source: RAGSource) => void;
  onOpenDocuments: () => void;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const endRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const drawerRef = useRef<HTMLDivElement>(null);
  const initialSelectionRef = useRef(initialConversationId);
  const activeRequestRef = useRef<AbortController | null>(null);
  const nearBottomRef = useRef(true);

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [listState, setListState] = useState<"loading" | "loaded" | "error">("loading");
  const [listError, setListError] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [messageState, setMessageState] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [messageError, setMessageError] = useState("");
  const [messageReloadToken, setMessageReloadToken] = useState(0);
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState("");
  const [streamState, setStreamState] = useState<"idle" | StreamingPhase | "error">("idle");
  const [retryContent, setRetryContent] = useState("");
  const [showLatest, setShowLatest] = useState(false);
  const [creating, setCreating] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<Conversation | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [renameError, setRenameError] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Conversation | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [sourceSummary, setSourceSummary] = useState<{ total: number; indexed: number } | null>(null);
  const [savedTurns, setSavedTurns] = useState<Set<string>>(new Set());
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);

  // Source Viewer Side Panel state
  const [activeViewer, setActiveViewer] = useState<{
    sources: RAGSource[];
    index: number;
    content?: string;
  } | null>(null);

  const submitting = !["idle", "error"].includes(streamState);
  const hasNoReadySources = sourceSummary !== null && sourceSummary.indexed === 0;

  const loadConversations = useCallback(async (preferredId?: string) => {
    setListState("loading");
    setListError("");
    try {
      const { items } = await api.conversations(workspaceId);
      let next = items;
      let selection = preferredId && items.some((item) => item.id === preferredId) ? preferredId : null;
      if (preferredId && !selection) {
        try {
          const requested = await api.conversation(workspaceId, preferredId);
          next = [requested, ...items];
          selection = requested.id;
        } catch {
          setMessageError("That conversation is unavailable or you no longer have access to it.");
        }
      }
      selection ||= next[0]?.id || null;
      setConversations(next);
      setMessageState(selection ? "loading" : "idle");
      if (!selection) setMessages([]);
      setSelectedId(selection);
      setListState("loaded");
    } catch (caught) {
      setListError(caught instanceof ApiError ? caught.message : "Conversations could not be loaded.");
      setListState("error");
    }
  }, [workspaceId]);

  useEffect(() => {
    let cancelled = false;
    api.documents(workspaceId)
      .then((data) => {
        if (cancelled) return;
        const total = data.total;
        const indexed = data.items.filter((item) => item.indexing_status === "INDEXED").length;
        setSourceSummary({ total, indexed });
      })
      .catch(() => {
        if (!cancelled) setSourceSummary(null);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  useEffect(() => {
    loadConversations(initialSelectionRef.current);
  }, [loadConversations]);

  useEffect(() => {
    if (!selectedId) {
      queueMicrotask(() => {
        setMessages([]);
        setMessageState("idle");
      });
      return;
    }

    const targetConversationId = selectedId;
    let cancelled = false;
    queueMicrotask(() => {
      if (!cancelled) {
        setMessageState("loading");
        setMessageError("");
      }
    });
    api.conversationMessages(workspaceId, targetConversationId)

      .then((data) => {
        if (cancelled) return;
        setMessages(data.items);
        setMessageState("loaded");
        setShowLatest(false);
      })
      .catch((caught) => {
        if (cancelled) return;
        setMessageError(caught instanceof ApiError ? caught.message : "Could not load conversation history.");
        setMessageState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, selectedId, messageReloadToken]);

  useEffect(() => {
    if (messageState === "loaded") {
      endRef.current?.scrollIntoView({ block: "nearest" });
      nearBottomRef.current = true;
    }
  }, [messageState, selectedId]);

  useEffect(() => () => activeRequestRef.current?.abort(), []);

  function adjustTextareaHeight(textarea: HTMLTextAreaElement) {
    textarea.style.height = "auto";
    const nextHeight = Math.min(textarea.scrollHeight, 180);
    textarea.style.height = `${nextHeight}px`;
  }

  function handleOpenSourceViewer(source: RAGSource, allSources: RAGSource[], turnContent?: string) {
    const list = allSources.length > 0 ? allSources : [source];
    const idx = list.findIndex(
      (s) => s.citation_id === source.citation_id || s.position === source.position
    );
    setActiveViewer({
      sources: list,
      index: idx >= 0 ? idx : 0,
      content: turnContent,
    });
  }

  function selectConversation(conversationId: string) {
    if (submitting) return;
    setMessageState("loading");
    setMessageError("");
    setShowLatest(false);
    setMessages([]);
    setSelectedId(conversationId);
    setDrawerOpen(false);
    setActiveViewer(null);
    router.replace(`${pathname}?view=research&conversation=${conversationId}`, { scroll: false });
  }

  async function createConversation() {
    if (submitting) return;
    setCreating(true);
    setListError("");
    try {
      const conversation = await api.createConversation(workspaceId);
      setConversations((current) => [conversation, ...current]);
      selectConversation(conversation.id);
    } catch (caught) {
      setListError(caught instanceof ApiError ? caught.message : "A new conversation could not be created.");
      setListState("error");
    } finally {
      setCreating(false);
    }
  }

  function scrollToLatest(behavior: ScrollBehavior = "smooth") {
    const viewport = viewportRef.current;
    if (viewport) viewport.scrollTo({ top: viewport.scrollHeight, behavior });
    nearBottomRef.current = true;
    setShowLatest(false);
  }

  function trackScroll() {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const nearBottom = isNearStreamBottom(viewport.scrollHeight, viewport.scrollTop, viewport.clientHeight);
    nearBottomRef.current = nearBottom;
    setShowLatest(!nearBottom && (submitting || messages.length > 0));
  }

  function stopStreaming() {
    activeRequestRef.current?.abort();
    activeRequestRef.current = null;
    setStreamState("idle");
  }

  function toggleSaveTurn(turnId: string) {
    setSavedTurns((prev) => {
      const next = new Set(prev);
      if (next.has(turnId)) next.delete(turnId);
      else next.add(turnId);
      return next;
    });
  }

  function exportTurn(message: ConversationMessage) {
    const selectedTitle = conversations.find((c) => c.id === selectedId)?.title || "AURORA Research";
    const citationsList = message.sources.length > 0
      ? `\n\n### Sources Cited\n` + message.sources.map((s) => `- **[${s.position}]** \`${s.filename}\` (${formatSourceLocation(s)})`).join("\n")
      : "";
    const markdown = `# ${selectedTitle}\n\n${message.content}${citationsList}\n\n---\n*Grounded research provided by AURORA*`;
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${selectedTitle.toLowerCase().replace(/[^a-z0-9]/g, "-")}-answer.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleDirectFileUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploadingDoc(true);
    try {
      const doc = await api.uploadDocument(workspaceId, file);
      await api.processDocument(workspaceId, doc.id);
      await api.indexDocument(workspaceId, doc.id);
      // Refresh source summary
      const updatedDocs = await api.documents(workspaceId);
      const total = updatedDocs.total;
      const indexed = updatedDocs.items.filter((item) => item.indexing_status === "INDEXED").length;
      setSourceSummary({ total, indexed });
    } catch (caught) {
      setMessageError(caught instanceof ApiError ? caught.message : "Failed to upload and index document.");
    } finally {
      setUploadingDoc(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function runStream(rawContent: string) {
    const content = rawContent.trim();
    if (!canStartStreaming(Boolean(activeRequestRef.current), selectedId, content)) return;
    if (!selectedId) return;

    const controller = new AbortController();
    activeRequestRef.current = controller;
    const requestConversationId = selectedId;
    const timestamp = new Date().toISOString();
    const requestId = crypto.randomUUID();
    const temporaryUserId = `optimistic-user-${requestId}`;
    const temporaryAssistantId = `streaming-assistant-${requestId}`;

    const optimisticUser: ConversationMessage = {
      id: temporaryUserId,
      conversation_id: requestConversationId,
      role: "USER",
      content,
      created_at: timestamp,
      response_id: null,
      sources: [],
      insufficient_evidence: false,
      model: null,
      latency_ms: null,
    };

    const streamingAssistant: ConversationMessage = {
      ...optimisticUser,
      id: temporaryAssistantId,
      role: "ASSISTANT",
      content: "",
    };

    let pendingText = "";
    let animationFrame = 0;
    const flushText = () => {
      animationFrame = 0;
      if (!pendingText) return;
      const delta = pendingText;
      pendingText = "";
      setMessages((current) =>
        current.map((message) =>
          message.id === temporaryAssistantId
            ? { ...message, content: message.content + delta }
            : message
        )
      );
      window.requestAnimationFrame(() => {
        if (nearBottomRef.current) scrollToLatest("auto");
        else setShowLatest(true);
      });
    };

    setStreamState("submitting");
    setRetryContent(content);
    setMessageError("");
    setQuery("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setMessages((current) => [...current, optimisticUser, streamingAssistant]);
    window.requestAnimationFrame(() => scrollToLatest("smooth"));

    try {
      const turn = await api.streamConversationMessage(
        workspaceId,
        requestConversationId,
        content,
        language || null,
        (event) => {
          if (event.event === "state") {
            setStreamState((current) => advanceStreamingState(current, { type: "phase", phase: event.phase }));
          }
          if (event.event === "text_delta") {
            pendingText += event.text;
            if (!animationFrame) animationFrame = window.requestAnimationFrame(flushText);
          }
        },
        controller.signal
      );
      if (animationFrame) window.cancelAnimationFrame(animationFrame);
      pendingText = "";
      setMessages((current) => [
        ...current.filter((message) => message.id !== temporaryUserId && message.id !== temporaryAssistantId),
        turn.user_message,
        turn.assistant_message,
      ]);
      setConversations((current) => [turn.conversation, ...current.filter((item) => item.id !== turn.conversation.id)]);
      setRetryContent("");
      setStreamState((current) => advanceStreamingState(current, { type: "complete" }));
      window.requestAnimationFrame(() => {
        if (nearBottomRef.current) scrollToLatest("smooth");
        else setShowLatest(true);
      });
    } catch (caught) {
      if (animationFrame) window.cancelAnimationFrame(animationFrame);
      pendingText = "";
      if (controller.signal.aborted) {
        setStreamState("idle");
        return;
      }
      setMessages((current) =>
        current.filter((message) => message.id !== temporaryUserId && message.id !== temporaryAssistantId)
      );
      setMessageError(caught instanceof ApiError ? caught.message : "The stream encountered an unexpected network disruption.");
      setStreamState("error");
    } finally {
      activeRequestRef.current = null;
    }
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    void runStream(query);
  }

  async function rename(event: React.FormEvent) {
    event.preventDefault();
    if (!renameTarget || renaming) return;
    const title = renameTitle.trim();
    if (!title) {
      setRenameError("The title must not be blank.");
      return;
    }
    setRenaming(true);
    setRenameError("");
    try {
      const updated = await api.renameConversation(workspaceId, renameTarget.id, title);
      setConversations((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setRenameTarget(null);
    } catch (caught) {
      setRenameError(caught instanceof ApiError ? caught.message : "The conversation could not be renamed.");
    } finally {
      setRenaming(false);
    }
  }

  async function remove() {
    if (!deleteTarget || deleting) return;
    setDeleting(true);
    setListError("");
    try {
      await api.deleteConversation(workspaceId, deleteTarget.id);
      const remaining = conversations.filter((item) => item.id !== deleteTarget.id);
      setConversations(remaining);
      const nextSelection = remaining[0]?.id || null;
      setDeleteTarget(null);
      if (selectedId === deleteTarget.id) {
        if (nextSelection) selectConversation(nextSelection);
        else {
          setSelectedId(null);
          setMessages([]);
          setMessageState("idle");
          router.replace(`${pathname}?view=research`, { scroll: false });
        }
      }
    } catch (caught) {
      setListError(caught instanceof ApiError ? caught.message : "The conversation could not be deleted.");
    } finally {
      setDeleting(false);
    }
  }

  const selected = conversations.find((item) => item.id === selectedId) || null;

  const conversationPanel = (
    <aside className={styles.conversationPanel} aria-label="Research conversations">
      <div className={styles.panelTop}>
        <span className={styles.kicker}>CONVERSATIONS</span>
        <button
          className={styles.newChatBtn}
          type="button"
          onClick={() => void createConversation()}
          disabled={creating || submitting}
          aria-label="New conversation"
          title="New conversation"
        >
          {creating ? <LoaderCircle className="spin" size={15} /> : <Plus size={15} />}
        </button>
      </div>

      {listError && <div className="error-banner" role="alert">{listError}</div>}

      <div className={styles.conversationList}>
        {listState === "loading" ? (
          <div className={styles.listLoading} role="status">
            <LoaderCircle className="spin" size={16} />
            <span>Loading threads…</span>
          </div>
        ) : null}
        {listState === "error" ? (
          <button className="button button-secondary" type="button" onClick={() => void loadConversations(selectedId || undefined)}>
            <RefreshCw size={15} /> Retry list
          </button>
        ) : null}
        {listState === "loaded" && conversations.length === 0 ? (
          <div className={styles.listEmpty}>
            <strong>No conversations yet</strong>
            <span>Click + above to start a thread with grounded citations.</span>
          </div>
        ) : null}

        {conversations.map((conversation) => (
          <div
            className={`${styles.conversationRow} ${conversation.id === selectedId ? styles.activeConversation : ""}`}
            key={conversation.id}
          >
            <button
              className={styles.conversationSelect}
              type="button"
              onClick={() => selectConversation(conversation.id)}
              disabled={submitting}
              aria-current={conversation.id === selectedId ? "true" : undefined}
            >
              <strong className={styles.convTitle}>{conversation.title}</strong>
              <span className={styles.convMeta}>
                {formatConversationDate(conversation.updated_at)}
                {sourceSummary && sourceSummary.indexed > 0 ? ` · ${sourceSummary.indexed} sources` : ""}
              </span>
            </button>
            <div className={styles.rowTools}>
              <button
                type="button"
                disabled={submitting}
                onClick={() => {
                  setRenameTarget(conversation);
                  setRenameTitle(conversation.title);
                  setRenameError("");
                }}
                aria-label={`Rename ${conversation.title}`}
                title="Rename"
              >
                <Pencil size={13} />
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={() => setDeleteTarget(conversation)}
                aria-label={`Delete ${conversation.title}`}
                title="Delete"
              >
                <Trash2 size={13} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </aside>
  );

  return (
    <div className={`${styles.desk} ${activeViewer ? styles.deskWithViewer : ""}`}>
      {drawerOpen && (
        <button
          className={styles.drawerBackdrop}
          type="button"
          onClick={() => setDrawerOpen(false)}
          aria-label="Close conversations"
        />
      )}
      <div
        ref={drawerRef}
        className={`${styles.mobileDrawer} ${drawerOpen ? styles.drawerOpen : ""}`}
        aria-hidden={!drawerOpen}
      >
        {conversationPanel}
      </div>
      <div className={styles.desktopPanel}>{conversationPanel}</div>

      {/* Main Chat Center Area */}
      <section
        className={styles.chat}
        aria-label="Research chat"
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragOver(false);
          const file = e.dataTransfer.files?.[0];
          if (file) {
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            if (fileInputRef.current) {
              fileInputRef.current.files = dataTransfer.files;
              fileInputRef.current.dispatchEvent(new Event("change", { bubbles: true }));
            }
          }
        }}
      >
        {isDragOver && (
          <div className={styles.dragOverlay}>
            <Paperclip size={24} />
            <strong>Drop document here to index & research</strong>
          </div>
        )}

        <div className={styles.messageViewport} ref={viewportRef} onScroll={trackScroll} aria-busy={messageState === "loading" || submitting}>
          {submitting ? <div className="sr-only" role="status" aria-live="polite">{streamingStatus(streamState)}</div> : null}

          {!selected && listState === "loaded" ? (
            <EmptyState
              icon={FileSearch}
              title="No conversation selected"
              description="Select an existing thread or start a new conversation to ask questions about your documents."
              action={
                <button className="button button-primary" type="button" onClick={() => void createConversation()}>
                  <Plus size={16} /> New conversation
                </button>
              }
            />
          ) : null}

          {selected && messageState === "loading" ? (
            <div className={styles.messageLoading} role="status">
              <LoaderCircle className="spin" size={20} />
              <span>Loading conversation…</span>
            </div>
          ) : null}

          {selected && messageState === "error" ? (
            <div className={styles.historyError}>
              <div className="error-banner" role="alert">{messageError}</div>
              <button
                className="button button-secondary"
                type="button"
                onClick={() => {
                  setMessageState("loading");
                  setMessageReloadToken((val) => val + 1);
                }}
              >
                <RefreshCw size={15} /> Retry
              </button>
            </div>
          ) : null}

          {selected && messageState === "loaded" && messages.length === 0 ? (
            <EmptyState
              icon={FileSearch}
              title="Ask your first question"
              description="Type a question below. AURORA will find relevant evidence from your documents and provide cited answers."
            />
          ) : null}

          {messages.length > 0 ? (
            <ol className={styles.messages} aria-label="Conversation messages">
              {messages.map((message, index) => {
                const streaming = message.id.startsWith("streaming-assistant-");
                const isLastAssistant = message.role === "ASSISTANT" && index === messages.length - 1;

                if (message.role === "USER") {
                  return (
                    <li className={styles.userTurn} key={message.id}>
                      <article aria-label="Your question" className={styles.userArticle}>
                        <div className={styles.userBubble}>{message.content}</div>
                      </article>
                    </li>
                  );
                }

                const prevUser = index > 0 ? messages[index - 1] : null;

                return (
                  <li className={`${styles.assistantTurn} ${streaming ? styles.streamingTurn : ""}`} key={message.id}>
                    <article aria-label={streaming ? "Answer in progress" : "Grounded answer"} aria-live={streaming ? "polite" : undefined}>
                      <div className={styles.assistantMeta}>
                        <span className={styles.auroraAvatar} aria-hidden="true">
                          <Sparkles size={13} />
                        </span>
                        <strong className={styles.auroraName}>AURORA</strong>
                        <span className={styles.auroraGroundedBadge}>
                          {streaming
                            ? "Typing…"
                            : message.sources.length > 0
                            ? `Grounded in ${message.sources.length} ${message.sources.length === 1 ? "source" : "sources"}`
                            : "Grounded answer"}
                        </span>
                      </div>

                      {message.insufficient_evidence && (
                        <div className={styles.refusalCard} role="alert">
                          <AlertTriangle size={18} className={styles.refusalIcon} />
                          <div className={styles.refusalBody}>
                            <strong className={styles.refusalTitle}>Not enough evidence</strong>
                            <p className={styles.refusalText}>
                              No uploaded source met the confidence threshold for this query.
                            </p>
                            <span className={styles.refusalHint}>
                              Try naming a document, page or slide, or ask for a summary of a specific section.
                            </span>
                          </div>
                        </div>
                      )}

                      {streaming && !message.content ? (
                        <div className={styles.streamPlaceholder} aria-hidden="true">
                          <LoaderCircle size={15} className="spin" />
                          <div>
                            <strong>{streamingStatus(streamState)}</strong>
                          </div>
                        </div>
                      ) : null}

                      {message.content ? (
                        <div className={styles.messageContent}>
                          <ChatMarkdown
                            content={message.content}
                            sources={message.sources}
                            onOpenSource={(src) => handleOpenSourceViewer(src, message.sources, message.content)}
                          />
                        </div>
                      ) : null}

                      {streaming && message.content ? <span className={styles.streamCursor} aria-hidden="true" /> : null}

                      {!message.insufficient_evidence && message.sources.length > 0 && (
                        <Evidence
                          sources={message.sources}
                          onOpenSource={(src) => handleOpenSourceViewer(src, message.sources, message.content)}
                        />
                      )}

                      {!streaming && message.content && (
                        <TurnActions
                          content={message.content}
                          onRegenerate={() => prevUser && void runStream(prevUser.content)}
                          onSave={() => toggleSaveTurn(message.id)}
                          isSaved={savedTurns.has(message.id)}
                          onExport={() => exportTurn(message)}
                          isLatest={isLastAssistant}
                        />
                      )}
                    </article>
                  </li>
                );
              })}
            </ol>
          ) : null}

          <div ref={endRef} />
        </div>

        {showLatest && (
          <button className={styles.jumpLatest} type="button" onClick={() => scrollToLatest("smooth")}>
            <ArrowDown size={14} /> Latest response
          </button>
        )}

        {/* Compact Floating Composer Card */}
        <div className={styles.composerCardWrap}>
          {hasNoReadySources && (
            <div className={styles.sourceNotice} role="status">
              <div>
                <strong>No ready documents</strong>
                <span>
                  {sourceSummary.total
                    ? "Process and index your uploaded documents before asking questions."
                    : "Upload documents to start researching."}
                </span>
              </div>
              <button className="button button-secondary" type="button" onClick={onOpenDocuments}>
                Go to Documents
              </button>
            </div>
          )}

          {messageError && messageState !== "error" && (
            <div className={`${styles.streamError} error-banner`} role="alert">
              <span>{messageError}</span>
              {streamState === "error" && retryContent && (
                <button className="button button-secondary" type="button" onClick={() => void runStream(retryContent)}>
                  <RefreshCw size={13} /> Retry last question
                </button>
              )}
            </div>
          )}

          <form className={styles.composerCard} onSubmit={submit}>
            <textarea
              ref={textareaRef}
              className={styles.composerInput}
              id="conversation-query"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                adjustTextareaHeight(e.target);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              maxLength={4000}
              placeholder={
                hasNoReadySources
                  ? "Upload and index documents to start researching…"
                  : selected
                  ? "Ask a question about your documents…"
                  : "Create a conversation to ask a question"
              }
              disabled={!selected || submitting}
              rows={1}
              required
            />

            <div className={styles.composerCardBottom}>
              <div className={styles.composerPills}>
                <button
                  type="button"
                  className={styles.composerIconBtn}
                  onClick={() => fileInputRef.current?.click()}
                  title="Upload document"
                  disabled={uploadingDoc}
                  aria-label="Upload document"
                >
                  {uploadingDoc ? <LoaderCircle className="spin" size={15} /> : <Paperclip size={15} />}
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={SUPPORTED_DOCUMENT_ACCEPT}
                  style={{ display: "none" }}
                  onChange={(e) => void handleDirectFileUpload(e)}
                />

                <div className={styles.pillDropdown} title="Document scope">
                  <Layers size={13} className={styles.pillIcon} />
                  <span>All documents</span>
                  <ChevronDown size={11} className={styles.pillChevron} />
                </div>

                <div className={styles.pillSelectWrap}>
                  <Globe size={13} className={styles.pillIcon} />
                  <select
                    className={styles.pillSelect}
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    disabled={!selected || submitting}
                    aria-label="Answer language preference"
                  >
                    {LANGUAGES.map((item) => (
                      <option value={item.value} key={item.label}>
                        Answer in: {item.label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={11} className={styles.pillChevron} />
                </div>
              </div>

              <div className={styles.composerRight}>
                <span className={styles.composerHint}>Enter to send · Shift+Enter for new line</span>
                {submitting ? (
                  <button
                    type="button"
                    className={styles.stopButton}
                    onClick={stopStreaming}
                    title="Stop generation"
                  >
                    <Square size={13} />
                    <span>Stop</span>
                  </button>
                ) : (
                  <button
                    className={styles.sendButton}
                    type="submit"
                    disabled={!selected || submitting || !query.trim()}
                  >
                    <span>Send</span>
                    <Send size={14} />
                  </button>
                )}
              </div>
            </div>
          </form>
        </div>
      </section>

      {/* Pane 3: Source Viewer Panel */}
      {activeViewer && (
        <SourceViewerPanel
          sources={activeViewer.sources}
          activeSourceIndex={activeViewer.index}
          onSelectSourceIndex={(idx) =>
            setActiveViewer((prev) => (prev ? { ...prev, index: idx } : null))
          }
          onClose={() => setActiveViewer(null)}
          onOpenDocument={(docId, page) =>
            onOpenSource({ document_id: docId, page_number: page } as RAGSource)
          }
          associatedContent={activeViewer.content}
        />
      )}

      {renameTarget && (
        <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && !renaming && setRenameTarget(null)}>
          <form className="modal" role="dialog" aria-modal="true" onSubmit={rename}>
            <h2>Rename conversation</h2>
            <div className="field">
              <label htmlFor="conversation-title">Conversation title</label>
              <input
                className="input"
                id="conversation-title"
                value={renameTitle}
                onChange={(e) => setRenameTitle(e.target.value)}
                maxLength={120}
                autoFocus
                required
              />
            </div>
            {renameError && <div className="error-banner" role="alert">{renameError}</div>}
            <div className="modal-actions">
              <button className="button button-ghost" type="button" onClick={() => setRenameTarget(null)} disabled={renaming}>Cancel</button>
              <button className="button button-primary" type="submit" disabled={renaming || !renameTitle.trim()}>
                {renaming ? "Saving…" : "Save title"}
              </button>
            </div>
          </form>
        </div>
      )}

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete this conversation?"
        description={deleteTarget ? `${deleteTarget.title} and its history will be permanently deleted.` : ""}
        confirmLabel="Delete conversation"
        busy={deleting}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => void remove()}
      />
    </div>
  );
}

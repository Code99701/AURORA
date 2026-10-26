"use client";

import { ArrowDown, BookOpenCheck, ExternalLink, FileSearch, LoaderCircle, Menu, Pencil, Plus, RefreshCw, Send, Trash2, X } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Conversation, ConversationMessage, RAGSource, StreamingPhase } from "@/lib/types";
import { advanceStreamingState, canStartStreaming, isNearStreamBottom } from "@/lib/streaming-state";
import { formatSourceLocation } from "@/lib/document-workspace";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/shared/empty-state";
import styles from "./research-desk.module.css";

const LANGUAGES = [
  { value: "", label: "Match my question" },
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
  if (state === "submitting") return "Opening the secure response stream";
  if (state === "retrieving") return "Retrieving fresh authorized evidence";
  if (state === "streaming") return "Grounded answer is arriving";
  if (state === "finalizing") return "Saving the answer and authoritative citations";
  return "";
}

function Evidence({
  sources,
  workspaceId,
  onOpenSource,
}: {
  sources: RAGSource[];
  workspaceId: string;
  onOpenSource: (source: RAGSource) => void;
}) {
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function openSource(citationId: string) {
    setOpeningId(citationId);
    setError("");
    try {
      const authoritativeSource = await api.citationSource(workspaceId, citationId);
      onOpenSource(authoritativeSource);
    } catch (caught) {
      setError(caught instanceof ApiError
        ? caught.message
        : "This evidence source is no longer available.");
    } finally {
      setOpeningId(null);
    }
  }

  return (
    <div className={styles.evidence} aria-label="Evidence sources">
      <div className={styles.evidenceHeading}><BookOpenCheck size={16} /><strong>{sources.length} verified {sources.length === 1 ? "source" : "sources"}</strong><span>Open the cited location</span></div>
      {sources.map((source) => (
        <button className={styles.source} type="button" key={source.citation_id} onClick={() => void openSource(source.citation_id)} disabled={Boolean(openingId)} aria-label={`Open ${source.filename}, ${formatSourceLocation(source)}`}>
          <span>[{source.position}]</span>
          <div><strong>{source.filename}</strong><small>{formatSourceLocation(source)} · {confidence(source.similarity)}</small></div>
          {openingId === source.citation_id ? <LoaderCircle className="spin" size={16} /> : <ExternalLink size={16} />}
        </button>
      ))}
      {error ? <div className={styles.evidenceError} role="alert">{error} Try another citation or refresh the conversation.</div> : null}
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
    const timer = window.setTimeout(() => void loadConversations(initialSelectionRef.current), 0);
    return () => window.clearTimeout(timer);
  }, [loadConversations]);

  useEffect(() => {
    let cancelled = false;
    api.documents(workspaceId)
      .then(({ items }) => {
        if (!cancelled) setSourceSummary({
          total: items.length,
          indexed: items.filter((item) => item.indexing_status === "INDEXED").length,
        });
      })
      .catch(() => { if (!cancelled) setSourceSummary(null); });
    return () => { cancelled = true; };
  }, [workspaceId]);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    api.conversationMessages(workspaceId, selectedId)
      .then(({ items }) => { if (!cancelled) { setMessages(items); setMessageState("loaded"); } })
      .catch((caught) => { if (!cancelled) { setMessageError(caught instanceof ApiError ? caught.message : "Message history could not be loaded."); setMessageState("error"); } });
    return () => { cancelled = true; };
  }, [messageReloadToken, selectedId, workspaceId]);

  useEffect(() => {
    if (messageState === "loaded") {
      endRef.current?.scrollIntoView({ block: "nearest" });
      nearBottomRef.current = true;
    }
  }, [messageState, selectedId]);

  useEffect(() => () => activeRequestRef.current?.abort(), []);

  useEffect(() => {
    if (!drawerOpen) return;
    drawerRef.current?.querySelector<HTMLButtonElement>('button[aria-label="Close conversations"]')?.focus();
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDrawerOpen(false);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [drawerOpen]);

  useEffect(() => {
    if (!renameTarget) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !renaming) setRenameTarget(null);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [renameTarget, renaming]);

  function selectConversation(conversationId: string) {
    if (submitting) return;
    setMessageState("loading");
    setMessageError("");
    setShowLatest(false);
    setMessages([]);
    setSelectedId(conversationId);
    setDrawerOpen(false);
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
      setMessages((current) => current.map((message) =>
        message.id === temporaryAssistantId
          ? { ...message, content: message.content + delta }
          : message,
      ));
      window.requestAnimationFrame(() => {
        if (nearBottomRef.current) scrollToLatest("auto");
        else setShowLatest(true);
      });
    };

    setStreamState("submitting");
    setRetryContent(content);
    setMessageError("");
    setQuery("");
    setMessages((current) => [...current, optimisticUser, streamingAssistant]);
    window.requestAnimationFrame(() => scrollToLatest("smooth"));
    try {
      const turn = await api.streamConversationMessage(
        workspaceId,
        requestConversationId,
        content,
        language || null,
        (event) => {
          if (event.event === "state") setStreamState((current) => advanceStreamingState(current, { type: "phase", phase: event.phase }));
          if (event.event === "text_delta") {
            pendingText += event.text;
            if (!animationFrame) animationFrame = window.requestAnimationFrame(flushText);
          }
        },
        controller.signal,
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
      setMessages((current) => current.filter((message) => message.id !== temporaryUserId && message.id !== temporaryAssistantId));
      if (caught instanceof DOMException && caught.name === "AbortError") {
        setStreamState("idle");
        return;
      }
      setQuery(content);
      setStreamState("error");
      setMessageError(caught instanceof ApiError ? caught.message : "AURORA could not complete this streamed research turn. Your draft is ready to retry.");
    } finally {
      if (activeRequestRef.current === controller) activeRequestRef.current = null;
    }
  }

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void runStream(query);
  }

  async function rename(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!renameTarget) return;
    setRenaming(true);
    setRenameError("");
    try {
      const updated = await api.renameConversation(workspaceId, renameTarget.id, renameTitle);
      setConversations((current) => current.map((item) => item.id === updated.id ? updated : item));
      setRenameTarget(null);
    } catch (caught) {
      setRenameError(caught instanceof ApiError ? caught.message : "The conversation could not be renamed.");
    } finally {
      setRenaming(false);
    }
  }

  async function remove() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.deleteConversation(workspaceId, deleteTarget.id);
      const remaining = conversations.filter((item) => item.id !== deleteTarget.id);
      setConversations(remaining);
      setDeleteTarget(null);
      if (selectedId === deleteTarget.id) {
        const nextId = remaining[0]?.id || null;
        setMessageState(nextId ? "loading" : "idle");
        setMessages([]);
        setSelectedId(nextId);
        router.replace(nextId ? `${pathname}?view=research&conversation=${nextId}` : `${pathname}?view=research`, { scroll: false });
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
        <div><p className={styles.kicker}>Research record</p><h2>Conversations</h2></div>
        <button className={`${styles.mobileClose} button button-ghost button-icon`} type="button" onClick={() => setDrawerOpen(false)} aria-label="Close conversations"><X size={18} /></button>
      </div>
      <button className="button button-primary" type="button" onClick={() => void createConversation()} disabled={creating || submitting}>{creating ? <LoaderCircle className="spin" size={17} /> : <Plus size={17} />}{creating ? "Creating…" : "New conversation"}</button>
      {listError && <div className="error-banner" role="alert">{listError}</div>}
      <div className={styles.conversationList}>
        {listState === "loading" ? <div className={styles.listLoading} role="status"><LoaderCircle className="spin" size={18} />Loading recent conversations…</div> : null}
        {listState === "error" ? <button className="button button-secondary" type="button" onClick={() => void loadConversations(selectedId || undefined)}><RefreshCw size={16} />Retry list</button> : null}
        {listState === "loaded" && conversations.length === 0 ? <div className={styles.listEmpty}><strong>No conversations yet</strong><span>Start a research thread to preserve questions, grounded answers, and evidence.</span></div> : null}
        {conversations.map((conversation) => (
          <div className={`${styles.conversationRow} ${conversation.id === selectedId ? styles.activeConversation : ""}`} key={conversation.id}>
            <button className={styles.conversationSelect} type="button" onClick={() => selectConversation(conversation.id)} disabled={submitting} aria-current={conversation.id === selectedId ? "true" : undefined}><strong>{conversation.title}</strong><span>{formatConversationDate(conversation.updated_at)}</span></button>
            <div className={styles.rowTools}>
              <button type="button" disabled={submitting} onClick={() => { setRenameTarget(conversation); setRenameTitle(conversation.title); setRenameError(""); }} aria-label={`Rename ${conversation.title}`} title="Rename"><Pencil size={14} /></button>
              <button type="button" disabled={submitting} onClick={() => setDeleteTarget(conversation)} aria-label={`Delete ${conversation.title}`} title="Delete"><Trash2 size={14} /></button>
            </div>
          </div>
        ))}
      </div>
      <p className={styles.listLimit}>Showing up to 50 recent conversations</p>
    </aside>
  );

  return (
    <div className={styles.desk}>
      {drawerOpen && <button className={styles.drawerBackdrop} type="button" onClick={() => setDrawerOpen(false)} aria-label="Close conversations" />}
      <div ref={drawerRef} className={`${styles.mobileDrawer} ${drawerOpen ? styles.drawerOpen : ""}`} aria-hidden={!drawerOpen} inert={!drawerOpen}>{conversationPanel}</div>
      <div className={styles.desktopPanel}>{conversationPanel}</div>

      <section className={`surface ${styles.chat}`} aria-label="Persistent research conversation">
        <header className={styles.chatHeader}>
          <button className={`${styles.drawerButton} button button-secondary`} type="button" onClick={() => setDrawerOpen(true)}><Menu size={17} />Conversations</button>
          <div><p className={styles.kicker}>Authorized research conversation</p><h2>{selected?.title || "Start a research conversation"}</h2></div>
          {selected && <span>{sourceSummary ? `${sourceSummary.indexed} ready ${sourceSummary.indexed === 1 ? "source" : "sources"}` : `${messages.filter((message) => message.role === "ASSISTANT" && !message.id.startsWith("streaming-assistant-")).length} grounded answers`}</span>}
        </header>

        <div className={styles.messageViewport} ref={viewportRef} onScroll={trackScroll} aria-busy={messageState === "loading" || submitting}>
          {submitting ? <div className="sr-only" role="status" aria-live="polite">{streamingStatus(streamState)}</div> : null}
          {!selected && listState === "loaded" ? <EmptyState icon={FileSearch} title="Begin a persistent inquiry" description="Create a conversation to keep follow-up questions, grounded answers, and their evidence together across sessions." action={<button className="button button-secondary" type="button" onClick={() => void createConversation()}><Plus size={17} />New conversation</button>} /> : null}
          {selected && messageState === "loading" ? <div className={styles.messageLoading} role="status"><LoaderCircle className="spin" size={20} /><span>Loading the persistent research record…</span></div> : null}
          {selected && messageState === "error" ? <div className={styles.historyError}><div className="error-banner" role="alert">{messageError}</div><button className="button button-secondary" type="button" onClick={() => { setMessageState("loading"); setMessageReloadToken((value) => value + 1); }}><RefreshCw size={16} />Retry history</button></div> : null}
          {selected && messageState === "loaded" && messages.length === 0 ? <EmptyState icon={FileSearch} title="Ask the first question" description="AURORA will retrieve fresh authorized evidence, compose a grounded answer, and preserve both for follow-up research." /> : null}
          {messages.length > 0 ? (
            <ol className={styles.messages} aria-label="Conversation messages">
              {messages.map((message) => {
                const streaming = message.id.startsWith("streaming-assistant-");
                return (
                  <li className={`${message.role === "USER" ? styles.userTurn : styles.assistantTurn} ${streaming ? styles.streamingTurn : ""}`} key={message.id}>
                    <article aria-label={message.role === "USER" ? "Your research question" : streaming ? "AURORA answer in progress" : "AURORA grounded answer"}>
                      <div className={styles.messageMeta}><span>{message.role === "USER" ? "Your question" : streaming ? "Grounded answer · live" : "Grounded answer"}</span><time dateTime={message.created_at}>{formatConversationDate(message.created_at)}</time></div>
                      {message.insufficient_evidence && <div className={styles.insufficient}><FileSearch size={17} /><div><strong>Evidence is limited</strong><span>This answer is intentionally constrained because no source met the evidence threshold.</span></div></div>}
                      {streaming && !message.content ? <div className={styles.streamPlaceholder} aria-hidden="true"><span /><div><strong>{streamingStatus(streamState)}</strong><small>Only completed responses are saved.</small></div></div> : null}
                      {message.content ? <div className={styles.messageContent}>{message.content.split(/\n{2,}/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div> : null}
                      {streaming && message.content ? <span className={styles.streamCursor} aria-hidden="true" /> : null}
                      {message.role === "ASSISTANT" && message.sources.length > 0 ? <Evidence sources={message.sources} workspaceId={workspaceId} onOpenSource={onOpenSource} /> : null}
                      {message.role === "ASSISTANT" && !streaming && <footer>{message.response_id ? `Response ${message.response_id.slice(0, 8)}` : "Historical response"}{message.latency_ms !== null ? ` · ${(message.latency_ms / 1000).toFixed(1)}s` : ""}</footer>}
                    </article>
                  </li>
                );
              })}
            </ol>
          ) : null}
          <div ref={endRef} />
          {showLatest ? <button className={styles.jumpLatest} type="button" onClick={() => scrollToLatest("smooth")}><ArrowDown size={16} />Latest response</button> : null}
        </div>

        <div className={styles.composerWrap}>
          {hasNoReadySources ? <div className={styles.sourceNotice} role="status"><div><strong>No research-ready sources</strong><span>{sourceSummary.total ? "Process and index the uploaded document before asking a grounded question." : "Add a supported source before asking a grounded question."}</span></div><button className="button button-secondary" type="button" onClick={onOpenDocuments}>Review sources</button></div> : null}
          {messageError && messageState !== "error" ? <div className={`${styles.streamError} error-banner`} role="alert"><span>{messageError}</span>{streamState === "error" && retryContent ? <button className="button button-secondary" type="button" onClick={() => void runStream(retryContent)}><RefreshCw size={16} />Retry last question</button> : null}</div> : null}
          <form className={styles.composer} onSubmit={submit}>
            <label className="field-label" htmlFor="conversation-query">Research question</label>
            <textarea className="textarea" id="conversation-query" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} maxLength={4000} placeholder={hasNoReadySources ? "Type your question, then review and index a source to research it" : selected ? "Ask across every indexed source in this workspace…" : "Create a conversation before asking a question"} disabled={!selected || submitting} required />
            <div className={styles.composerFooter}>
              <div><label htmlFor="conversation-language">Answer language</label><select className="select" id="conversation-language" value={language} onChange={(event) => setLanguage(event.target.value)} disabled={!selected || submitting}>{LANGUAGES.map((item) => <option value={item.value} key={item.label}>{item.label}</option>)}</select></div>
              <span>Enter to send · Shift+Enter for a new line</span>
              <button className="button button-primary" type="submit" disabled={!selected || submitting || !query.trim()}>{submitting ? <LoaderCircle className="spin" size={17} /> : <Send size={17} />}{streamState === "finalizing" ? "Saving…" : submitting ? "Answering…" : "Send"}</button>
            </div>
          </form>
        </div>
      </section>

      {renameTarget && <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !renaming && setRenameTarget(null)}><form className="modal" role="dialog" aria-modal="true" aria-labelledby="rename-conversation-title" aria-describedby="rename-conversation-description" onSubmit={rename}><h2 id="rename-conversation-title">Rename conversation</h2><p id="rename-conversation-description">Use a short title that makes this research thread easy to find later.</p><div className="field"><label htmlFor="conversation-title">Conversation title</label><input className="input" id="conversation-title" value={renameTitle} onChange={(event) => setRenameTitle(event.target.value)} maxLength={120} autoFocus required /></div>{renameError && <div className="error-banner" role="alert">{renameError}</div>}<div className="modal-actions"><button className="button button-ghost" type="button" onClick={() => setRenameTarget(null)} disabled={renaming}>Cancel</button><button className="button button-primary" type="submit" disabled={renaming || !renameTitle.trim()}>{renaming ? "Saving…" : "Save title"}</button></div></form></div>}
      <ConfirmDialog open={Boolean(deleteTarget)} title="Delete this conversation?" description={deleteTarget ? `${deleteTarget.title}, its messages, and linked response citations will be permanently removed. Workspace documents will not be affected.` : ""} confirmLabel="Delete conversation" busy={deleting} onCancel={() => setDeleteTarget(null)} onConfirm={() => void remove()} />
    </div>
  );
}

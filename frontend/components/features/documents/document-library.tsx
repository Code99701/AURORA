"use client";

import {
  Download,
  Eye,
  FileText,
  LoaderCircle,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatUploadApiError } from "@/lib/api-errors";
import {
  documentIssueMessage,
  documentFormatName,
  documentStructureSummary,
  filterAndSortDocuments,
  partialProcessingMessage,
  SUPPORTED_DOCUMENT_ACCEPT,
  type DocumentFilter,
  type DocumentSort,
} from "@/lib/document-workspace";
import type { Document } from "@/lib/types";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { DocumentPreview } from "@/components/features/documents/document-preview";
import { EmptyState } from "@/components/shared/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import styles from "./document-library.module.css";

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

function nextAction(document: Document): "process" | "index" | null {
  if (document.status === "UPLOADED" || document.status === "FAILED") return "process";
  if (["PROCESSED", "PARTIALLY_PROCESSED"].includes(document.status) && document.indexing_status !== "INDEXED") return "index";
  return null;
}

function canIndex(document: Document) {
  return ["PROCESSED", "PARTIALLY_PROCESSED"].includes(document.status);
}

export function DocumentLibrary({
  workspaceId,
  selectedDocumentId,
  requestedPage,
  onInspectDocument,
}: {
  workspaceId: string;
  selectedDocumentId?: string;
  requestedPage: number;
  onInspectDocument: (documentId: string | null, page: number) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const previewRef = useRef<HTMLDivElement>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [pipelineStage, setPipelineStage] = useState<"uploading" | "processing" | "indexing">("uploading");
  const [pendingDelete, setPendingDelete] = useState<Document | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<DocumentFilter>("all");
  const [sort, setSort] = useState<DocumentSort>("newest");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const { items } = await api.documents(workspaceId);
      setDocuments(items);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The document library could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    api.documents(workspaceId)
      .then(({ items }) => { if (!cancelled) setDocuments(items); })
      .catch((caught) => { if (!cancelled) setError(caught instanceof ApiError ? caught.message : "The document library could not be loaded."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [workspaceId]);

  useEffect(() => {
    if (!selectedDocumentId || !previewRef.current || window.matchMedia("(min-width: 1001px)").matches) return;
    previewRef.current.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [selectedDocumentId]);

  async function upload(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    setPipelineStage("uploading");
    setError("");
    let documentId: string | null = null;
    let currentStage: "uploading" | "processing" | "indexing" = "uploading";
    try {
      let document = await api.uploadDocument(workspaceId, file);
      documentId = document.id;
      setDocuments((current) => [document, ...current]);

      currentStage = "processing";
      setPipelineStage(currentStage);
      document = await api.processDocument(workspaceId, document.id);
      setDocuments((current) => current.map((item) => item.id === document.id ? document : item));

      if (canIndex(document)) {
        currentStage = "indexing";
        setPipelineStage(currentStage);
        document = await api.indexDocument(workspaceId, document.id);
        setDocuments((current) => current.map((item) => item.id === document.id ? document : item));
      }
      onInspectDocument(document.id, 1);
    } catch (caught) {
      setError(caught instanceof ApiError
        ? (currentStage === "uploading" ? formatUploadApiError(caught.message, caught.status) : caught.message)
        : "The source could not complete automatic processing. Please retry.");
      await load();
      if (documentId) onInspectDocument(documentId, 1);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function advance(document: Document) {
    const action = nextAction(document);
    if (!action) return;
    setBusyId(document.id);
    setError("");
    try {
      let updated = action === "process"
        ? await api.processDocument(workspaceId, document.id)
        : await api.indexDocument(workspaceId, document.id);
      setDocuments((current) => current.map((item) => item.id === updated.id ? updated : item));
      if (action === "process" && canIndex(updated)) {
        updated = await api.indexDocument(workspaceId, document.id);
        setDocuments((current) => current.map((item) => item.id === updated.id ? updated : item));
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : `The document could not be ${action === "process" ? "processed" : "indexed"}.`);
      await load();
    } finally {
      setBusyId(null);
    }
  }

  async function remove() {
    if (!pendingDelete) return;
    setBusyId(pendingDelete.id);
    setError("");
    try {
      await api.deleteDocument(workspaceId, pendingDelete.id);
      setDocuments((current) => current.filter((item) => item.id !== pendingDelete.id));
      if (selectedDocumentId === pendingDelete.id) onInspectDocument(null, 1);
      setPendingDelete(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The document could not be removed.");
    } finally {
      setBusyId(null);
    }
  }

  const indexedCount = documents.filter((document) => document.indexing_status === "INDEXED").length;
  const visibleDocuments = useMemo(
    () => filterAndSortDocuments(documents, query, filter, sort),
    [documents, filter, query, sort],
  );

  return (
    <div className={styles.library}>
      <header className={styles.toolbar}>
        <div><p className={styles.kicker}>Source library</p><h2>{loading ? "Loading sources…" : `${documents.length} ${documents.length === 1 ? "document" : "documents"}`}</h2><span>{indexedCount} ready across this workspace</span></div>
        <div className={styles.actions}>
          <button className="button button-ghost button-icon" type="button" onClick={() => void load()} aria-label="Refresh documents" title="Refresh documents" disabled={loading}><RefreshCw className={loading ? "spin" : undefined} size={18} /></button>
          <input ref={inputRef} className={styles.fileInput} id="source-upload" type="file" accept={SUPPORTED_DOCUMENT_ACCEPT} onChange={(event) => void upload(event.target.files?.[0])} disabled={uploading} />
          <label className="button button-primary" htmlFor="source-upload" aria-disabled={uploading}>{uploading ? <LoaderCircle className="spin" size={18} /> : <Plus size={18} />}{uploading ? (pipelineStage === "uploading" ? "Uploading…" : pipelineStage === "processing" ? "Processing…" : "Indexing…") : "Add source"}</label>
        </div>
      </header>

      {error && <div className="error-banner" role="alert">{error}</div>}

      {documents.length > 0 ? (
        <section className={styles.filters} aria-label="Filter document register">
          <div className={styles.searchField}>
            <label className="sr-only" htmlFor="document-search">Search source filenames</label>
            <Search size={16} aria-hidden="true" />
            <input id="document-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search source filenames" />
          </div>
          <div><label htmlFor="document-filter">Status</label><select id="document-filter" value={filter} onChange={(event) => setFilter(event.target.value as DocumentFilter)}><option value="all">All sources</option><option value="ready">Research ready</option><option value="needs_action">Needs action</option><option value="failed">Failed</option></select></div>
          <div><label htmlFor="document-sort">Sort</label><select id="document-sort" value={sort} onChange={(event) => setSort(event.target.value as DocumentSort)}><option value="newest">Newest first</option><option value="name">Filename A–Z</option></select></div>
        </section>
      ) : null}

      <div className={`${styles.workspaceGrid} ${selectedDocumentId ? styles.withInspector : ""}`}>
        <section className={`surface ${styles.table}`} aria-label="Workspace documents" aria-busy={loading || uploading}>
          {loading ? (
            <div className={styles.loading}><LoaderCircle className="spin" size={21} /><span>Reading the document register…</span></div>
          ) : documents.length === 0 ? (
            <EmptyState icon={UploadCloud} title="No source documents yet" description="Upload PDF, TXT, Markdown, CSV, TSV, DOCX, XLSX, or PPTX. AURORA will automatically process and index usable evidence." action={<label className="button button-secondary" htmlFor="source-upload"><Plus size={17} />Choose source</label>} />
          ) : visibleDocuments.length === 0 ? (
            <EmptyState icon={Search} title="No matching sources" description="Adjust the filename search or lifecycle filter to return to the document register." action={<button className="button button-secondary" type="button" onClick={() => { setQuery(""); setFilter("all"); }}>Clear filters</button>} />
          ) : (
            <div className={styles.rows}>
              {visibleDocuments.map((document) => {
                const action = nextAction(document);
                const busy = busyId === document.id;
                const lifecycleError = documentIssueMessage(document);
                const partialMessage = partialProcessingMessage(document);
                const selected = document.id === selectedDocumentId;
                return (
                  <article className={`${styles.row} ${selected ? styles.selectedRow : ""}`} key={document.id} aria-current={selected ? "true" : undefined}>
                    <div className={styles.fileIcon}><FileText size={20} /></div>
                    <div className={styles.identity}>
                      <button type="button" onClick={() => onInspectDocument(document.id, 1)} title={document.original_filename}>{document.original_filename}</button>
                      <span>{documentFormatName(document)} · {formatBytes(document.file_size)} · {documentStructureSummary(document)} · Added {formatDate(document.created_at)}</span>
                      {lifecycleError && <small role="alert">{lifecycleError}</small>}
                      {partialMessage && <small className={styles.partialNote}>{partialMessage}</small>}
                    </div>
                    <div className={styles.statuses}><StatusBadge value={document.status} /><StatusBadge value={document.indexing_status} /></div>
                    <div className={styles.rowActions}>
                      <button className="button button-ghost" type="button" onClick={() => onInspectDocument(document.id, 1)} aria-label={`Inspect ${document.original_filename}`}><Eye size={16} />Inspect</button>
                      {action && <button className="button button-secondary" type="button" onClick={() => void advance(document)} disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : null}{busy ? (action === "process" ? "Processing…" : "Indexing…") : (action === "process" ? "Process" : "Index")}</button>}
                      {document.indexing_status === "INDEXED" && <span className={styles.ready}>Research ready</span>}
                      <a className="button button-ghost button-icon" href={`/api/v1/workspaces/${workspaceId}/documents/${document.id}/download`} aria-label={`Download ${document.original_filename}`} title="Download"><Download size={17} /></a>
                      <button className="button button-ghost button-icon" type="button" onClick={() => setPendingDelete(document)} aria-label={`Remove ${document.original_filename}`} title="Remove" disabled={busy}><Trash2 size={17} /></button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        {selectedDocumentId ? (
          <div ref={previewRef} className={styles.previewColumn}>
            <DocumentPreview workspaceId={workspaceId} documentId={selectedDocumentId} requestedPage={requestedPage} onPageChange={(page) => onInspectDocument(selectedDocumentId, page)} />
          </div>
        ) : null}
      </div>

      <ConfirmDialog open={Boolean(pendingDelete)} title="Remove this source?" description={pendingDelete ? `${pendingDelete.original_filename} and its indexed evidence will be permanently removed from this workspace.` : ""} confirmLabel="Remove document" busy={Boolean(pendingDelete && busyId === pendingDelete.id)} onCancel={() => setPendingDelete(null)} onConfirm={() => void remove()} />
    </div>
  );
}

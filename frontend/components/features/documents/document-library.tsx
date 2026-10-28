"use client";

import {
  AlertCircle,
  Download,
  Eye,
  FileText,
  LoaderCircle,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { formatUploadApiError } from "@/lib/api-errors";
import {
  documentIssueMessage,
  documentFormatName,
  filterAndSortDocuments,
  SUPPORTED_DOCUMENT_ACCEPT,
  type DocumentFilter,
  type DocumentSort,
} from "@/lib/document-workspace";
import type { Document } from "@/lib/types";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { DocumentPreview } from "@/components/features/documents/document-preview";
import { StatusChip } from "@/components/ui/status-chip";
import styles from "./document-library.module.css";

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function nextAction(document: Document): "process" | "index" | null {
  if (document.status === "UPLOADED" || document.status === "FAILED") return "process";
  if (["PROCESSED", "PARTIALLY_PROCESSED"].includes(document.status) && document.indexing_status !== "INDEXED") return "index";
  return null;
}

function canIndex(document: Document) {
  return ["PROCESSED", "PARTIALLY_PROCESSED"].includes(document.status);
}

function getMergedStatus(doc: Document): { tone: "ready" | "indexing" | "failed" | "partial" | "neutral"; label: string } {
  if (doc.indexing_status === "INDEXED") {
    return { tone: "ready", label: "Ready" };
  }
  if (doc.status === "FAILED" || doc.indexing_status === "FAILED") {
    return { tone: "failed", label: "Failed" };
  }
  if (doc.status === "PARTIALLY_PROCESSED") {
    return { tone: "partial", label: "Partial" };
  }
  if (doc.status === "PROCESSING" || doc.indexing_status === "INDEXING") {
    return { tone: "indexing", label: "Indexing" };
  }
  if (doc.status === "UPLOADED") {
    return { tone: "neutral", label: "Uploaded" };
  }
  return { tone: "neutral", label: doc.status.toLowerCase().replace(/_/g, " ") };
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
  const [uploadingFilename, setUploadingFilename] = useState<string | null>(null);
  const [pipelineStage, setPipelineStage] = useState<"uploading" | "processing" | "indexing">("uploading");
  const [pendingDelete, setPendingDelete] = useState<Document | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<DocumentFilter>("all");
  const [sort, setSort] = useState<DocumentSort>("newest");
  const [isDragging, setIsDragging] = useState(false);

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
    if (!selectedDocumentId || !previewRef.current || window.matchMedia("(min-width: 961px)").matches) return;
    previewRef.current.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [selectedDocumentId]);

  async function upload(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    setUploadingFilename(file.name);
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
      if (caught instanceof ApiError) {
        if (caught.status === 409 || caught.message.toLowerCase().includes("already exists")) {
          setError(`"${file.name}" already exists in this workspace.`);
        } else if (currentStage === "uploading") {
          setError(formatUploadApiError(caught.message, caught.status));
        } else {
          setError(caught.message);
        }
      } else {
        setError("The source could not complete automatic processing. Please retry.");
      }
      await load();
      if (documentId) onInspectDocument(documentId, 1);
    } finally {
      setUploading(false);
      setUploadingFilename(null);
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

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(true);
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void upload(file);
  }

  const visibleDocuments = useMemo(
    () => filterAndSortDocuments(documents, query, filter, sort),
    [documents, filter, query, sort],
  );

  return (
    <div className={styles.library}>
      <header className={styles.header}>
        <div className={styles.titleArea}>
          <h1 className={styles.title}>Documents</h1>
          <span className={styles.countBadge}>
            {loading ? "Loading…" : `${documents.length} ${documents.length === 1 ? "document" : "documents"}`}
          </span>
        </div>
        <div className={styles.headerActions}>
          <button
            className="button button-ghost button-icon"
            type="button"
            onClick={() => void load()}
            aria-label="Refresh documents"
            title="Refresh documents"
            disabled={loading}
          >
            <RefreshCw className={loading ? "spin" : undefined} size={16} />
          </button>
          <input
            ref={inputRef}
            className={styles.fileInput}
            id="source-upload"
            type="file"
            accept={SUPPORTED_DOCUMENT_ACCEPT}
            onChange={(event) => void upload(event.target.files?.[0])}
            disabled={uploading}
          />
          <label
            className="button button-primary"
            htmlFor="source-upload"
            aria-disabled={uploading}
          >
            {uploading ? <LoaderCircle className="spin" size={16} /> : <Plus size={16} />}
            {uploading
              ? pipelineStage === "uploading"
                ? "Uploading…"
                : pipelineStage === "processing"
                  ? "Processing…"
                  : "Indexing…"
              : "Upload document"}
          </label>
        </div>
      </header>

      {error && (
        <div className="error-banner" role="alert" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <AlertCircle size={16} style={{ flexShrink: 0 }} />
          <span>{error}</span>
        </div>
      )}

      <div
        className={`${styles.dropZone} ${isDragging ? styles.dropZoneActive : ""}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {uploading ? (
          <div className={styles.uploadProgress}>
            <LoaderCircle className="spin" size={16} />
            <span>
              {pipelineStage === "uploading"
                ? `Uploading ${uploadingFilename || "document"}…`
                : pipelineStage === "processing"
                  ? `Processing ${uploadingFilename || "document"}…`
                  : `Indexing ${uploadingFilename || "document"}…`}
            </span>
          </div>
        ) : (
          <div className={styles.dropZonePrompt}>
            <UploadCloud size={16} className={styles.dropIcon} />
            <span>Drag and drop PDF, DOCX, XLSX, TXT, or MD files here to upload (up to 10 MB)</span>
          </div>
        )}
      </div>

      {documents.length > 0 ? (
        <div className={styles.toolbar} role="search" aria-label="Filter documents">
          <div className={styles.searchField}>
            <Search size={15} aria-hidden="true" />
            <input
              id="document-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search documents…"
              className={styles.searchInput}
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                className={styles.clearSearchBtn}
                aria-label="Clear search"
              >
                <X size={14} />
              </button>
            )}
          </div>
          <div className={styles.filterControls}>
            <select
              id="document-filter"
              value={filter}
              onChange={(event) => setFilter(event.target.value as DocumentFilter)}
              className={styles.select}
              aria-label="Filter by status"
            >
              <option value="all">All statuses</option>
              <option value="ready">Research ready</option>
              <option value="needs_action">Needs action</option>
              <option value="failed">Failed</option>
            </select>
            <select
              id="document-sort"
              value={sort}
              onChange={(event) => setSort(event.target.value as DocumentSort)}
              className={styles.select}
              aria-label="Sort documents"
            >
              <option value="newest">Newest first</option>
              <option value="name">Name (A–Z)</option>
            </select>
          </div>
        </div>
      ) : null}

      <div className={`${styles.workspaceGrid} ${selectedDocumentId ? styles.withInspector : ""}`}>
        <div className={styles.tableCard}>
          {loading ? (
            <div className={styles.loadingState}>
              <LoaderCircle className="spin" size={20} />
              <span>Loading documents…</span>
            </div>
          ) : documents.length === 0 ? (
            <div className={styles.emptyStateWrap}>
              <UploadCloud size={32} className={styles.emptyIcon} />
              <h3 className={styles.emptyTitle}>No documents yet</h3>
              <p className={styles.emptyText}>Upload PDF, DOCX, XLSX, TXT, or Markdown files to begin researching with citations.</p>
              <label className="button button-primary" htmlFor="source-upload">
                <Plus size={16} />
                Upload document
              </label>
            </div>
          ) : visibleDocuments.length === 0 ? (
            <div className={styles.emptyStateWrap}>
              <Search size={32} className={styles.emptyIcon} />
              <h3 className={styles.emptyTitle}>No matching documents</h3>
              <p className={styles.emptyText}>Try adjusting your search query or status filter.</p>
              <button className="button button-secondary" type="button" onClick={() => { setQuery(""); setFilter("all"); }}>
                Clear filters
              </button>
            </div>
          ) : (
            <div className={styles.tableScroll}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th className={styles.thName}>Name</th>
                    <th className={styles.thStatus}>Status</th>
                    <th className={styles.thPages}>Pages</th>
                    <th className={styles.thAdded}>Added</th>
                    <th className={styles.thActions}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleDocuments.map((doc) => {
                    const isSelected = doc.id === selectedDocumentId;
                    const statusInfo = getMergedStatus(doc);
                    const action = nextAction(doc);
                    const busy = busyId === doc.id;
                    const lifecycleError = documentIssueMessage(doc);
                    return (
                      <tr
                        key={doc.id}
                        className={`${styles.tr} ${isSelected ? styles.trSelected : ""}`}
                        onClick={() => onInspectDocument(doc.id, 1)}
                      >
                        <td className={styles.tdName}>
                          <div className={styles.nameCell}>
                            <div className={styles.fileTypeIcon}>
                              <FileText size={18} />
                            </div>
                            <div className={styles.nameDetails}>
                              <span className={styles.filename} title={doc.original_filename}>
                                {doc.original_filename}
                              </span>
                              <span className={styles.metaLine}>
                                {documentFormatName(doc)} · {formatBytes(doc.file_size)}
                              </span>
                              {lifecycleError && (
                                <span className={styles.issueText} role="alert">
                                  {lifecycleError}
                                </span>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className={styles.tdStatus}>
                          <StatusChip status={statusInfo.tone} label={statusInfo.label} />
                        </td>
                        <td className={styles.tdPages}>
                          <span className={styles.pagesText}>
                            {doc.page_count ? `${doc.page_count} p` : "—"}
                          </span>
                        </td>
                        <td className={styles.tdAdded}>
                          <span className={styles.dateText}>{formatDate(doc.created_at)}</span>
                        </td>
                        <td className={styles.tdActions} onClick={(e) => e.stopPropagation()}>
                          <div className={styles.actionGroup}>
                            <button
                              className="button button-ghost button-icon"
                              type="button"
                              onClick={() => onInspectDocument(doc.id, 1)}
                              aria-label={`Preview ${doc.original_filename}`}
                              title="Preview document"
                            >
                              <Eye size={15} />
                            </button>
                            {action && (
                              <button
                                className="button button-secondary"
                                type="button"
                                onClick={() => void advance(doc)}
                                disabled={busy}
                                title={action === "process" ? "Process document" : "Index document"}
                                style={{ height: "30px", padding: "0 8px", fontSize: "12px" }}
                              >
                                {busy ? <LoaderCircle className="spin" size={13} /> : null}
                                {action === "process" ? "Process" : "Index"}
                              </button>
                            )}
                            <a
                              className="button button-ghost button-icon"
                              href={`/api/v1/workspaces/${workspaceId}/documents/${doc.id}/download`}
                              aria-label={`Download ${doc.original_filename}`}
                              title="Download document"
                            >
                              <Download size={15} />
                            </a>
                            <button
                              className="button button-ghost button-icon"
                              type="button"
                              onClick={() => setPendingDelete(doc)}
                              aria-label={`Delete ${doc.original_filename}`}
                              title="Delete document"
                              disabled={busy}
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {selectedDocumentId ? (
          <div ref={previewRef} className={styles.previewDrawer}>
            <DocumentPreview
              workspaceId={workspaceId}
              documentId={selectedDocumentId}
              requestedPage={requestedPage}
              onPageChange={(page) => onInspectDocument(selectedDocumentId, page)}
              onClose={() => onInspectDocument(null, 1)}
            />
          </div>
        ) : null}
      </div>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Remove this document?"
        description={pendingDelete ? `${pendingDelete.original_filename} and its indexed evidence will be permanently removed from this workspace.` : ""}
        confirmLabel="Remove document"
        busy={Boolean(pendingDelete && busyId === pendingDelete.id)}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => void remove()}
      />
    </div>
  );
}

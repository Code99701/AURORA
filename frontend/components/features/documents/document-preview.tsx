"use client";

import {
  ArrowLeft,
  ArrowRight,
  Download,
  ExternalLink,
  FileQuestion,
  FileText,
  LoaderCircle,
  RefreshCw,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { clampDocumentPage, documentFormatName, documentIssueMessage, documentStructureSummary, partialProcessingMessage } from "@/lib/document-workspace";
import type { Document } from "@/lib/types";
import { StatusBadge } from "@/components/ui/status-badge";
import styles from "./document-preview.module.css";

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string | null) {
  if (!value) return "Not completed";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function DocumentPreview({
  workspaceId,
  documentId,
  requestedPage,
  onPageChange,
}: {
  workspaceId: string;
  documentId: string;
  requestedPage: number;
  onPageChange: (page: number) => void;
}) {
  const [document, setDocument] = useState<Document | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [state, setState] = useState<"loading" | "ready" | "unsupported" | "error">("loading");
  const [error, setError] = useState("");
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let objectUrl = "";

    async function loadPreview() {
      await Promise.resolve();
      if (controller.signal.aborted) return;
      setState("loading");
      setError("");
      setDocument(null);
      setPreviewUrl("");
      try {
        const metadata = await api.document(workspaceId, documentId);
        if (controller.signal.aborted) return;
        setDocument(metadata);
        if (metadata.content_type !== "application/pdf") {
          setState("unsupported");
          return;
        }
        const blob = await api.documentPreview(workspaceId, documentId, controller.signal);
        if (controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(blob);
        setPreviewUrl(objectUrl);
        setState("ready");
      } catch (caught) {
        if (controller.signal.aborted) return;
        setError(caught instanceof ApiError
          ? caught.message
          : "This source could not be opened. Refresh the inspector or download the file.");
        setState("error");
      }
    }
    void loadPreview();

    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId, reloadToken, workspaceId]);

  const page = useMemo(
    () => clampDocumentPage(requestedPage, document?.page_count || null),
    [document?.page_count, requestedPage],
  );

  useEffect(() => {
    if (document?.page_count && page !== requestedPage) onPageChange(page);
  }, [document?.page_count, onPageChange, page, requestedPage]);

  if (state === "loading") {
    return (
      <section className={`surface ${styles.inspector}`} aria-label="Document inspector" aria-busy="true">
        <div className={styles.centerState} role="status">
          <LoaderCircle className="spin" size={24} />
          <div><strong>Opening authorized source</strong><span>Checking access and preparing the source inspector…</span></div>
        </div>
      </section>
    );
  }

  if (state === "error") {
    return (
      <section className={`surface ${styles.inspector}`} aria-label="Document inspector">
        <div className={styles.centerState}>
          <FileQuestion size={26} />
          <div><strong>Preview unavailable</strong><span>{error}</span></div>
          <button className="button button-secondary" type="button" onClick={() => setReloadToken((value) => value + 1)}><RefreshCw size={16} />Retry preview</button>
        </div>
      </section>
    );
  }

  if (!document) return null;

  const lifecycleError = documentIssueMessage(document);
  const partialMessage = partialProcessingMessage(document);
  const downloadUrl = `/api/v1/workspaces/${workspaceId}/documents/${document.id}/download`;
  const inlinePreviewUrl = `/api/v1/workspaces/${workspaceId}/documents/${document.id}/preview`;

  return (
    <section className={`surface ${styles.inspector}`} aria-label={`Document inspector: ${document.original_filename}`}>
      <header className={styles.header}>
        <div className={styles.titleBlock}>
          <span className={styles.icon}><FileText size={20} /></span>
          <div><p>Source inspection</p><h2 title={document.original_filename}>{document.original_filename}</h2></div>
        </div>
        <div className={styles.headerActions}>
          <a className="button button-ghost button-icon" href={downloadUrl} aria-label={`Download ${document.original_filename}`} title="Download source"><Download size={17} /></a>
          <a className="button button-secondary" href={state === "unsupported" ? downloadUrl : inlinePreviewUrl} target={state === "unsupported" ? undefined : "_blank"} rel={state === "unsupported" ? undefined : "noreferrer"}>{state === "unsupported" ? <Download size={16} /> : <ExternalLink size={16} />}{state === "unsupported" ? "Download file" : "Open file"}</a>
        </div>
      </header>

      <div className={styles.statusBar}>
        <div><StatusBadge value={document.status} /><StatusBadge value={document.indexing_status} /></div>
        <span>{document.indexing_status === "INDEXED" ? "Available to workspace research" : "Not yet available to retrieval"}</span>
      </div>
      {lifecycleError ? <div className={`${styles.lifecycleError} error-banner`} role="alert">{lifecycleError}</div> : null}
      {partialMessage ? <div className={`${styles.lifecycleError} ${styles.partialNotice}`} role="status">{partialMessage} Only usable evidence will be indexed and retrieved.</div> : null}

      <dl className={styles.metadata}>
        <div><dt>Format</dt><dd>{documentFormatName(document)}</dd></div>
        <div><dt>Structure</dt><dd>{documentStructureSummary(document)}</dd></div>
        <div><dt>File size</dt><dd>{formatBytes(document.file_size)}</dd></div>
        <div><dt>Uploaded</dt><dd>{formatDate(document.created_at)}</dd></div>
        <div><dt>Indexed</dt><dd>{formatDate(document.indexed_at)}</dd></div>
      </dl>

      {state === "unsupported" ? (
        <div className={styles.centerState}>
          <FileQuestion size={26} />
          <div><strong>Inline preview is not supported</strong><span>Download this source to inspect it in a compatible application.</span></div>
          <a className="button button-secondary" href={downloadUrl}><Download size={16} />Download source</a>
        </div>
      ) : (
        <>
          <nav className={styles.pageControls} aria-label="PDF page navigation">
            <button className="button button-ghost button-icon" type="button" onClick={() => onPageChange(page - 1)} disabled={page <= 1} aria-label="Previous page"><ArrowLeft size={17} /></button>
            <label htmlFor={`preview-page-${document.id}`}>Page</label>
            <input
              id={`preview-page-${document.id}`}
              type="number"
              min={1}
              max={document.page_count || 1}
              value={page}
              onChange={(event) => onPageChange(clampDocumentPage(Number(event.target.value), document.page_count))}
              aria-label="PDF page number"
            />
            <span>of {document.page_count || 1}</span>
            <button className="button button-ghost button-icon" type="button" onClick={() => onPageChange(page + 1)} disabled={page >= (document.page_count || 1)} aria-label="Next page"><ArrowRight size={17} /></button>
          </nav>
          <div className={styles.frameWrap}>
            <iframe
              key={`${document.id}-${page}`}
              className={styles.frame}
              src={`${previewUrl}#page=${page}&view=FitH`}
              title={`${document.original_filename}, page ${page}`}
            />
          </div>
          <p className={styles.previewNote}>Preview is loaded from the authorized API and kept out of shared caches. Browser PDF controls may vary.</p>
        </>
      )}
    </section>
  );
}

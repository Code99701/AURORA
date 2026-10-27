"use client";

import { ChevronDown, FolderKanban, Upload } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { RAGSource, Workspace } from "@/lib/types";
import { DocumentLibrary } from "@/components/features/documents/document-library";
import { ResearchDesk } from "@/components/features/chat/research-desk";
import { PageSkeleton } from "@/components/ui/skeleton";
import { ErrorBoundary } from "@/components/shared/error-boundary";
import { UploadModal } from "@/components/features/workspace/upload-modal";
import styles from "./workspace-view.module.css";

export function WorkspaceView({
  workspaceId,
  initialView = "research",
  initialConversationId,
  initialDocumentId,
  initialPage = 1,
}: {
  workspaceId: string;
  initialView?: "documents" | "research";
  initialConversationId?: string;
  initialDocumentId?: string;
  initialPage?: number;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [view, setView] = useState<"documents" | "research">(initialView);
  const [selectedDocumentId, setSelectedDocumentId] = useState(initialDocumentId);
  const [requestedPage, setRequestedPage] = useState(initialPage);
  const [sourceCount, setSourceCount] = useState<number>(0);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [error, setError] = useState("");

  const loadWorkspaceMeta = useCallback(() => {
    let cancelled = false;
    api.workspace(workspaceId)
      .then((data) => {
        if (!cancelled) setWorkspace(data);
      })
      .catch((caught) => {
        if (!cancelled) {
          setError(
            caught instanceof ApiError
              ? caught.message
              : "This workspace could not be loaded."
          );
        }
      });

    api.documents(workspaceId)
      .then((docs) => {
        if (!cancelled) {
          const ready = docs.items.filter((d) => d.indexing_status === "INDEXED").length;
          setSourceCount(ready);
        }
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  useEffect(() => {
    return loadWorkspaceMeta();
  }, [loadWorkspaceMeta]);


  function selectView(next: "documents" | "research") {
    setView(next);
    const parameters = new URLSearchParams();
    if (next === "research") {
      parameters.set("view", "research");
      if (initialConversationId) parameters.set("conversation", initialConversationId);
    } else {
      parameters.set("view", "documents");
      if (selectedDocumentId) {
        parameters.set("document", selectedDocumentId);
        parameters.set("page", String(requestedPage));
      }
    }
    const query = parameters.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  function inspectDocument(documentId: string | null, page: number) {
    setView("documents");
    setSelectedDocumentId(documentId || undefined);
    setRequestedPage(page);
    if (!documentId) {
      const parameters = new URLSearchParams({ view: "documents" });
      router.replace(`${pathname}?${parameters.toString()}`, { scroll: false });
      return;
    }
    const parameters = new URLSearchParams({
      view: "documents",
      document: documentId,
      page: String(page),
    });
    router.replace(`${pathname}?${parameters.toString()}`, { scroll: false });
  }

  function openSource(source: RAGSource) {
    inspectDocument(source.document_id, source.page_number ?? 1);
  }

  if (error) {
    const isNotFound = error.toLowerCase().includes("not found") || error.includes("404");
    return (
      <div className={styles.center} style={{ padding: "4rem 1.5rem", textAlign: "center", maxWidth: "500px", margin: "0 auto" }}>
        <div style={{
          width: 56,
          height: 56,
          borderRadius: "16px",
          background: "var(--coral-soft, #FFF0F0)",
          color: "var(--coral, #FF6B6B)",
          display: "grid",
          placeItems: "center",
          margin: "0 auto 1.25rem",
        }}>
          <FolderKanban size={26} />
        </div>
        <h2 style={{ fontSize: "1.4rem", fontWeight: 800, margin: "0 0 0.5rem" }}>
          {isNotFound ? "Workspace Not Found" : "Could not open workspace"}
        </h2>
        <p style={{ color: "var(--foreground-soft)", fontSize: "0.95rem", lineHeight: 1.5, margin: "0 0 1.5rem" }}>
          {isNotFound
            ? "This workspace may have been deleted, or you don't have access to view it."
            : error}
        </p>
        <Link href="/workspaces" className="button button-primary" style={{ display: "inline-flex", gap: "0.5rem", alignItems: "center" }}>
          Back to all workspaces
        </Link>
      </div>
    );
  }

  if (!workspace) return <PageSkeleton />;

  const sectionName = view === "research" ? "Research Desk" : "Documents";

  return (
    <div className={styles.workspaceContainer}>
      {/* Slim Sticky Workspace Header matching mockup */}
      <header className={styles.stickyHeader}>
        <div className={styles.breadcrumbs}>
          <span className={styles.breadWorkspace}>{workspace.name}</span>
          <span className={styles.breadDivider}>/</span>
          <span className={styles.breadSection}>{sectionName}</span>
        </div>

        <div className={styles.headerControls}>
          {/* Segmented Pill Tabs */}
          <div className={styles.segmentedTabs} role="tablist" aria-label="Workspace view modes">
            <button
              id="research-tab"
              aria-controls="research-panel"
              className={`${styles.segmentBtn} ${view === "research" ? styles.segmentActive : ""}`}
              role="tab"
              aria-selected={view === "research"}
              type="button"
              onClick={() => selectView("research")}
            >
              Chat
            </button>
            <button
              id="documents-tab"
              aria-controls="documents-panel"
              className={`${styles.segmentBtn} ${view === "documents" ? styles.segmentActive : ""}`}
              role="tab"
              aria-selected={view === "documents"}
              type="button"
              onClick={() => selectView("documents")}
            >
              Documents
            </button>
          </div>

          {/* Document Scope Pill */}
          <div className={styles.scopePill} title="Sources ready for retrieval in this workspace">
            <span>{sourceCount} {sourceCount === 1 ? "source" : "sources"} in scope</span>
            <ChevronDown size={12} className={styles.scopeChevron} />
          </div>

          {/* Quick Upload Button */}
          <button
            type="button"
            className={styles.uploadIconBtn}
            onClick={() => setUploadOpen(true)}
            aria-label="Upload document"
            title="Upload document"
          >
            <Upload size={14} />
          </button>
        </div>
      </header>

      {/* Workspace Body: Research Desk or Document Library */}
      <main className={styles.mainContent} id={`${view}-panel`} role="tabpanel" aria-labelledby={`${view}-tab`}>
        <ErrorBoundary fallbackTitle="Could not load view" fallbackMessage="An unexpected error occurred in this view. Click below to try again.">
          {view === "documents" ? (
            <DocumentLibrary
              workspaceId={workspaceId}
              selectedDocumentId={selectedDocumentId}
              requestedPage={requestedPage}
              onInspectDocument={inspectDocument}
            />
          ) : (
            <ResearchDesk
              workspaceId={workspaceId}
              initialConversationId={initialConversationId}
              onOpenSource={openSource}
              onOpenDocuments={() => selectView("documents")}
            />
          )}
        </ErrorBoundary>
      </main>

      <UploadModal
        isOpen={uploadOpen}
        onClose={() => setUploadOpen(false)}
        workspaceId={workspaceId}
        onUploadSuccess={() => loadWorkspaceMeta()}
      />
    </div>
  );
}

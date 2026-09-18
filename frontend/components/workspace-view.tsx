"use client";

import { ArrowLeft, BookOpenText, Files } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { RAGSource, Workspace } from "@/lib/types";
import { DocumentLibrary } from "@/components/document-library";
import { ResearchDesk } from "@/components/research-desk";
import { PageSkeleton } from "@/components/skeleton";
import styles from "./workspace-view.module.css";

export function WorkspaceView({
  workspaceId,
  initialView,
  initialConversationId,
  initialDocumentId,
  initialPage,
}: {
  workspaceId: string;
  initialView: "documents" | "research";
  initialConversationId?: string;
  initialDocumentId?: string;
  initialPage: number;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [view, setView] = useState<"documents" | "research">(initialView);
  const [selectedDocumentId, setSelectedDocumentId] = useState(initialDocumentId);
  const [requestedPage, setRequestedPage] = useState(initialPage);
  const [error, setError] = useState("");

  useEffect(() => {
    api.workspace(workspaceId)
      .then(setWorkspace)
      .catch((caught) => setError(caught instanceof ApiError ? caught.message : "This workspace could not be loaded."));
  }, [workspaceId]);

  function selectView(next: "documents" | "research") {
    setView(next);
    const parameters = new URLSearchParams();
    if (next === "research") {
      parameters.set("view", "research");
      if (initialConversationId) parameters.set("conversation", initialConversationId);
    } else if (selectedDocumentId) {
      parameters.set("document", selectedDocumentId);
      parameters.set("page", String(requestedPage));
    }
    const query = parameters.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  function inspectDocument(documentId: string | null, page: number) {
    setView("documents");
    setSelectedDocumentId(documentId || undefined);
    setRequestedPage(page);
    if (!documentId) {
      router.replace(pathname, { scroll: false });
      return;
    }
    const parameters = new URLSearchParams({ document: documentId, page: String(page) });
    router.replace(`${pathname}?${parameters.toString()}`, { scroll: false });
  }

  function openSource(source: RAGSource) {
    inspectDocument(source.document_id, source.page_number ?? 1);
  }

  if (error) return <div className={styles.center}><div className="error-banner" role="alert">{error}</div><Link className="button button-secondary" href="/workspaces"><ArrowLeft size={17} />Back to workspaces</Link></div>;
  if (!workspace) return <PageSkeleton />;

  return (
    <div className={styles.page}>
      <Link className={styles.back} href="/workspaces"><ArrowLeft size={15} />Workspace index</Link>
      <header className={styles.header}>
        <p className={styles.eyebrow}>Research workspace</p>
        <h1>{workspace.name}</h1>
        <p>{workspace.description || "A private source collection for grounded research."}</p>
      </header>
      <div className={styles.tabs} role="tablist" aria-label="Workspace views">
        <button id="documents-tab" aria-controls="documents-panel" className={view === "documents" ? styles.active : ""} role="tab" aria-selected={view === "documents"} type="button" onClick={() => selectView("documents")}><Files size={18} />Documents</button>
        <button id="research-tab" aria-controls="research-panel" className={view === "research" ? styles.active : ""} role="tab" aria-selected={view === "research"} type="button" onClick={() => selectView("research")}><BookOpenText size={18} />Research</button>
      </div>
      <section id={`${view}-panel`} role="tabpanel" aria-labelledby={`${view}-tab`}>
        {view === "documents" ? <DocumentLibrary workspaceId={workspaceId} selectedDocumentId={selectedDocumentId} requestedPage={requestedPage} onInspectDocument={inspectDocument} /> : <ResearchDesk workspaceId={workspaceId} initialConversationId={initialConversationId} onOpenSource={openSource} onOpenDocuments={() => selectView("documents")} />}
      </section>
    </div>
  );
}

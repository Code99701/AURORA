"use client";

import { ArrowUpRight, FolderKanban, Plus, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Workspace } from "@/lib/types";
import { EmptyState } from "@/components/empty-state";
import { PageSkeleton } from "@/components/skeleton";
import styles from "./workspace-dashboard.module.css";

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

export function WorkspaceDashboard() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.workspaces()
      .then(({ items }) => setWorkspaces(items))
      .catch((caught) => setError(caught instanceof ApiError ? caught.message : "Your workspaces could not be loaded."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (formOpen) nameRef.current?.focus();
  }, [formOpen]);

  useEffect(() => {
    if (!formOpen) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !saving) setFormOpen(false);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [formOpen, saving]);

  async function createWorkspace(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const workspace = await api.createWorkspace(name, description);
      setWorkspaces((current) => [workspace, ...current]);
      setName("");
      setDescription("");
      setFormOpen(false);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The workspace could not be created.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <PageSkeleton />;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Knowledge spaces</p>
          <h1>Your research, deliberately separated.</h1>
          <p>Each workspace is a private boundary for documents, evidence, and grounded answers.</p>
        </div>
        <button className="button button-primary" type="button" onClick={() => setFormOpen(true)}><Plus size={18} />New workspace</button>
      </header>

      {error && <div className="error-banner" role="alert">{error}</div>}

      <section className={`surface ${styles.index}`} aria-labelledby="workspace-index">
        <div className={styles.indexHeader}>
          <div><p className={styles.kicker}>Workspace index</p><h2 id="workspace-index">{workspaces.length} {workspaces.length === 1 ? "workspace" : "workspaces"}</h2></div>
          <span>Updated as you create</span>
        </div>
        {workspaces.length === 0 ? (
          <EmptyState
            icon={FolderKanban}
            title="Create your first evidence boundary"
            description="A workspace keeps its source documents, processing lifecycle, and research history isolated from every other project."
            action={<button className="button button-secondary" type="button" onClick={() => setFormOpen(true)}><Plus size={17} />Create workspace</button>}
          />
        ) : (
          <div className={styles.list}>
            {workspaces.map((workspace, index) => (
              <Link className={styles.row} href={`/workspaces/${workspace.id}`} key={workspace.id}>
                <span className={styles.ordinal}>{String(index + 1).padStart(2, "0")}</span>
                <span className={styles.rowMain}>
                  <strong>{workspace.name}</strong>
                  <span>{workspace.description || "No description yet. Open the workspace to add and research sources."}</span>
                </span>
                <span className={styles.date}>Created {formatDate(workspace.created_at)}</span>
                <ArrowUpRight size={19} aria-hidden="true" />
              </Link>
            ))}
          </div>
        )}
      </section>

      {formOpen && (
        <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !saving && setFormOpen(false)}>
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="new-workspace-title" aria-describedby="new-workspace-description">
            <div className={styles.modalHeader}><div><p className={styles.kicker}>New boundary</p><h2 id="new-workspace-title">Create workspace</h2></div><button className="button button-ghost button-icon" type="button" onClick={() => setFormOpen(false)} aria-label="Close" disabled={saving}><X size={19} /></button></div>
            <p id="new-workspace-description">Give this collection a clear research purpose. You can add source documents next.</p>
            <form className={styles.form} onSubmit={createWorkspace}>
              <div className="field"><label htmlFor="workspace-name">Name</label><input ref={nameRef} className="input" id="workspace-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={120} required /></div>
              <div className="field"><label htmlFor="workspace-description">Description <span className={styles.optional}>Optional</span></label><textarea className="textarea" id="workspace-description" value={description} onChange={(event) => setDescription(event.target.value)} maxLength={2000} placeholder="What evidence belongs here, and what will you investigate?" /></div>
              <div className="modal-actions"><button className="button button-ghost" type="button" onClick={() => setFormOpen(false)} disabled={saving}>Cancel</button><button className="button button-primary" type="submit" disabled={saving || !name.trim()}>{saving ? "Creating…" : "Create workspace"}</button></div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

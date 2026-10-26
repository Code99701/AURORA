"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FolderKanban,
  Plus,
  Search,
  Grid,
  List,
  ArrowRight,
  X,
  FileText,
  Network,
  Cpu,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageSkeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { useWorkspaces } from "@/hooks/use-workspaces";
import { ApiError } from "@/lib/api";

const TAG_COLORS = ["purple", "teal", "coral", "amber"] as const;

export function WorkspaceDashboard() {
  const router = useRouter();
  const { workspaces, loading, error, createWorkspace } = useWorkspaces();
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const filteredWorkspaces = useMemo(() => {
    return workspaces.filter((ws) => {
      const query = searchQuery.toLowerCase();
      const matchesName = ws.name.toLowerCase().includes(query);
      const matchesDesc = (ws.description || "").toLowerCase().includes(query);
      return matchesName || matchesDesc;
    });
  }, [workspaces, searchQuery]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const title = newTitle.trim();
    if (!title) return;

    setCreating(true);
    setCreateError("");
    try {
      const created = await createWorkspace(title, newDesc.trim() || undefined);
      setIsModalOpen(false);
      setNewTitle("");
      setNewDesc("");
      router.push(`/workspaces/${created.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setCreateError(err.message);
      } else if (err instanceof Error) {
        setCreateError(err.message);
      } else {
        setCreateError("Could not create workspace. Please try again.");
      }
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return <PageSkeleton />;
  }

  return (
    <div style={{ maxWidth: "1280px", margin: "0 auto", padding: "1.5rem 1.5rem 5rem" }}>
      {/* Top Telemetry / Status Line */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem", flexWrap: "wrap", gap: "0.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", padding: "0.2rem 0.65rem", borderRadius: "999px", background: "rgba(108, 92, 231, 0.1)", color: "var(--accent, #6C5CE7)", fontFamily: "var(--font-mono)", fontSize: "0.75rem", fontWeight: 700 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent, #6C5CE7)" }} />
            Hybrid RAG Pipeline · pgvector
          </span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--muted, #8E93B0)" }}>
            PostgreSQL 16 + pgvector 768-d
          </span>
        </div>
      </div>

      {/* Main Header & Actions */}
      <section style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: "1.5rem", marginBottom: "2rem" }}>
        <div>
          <h1 style={{ fontSize: "2.4rem", fontWeight: 800, margin: "0 0 0.5rem", letterSpacing: "-0.02em", color: "var(--foreground, #1A1D2E)" }}>
            Research Workspaces
          </h1>
          <p style={{ fontSize: "1.05rem", color: "var(--foreground-soft, #4A4F6A)", margin: 0, maxWidth: "680px" }}>
            Organize, ingest, and interrogate domain corpora with citation grounding across academic and institutional literature.
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <Button
            size="md"
            leftIcon={<Plus size={18} />}
            onClick={() => {
              setCreateError("");
              setIsModalOpen(true);
            }}
            style={{
              background: "linear-gradient(135deg, var(--accent, #6C5CE7) 0%, var(--accent-strong, #5A4BD1) 100%)",
              boxShadow: "0 4px 16px rgba(108, 92, 231, 0.28)",
            }}
          >
            Create New Workspace
          </Button>
        </div>
      </section>

      {/* Real Metric Ribbon */}
      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1.25rem", marginBottom: "2rem" }}>
        {/* Metric 1 */}
        <div style={{ background: "var(--surface, #FFFFFF)", padding: "1.5rem", borderRadius: "var(--radius-xl, 24px)", boxShadow: "0 4px 20px rgba(108, 92, 231, 0.05)", border: "1px solid var(--border, #E2E5F0)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <span style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--muted, #8E93B0)" }}>
              Active Workspaces
            </span>
            <div style={{ width: 32, height: 32, borderRadius: "8px", background: "var(--accent-soft, #EDE9FE)", color: "var(--accent, #6C5CE7)", display: "grid", placeItems: "center" }}>
              <FolderKanban size={16} />
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
            <span style={{ fontSize: "2rem", fontWeight: 800, color: "var(--foreground, #1A1D2E)" }}>{workspaces.length}</span>
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--muted, #8E93B0)", margin: "0.35rem 0 0" }}>
            Private research collections
          </p>
        </div>

        {/* Metric 2 */}
        <div style={{ background: "var(--surface, #FFFFFF)", padding: "1.5rem", borderRadius: "var(--radius-xl, 24px)", boxShadow: "0 4px 20px rgba(108, 92, 231, 0.05)", border: "1px solid var(--border, #E2E5F0)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <span style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--muted, #8E93B0)" }}>
              Vector Store
            </span>
            <div style={{ width: 32, height: 32, borderRadius: "8px", background: "var(--teal-soft, #E0FAFA)", color: "var(--teal, #00D2D3)", display: "grid", placeItems: "center" }}>
              <Network size={16} />
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
            <span style={{ fontSize: "1.35rem", fontWeight: 800, color: "var(--foreground, #1A1D2E)" }}>768-dim</span>
            <span style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", background: "var(--surface-raised, #F5F7FC)", padding: "0.15rem 0.5rem", borderRadius: "999px", color: "var(--foreground-soft, #4A4F6A)" }}>
              Cosine
            </span>
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--muted, #8E93B0)", margin: "0.35rem 0 0" }}>
            pgvector exact vector search
          </p>
        </div>

        {/* Metric 3 */}
        <div style={{ background: "var(--surface, #FFFFFF)", padding: "1.5rem", borderRadius: "var(--radius-xl, 24px)", boxShadow: "0 4px 20px rgba(108, 92, 231, 0.05)", border: "1px solid var(--border, #E2E5F0)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <span style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--muted, #8E93B0)" }}>
              OCR Engine
            </span>
            <div style={{ width: 32, height: 32, borderRadius: "8px", background: "var(--coral-soft, #FFF0F0)", color: "var(--coral, #FF6B6B)", display: "grid", placeItems: "center" }}>
              <Cpu size={16} />
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
            <span style={{ fontSize: "1.35rem", fontWeight: 800, color: "var(--foreground, #1A1D2E)" }}>Tesseract 5</span>
            <span style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "var(--accent, #6C5CE7)", fontWeight: 700 }}>
              eng + hin
            </span>
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--muted, #8E93B0)", margin: "0.35rem 0 0" }}>
            English & Hindi OCR extraction
          </p>
        </div>

        {/* Metric 4 */}
        <div style={{ background: "var(--surface, #FFFFFF)", padding: "1.5rem", borderRadius: "var(--radius-xl, 24px)", boxShadow: "0 4px 20px rgba(108, 92, 231, 0.05)", border: "1px solid var(--border, #E2E5F0)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <span style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--muted, #8E93B0)" }}>
              Supported Formats
            </span>
            <div style={{ width: 32, height: 32, borderRadius: "8px", background: "var(--teal-soft, #E0FAFA)", color: "var(--teal, #00D2D3)", display: "grid", placeItems: "center" }}>
              <FileText size={16} />
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
            <span style={{ fontSize: "1.2rem", fontWeight: 800, color: "var(--teal, #00D2D3)" }}>PDF · TXT · DOCX</span>
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--muted, #8E93B0)", margin: "0.35rem 0 0" }}>
            + XLSX, PPTX, MD, CSV, TSV
          </p>
        </div>
      </section>

      {/* Search & View Controls */}
      <section
        style={{
          background: "var(--surface, #FFFFFF)",
          padding: "1rem 1.25rem",
          borderRadius: "var(--radius-xl, 24px)",
          border: "1px solid var(--border, #E2E5F0)",
          boxShadow: "0 2px 12px rgba(108, 92, 231, 0.03)",
          marginBottom: "2rem",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        {/* Search Box */}
        <div style={{ position: "relative", width: "100%", maxWidth: "420px" }}>
          <Search size={18} color="var(--muted, #8E93B0)" style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)" }} />
          <input
            type="text"
            placeholder="Search workspaces by name or description..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: "100%",
              padding: "0.6rem 1rem 0.6rem 2.6rem",
              borderRadius: "var(--radius-md, 12px)",
              border: "1px solid var(--border, #E2E5F0)",
              background: "var(--surface-raised, #F5F7FC)",
              fontSize: "0.9rem",
              outline: "none",
              color: "var(--foreground, #1A1D2E)",
            }}
          />
        </div>

        {/* View Toggles */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <div style={{ display: "flex", background: "var(--surface-raised, #F5F7FC)", padding: "0.25rem", borderRadius: "8px", border: "1px solid var(--border, #E2E5F0)" }}>
            <button
              type="button"
              onClick={() => setViewMode("grid")}
              aria-label="Grid view"
              style={{
                border: "none",
                padding: "0.35rem 0.5rem",
                borderRadius: "6px",
                background: viewMode === "grid" ? "#FFFFFF" : "transparent",
                color: viewMode === "grid" ? "var(--accent, #6C5CE7)" : "var(--muted, #8E93B0)",
                cursor: "pointer",
                display: "grid",
                placeItems: "center",
                boxShadow: viewMode === "grid" ? "0 2px 6px rgba(0,0,0,0.06)" : "none",
              }}
            >
              <Grid size={16} />
            </button>
            <button
              type="button"
              onClick={() => setViewMode("table")}
              aria-label="List view"
              style={{
                border: "none",
                padding: "0.35rem 0.5rem",
                borderRadius: "6px",
                background: viewMode === "table" ? "#FFFFFF" : "transparent",
                color: viewMode === "table" ? "var(--accent, #6C5CE7)" : "var(--muted, #8E93B0)",
                cursor: "pointer",
                display: "grid",
                placeItems: "center",
                boxShadow: viewMode === "table" ? "0 2px 6px rgba(0,0,0,0.06)" : "none",
              }}
            >
              <List size={16} />
            </button>
          </div>
        </div>
      </section>

      {/* Error Banner */}
      {error && (
        <div role="alert" className="error-banner" style={{ marginBottom: "2rem" }}>
          {error}
        </div>
      )}

      {/* Workspaces List / Empty State */}
      {workspaces.length === 0 ? (
        <EmptyState
          icon={FolderKanban}
          title="No research workspaces yet"
          description="Create your first workspace to begin uploading literature and asking grounded research questions."
          action={
            <Button
              variant="primary"
              size="md"
              leftIcon={<Plus size={18} />}
              onClick={() => {
                setCreateError("");
                setIsModalOpen(true);
              }}
            >
              Create Workspace
            </Button>
          }
        />
      ) : filteredWorkspaces.length === 0 ? (
        <div style={{ textAlign: "center", padding: "4rem 2rem", color: "var(--muted, #8E93B0)" }}>
          <p style={{ margin: 0, fontSize: "1.1rem" }}>No workspaces match &quot;{searchQuery}&quot;</p>
        </div>
      ) : viewMode === "grid" ? (
        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: "1.75rem" }}>
          {filteredWorkspaces.map((ws, index) => {
            const color = TAG_COLORS[index % TAG_COLORS.length];
            return (
              <article
                key={ws.id}
                style={{
                  background: "var(--surface, #FFFFFF)",
                  borderRadius: "var(--radius-xl, 24px)",
                  padding: "1.5rem",
                  boxShadow: "0 8px 30px rgba(108, 92, 231, 0.06)",
                  border: "1px solid var(--border, #E2E5F0)",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  position: "relative",
                  overflow: "hidden",
                  transition: "all 0.2s ease",
                }}
              >
                {/* Top Accent Gradient Border */}
                <div
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    right: 0,
                    height: "4px",
                    background:
                      color === "teal"
                        ? "linear-gradient(90deg, #00D2D3, #6C5CE7)"
                        : color === "purple"
                        ? "linear-gradient(90deg, #6C5CE7, #A29BFE)"
                        : color === "coral"
                        ? "linear-gradient(90deg, #FF6B6B, #FFA07A)"
                        : "linear-gradient(90deg, #FECA57, #FF9FF3)",
                  }}
                />

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.85rem" }}>
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "0.35rem",
                        fontSize: "0.78rem",
                        fontWeight: 600,
                        padding: "0.25rem 0.65rem",
                        borderRadius: "999px",
                        background: "var(--surface-raised, #F5F7FC)",
                        color: "var(--foreground, #1A1D2E)",
                        border: "1px solid var(--border, #E2E5F0)",
                      }}
                    >
                      <span>📁</span> Workspace
                    </span>
                    <span style={{ fontSize: "0.72rem", color: "var(--muted, #8E93B0)", fontFamily: "var(--font-mono)" }}>
                      {new Date(ws.created_at).toLocaleDateString()}
                    </span>
                  </div>

                  <h3 style={{ fontSize: "1.25rem", fontWeight: 700, margin: "0 0 0.5rem", color: "var(--foreground, #1A1D2E)" }}>
                    {ws.name}
                  </h3>
                  <p style={{ fontSize: "0.88rem", color: "var(--foreground-soft, #4A4F6A)", margin: "0 0 1.25rem", lineHeight: 1.55 }}>
                    {ws.description || "A private source collection for grounded research."}
                  </p>
                </div>

                {/* Bottom Row */}
                <div style={{ borderTop: "1px solid var(--border, #E2E5F0)", paddingTop: "0.85rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "0.75rem", color: "var(--muted, #8E93B0)" }}>
                    ID: {ws.id.slice(0, 8)}...
                  </span>

                  <Link href={`/workspaces/${ws.id}`}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem", color: "var(--accent, #6C5CE7)", fontSize: "0.85rem", fontWeight: 700 }}>
                      Open Desk <ArrowRight size={14} />
                    </span>
                  </Link>
                </div>
              </article>
            );
          })}
        </section>
      ) : (
        /* Dense Table View */
        <section style={{ background: "var(--surface, #FFFFFF)", borderRadius: "var(--radius-xl, 24px)", overflow: "hidden", border: "1px solid var(--border, #E2E5F0)", boxShadow: "0 4px 20px rgba(108, 92, 231, 0.04)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.88rem" }}>
            <thead>
              <tr style={{ background: "var(--surface-raised, #F5F7FC)", color: "var(--foreground-soft, #4A4F6A)", borderBottom: "1px solid var(--border, #E2E5F0)" }}>
                <th style={{ padding: "0.85rem 1.25rem", textAlign: "left" }}>Workspace</th>
                <th style={{ padding: "0.85rem 1rem", textAlign: "left" }}>Description</th>
                <th style={{ padding: "0.85rem 1rem", textAlign: "left" }}>Created</th>
                <th style={{ padding: "0.85rem 1.25rem", textAlign: "right" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredWorkspaces.map((ws) => (
                <tr key={ws.id} style={{ borderBottom: "1px solid var(--border, #E2E5F0)" }}>
                  <td style={{ padding: "1rem 1.25rem" }}>
                    <div style={{ fontWeight: 700, color: "var(--foreground, #1A1D2E)" }}>{ws.name}</div>
                  </td>
                  <td style={{ padding: "1rem", color: "var(--foreground-soft, #4A4F6A)", fontSize: "0.82rem", maxWidth: "380px" }}>
                    {ws.description || "A private source collection for grounded research."}
                  </td>
                  <td style={{ padding: "1rem", fontSize: "0.78rem", color: "var(--muted, #8E93B0)", fontFamily: "var(--font-mono)" }}>
                    {new Date(ws.created_at).toLocaleDateString()}
                  </td>
                  <td style={{ padding: "1rem 1.25rem", textAlign: "right" }}>
                    <Link href={`/workspaces/${ws.id}`} className="button button-secondary button-sm">
                      Open Desk <ArrowRight size={14} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* Real Create Workspace Modal */}
      {isModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15, 23, 42, 0.45)",
            backdropFilter: "blur(4px)",
            display: "grid",
            placeItems: "center",
            padding: "1rem",
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: "var(--surface, #FFFFFF)",
              borderRadius: "var(--radius-xl, 24px)",
              padding: "2rem",
              width: "100%",
              maxWidth: "520px",
              boxShadow: "0 24px 60px rgba(0,0,0,0.18)",
              border: "1px solid var(--border, #E2E5F0)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <div style={{ width: 36, height: 36, borderRadius: "10px", background: "var(--accent-soft, #EDE9FE)", color: "var(--accent, #6C5CE7)", display: "grid", placeItems: "center" }}>
                  <Plus size={20} />
                </div>
                <h2 style={{ fontSize: "1.35rem", fontWeight: 800, margin: 0 }}>Create Research Workspace</h2>
              </div>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--muted, #8E93B0)" }}
              >
                <X size={20} />
              </button>
            </div>

            {createError && (
              <div role="alert" className="error-banner" style={{ marginBottom: "1rem" }}>
                {createError}
              </div>
            )}

            <form onSubmit={handleCreate} style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.35rem", color: "var(--foreground, #1A1D2E)" }}>
                  Workspace Title *
                </label>
                <input
                  id="workspace-title-input"
                  type="text"
                  required
                  placeholder="e.g., Solid-State Electrolyte Lab"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "0.65rem 0.85rem",
                    borderRadius: "var(--radius-md, 12px)",
                    border: "1px solid var(--border, #E2E5F0)",
                    background: "var(--surface-raised, #F5F7FC)",
                    fontSize: "0.9rem",
                    outline: "none",
                  }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.35rem", color: "var(--foreground, #1A1D2E)" }}>
                  Research Scope / Description
                </label>
                <textarea
                  id="workspace-desc-input"
                  rows={3}
                  placeholder="Specify primary research objectives and initial document types..."
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "0.65rem 0.85rem",
                    borderRadius: "var(--radius-md, 12px)",
                    border: "1px solid var(--border, #E2E5F0)",
                    background: "var(--surface-raised, #F5F7FC)",
                    fontSize: "0.9rem",
                    outline: "none",
                    resize: "none",
                  }}
                />
              </div>

              <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end", marginTop: "0.5rem" }}>
                <Button type="button" variant="ghost" onClick={() => setIsModalOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" busy={creating}>
                  Create Workspace
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

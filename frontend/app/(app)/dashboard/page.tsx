"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Plus, PanelsTopLeft, FileText, ArrowRight, Activity } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useWorkspaces } from "@/hooks/use-workspaces";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageSkeleton } from "@/components/ui/skeleton";
import { formatDate } from "@/lib/utils";
import { api } from "@/lib/api";

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth();
  const { workspaces, loading: wsLoading } = useWorkspaces();
  const [platformStatus, setPlatformStatus] = useState<string>("Checking…");
  const [isHealthy, setIsHealthy] = useState<boolean>(true);

  useEffect(() => {
    let cancelled = false;
    api.health()
      .then((res) => {
        if (!cancelled) {
          setPlatformStatus(res.status === "ok" ? "Operational" : res.status);
          setIsHealthy(res.status === "ok");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPlatformStatus("Offline");
          setIsHealthy(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (authLoading || wsLoading) {
    return <PageSkeleton />;
  }

  const workspaceCount = workspaces.length;
  const recentWorkspace = workspaces[0];

  return (
    <div style={{ maxWidth: "1080px", margin: "0 auto", padding: "1.5rem 1.5rem 4rem" }}>
      {/* Welcome Header */}
      <section style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "1.75rem", fontWeight: 800, margin: "0 0 0.4rem", color: "var(--foreground)" }}>
          Welcome back, {user?.display_name || "Researcher"}
        </h1>
        <p style={{ color: "var(--foreground-soft)", margin: 0, fontSize: "0.95rem" }}>
          Manage your research workspaces, indexed document collections, and conversations.
        </p>
      </section>

      {/* Continue where you left off */}
      {recentWorkspace && (
        <section style={{ marginBottom: "2rem" }}>
          <div
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              padding: "1.25rem 1.5rem",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "1rem",
            }}
          >
            <div>
              <div style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--accent)", marginBottom: "0.25rem" }}>
                Continue where you left off
              </div>
              <h2 style={{ fontSize: "1.15rem", fontWeight: 700, margin: "0 0 0.25rem", color: "var(--foreground)" }}>
                {recentWorkspace.name}
              </h2>
              <span style={{ fontSize: "0.82rem", color: "var(--muted)" }}>
                Updated {formatDate(recentWorkspace.updated_at)}
              </span>
            </div>
            <Link href={`/workspaces/${recentWorkspace.id}`} className="button button-primary">
              Open Research Desk <ArrowRight size={15} />
            </Link>
          </div>
        </section>
      )}

      {/* Real Stats Cards */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "1rem",
          marginBottom: "2.5rem",
        }}
      >
        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: "6px",
                background: "var(--accent-soft)",
                color: "var(--accent)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <PanelsTopLeft size={16} />
            </div>
            <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--muted)" }}>
              Workspaces
            </span>
          </div>
          <div style={{ fontSize: "1.85rem", fontWeight: 800, color: "var(--foreground)" }}>{workspaceCount}</div>
        </Card>

        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: "6px",
                background: "var(--surface-raised)",
                color: "var(--foreground-soft)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Activity size={16} />
            </div>
            <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--muted)" }}>
              Platform Status
            </span>
          </div>
          <div style={{ fontSize: "1.2rem", fontWeight: 700, color: isHealthy ? "var(--success)" : "var(--danger)", marginTop: "0.3rem" }}>
            {platformStatus}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "0.2rem" }}>
            Real-time API health
          </div>
        </Card>

        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: "6px",
                background: "var(--surface-raised)",
                color: "var(--foreground-soft)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <FileText size={16} />
            </div>
            <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--muted)" }}>
              Supported Formats
            </span>
          </div>
          <div style={{ fontSize: "1.05rem", fontWeight: 700, marginTop: "0.3rem", color: "var(--foreground)" }}>
            PDF · DOCX · PPTX · XLSX · TXT
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "0.2rem" }}>
            Up to 10 MB per file
          </div>
        </Card>
      </section>

      {/* Recent Workspaces */}
      <section>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
          <h2 style={{ fontSize: "1.15rem", fontWeight: 700, margin: 0, color: "var(--foreground)" }}>Your Workspaces</h2>
          <Link href="/workspaces?manage=true" style={{ fontSize: "0.85rem", color: "var(--accent)", textDecoration: "none", fontWeight: 600 }}>
            Manage All →
          </Link>
        </div>

        {workspaces.length === 0 ? (
          <Card style={{ textAlign: "center", padding: "3rem 1.5rem" }}>
            <PanelsTopLeft size={36} style={{ color: "var(--muted)", marginBottom: "1rem" }} />
            <h3 style={{ fontSize: "1.05rem", margin: "0 0 0.5rem", color: "var(--foreground)" }}>No workspaces created yet</h3>
            <p style={{ color: "var(--foreground-soft)", maxWidth: "420px", margin: "0 auto 1.5rem", fontSize: "0.875rem" }}>
              Workspaces isolate your uploaded documents, embeddings, and research conversations.
            </p>
            <Link href="/workspaces?manage=true">
              <Button size="sm" leftIcon={<Plus size={16} />}>
                Create Workspace
              </Button>
            </Link>
          </Card>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "1rem" }}>
            {workspaces.slice(0, 6).map((ws) => (
              <Link key={ws.id} href={`/workspaces/${ws.id}`} style={{ textDecoration: "none" }}>
                <Card interactive>
                  <h3 style={{ fontSize: "1rem", fontWeight: 700, margin: "0 0 0.35rem", color: "var(--foreground)" }}>{ws.name}</h3>
                  <p style={{ fontSize: "0.82rem", color: "var(--foreground-soft)", margin: "0 0 0.75rem", minHeight: "2.4em", lineHeight: 1.5 }}>
                    {ws.description || "Upload documents and ask questions with cited answers."}
                  </p>
                  <div style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
                    Updated {formatDate(ws.updated_at)}
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Plus, PanelsTopLeft, FileText, MessageSquare, ArrowRight } from "lucide-react";
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
  const [platformStatus, setPlatformStatus] = useState<string>("Checking...");
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

  return (
    <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "1.5rem" }}>
      {/* Welcome Header */}
      <section style={{ marginBottom: "2.5rem" }}>
        <h1 style={{ fontSize: "1.75rem", fontWeight: 800, margin: "0 0 0.5rem" }}>
          Welcome back, {user?.display_name || "Researcher"}
        </h1>
        <p style={{ color: "var(--foreground-soft, #4A4F6A)", margin: 0 }}>
          Manage your research workspaces, indexed document collections, and conversations.
        </p>
      </section>

      {/* Stats Cards */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "1.25rem",
          marginBottom: "2.5rem",
        }}
      >
        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: "var(--radius-sm, 8px)",
                background: "var(--accent-soft, #EDE9FE)",
                color: "var(--accent, #6C5CE7)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <PanelsTopLeft size={18} />
            </div>
            <span style={{ fontSize: "var(--text-sm, 0.875rem)", fontWeight: 600, color: "var(--foreground-soft, #4A4F6A)" }}>
              Workspaces
            </span>
          </div>
          <div style={{ fontSize: "2rem", fontWeight: 800 }}>{workspaceCount}</div>
        </Card>

        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: "var(--radius-sm, 8px)",
                background: "rgba(0, 210, 211, 0.12)",
                color: "var(--teal, #00D2D3)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <FileText size={18} />
            </div>
            <span style={{ fontSize: "var(--text-sm, 0.875rem)", fontWeight: 600, color: "var(--foreground-soft, #4A4F6A)" }}>
              Platform Status
            </span>
          </div>
          <div style={{ fontSize: "1.25rem", fontWeight: 700, color: isHealthy ? "var(--success, #00B894)" : "var(--coral, #FF6B6B)", marginTop: "0.4rem" }}>
            {platformStatus}
          </div>
        </Card>

        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: "var(--radius-sm, 8px)",
                background: "rgba(255, 107, 107, 0.12)",
                color: "var(--coral, #FF6B6B)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <MessageSquare size={18} />
            </div>
            <span style={{ fontSize: "var(--text-sm, 0.875rem)", fontWeight: 600, color: "var(--foreground-soft, #4A4F6A)" }}>
              Supported Modes
            </span>
          </div>
          <div style={{ fontSize: "1.25rem", fontWeight: 700, marginTop: "0.4rem" }}>
            English & हिन्दी
          </div>
        </Card>
      </section>

      {/* Recent Workspaces */}
      <section>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.25rem" }}>
          <h2 style={{ fontSize: "1.25rem", fontWeight: 700, margin: 0 }}>Your Workspaces</h2>
          <Link href="/workspaces">
            <Button variant="ghost" size="sm" rightIcon={<ArrowRight size={14} />}>
              View All
            </Button>
          </Link>
        </div>

        {workspaces.length === 0 ? (
          <Card style={{ textAlign: "center", padding: "3rem 1.5rem" }}>
            <PanelsTopLeft size={36} style={{ color: "var(--muted, #8E93B0)", marginBottom: "1rem" }} />
            <h3 style={{ fontSize: "1.1rem", margin: "0 0 0.5rem" }}>No workspaces created yet</h3>
            <p style={{ color: "var(--foreground-soft, #4A4F6A)", maxWidth: "420px", margin: "0 auto 1.5rem" }}>
              Workspaces isolate your uploaded documents, embeddings, and research conversations.
            </p>
            <Link href="/workspaces">
              <Button size="sm" leftIcon={<Plus size={16} />}>
                Create Workspace
              </Button>
            </Link>
          </Card>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "1rem" }}>
            {workspaces.slice(0, 6).map((ws) => (
              <Link key={ws.id} href={`/workspaces/${ws.id}`} style={{ textDecoration: "none" }}>
                <Card interactive>
                  <h3 style={{ fontSize: "1.05rem", fontWeight: 700, margin: "0 0 0.4rem" }}>{ws.name}</h3>
                  <p style={{ fontSize: "0.85rem", color: "var(--foreground-soft, #4A4F6A)", margin: "0 0 0.85rem", minHeight: "2.4em" }}>
                    {ws.description || "Evidence workspace with uploaded knowledge sources."}
                  </p>
                  <div style={{ fontSize: "0.75rem", color: "var(--muted, #8E93B0)" }}>
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

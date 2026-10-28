"use client";

import { useAuth } from "@/hooks/use-auth";
import { useTheme } from "@/hooks/use-theme";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PageSkeleton } from "@/components/ui/skeleton";
import { Moon, Sun, User, Shield, Info, LogOut, Globe } from "lucide-react";
import { formatDate } from "@/lib/utils";

export default function SettingsPage() {
  const { user, loading, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  if (loading) {
    return <PageSkeleton />;
  }

  return (
    <div style={{ maxWidth: "760px", margin: "0 auto", padding: "1.5rem 1.5rem 4rem" }}>
      <h1 style={{ fontSize: "1.75rem", fontWeight: 800, margin: "0 0 1.5rem", color: "var(--foreground)" }}>Settings</h1>

      <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        {/* Profile Details */}
        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
            <div style={{ width: 28, height: 28, borderRadius: "6px", background: "var(--accent-soft)", color: "var(--accent)", display: "grid", placeItems: "center" }}>
              <User size={15} />
            </div>
            <h2 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0, color: "var(--foreground)" }}>Account Information</h2>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "140px 1fr", rowGap: "0.75rem", fontSize: "0.875rem" }}>
            <span style={{ color: "var(--muted)" }}>Display Name</span>
            <strong style={{ color: "var(--foreground)" }}>{user?.display_name || "—"}</strong>
            <span style={{ color: "var(--muted)" }}>Email</span>
            <span style={{ color: "var(--foreground)" }}>{user?.email || "—"}</span>
            <span style={{ color: "var(--muted)" }}>System Role</span>
            <span style={{ color: "var(--foreground)" }}>{user?.system_role || "User"}</span>
            <span style={{ color: "var(--muted)" }}>Member Since</span>
            <span style={{ color: "var(--foreground)" }}>{user?.created_at ? formatDate(user.created_at) : "—"}</span>
          </div>
        </Card>

        {/* Appearance Settings */}
        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem" }}>
            <div style={{ width: 28, height: 28, borderRadius: "6px", background: "var(--surface-raised)", color: "var(--foreground-soft)", display: "grid", placeItems: "center" }}>
              {theme === "dark" ? <Moon size={15} /> : <Sun size={15} />}
            </div>
            <h2 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0, color: "var(--foreground)" }}>Appearance</h2>
          </div>
          <p style={{ color: "var(--foreground-soft)", fontSize: "0.875rem", margin: "0 0 1rem" }}>
            Select your preferred visual theme for the AURORA workspace.
          </p>
          <div style={{ display: "inline-flex", background: "var(--surface-raised)", padding: "4px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)" }}>
            <button
              type="button"
              onClick={() => { if (theme === "dark") toggleTheme(); }}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                height: "32px",
                padding: "0 14px",
                border: "none",
                borderRadius: "4px",
                background: theme === "light" ? "var(--surface)" : "transparent",
                color: theme === "light" ? "var(--accent)" : "var(--muted)",
                boxShadow: theme === "light" ? "var(--shadow-sm)" : "none",
                fontSize: "0.84rem",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              <Sun size={14} /> Light
            </button>
            <button
              type="button"
              onClick={() => { if (theme === "light") toggleTheme(); }}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                height: "32px",
                padding: "0 14px",
                border: "none",
                borderRadius: "4px",
                background: theme === "dark" ? "var(--surface)" : "transparent",
                color: theme === "dark" ? "var(--accent)" : "var(--muted)",
                boxShadow: theme === "dark" ? "var(--shadow-sm)" : "none",
                fontSize: "0.84rem",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              <Moon size={14} /> Dark
            </button>
          </div>
        </Card>

        {/* Language & Multilingual Grounding */}
        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem" }}>
            <div style={{ width: 28, height: 28, borderRadius: "6px", background: "var(--surface-raised)", color: "var(--foreground-soft)", display: "grid", placeItems: "center" }}>
              <Globe size={15} />
            </div>
            <h2 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0, color: "var(--foreground)" }}>Language Grounding</h2>
          </div>
          <p style={{ color: "var(--foreground-soft)", fontSize: "0.875rem", margin: "0 0 0.5rem", lineHeight: 1.5 }}>
            AURORA natively supports cross-lingual retrieval and citation matching across English and Hindi documents.
          </p>
          <span style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
            Multilingual embedding model: intfloat/multilingual-e5-base
          </span>
        </Card>

        {/* Security & Session */}
        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem" }}>
            <div style={{ width: 28, height: 28, borderRadius: "6px", background: "var(--surface-raised)", color: "var(--foreground-soft)", display: "grid", placeItems: "center" }}>
              <Shield size={15} />
            </div>
            <h2 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0, color: "var(--foreground)" }}>Session & Security</h2>
          </div>
          <p style={{ color: "var(--foreground-soft)", fontSize: "0.875rem", margin: "0 0 1rem", lineHeight: 1.5 }}>
            Your session is secured with encrypted HTTP-only cookies. To end your current session across this browser:
          </p>
          <Button
            variant="danger"
            size="sm"
            onClick={() => void logout()}
            leftIcon={<LogOut size={14} />}
          >
            Sign Out
          </Button>
        </Card>

        {/* System Information */}
        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem" }}>
            <div style={{ width: 28, height: 28, borderRadius: "6px", background: "var(--surface-raised)", color: "var(--foreground-soft)", display: "grid", placeItems: "center" }}>
              <Info size={15} />
            </div>
            <h2 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0, color: "var(--foreground)" }}>System Version</h2>
          </div>
          <div style={{ fontSize: "0.85rem", color: "var(--foreground-soft)", display: "flex", flexDirection: "column", gap: "0.3rem" }}>
            <span style={{ fontWeight: 600 }}>AURORA Platform · v1.0.0</span>
            <span style={{ color: "var(--success)", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.35rem" }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "currentColor", display: "inline-block" }} />
              All services operational
            </span>
          </div>
        </Card>
      </div>
    </div>
  );
}

"use client";

import { useAuth } from "@/hooks/use-auth";
import { useTheme } from "@/hooks/use-theme";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PageSkeleton } from "@/components/ui/skeleton";
import { Moon, Sun, User, Shield, Info } from "lucide-react";
import { formatDate } from "@/lib/utils";

export default function SettingsPage() {
  const { user, loading } = useAuth();
  const { theme, toggleTheme } = useTheme();

  if (loading) {
    return <PageSkeleton />;
  }

  return (
    <div style={{ maxWidth: "800px", margin: "0 auto", padding: "1.5rem" }}>
      <h1 style={{ fontSize: "1.75rem", fontWeight: 800, margin: "0 0 1.5rem" }}>Settings</h1>

      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        {/* Profile Details */}
        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
            <User size={20} color="var(--accent, #6C5CE7)" />
            <h2 style={{ fontSize: "1.15rem", fontWeight: 700, margin: 0 }}>Account Information</h2>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "140px 1fr", rowGap: "0.75rem", fontSize: "0.9rem" }}>
            <span style={{ color: "var(--muted, #8E93B0)" }}>Display Name:</span>
            <strong>{user?.display_name || "—"}</strong>
            <span style={{ color: "var(--muted, #8E93B0)" }}>Email:</span>
            <span>{user?.email || "—"}</span>
            <span style={{ color: "var(--muted, #8E93B0)" }}>System Role:</span>
            <span>{user?.system_role || "User"}</span>
            <span style={{ color: "var(--muted, #8E93B0)" }}>Member Since:</span>
            <span>{user?.created_at ? formatDate(user.created_at) : "—"}</span>
          </div>
        </Card>

        {/* Appearance Settings */}
        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
            {theme === "dark" ? <Moon size={20} color="var(--accent, #6C5CE7)" /> : <Sun size={20} color="var(--amber, #FECA57)" />}
            <h2 style={{ fontSize: "1.15rem", fontWeight: 700, margin: 0 }}>Appearance</h2>
          </div>
          <p style={{ color: "var(--foreground-soft, #4A4F6A)", fontSize: "0.9rem", margin: "0 0 1rem" }}>
            Choose between light and dark visual themes.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={toggleTheme}
            leftIcon={theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          >
            Switch to {theme === "dark" ? "Light" : "Dark"} Mode
          </Button>
        </Card>

        {/* Security & Sessions */}
        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
            <Shield size={20} color="var(--teal, #00D2D3)" />
            <h2 style={{ fontSize: "1.15rem", fontWeight: 700, margin: 0 }}>Security & Storage</h2>
          </div>
          <p style={{ color: "var(--foreground-soft, #4A4F6A)", fontSize: "0.9rem", margin: 0, lineHeight: 1.6 }}>
            Your session is secured with an HttpOnly cookie and argon2id password hashing. Documents are stored in private workspace storage and parsed locally with Tesseract 5 OCR and PyMuPDF.
          </p>
        </Card>

        {/* System Information */}
        <Card>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
            <Info size={20} color="var(--coral, #FF6B6B)" />
            <h2 style={{ fontSize: "1.15rem", fontWeight: 700, margin: 0 }}>System Version</h2>
          </div>
          <div style={{ fontSize: "0.85rem", color: "var(--foreground-soft, #4A4F6A)", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
            <span>AURORA Web Platform · Version 1.0.0</span>
            <span>Next.js 16.3.0 · React 19.2.8 · PostgreSQL 16 pgvector</span>
          </div>
        </Card>
      </div>
    </div>
  );
}

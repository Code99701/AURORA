"use client";

import { BookOpen, LogOut, Menu, PanelsTopLeft, Settings, LayoutDashboard, ExternalLink, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";
import { Brand } from "@/components/shared/brand";
import { PageSkeleton } from "@/components/ui/skeleton";
import styles from "./app-shell.module.css";

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.me()
      .then((u) => {
        if (!cancelled) {
          setUser(u);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          router.replace("/login");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function logout() {
    await api.logout().catch(() => undefined);
    router.replace("/login");
  }

  // Detect active workspace UUID in pathname if present
  const workspaceIdMatch = pathname.match(/\/workspaces\/([0-9a-fA-F-]{36})/);
  const activeWorkspaceId = workspaceIdMatch ? workspaceIdMatch[1] : null;

  const researchHref = activeWorkspaceId ? `/workspaces/${activeWorkspaceId}` : "/workspaces";
  const documentsHref = activeWorkspaceId ? `/workspaces/${activeWorkspaceId}/documents` : "/documents";

  if (loading || !user) {
    return <PageSkeleton />;
  }

  const nav = (
    <>
      <div className={styles.sidebarTop}>
        <Brand />
        <button
          className="button button-ghost button-icon"
          onClick={() => setMobileOpen(false)}
          aria-label="Close navigation"
        >
          <X size={20} />
        </button>
      </div>

      <nav className={styles.nav} aria-label="Primary navigation">
        <Link
          className={pathname === "/workspaces" ? styles.active : ""}
          href="/workspaces"
          onClick={() => setMobileOpen(false)}
        >
          <PanelsTopLeft size={18} />
          Workspaces
        </Link>
        <Link
          className={pathname.includes("/workspaces/") && !pathname.includes("/documents") ? styles.active : ""}
          href={researchHref}
          onClick={() => setMobileOpen(false)}
        >
          <BookOpen size={18} />
          Research Studio
        </Link>
        <Link
          className={pathname.includes("/documents") ? styles.active : ""}
          href={documentsHref}
          onClick={() => setMobileOpen(false)}
        >
          <PanelsTopLeft size={18} />
          Ingestion Pipeline
        </Link>

        <span className={styles.navLabel}>System & Settings</span>
        <Link
          className={pathname === "/dashboard" ? styles.active : ""}
          href="/dashboard"
          onClick={() => setMobileOpen(false)}
        >
          <LayoutDashboard size={18} />
          System Dashboard
        </Link>
        <Link
          className={pathname === "/settings" ? styles.active : ""}
          href="/settings"
          onClick={() => setMobileOpen(false)}
        >
          <Settings size={18} />
          Settings
        </Link>
        <a
          href="http://127.0.0.1:8000/docs"
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => setMobileOpen(false)}
          style={{ display: "flex", alignItems: "center", gap: "9px" }}
        >
          <ExternalLink size={18} />
          API Docs (FastAPI)
        </a>
      </nav>

      <div className={styles.userBlock}>
        <div className={styles.avatar} aria-hidden="true">
          {(user.display_name || user.email).slice(0, 2).toUpperCase()}
        </div>
        <div>
          <strong>{user.display_name || user.email}</strong>
          <span>{user.email}</span>
        </div>
        <button
          className="button button-ghost button-icon"
          type="button"
          onClick={logout}
          aria-label="Sign out"
          title="Sign out"
        >
          <LogOut size={18} />
        </button>
      </div>
    </>
  );

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>{nav}</aside>
      {mobileOpen && (
        <div className={styles.mobileOverlay} onClick={() => setMobileOpen(false)} aria-hidden="true" />
      )}
      <aside className={`${styles.mobileSidebar} ${mobileOpen ? styles.mobileSidebarOpen : ""}`}>
        {nav}
      </aside>
      <header className={styles.mobileHeader}>
        <button
          className="button button-ghost button-icon"
          type="button"
          onClick={() => setMobileOpen(true)}
          aria-label="Open navigation"
        >
          <Menu size={21} />
        </button>
        <Brand compact />
      </header>
      <div className={styles.content}>
        <main id="main-content">{children}</main>
      </div>
    </div>
  );
}

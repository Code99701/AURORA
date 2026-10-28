"use client";

import { Suspense, useEffect, useState } from "react";
import {
  BookOpen,
  ChevronDown,
  Files,
  LayoutDashboard,
  LoaderCircle,
  LogOut,
  Menu,
  Moon,
  PanelsTopLeft,
  Plus,
  Search,
  Settings,
  Sun,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import type { Conversation, User, Workspace } from "@/lib/types";
import { Brand } from "@/components/shared/brand";
import { PageSkeleton } from "@/components/ui/skeleton";
import { CommandPalette } from "@/components/shared/command-palette";
import styles from "./app-shell.module.css";

function formatSidebarDate(dateString: string) {
  const d = new Date(dateString);
  const now = new Date();
  const isSameDay =
    d.getDate() === now.getDate() &&
    d.getMonth() === now.getMonth() &&
    d.getFullYear() === now.getFullYear();

  if (isSameDay) return "Today";

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const isYesterday =
    d.getDate() === yesterday.getDate() &&
    d.getMonth() === yesterday.getMonth() &&
    d.getFullYear() === yesterday.getFullYear();

  if (isYesterday) return "Yesterday";

  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

function AppShellInner({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentConvId = searchParams.get("conversation");

  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    if (typeof document !== "undefined") {
      return (document.documentElement.dataset.theme as "light" | "dark") || "light";
    }
    return "light";
  });
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [creatingConv, setCreatingConv] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommandOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    if (!mobileOpen) return;
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileOpen(false);
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [mobileOpen]);


  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    localStorage.setItem("aurora-theme", next);
  };

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

  // Detect active workspace UUID in pathname if present
  const workspaceIdMatch = pathname.match(/\/workspaces\/([0-9a-fA-F-]{36})/);
  const activeWorkspaceId = workspaceIdMatch ? workspaceIdMatch[1] : null;

  useEffect(() => {
    let cancelled = false;
    if (activeWorkspaceId) {
      api.workspace(activeWorkspaceId)
        .then((data) => {
          if (!cancelled) setActiveWorkspace(data);
        })
        .catch(() => {
          if (!cancelled) setActiveWorkspace(null);
        });
    } else {
      // Look up first workspace as fallback
      api.workspaces()
        .then((data) => {
          if (!cancelled && data.items && data.items.length > 0) {
            setActiveWorkspace(data.items[0]);
          }
        })
        .catch(() => {
          if (!cancelled) setActiveWorkspace(null);
        });
    }
    return () => {
      cancelled = true;
    };
  }, [activeWorkspaceId]);

  // Load conversations for active workspace
  useEffect(() => {
    const wsId = activeWorkspaceId || activeWorkspace?.id;
    if (!wsId) return;

    let cancelled = false;
    api.conversations(wsId)
      .then((data) => {
        if (!cancelled) setConversations(data.items || []);
      })
      .catch(() => {
        if (!cancelled) setConversations([]);
      });

    return () => {
      cancelled = true;
    };
  }, [activeWorkspaceId, activeWorkspace?.id, currentConvId]);

  const handleNewConversation = async () => {
    const wsId = activeWorkspaceId || activeWorkspace?.id;
    if (!wsId || creatingConv) return;
    setCreatingConv(true);
    try {
      const conv = await api.createConversation(wsId);
      setConversations((prev) => [conv, ...prev.filter((c) => c.id !== conv.id)]);
      router.push(`/workspaces/${wsId}?conversation=${conv.id}`);
    } catch {
      // ignore
    } finally {
      setCreatingConv(false);
    }
  };

  async function logout() {
    await api.logout().catch(() => undefined);
    router.replace("/login");
  }

  const effectiveWsId = activeWorkspaceId || activeWorkspace?.id;
  const researchHref = effectiveWsId ? `/workspaces/${effectiveWsId}` : "/workspaces";
  const documentsHref = effectiveWsId ? `/workspaces/${effectiveWsId}?view=documents` : "/documents";

  if (loading || !user) {
    return <PageSkeleton />;
  }

  const workspaceName = activeWorkspace?.name || "My Space";
  const workspaceInitial = workspaceName.charAt(0).toUpperCase();

  const isResearchActive = pathname.startsWith("/workspaces/") && !pathname.includes("view=documents");
  const isDocumentsActive = pathname.includes("view=documents") || pathname.includes("/documents");

  const userInitials = (user.display_name || user.email || "AU")
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

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
        {/* Search / ⌘K Button */}
        <button
          type="button"
          onClick={() => {
            setMobileOpen(false);
            setCommandOpen(true);
          }}
          className={styles.searchTrigger}
          aria-label="Search or jump to"
        >
          <span className={styles.searchTriggerLeft}>
            <Search size={14} /> Search or jump to...
          </span>
          <kbd className={styles.searchKbd}>⌘K</kbd>
        </button>

        {/* NAVIGATE Section */}
        <div className={styles.navSectionGroup}>
          <span className={styles.sectionHeader}>NAVIGATE</span>
          <Link
            className={pathname === "/workspaces" && searchParams.get("manage") === "true" ? styles.active : ""}
            href="/workspaces?manage=true"
            onClick={() => setMobileOpen(false)}
          >
            <PanelsTopLeft size={16} />
            <span>Workspaces</span>
          </Link>
          <Link
            className={pathname === "/dashboard" ? styles.active : ""}
            href="/dashboard"
            onClick={() => setMobileOpen(false)}
          >
            <LayoutDashboard size={16} />
            <span>Dashboard</span>
          </Link>
          <Link
            className={pathname === "/settings" ? styles.active : ""}
            href="/settings"
            onClick={() => setMobileOpen(false)}
          >
            <Settings size={16} />
            <span>Settings</span>
          </Link>
        </div>

        {/* WORKSPACE Section */}
        <div className={styles.workspaceSection}>
          <span className={styles.sectionHeader}>WORKSPACE</span>

          <Link href="/workspaces?manage=true" className={styles.workspaceDropdownCard} title="Switch workspace">
            <span className={styles.wsAvatar}>{workspaceInitial}</span>
            <strong className={styles.wsName}>{workspaceName}</strong>
            <ChevronDown size={14} className={styles.wsChevron} />
          </Link>

          <Link
            className={`${styles.subNavLink} ${isResearchActive ? styles.activeSubNav : ""}`}
            href={researchHref}
            onClick={() => setMobileOpen(false)}
          >
            <BookOpen size={16} />
            <span>Research Desk</span>
          </Link>
          <Link
            className={`${styles.subNavLink} ${isDocumentsActive ? styles.activeSubNav : ""}`}
            href={documentsHref}
            onClick={() => setMobileOpen(false)}
          >
            <Files size={16} />
            <span>Documents</span>
          </Link>
        </div>

        {/* CONVERSATIONS Section */}
        <div className={styles.conversationsSection}>
          <div className={styles.conversationsHeader}>
            <span className={styles.sectionHeader}>CONVERSATIONS</span>
          </div>

          <button
            className={styles.newChatButton}
            type="button"
            onClick={handleNewConversation}
            disabled={creatingConv}
            aria-label="New chat"
          >
            {creatingConv ? <LoaderCircle className="spin" size={14} /> : <Plus size={14} />}
            <span>New chat</span>
          </button>

          <div className={styles.conversationsList}>
            {conversations.length === 0 ? (
              <span className={styles.emptyConversations}>No conversations yet</span>
            ) : (
              conversations.map((conv, idx) => {
                const isActive = currentConvId ? conv.id === currentConvId : idx === 0 && isResearchActive;
                return (
                  <Link
                    key={conv.id}
                    href={`/workspaces/${effectiveWsId}?conversation=${conv.id}`}
                    className={`${styles.conversationItem} ${isActive ? styles.activeConversationItem : ""}`}
                    onClick={() => setMobileOpen(false)}
                    title={conv.title || "New thread"}
                  >
                    <span className={styles.convItemTitle}>{conv.title || "New thread"}</span>
                    <span className={styles.convItemMeta}>
                      {formatSidebarDate(conv.updated_at)}
                    </span>
                  </Link>
                );
              })
            )}
          </div>
        </div>
      </nav>

      {/* User Profile Block at bottom */}
      <div className={styles.userBlock}>
        <div className={styles.avatar} aria-hidden="true">
          {userInitials}
        </div>
        <div className={styles.userInfo}>
          <strong>{user.display_name || user.email}</strong>
          <span>{user.email}</span>
        </div>
        <button
          className={styles.themeToggleBtn}
          type="button"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </button>
        <button
          className={styles.logoutBtn}
          type="button"
          onClick={logout}
          aria-label="Sign out"
          title="Sign out"
        >
          <LogOut size={16} />
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
        <main id="main-content" className={styles.main}>
          {children}
        </main>
      </div>
      <CommandPalette isOpen={commandOpen} onClose={() => setCommandOpen(false)} />
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <AppShellInner>{children}</AppShellInner>
    </Suspense>
  );
}

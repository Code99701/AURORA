"use client";

import { BookOpen, LogOut, Menu, PanelsTopLeft, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { PageSkeleton } from "@/components/skeleton";
import styles from "./app-shell.module.css";

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [authError, setAuthError] = useState("");

  useEffect(() => {
    api.me().then(setUser).catch((error) => {
      if (error instanceof ApiError && error.status === 401) router.replace("/login");
      else setAuthError("AURORA could not verify your session. Try refreshing the page.");
    });
  }, [router]);

  async function logout() {
    await api.logout().catch(() => undefined);
    router.replace("/login");
  }

  if (authError) return <main id="main-content" className={styles.center}><div className="error-banner" role="alert">{authError}</div></main>;
  if (!user) return <main id="main-content" className={styles.center}><PageSkeleton /></main>;

  const nav = (
    <>
      <div className={styles.sidebarTop}><Brand /><button className="button button-ghost button-icon" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X size={20} /></button></div>
      <nav className={styles.nav} aria-label="Primary navigation">
        <Link className={pathname === "/workspaces" ? styles.active : ""} href="/workspaces" onClick={() => setMobileOpen(false)}><PanelsTopLeft size={18} />Workspaces</Link>
        <span className={styles.navLabel}>Research</span>
        <span className={styles.navHint}><BookOpen size={17} />Open a workspace to research its sources.</span>
      </nav>
      <div className={styles.userBlock}>
        <div className={styles.avatar} aria-hidden="true">{user.display_name.slice(0, 2).toUpperCase()}</div>
        <div><strong>{user.display_name}</strong><span>{user.email}</span></div>
        <button className="button button-ghost button-icon" type="button" onClick={logout} aria-label="Sign out" title="Sign out"><LogOut size={18} /></button>
      </div>
    </>
  );

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>{nav}</aside>
      {mobileOpen && <div className={styles.mobileOverlay} onClick={() => setMobileOpen(false)} aria-hidden="true" />}
      <aside className={`${styles.mobileSidebar} ${mobileOpen ? styles.mobileSidebarOpen : ""}`}>{nav}</aside>
      <header className={styles.mobileHeader}><button className="button button-ghost button-icon" type="button" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={21} /></button><Brand compact /><ThemeToggle /></header>
      <div className={styles.content}>
        <div className={styles.desktopTools}><ThemeToggle /></div>
        <main id="main-content">{children}</main>
      </div>
    </div>
  );
}

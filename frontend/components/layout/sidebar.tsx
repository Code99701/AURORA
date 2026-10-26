"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  PanelsTopLeft,
  Settings,
  LogOut,
} from "lucide-react";
import { Brand } from "@/components/shared/brand";
import type { User } from "@/lib/types";
import { getInitials } from "@/lib/utils";
import styles from "./sidebar.module.css";

interface SidebarProps {
  user?: User | null;
  onLogout?: () => void;
}

export function Sidebar({ user, onLogout }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside className={styles.sidebar} aria-label="Application navigation">
      <div className={styles.top}>
        <Link href="/" aria-label="AURORA Home">
          <Brand />
        </Link>
      </div>

      <nav className={styles.nav}>
        <span className={styles.navSection}>Main</span>
        <Link
          href="/dashboard"
          className={`${styles.navItem} ${pathname === "/dashboard" ? styles.active : ""}`}
        >
          <LayoutDashboard size={18} />
          <span>Dashboard</span>
        </Link>
        <Link
          href="/workspaces"
          className={`${styles.navItem} ${
            pathname.startsWith("/workspaces") ? styles.active : ""
          }`}
        >
          <PanelsTopLeft size={18} />
          <span>Workspaces</span>
        </Link>

        <span className={styles.navSection}>System</span>
        <Link
          href="/settings"
          className={`${styles.navItem} ${pathname === "/settings" ? styles.active : ""}`}
        >
          <Settings size={18} />
          <span>Settings</span>
        </Link>
      </nav>

      {user && (
        <div className={styles.userBlock}>
          <div className={styles.avatar} aria-hidden="true">
            {getInitials(user.display_name)}
          </div>
          <div className={styles.userInfo}>
            <div className={styles.userName}>{user.display_name}</div>
            <div className={styles.userEmail}>{user.email}</div>
          </div>
          {onLogout && (
            <button
              className="button button-ghost button-icon"
              type="button"
              onClick={onLogout}
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut size={16} />
            </button>
          )}
        </div>
      )}
    </aside>
  );
}

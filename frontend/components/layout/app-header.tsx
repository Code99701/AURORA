"use client";

import React from "react";
import { ThemeToggle } from "@/components/shared/theme-toggle";
import styles from "./app-header.module.css";

interface AppHeaderProps {
  title?: string;
  children?: React.ReactNode;
}

export function AppHeader({ title, children }: AppHeaderProps) {
  return (
    <header className={styles.header}>
      <div className={styles.left}>
        {title && <span className={styles.title}>{title}</span>}
        {children}
      </div>
      <div className={styles.right}>
        <ThemeToggle />
      </div>
    </header>
  );
}

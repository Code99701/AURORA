"use client";

import React from "react";
import styles from "./tabs.module.css";

export interface TabItem {
  id: string;
  label: string;
  icon?: React.ReactNode;
}

export interface TabsProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (id: string) => void;
  className?: string;
  ariaLabel?: string;
}

export function Tabs({
  tabs,
  activeTab,
  onChange,
  className = "",
  ariaLabel = "Navigation tabs",
}: TabsProps) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={`${styles.tabsList} ${className}`}
    >
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab;
        return (
          <button
            key={tab.id}
            role="tab"
            type="button"
            aria-selected={isActive}
            tabIndex={isActive ? 0 : -1}
            className={`${styles.tabTrigger} ${isActive ? styles.active : ""}`}
            onClick={() => onChange(tab.id)}
          >
            {tab.icon}
            <span>{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}

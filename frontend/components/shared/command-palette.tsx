"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  FolderKanban,
  Sparkles,
  ArrowRight,
  X,
  Plus,
  Languages,
} from "lucide-react";
import { useWorkspaces } from "@/hooks/use-workspaces";

interface CommandItem {
  id: string;
  title: string;
  category: "Workspaces" | "Documents" | "Quick Actions";
  subtitle: string;
  href?: string;
  action?: () => void;
  icon: React.ReactNode;
  badge?: string;
}

export function CommandPalette({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  const { workspaces } = useWorkspaces();

  const handleSelect = React.useCallback((item: CommandItem) => {
    onClose();
    if (item.action) {
      item.action();
    } else if (item.href) {
      router.push(item.href);
    }
  }, [onClose, router]);

  const items: CommandItem[] = [
    ...workspaces.map((ws) => ({
      id: `ws-${ws.id}`,
      title: ws.name,
      category: "Workspaces" as const,
      subtitle: ws.description || "Research workspace",
      href: `/workspaces/${ws.id}`,
      icon: <FolderKanban size={16} color="var(--accent, #6C5CE7)" />,
    })),
    {
      id: "act-1",
      title: "Create New Research Workspace",
      category: "Quick Actions",
      subtitle: "Initialize a high-assurance research corpus",
      href: "/workspaces",
      icon: <Plus size={16} color="var(--accent, #6C5CE7)" />,
    },
    {
      id: "act-2",
      title: "Open Ingestion Pipeline",
      category: "Quick Actions",
      subtitle: "Inspect multi-format document parser and chunks",
      href: "/documents",
      icon: <Sparkles size={16} color="var(--teal, #00D2D3)" />,
    },
    {
      id: "act-3",
      title: "System Settings",
      category: "Quick Actions",
      subtitle: "Inspect model configuration and language options",
      href: "/settings",
      icon: <Languages size={16} color="var(--accent, #6C5CE7)" />,
    },
  ];

  const filteredItems = items.filter(
    (item) =>
      item.title.toLowerCase().includes(query.toLowerCase()) ||
      item.subtitle.toLowerCase().includes(query.toLowerCase()) ||
      item.category.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        if (isOpen) {
          onClose();
        }
      }
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
      if (isOpen) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          setSelectedIndex((prev) => (prev + 1) % (filteredItems.length || 1));
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          setSelectedIndex((prev) => (prev - 1 + filteredItems.length) % (filteredItems.length || 1));
        } else if (e.key === "Enter" && filteredItems[selectedIndex]) {
          e.preventDefault();
          handleSelect(filteredItems[selectedIndex]);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, filteredItems, selectedIndex, onClose, handleSelect]);

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: "rgba(26, 29, 46, 0.45)",
        backdropFilter: "blur(8px)",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "6vh 1rem 2rem",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "640px",
          background: "var(--surface, #FFFFFF)",
          borderRadius: "var(--radius-xl, 24px)",
          boxShadow: "0 24px 64px rgba(108, 92, 231, 0.18), 0 4px 16px rgba(0,0,0,0.06)",
          border: "1.5px solid var(--border, #E2E5F0)",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          animation: "scaleIn 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div
          style={{
            padding: "1rem 1.25rem",
            borderBottom: "1px solid var(--border, #E2E5F0)",
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
          }}
        >
          <Search size={20} color="var(--accent, #6C5CE7)" />
          <input
            type="text"
            autoFocus
            placeholder="Search workspaces, corpus documents, equations, actions..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            style={{
              flex: 1,
              border: "none",
              outline: "none",
              fontSize: "1rem",
              fontFamily: "var(--font-inter)",
              color: "var(--foreground, #1A1D2E)",
              background: "transparent",
            }}
          />
          <button
            type="button"
            onClick={onClose}
            style={{
              border: "none",
              background: "var(--surface-raised, #F5F7FC)",
              borderRadius: "6px",
              padding: "0.3rem",
              cursor: "pointer",
              color: "var(--muted, #8E93B0)",
              display: "grid",
              placeItems: "center",
            }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Results List */}
        <div
          style={{
            maxHeight: "380px",
            overflowY: "auto",
            padding: "0.5rem",
            display: "flex",
            flexDirection: "column",
            gap: "0.25rem",
          }}
        >
          {filteredItems.length === 0 ? (
            <div style={{ textAlign: "center", padding: "2.5rem 1rem", color: "var(--muted, #8E93B0)" }}>
              <p style={{ margin: 0, fontSize: "0.95rem" }}>No matching results for &ldquo;{query}&rdquo;</p>
              <p style={{ margin: "0.35rem 0 0", fontSize: "0.8rem" }}>Try searching for &ldquo;LLZO&rdquo;, &ldquo;LiPON&rdquo;, or &ldquo;Workspaces&rdquo;</p>
            </div>
          ) : (
            filteredItems.map((item, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={item.id}
                  onClick={() => handleSelect(item)}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  style={{
                    padding: "0.75rem 1rem",
                    borderRadius: "var(--radius-md, 12px)",
                    background: isSelected ? "var(--accent-soft, #EDE9FE)" : "transparent",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "0.75rem",
                    transition: "all 0.1s ease",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", minWidth: 0 }}>
                    <div
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: "8px",
                        background: isSelected ? "#FFFFFF" : "var(--surface-raised, #F5F7FC)",
                        display: "grid",
                        placeItems: "center",
                        border: "1px solid var(--border, #E2E5F0)",
                        flexShrink: 0,
                      }}
                    >
                      {item.icon}
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span
                          style={{
                            fontWeight: 600,
                            fontSize: "0.9rem",
                            color: isSelected ? "var(--accent, #6C5CE7)" : "var(--foreground, #1A1D2E)",
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                          }}
                        >
                          {item.title}
                        </span>
                        {item.badge && (
                          <span
                            style={{
                              fontSize: "0.7rem",
                              fontWeight: 700,
                              fontFamily: "var(--font-mono)",
                              background: "rgba(0, 210, 211, 0.15)",
                              color: "var(--teal, #00D2D3)",
                              padding: "0.1rem 0.4rem",
                              borderRadius: "4px",
                            }}
                          >
                            {item.badge}
                          </span>
                        )}
                      </div>
                      <div
                        style={{
                          fontSize: "0.78rem",
                          color: "var(--foreground-soft, #4A4F6A)",
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {item.subtitle}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span
                      style={{
                        fontSize: "0.7rem",
                        fontWeight: 600,
                        color: "var(--muted, #8E93B0)",
                        textTransform: "uppercase",
                      }}
                    >
                      {item.category}
                    </span>
                    <ArrowRight
                      size={14}
                      color={isSelected ? "var(--accent, #6C5CE7)" : "var(--muted, #8E93B0)"}
                      style={{ transform: isSelected ? "translateX(2px)" : "none", transition: "transform 0.15s ease" }}
                    />
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer shortcuts */}
        <div
          style={{
            padding: "0.6rem 1.25rem",
            background: "var(--surface-raised, #F5F7FC)",
            borderTop: "1px solid var(--border, #E2E5F0)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: "0.75rem",
            color: "var(--muted, #8E93B0)",
          }}
        >
          <div style={{ display: "flex", gap: "1rem" }}>
            <span>↑↓ Navigate</span>
            <span>↵ Select</span>
            <span>Esc Close</span>
          </div>
          <span style={{ fontFamily: "var(--font-mono)", color: "var(--accent, #6C5CE7)", fontWeight: 600 }}>
            AURORA Universal Index
          </span>
        </div>
      </div>
    </div>
  );
}

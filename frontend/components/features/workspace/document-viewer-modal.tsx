"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  Download,
  FileText,
  AlertCircle,
  ExternalLink,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Document } from "@/lib/types";

interface DocumentViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  workspaceId: string;
  documentId: string;
  pageNumber?: number;
  highlightText?: string;
}

export function DocumentViewerModal({
  isOpen,
  onClose,
  workspaceId,
  documentId,
  pageNumber = 1,
  highlightText,
}: DocumentViewerModalProps) {
  const [document, setDocument] = useState<Document | null>(null);
  const [loadedKey, setLoadedKey] = useState("");
  const [error, setError] = useState("");

  const docKey = `${workspaceId}:${documentId}`;
  const loading = isOpen && Boolean(documentId) && loadedKey !== docKey;

  useEffect(() => {
    if (!isOpen || !documentId || !workspaceId) return;

    let cancelled = false;
    api.document(workspaceId, documentId)
      .then((doc) => {
        if (!cancelled) {
          setDocument(doc);
          setLoadedKey(docKey);
          setError("");
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setError(
            caught instanceof ApiError
              ? caught.message
              : "Could not retrieve document details."
          );
          setLoadedKey(docKey);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen, workspaceId, documentId, docKey]);

  if (!isOpen) return null;

  const downloadUrl = `/api/v1/workspaces/${workspaceId}/documents/${documentId}/download`;
  const previewUrl = `/api/v1/workspaces/${workspaceId}/documents/${documentId}/preview`;

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: "rgba(26, 29, 46, 0.6)",
        backdropFilter: "blur(12px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1.5rem",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "1080px",
          height: "85vh",
          background: "var(--surface, #FFFFFF)",
          borderRadius: "var(--radius-2xl, 32px)",
          boxShadow: "0 28px 72px rgba(108, 92, 231, 0.22), 0 4px 20px rgba(0,0,0,0.08)",
          border: "1.5px solid var(--border, #E2E5F0)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <header
          style={{
            padding: "1rem 1.5rem",
            background: "var(--surface-raised, #F5F7FC)",
            borderBottom: "1px solid var(--border, #E2E5F0)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "1rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: "10px",
                background: "var(--accent-soft, #EDE9FE)",
                color: "var(--accent, #6C5CE7)",
                display: "grid",
                placeItems: "center",
              }}
            >
              <FileText size={18} />
            </div>
            <div>
              <h2 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0, color: "var(--foreground, #1A1D2E)" }}>
                {document ? document.original_filename : "Loading document..."}
              </h2>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.78rem", color: "var(--muted, #8E93B0)" }}>
                <span>Page {pageNumber}</span>
                {document && (
                  <>
                    <span>·</span>
                    <span>Status: {document.status}</span>
                    <span>·</span>
                    <span>Indexed: {document.indexing_status}</span>
                  </>
                )}
              </div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            {document && (
              <>
                <a
                  href={downloadUrl}
                  className="button button-secondary button-sm"
                  download
                  style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", textDecoration: "none" }}
                >
                  <Download size={14} /> Download
                </a>
                <a
                  href={previewUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="button button-secondary button-sm"
                  style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", textDecoration: "none" }}
                >
                  <ExternalLink size={14} /> Raw Preview
                </a>
              </>
            )}
            <button
              type="button"
              onClick={onClose}
              style={{
                border: "none",
                background: "transparent",
                cursor: "pointer",
                color: "var(--muted, #8E93B0)",
                padding: "0.35rem",
              }}
            >
              <X size={20} />
            </button>
          </div>
        </header>

        {/* Content Body */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", padding: "1.5rem" }}>
          {error ? (
            <div
              role="alert"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                background: "var(--coral-soft, #FFF0F0)",
                border: "1px solid color-mix(in srgb, var(--coral) 30%, transparent)",
                borderRadius: "var(--radius-sm, 8px)",
                padding: "1rem",
                color: "var(--coral, #FF6B6B)",
              }}
            >
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          ) : loading ? (
            <div style={{ display: "grid", placeItems: "center", height: "100%", color: "var(--muted, #8E93B0)" }}>
              <p>Loading document evidence...</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem", height: "100%", overflowY: "auto" }}>
              {highlightText && (
                <div
                  style={{
                    background: "var(--surface-raised, #F5F7FC)",
                    border: "1px solid var(--border, #E2E5F0)",
                    borderRadius: "var(--radius-md, 12px)",
                    padding: "1.25rem",
                  }}
                >
                  <span
                    style={{
                      display: "block",
                      fontSize: "0.72rem",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                      color: "var(--accent, #6C5CE7)",
                      marginBottom: "0.5rem",
                    }}
                  >
                    Cited Evidence Chunk (Page {pageNumber})
                  </span>
                  <p
                    style={{
                      margin: 0,
                      fontSize: "0.92rem",
                      lineHeight: 1.65,
                      color: "var(--foreground, #1A1D2E)",
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {highlightText}
                  </p>
                </div>
              )}

              {/* Embedded Document Frame */}
              <iframe
                src={`${previewUrl}#page=${pageNumber}`}
                title={`Preview of ${document?.original_filename || "document"}`}
                style={{
                  width: "100%",
                  flex: 1,
                  minHeight: "400px",
                  border: "1px solid var(--border, #E2E5F0)",
                  borderRadius: "var(--radius-md, 12px)",
                  background: "#FFFFFF",
                }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

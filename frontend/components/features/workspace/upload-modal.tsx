"use client";

import React, { useState, useRef } from "react";
import {
  UploadCloud,
  X,
  CheckCircle2,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type { Document } from "@/lib/types";

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  workspaceId: string;
  onUploadSuccess?: (newDoc: Document) => void;
}

export function UploadModal({
  isOpen,
  onClose,
  workspaceId,
  onUploadSuccess,
}: UploadModalProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [status, setStatus] = useState<"idle" | "uploading" | "processing" | "indexing" | "done" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      if (file.size > MAX_FILE_SIZE) {
        setErrorMessage("File exceeds the 10 MB limit. Please select a smaller document.");
        setSelectedFile(null);
        return;
      }
      setSelectedFile(file);
      setErrorMessage("");
      setStatus("idle");
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      if (file.size > MAX_FILE_SIZE) {
        setErrorMessage("File exceeds the 10 MB limit. Please select a smaller document.");
        setSelectedFile(null);
        return;
      }
      setSelectedFile(file);
      setErrorMessage("");
      setStatus("idle");
    }
  };

  const handleStartIngest = async () => {
    if (!selectedFile) return;

    setErrorMessage("");
    setStatus("uploading");

    try {
      // Step 1: Upload
      const uploadedDoc = await api.uploadDocument(workspaceId, selectedFile);

      // Step 2: Process / Extract Text
      setStatus("processing");
      const processedDoc = await api.processDocument(workspaceId, uploadedDoc.id);

      // Step 3: Vector Indexing
      setStatus("indexing");
      const indexedDoc = await api.indexDocument(workspaceId, processedDoc.id);

      setStatus("done");
      if (onUploadSuccess) {
        onUploadSuccess(indexedDoc);
      }
      setTimeout(() => {
        onClose();
        setSelectedFile(null);
        setStatus("idle");
      }, 900);
    } catch (caught) {
      setStatus("error");
      if (caught instanceof ApiError) {
        setErrorMessage(caught.message);
      } else if (caught instanceof Error) {
        setErrorMessage(caught.message);
      } else {
        setErrorMessage("Upload and indexing failed. Please try again.");
      }
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const isBusy = status === "uploading" || status === "processing" || status === "indexing";

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: "rgba(26, 29, 46, 0.55)",
        backdropFilter: "blur(10px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1.5rem",
      }}
      onClick={() => {
        if (!isBusy) onClose();
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "580px",
          background: "var(--surface, #FFFFFF)",
          borderRadius: "var(--radius-xl, 24px)",
          boxShadow: "0 24px 64px rgba(108, 92, 231, 0.2), 0 4px 16px rgba(0,0,0,0.06)",
          border: "1.5px solid var(--border, #E2E5F0)",
          padding: "2rem",
          display: "flex",
          flexDirection: "column",
          gap: "1.5rem",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: "12px",
                background: "var(--accent-soft, #EDE9FE)",
                color: "var(--accent, #6C5CE7)",
                display: "grid",
                placeItems: "center",
              }}
            >
              <UploadCloud size={20} />
            </div>
            <div>
              <h2 style={{ fontSize: "1.25rem", fontWeight: 700, margin: 0, color: "var(--foreground, #1A1D2E)" }}>
                Upload Document
              </h2>
              <p style={{ fontSize: "0.82rem", color: "var(--muted, #8E93B0)", margin: 0 }}>
                PDF, DOCX, XLSX, PPTX, TXT, MD up to 10 MB
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isBusy}
            style={{
              border: "none",
              background: "transparent",
              cursor: isBusy ? "not-allowed" : "pointer",
              color: "var(--muted, #8E93B0)",
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Error Banner */}
        {errorMessage && (
          <div
            role="alert"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              background: "var(--coral-soft, #FFF0F0)",
              border: "1px solid color-mix(in srgb, var(--coral) 30%, transparent)",
              borderRadius: "var(--radius-sm, 8px)",
              padding: "0.65rem 0.85rem",
              fontSize: "0.82rem",
              color: "var(--coral, #FF6B6B)",
            }}
          >
            <AlertCircle size={16} />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Drag and Drop Zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !isBusy && fileInputRef.current?.click()}
          style={{
            border: isDragging ? "2px dashed var(--accent, #6C5CE7)" : "2px dashed var(--border, #E2E5F0)",
            borderRadius: "var(--radius-lg, 16px)",
            padding: "2rem 1.5rem",
            textAlign: "center",
            background: isDragging ? "var(--accent-soft, #EDE9FE)" : "var(--surface-raised, #F5F7FC)",
            cursor: isBusy ? "not-allowed" : "pointer",
            transition: "all 0.15s ease",
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.xlsx,.pptx,.txt,.md,.csv,.tsv"
            onChange={handleFileChange}
            style={{ display: "none" }}
            disabled={isBusy}
          />
          <UploadCloud size={36} color="var(--accent, #6C5CE7)" style={{ margin: "0 auto 0.75rem" }} />
          <p style={{ margin: "0 0 0.35rem", fontWeight: 600, color: "var(--foreground, #1A1D2E)" }}>
            {selectedFile ? selectedFile.name : "Choose a file or drag & drop it here"}
          </p>
          <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--muted, #8E93B0)" }}>
            {selectedFile ? `${formatFileSize(selectedFile.size)} · Click to change` : "Extracts text, preserves tables, and prepares citations"}
          </p>
        </div>

        {/* Progress Stages */}
        {isBusy && (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", fontSize: "0.85rem", color: "var(--foreground, #1A1D2E)" }}>
              <Loader2 size={16} className="animate-spin" color="var(--accent, #6C5CE7)" />
              <span>
                {status === "uploading" && "Uploading document…"}
                {status === "processing" && "Extracting text and tables…"}
                {status === "indexing" && "Indexing document for search…"}
              </span>
            </div>
            <div style={{ height: "4px", background: "var(--surface-raised, #F5F7FC)", borderRadius: "2px", overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  background: "var(--accent, #6C5CE7)",
                  width: status === "uploading" ? "33%" : status === "processing" ? "66%" : "100%",
                  transition: "width 0.4s ease",
                }}
              />
            </div>
          </div>
        )}

        {status === "done" && (
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--teal, #00D2D3)", fontSize: "0.88rem", fontWeight: 600 }}>
            <CheckCircle2 size={18} />
            <span>Document ready for research!</span>
          </div>
        )}

        {/* Footer Actions */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
          <Button variant="ghost" size="md" onClick={onClose} disabled={isBusy}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="md"
            onClick={handleStartIngest}
            disabled={!selectedFile || isBusy || status === "done"}
            busy={isBusy}
          >
            {isBusy ? "Processing..." : "Upload Document"}
          </Button>
        </div>
      </div>
    </div>
  );
}

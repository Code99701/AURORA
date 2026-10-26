"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { Document } from "@/lib/types";

export function useDocuments(workspaceId?: string) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!workspaceId) return;

    let cancelled = false;
    api.documents(workspaceId)
      .then((data) => {
        if (!cancelled) {
          setDocuments(data.items);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : "Failed to load documents";
          setError(message);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  const fetchDocuments = useCallback(async () => {
    if (!workspaceId) return [];
    setLoading(true);
    setError(null);
    try {
      const data = await api.documents(workspaceId);
      setDocuments(data.items);
      return data.items;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load documents";
      setError(message);
      return [];
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  const deleteDocument = async (docId: string) => {
    if (!workspaceId) return;
    await api.deleteDocument(workspaceId, docId);
    setDocuments((prev) => prev.filter((d) => d.id !== docId));
  };

  return {
    documents,
    loading,
    error,
    refetch: fetchDocuments,
    deleteDocument,
  };
}

"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { Workspace } from "@/lib/types";

export function useWorkspaces() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.workspaces()
      .then((data) => {
        if (!cancelled) {
          setWorkspaces(data.items);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : "Failed to load workspaces";
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
  }, []);

  const fetchWorkspaces = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.workspaces();
      setWorkspaces(data.items);
      return data.items;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load workspaces";
      setError(message);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  const createWorkspace = async (name: string, description?: string) => {
    const newWs = await api.createWorkspace(name, description || "");
    setWorkspaces((prev) => [newWs, ...prev]);
    return newWs;
  };

  const deleteWorkspace = async (workspaceId: string) => {
    await api.deleteWorkspace(workspaceId);
    setWorkspaces((prev) => prev.filter((ws) => ws.id !== workspaceId));
  };

  return {
    workspaces,
    loading,
    error,
    refetch: fetchWorkspaces,
    createWorkspace,
    deleteWorkspace,
  };
}

"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { Conversation, ConversationMessage } from "@/lib/types";

export function useChat(workspaceId?: string) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!workspaceId) return;

    let cancelled = false;
    api.conversations(workspaceId)
      .then((data) => {
        if (!cancelled) {
          setConversations(data.items);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : "Failed to load conversations";
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

  const fetchConversations = useCallback(async () => {
    if (!workspaceId) return [];
    setLoading(true);
    setError(null);
    try {
      const data = await api.conversations(workspaceId);
      setConversations(data.items);
      return data.items;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load conversations";
      setError(message);
      return [];
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  const loadConversation = async (conversationId: string) => {
    if (!workspaceId) return null;
    setLoading(true);
    try {
      const [conv, msgData] = await Promise.all([
        api.conversation(workspaceId, conversationId),
        api.conversationMessages(workspaceId, conversationId),
      ]);
      setActiveConversation(conv);
      setMessages(msgData.items);
      return { conversation: conv, messages: msgData.items };
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load conversation");
      return null;
    } finally {
      setLoading(false);
    }
  };

  return {
    conversations,
    activeConversation,
    messages,
    loading,
    error,
    refetchConversations: fetchConversations,
    loadConversation,
  };
}

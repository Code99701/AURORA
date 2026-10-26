"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";

export function useAuth(options: { redirectToLogin?: boolean } = {}) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.me()
      .then((currentUser) => {
        if (!cancelled) {
          setUser(currentUser);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          if (err instanceof ApiError && err.status === 401) {
            setUser(null);
            if (options.redirectToLogin) {
              router.replace("/login");
            }
          } else {
            setError(err instanceof Error ? err.message : "Failed to authenticate");
          }
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
  }, [options.redirectToLogin, router]);

  const fetchUser = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const currentUser = await api.me();
      setUser(currentUser);
      return currentUser;
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
        if (options.redirectToLogin) {
          router.replace("/login");
        }
      } else {
        setError(err instanceof Error ? err.message : "Failed to authenticate");
      }
      return null;
    } finally {
      setLoading(false);
    }
  }, [options.redirectToLogin, router]);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // Ignored - cleanup local state anyway
    } finally {
      setUser(null);
      router.replace("/login");
    }
  }, [router]);

  return {
    user,
    loading,
    error,
    isAuthenticated: !!user,
    refetch: fetchUser,
    logout,
  };
}

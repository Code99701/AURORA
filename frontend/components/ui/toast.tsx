"use client";

import React, { createContext, useContext, useState, useCallback } from "react";
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from "lucide-react";
import styles from "./toast.module.css";

export type ToastVariant = "neutral" | "success" | "warning" | "danger";

export interface ToastItem {
  id: string;
  title?: string;
  message: string;
  variant?: ToastVariant;
}

interface ToastContextType {
  toast: (item: Omit<ToastItem, "id">) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    ({ title, message, variant = "neutral" }: Omit<ToastItem, "id">) => {
      const id = Math.random().toString(36).substring(2, 9);
      setToasts((prev) => [...prev, { id, title, message, variant }]);

      setTimeout(() => {
        removeToast(id);
      }, 4000);
    },
    [removeToast]
  );

  return (
    <ToastContext.Provider value={{ toast, removeToast }}>
      {children}
      <div className={styles.toastContainer} role="region" aria-label="Notifications">
        {toasts.map((t) => {
          const Icon =
            t.variant === "success"
              ? CheckCircle2
              : t.variant === "warning"
              ? AlertTriangle
              : t.variant === "danger"
              ? AlertCircle
              : Info;

          return (
            <div
              key={t.id}
              role="status"
              className={`${styles.toast} ${styles[t.variant || "neutral"]}`}
            >
              <Icon size={18} className={styles.icon} aria-hidden="true" />
              <div className={styles.content}>
                {t.title && <div className={styles.title}>{t.title}</div>}
                <div className={styles.message}>{t.message}</div>
              </div>
              <button
                type="button"
                className={styles.closeButton}
                onClick={() => removeToast(t.id)}
                aria-label="Close notification"
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}

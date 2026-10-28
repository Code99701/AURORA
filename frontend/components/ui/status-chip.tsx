import React from "react";
import { CheckCircle2, AlertCircle, AlertTriangle, Loader2, Circle } from "lucide-react";
import styles from "./status-chip.module.css";

export type StatusType =
  | "ready"
  | "processed"
  | "indexed"
  | "indexing"
  | "processing"
  | "failed"
  | "partial"
  | "partially_processed"
  | "queued"
  | "pending"
  | "neutral";

export interface StatusChipProps extends React.HTMLAttributes<HTMLSpanElement> {
  status: string;
  label?: string;
}

export function StatusChip({ status, label, className = "", ...props }: StatusChipProps) {
  const norm = status.toLowerCase().replace(/\s+/g, "_");

  let tone: "ready" | "indexing" | "failed" | "partial" | "neutral" = "neutral";
  let Icon = Circle;
  let isSpinning = false;
  let displayLabel = label || status.replace(/_/g, " ");

  if (["ready", "processed", "indexed"].includes(norm)) {
    tone = "ready";
    Icon = CheckCircle2;
    displayLabel = label || "Ready";
  } else if (["indexing", "processing"].includes(norm)) {
    tone = "indexing";
    Icon = Loader2;
    isSpinning = true;
    displayLabel = label || "Indexing";
  } else if (["failed", "error"].includes(norm)) {
    tone = "failed";
    Icon = AlertCircle;
    displayLabel = label || "Failed";
  } else if (["partial", "partially_processed"].includes(norm)) {
    tone = "partial";
    Icon = AlertTriangle;
    displayLabel = label || "Partial";
  } else {
    tone = "neutral";
    Icon = Circle;
  }

  const toneClass = styles[tone] || styles.neutral;

  return (
    <span className={`${styles.statusChip} ${toneClass} ${className}`} {...props}>
      <Icon size={12} className={isSpinning ? styles.spinner : undefined} aria-hidden="true" />
      <span>{displayLabel}</span>
    </span>
  );
}

import React from "react";
import { Loader2 } from "lucide-react";

export interface SpinnerProps {
  size?: number | "sm" | "md" | "lg";
  className?: string;
  label?: string;
  color?: string;
}

export function Spinner({
  size = "md",
  className = "",
  label = "Loading...",
  color = "var(--accent)",
}: SpinnerProps) {
  const pixelSize =
    typeof size === "number"
      ? size
      : size === "sm"
      ? 14
      : size === "lg"
      ? 24
      : 18;

  return (
    <div
      role="status"
      aria-label={label}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        color,
      }}
      className={className}
    >
      <Loader2
        size={pixelSize}
        style={{ animation: "spin 1s linear infinite" }}
        aria-hidden="true"
      />
      <span className="sr-only">{label}</span>
    </div>
  );
}

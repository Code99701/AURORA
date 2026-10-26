import { Loader2 } from "lucide-react";

export function LoadingSpinner({
  size = 24,
  label = "Loading…",
  className = "",
}: {
  size?: number;
  label?: string;
  className?: string;
}) {
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "0.5rem",
        color: "var(--accent, #6C5CE7)",
      }}
      className={className}
      role="status"
      aria-label={label}
    >
      <Loader2
        size={size}
        style={{ animation: "spin 1s linear infinite" }}
        aria-hidden="true"
      />
      {label && <span className="sr-only">{label}</span>}
    </div>
  );
}

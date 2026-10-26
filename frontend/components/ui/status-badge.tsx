import { CircleAlert, CircleCheck, CircleDashed, CircleX, LoaderCircle } from "lucide-react";

export function StatusBadge({ value }: { value: string }) {
  const normalized = value.replaceAll("_", " ").toLowerCase();
  const active = ["processing", "indexing"].includes(value.toLowerCase());
  const ready = ["processed", "indexed", "ready"].includes(value.toLowerCase());
  const failed = value.toLowerCase() === "failed";
  const partial = value.toLowerCase() === "partially_processed";
  const tone = failed ? "failed" : partial ? "partial" : active ? "active" : ready ? "ready" : "neutral";
  const Icon = failed ? CircleX : partial ? CircleAlert : active ? LoaderCircle : ready ? CircleCheck : CircleDashed;
  return (
    <span className="badge" data-tone={tone}>
      <Icon size={13} className={active ? "spin" : undefined} aria-hidden="true" />
      {normalized}
    </span>
  );
}

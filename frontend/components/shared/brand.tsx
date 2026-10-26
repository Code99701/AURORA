import { Sparkles } from "lucide-react";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="brand" aria-label="AURORA">
      <span className="brand-mark" aria-hidden="true"><Sparkles size={18} strokeWidth={1.8} /></span>
      {!compact && <span className="brand-word">AURORA</span>}
    </div>
  );
}

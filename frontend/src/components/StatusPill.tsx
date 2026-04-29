import { cn } from "@/lib/utils";

const TONE: Record<string, string> = {
  received: "border-info text-info",
  pending: "border-border text-text-muted",
  running: "border-info text-info",
  waiting: "border-warning text-warning",
  escalated: "border-warning text-warning",
  completed: "border-success text-success",
  failed: "border-error text-error",
  cancelled: "border-border text-text-muted",
  allowed: "border-success text-success",
  allow: "border-success text-success",
  propose: "border-info text-info",
  rewrite: "border-warning text-warning",
  approval_required: "border-warning text-warning",
  block: "border-error text-error",
  recorded: "border-border text-text-muted",
  denied: "border-error text-error",
  deferred: "border-warning text-warning",
  passed: "border-success text-success",
  proposed: "border-info text-info",
  answered: "border-success text-success",
  blocked: "border-error text-error",
};

export interface StatusPillProps {
  value: string;
}

/**
 * Compact, plain-text status indicator. Border-only colour — no fills, no icons.
 * Intentionally low visual weight to keep tables readable.
 */
export function StatusPill({ value }: StatusPillProps) {
  const tone = TONE[value] ?? "border-border text-text-muted";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm border px-1.5 py-px text-[10px] uppercase tracking-wide",
        tone,
      )}
    >
      {value}
    </span>
  );
}

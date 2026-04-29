import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * British timestamp format used in every dense list row: DD/MM/YYYY HH:MM:SS.
 * Returns "—" for null/undefined input so it is safe to use directly in JSX.
 */
export function formatTimestamp(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  );
}

/**
 * Render a correlation ID compactly: full value still visible to a power user via title attribute,
 * but the rendered text is truncated to the first 8 characters.
 */
export function formatCorrelationId(value: string | null | undefined): string {
  if (!value) return "—";
  return value.length <= 8 ? value : `${value.slice(0, 8)}…`;
}

/** Relative duration in milliseconds rendered as "Nms" / "N.NNs" / "Nm Ns". Used in dense tables. */
export function formatDurationMs(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(2)}s`;
  const m = Math.floor(ms / 60_000);
  const s = Math.floor((ms % 60_000) / 1000);
  return `${m}m ${s}s`;
}

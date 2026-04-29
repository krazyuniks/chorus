import type { ReactNode } from "react";
import { formatTimestamp, formatCorrelationId } from "@/lib/utils";

export interface TimelineEntry {
  id: string;
  occurred_at: string;
  correlation_id: string;
  label: ReactNode;
  detail?: ReactNode;
}

export interface TimelineProps {
  entries: TimelineEntry[];
}

/**
 * Vertical, dense timeline. One row per event, monospaced timestamp + correlation,
 * label + collapsible detail. No icons, no rails, no decorative dividers beyond the row border.
 */
export function Timeline({ entries }: TimelineProps) {
  if (entries.length === 0) {
    return (
      <div className="px-4 py-3 text-xs text-text-muted">
        No events recorded.
      </div>
    );
  }

  return (
    <ol className="text-xs">
      {entries.map((entry) => (
        <li
          key={entry.id}
          className="grid grid-cols-[10rem_8rem_1fr] gap-3 border-b border-border-muted px-4 py-1.5 align-baseline"
        >
          <span className="mono tabular text-text-muted">
            {formatTimestamp(entry.occurred_at)}
          </span>
          <span
            className="mono text-text-subtle"
            title={entry.correlation_id}
          >
            {formatCorrelationId(entry.correlation_id)}
          </span>
          <div className="text-text">
            <div>{entry.label}</div>
            {entry.detail && (
              <div className="mt-0.5 text-text-muted">{entry.detail}</div>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}

/**
 * SSE helper for workflow progress.
 *
 * The SSE stream is a progress channel only — UI state must survive refresh
 * and reconnect by reading projections from the BFF. Treat events as best-effort
 * cache invalidation hints, not as the source of truth.
 */
import { buildUrl } from "./client";

export interface ProgressEvent {
  id: string;
  workflow_id: string;
  event_type: string;
  sequence: number;
  step: string | null;
  payload: Record<string, unknown>;
  occurred_at: string;
  correlation_id: string;
}

export interface ProgressFilter {
  workflow_id?: string;
  correlation_id?: string;
}

export function progressPath(filter: ProgressFilter = {}): string {
  const params = new URLSearchParams();
  if (filter.workflow_id) params.set("workflow_id", filter.workflow_id);
  if (filter.correlation_id) params.set("correlation_id", filter.correlation_id);
  const query = params.toString();
  return query ? `/progress?${query}` : "/progress";
}

export interface ProgressStream {
  close(): void;
}

export function subscribeProgress(
  path: string,
  onEvent: (event: ProgressEvent) => void,
  onConnectionChange?: (connected: boolean) => void,
): ProgressStream {
  if (import.meta.env.VITE_USE_FIXTURES === "true") {
    return {
      close() {
        onConnectionChange?.(false);
      },
    };
  }

  const source = new EventSource(buildUrl(path), { withCredentials: false });

  source.addEventListener("open", () => {
    onConnectionChange?.(true);
  });

  source.addEventListener("error", () => {
    onConnectionChange?.(false);
  });

  source.addEventListener("message", (message) => {
    try {
      const parsed = JSON.parse(message.data) as ProgressEvent;
      onEvent(parsed);
    } catch (error) {
      // Best-effort: malformed events do not block the projection-driven UI.
      console.warn("Failed to parse progress event", error);
    }
  });

  return {
    close() {
      onConnectionChange?.(false);
      source.close();
    },
  };
}

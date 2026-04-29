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
  workflow_id: string | null;
  event_type: string;
  payload: Record<string, unknown>;
  occurred_at: string;
}

export interface ProgressStream {
  close(): void;
}

export function subscribeProgress(
  path: string,
  onEvent: (event: ProgressEvent) => void,
  onConnectionChange?: (connected: boolean) => void,
): ProgressStream {
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

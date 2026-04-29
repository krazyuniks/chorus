/**
 * Thin fetch wrapper for the Chorus BFF.
 *
 * The BFF is read-only in Phase 1: the UI fetches projections, decision-trail
 * entries, and tool-verdict records. All mutating action authority sits with
 * the Tool Gateway and Temporal workflows; the UI never originates writes.
 */
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: string,
  ) {
    super(`API ${status}: ${body}`);
    this.name = "ApiError";
  }
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body);
  }
  return res.json() as Promise<T>;
}

export function buildUrl(path: string): string {
  return `${BASE_URL}${path}`;
}

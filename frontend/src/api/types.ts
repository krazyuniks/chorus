/**
 * Stub types for the Lighthouse projections.
 *
 * These are placeholders until the BFF endpoints are wired up. They shape the
 * UI tables and detail views consistently with the Chorus architecture
 * (workflow runs, decision trail entries, tool gateway verdicts).
 */

export type WorkflowStatus =
  | "pending"
  | "running"
  | "waiting"
  | "escalated"
  | "completed"
  | "failed"
  | "cancelled";

export interface WorkflowRunSummary {
  workflow_id: string;
  run_id: string;
  workflow_type: string;
  status: WorkflowStatus;
  started_at: string;
  closed_at: string | null;
  correlation_id: string;
  lead_subject: string | null;
  lead_from: string | null;
}

export interface WorkflowEvent {
  id: string;
  workflow_id: string;
  event_type: string;
  occurred_at: string;
  correlation_id: string;
  payload: Record<string, unknown>;
}

export interface DecisionTrailEntry {
  id: string;
  workflow_id: string;
  agent_id: string;
  invocation_id: string;
  prompt_ref: string;
  model_route: string;
  outcome: "proposed" | "answered" | "escalated" | "blocked";
  reasoning_summary: string | null;
  cost_usd: number | null;
  latency_ms: number | null;
  occurred_at: string;
  correlation_id: string;
}

export type ToolVerdict = "allowed" | "denied" | "escalated" | "deferred";

export interface ToolVerdictEntry {
  id: string;
  workflow_id: string;
  tool_name: string;
  mode: "sandbox" | "local" | "live";
  verdict: ToolVerdict;
  reason: string | null;
  redactions: string[];
  caller_agent_id: string;
  correlation_id: string;
  occurred_at: string;
}

export interface RegistryEntry {
  agent_id: string;
  version: string;
  prompt_ref: string;
  model_route: string;
  description: string;
  updated_at: string;
}

export interface GrantEntry {
  agent_id: string;
  tool_name: string;
  mode: "sandbox" | "local" | "live";
  scope: string;
  approval_required: boolean;
  granted_at: string;
}

export interface RoutingEntry {
  route_id: string;
  match: string;
  provider: string;
  model: string;
  budget_usd: number;
  fallback: string | null;
}

export interface EvalRunSummary {
  run_id: string;
  fixture: string;
  status: "passed" | "failed" | "running";
  pass_count: number;
  fail_count: number;
  duration_ms: number;
  finished_at: string | null;
}

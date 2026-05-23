export type WorkflowStatus =
  | "received"
  | "running"
  | "escalated"
  | "completed"
  | "failed";

export interface WorkflowRunSummary {
  workflow_id: string;
  run_id: string | null;
  workflow_type: string;
  status: WorkflowStatus;
  current_step: string | null;
  started_at: string | null;
  closed_at: string | null;
  updated_at: string;
  correlation_id: string;
  subject_id: string;
  subject_ref: string | null;
  subject_summary: string | null;
  subject_from: string | null;
  metadata: Record<string, unknown>;
}

export interface WorkflowEvent {
  id: string;
  workflow_id: string;
  event_type: string;
  sequence?: number;
  step?: string | null;
  occurred_at: string;
  correlation_id: string;
  payload: Record<string, unknown>;
}

export interface DecisionTrailEntry {
  id: string;
  workflow_id: string;
  agent_id: string;
  agent_role?: string;
  invocation_id: string;
  prompt_ref: string;
  prompt_hash?: string;
  model_route: string;
  route_id?: string | null;
  route_version?: number | null;
  provider?: string;
  model?: string;
  fallback_reason?: string | null;
  fallback_applied?: boolean | null;
  task_kind?: string;
  outcome: "proposed" | "answered" | "escalated" | "blocked" | "succeeded" | "failed";
  reasoning_summary: string | null;
  cost_usd: number | null;
  latency_ms: number | null;
  occurred_at: string;
  correlation_id: string;
  contract_refs?: string[];
}


export type ToolVerdict =
  | "allow"
  | "rewrite"
  | "propose"
  | "approval_required"
  | "block"
  | "recorded"
  | "allowed"
  | "denied"
  | "escalated"
  | "deferred";

export interface ToolVerdictEntry {
  id: string;
  workflow_id: string;
  tool_name: string | null;
  mode?: "sandbox" | "local" | "live";
  requested_mode?: "read" | "propose" | "write" | null;
  enforced_mode?: "read" | "propose" | "write" | null;
  verdict: ToolVerdict;
  reason: string | null;
  redactions: string[];
  caller_agent_id: string;
  correlation_id: string;
  occurred_at: string;
}

export interface RegistryEntry {
  agent_id: string;
  role?: string;
  version: string;
  lifecycle_state?: string;
  owner?: string;
  prompt_ref: string;
  prompt_hash?: string;
  model_route?: string;
  description?: string;
  capability_tags?: string[];
  updated_at: string;
}

export interface GrantEntry {
  grant_id?: string;
  agent_id: string;
  agent_version?: string;
  tool_name: string;
  mode: "sandbox" | "local" | "live" | "read" | "propose" | "write";
  allowed?: boolean;
  scope?: string;
  approval_required: boolean;
  redaction_policy?: Record<string, unknown>;
  granted_at?: string;
}

export interface RoutingEntry {
  route_id: string;
  match?: string;
  agent_role?: string;
  task_kind?: string;
  tenant_tier?: string;
  provider: string;
  model: string;
  parameters?: Record<string, unknown>;
  budget_usd: number;
  fallback?: string | null;
  fallback_policy?: Record<string, unknown>;
  lifecycle_state?: string;
}

export interface ProviderEntry {
  catalogue_id: string;
  provider_id: string;
  display_name: string;
  provider_kind: string;
  lifecycle_state: string;
  credential_required: boolean;
  secret_ref_names: string[];
  missing_credentials_behaviour: string;
  data_boundary: Record<string, unknown>;
  operational_limits: Record<string, unknown>;
  audit: Record<string, unknown>;
}

export interface ProviderModelEntry {
  catalogue_id: string;
  provider_id: string;
  model_id: string;
  display_name: string;
  lifecycle_state: string;
  supported_task_kinds: string[];
  supports_structured_output: boolean;
  context_window_tokens: number | null;
  cost_policy: Record<string, unknown>;
}

export interface RouteVersionEntry {
  route_id: string;
  route_version: number;
  lifecycle_state: string;
  agent_role: string;
  task_kind: string;
  tenant_tier: string;
  provider_catalogue_id: string;
  provider_id: string;
  model_id: string;
  parameters: Record<string, unknown>;
  budget_usd: number;
  max_latency_ms: number;
  fallback_policy: Record<string, unknown>;
  eval_required: boolean;
  eval_fixture_refs: string[];
  promotion: Record<string, unknown>;
  created_at: string;
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

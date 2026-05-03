/**
 * In-memory fixture data used by optional Phase 1 UI fixture mode.
 *
 * These are deterministic, typed shapes that exercise the table/timeline
 * layouts without requiring the BFF to be running. Runtime review uses the
 * BFF-backed query functions unless VITE_USE_FIXTURES is explicitly set.
 */
import type {
  DecisionTrailEntry,
  EvalRunSummary,
  GrantEntry,
  RegistryEntry,
  RoutingEntry,
  ToolVerdictEntry,
  WorkflowEvent,
  WorkflowRunSummary,
} from "./types";

const NOW = Date.UTC(2026, 3, 29, 9, 0, 0);

const iso = (offsetSeconds: number) =>
  new Date(NOW + offsetSeconds * 1000).toISOString();

export const workflowRuns: WorkflowRunSummary[] = [
  {
    workflow_id: "lighthouse-2026-04-29-0001",
    run_id: "01JT9VR1H6V7RZK1H6MB7VM3WX",
    workflow_type: "Lighthouse",
    status: "running",
    current_step: "propose_send",
    started_at: iso(-1800),
    closed_at: null,
    updated_at: iso(-1750),
    correlation_id: "corr-9f3a14b1c0d8",
    lead_id: "00000000-0000-4000-8000-000000000001",
    lead_subject: "Quote request — 12 panel laptops",
    lead_from: "buyer@acme.example",
    metadata: { source: "fixture" },
  },
  {
    workflow_id: "lighthouse-2026-04-29-0002",
    run_id: "01JT9VS2K0M9P5G1Q7H8XJN0AB",
    workflow_type: "Lighthouse",
    status: "escalated",
    current_step: "escalate",
    started_at: iso(-7200),
    closed_at: null,
    updated_at: iso(-6900),
    correlation_id: "corr-7c4be9a1d22e",
    lead_id: "00000000-0000-4000-8000-000000000002",
    lead_subject: "Renewal — managed services",
    lead_from: "ops@globex.example",
    metadata: { source: "fixture" },
  },
  {
    workflow_id: "lighthouse-2026-04-29-0003",
    run_id: "01JT9VT3L1N0Q6H2R8J9YK1BCD",
    workflow_type: "Lighthouse",
    status: "completed",
    current_step: "complete",
    started_at: iso(-86_400),
    closed_at: iso(-82_800),
    updated_at: iso(-82_800),
    correlation_id: "corr-2d5af0c3b914",
    lead_id: "00000000-0000-4000-8000-000000000003",
    lead_subject: "Inquiry — onboarding playbook",
    lead_from: "lead@initech.example",
    metadata: { source: "fixture" },
  },
];

export const workflowEvents: Record<string, WorkflowEvent[]> = {
  "lighthouse-2026-04-29-0001": [
    {
      id: "evt-001",
      workflow_id: "lighthouse-2026-04-29-0001",
      event_type: "workflow.started",
      occurred_at: iso(-1800),
      correlation_id: "corr-9f3a14b1c0d8",
      payload: { trigger: "mailpit.intake" },
    },
    {
      id: "evt-002",
      workflow_id: "lighthouse-2026-04-29-0001",
      event_type: "lead.parsed",
      occurred_at: iso(-1795),
      correlation_id: "corr-9f3a14b1c0d8",
      payload: { source: "mailpit", message_id: "<a1b2@acme.example>" },
    },
    {
      id: "evt-003",
      workflow_id: "lighthouse-2026-04-29-0001",
      event_type: "agent.invoked",
      occurred_at: iso(-1780),
      correlation_id: "corr-9f3a14b1c0d8",
      payload: { agent_id: "intake.classifier", invocation_id: "inv-aa01" },
    },
    {
      id: "evt-004",
      workflow_id: "lighthouse-2026-04-29-0001",
      event_type: "tool.call",
      occurred_at: iso(-1770),
      correlation_id: "corr-9f3a14b1c0d8",
      payload: { tool: "crm.lookup", verdict: "allowed" },
    },
    {
      id: "evt-005",
      workflow_id: "lighthouse-2026-04-29-0001",
      event_type: "agent.responded",
      occurred_at: iso(-1750),
      correlation_id: "corr-9f3a14b1c0d8",
      payload: { agent_id: "intake.classifier", outcome: "answered" },
    },
  ],
};

export const decisionTrail: DecisionTrailEntry[] = [
  {
    id: "dec-001",
    workflow_id: "lighthouse-2026-04-29-0001",
    agent_id: "intake.classifier",
    invocation_id: "inv-aa01",
    prompt_ref: "intake/classifier@v3",
    model_route: "claude-3.5-sonnet:eu",
    outcome: "answered",
    reasoning_summary: "Inbound is a quote request; routed to commercial workstream.",
    cost_usd: 0.0042,
    latency_ms: 1820,
    occurred_at: iso(-1750),
    correlation_id: "corr-9f3a14b1c0d8",
  },
  {
    id: "dec-002",
    workflow_id: "lighthouse-2026-04-29-0002",
    agent_id: "renewal.assessor",
    invocation_id: "inv-bb14",
    prompt_ref: "renewal/assessor@v2",
    model_route: "claude-3.5-sonnet:eu",
    outcome: "escalated",
    reasoning_summary: "Contract value above autonomous threshold; human approval required.",
    cost_usd: 0.0091,
    latency_ms: 2440,
    occurred_at: iso(-7000),
    correlation_id: "corr-7c4be9a1d22e",
  },
];

export const toolVerdicts: ToolVerdictEntry[] = [
  {
    id: "ver-001",
    workflow_id: "lighthouse-2026-04-29-0001",
    tool_name: "crm.lookup",
    mode: "local",
    verdict: "allowed",
    reason: null,
    redactions: [],
    caller_agent_id: "intake.classifier",
    correlation_id: "corr-9f3a14b1c0d8",
    occurred_at: iso(-1770),
  },
  {
    id: "ver-002",
    workflow_id: "lighthouse-2026-04-29-0002",
    tool_name: "email.send",
    mode: "sandbox",
    verdict: "escalated",
    reason: "Approval required for outbound to renewal contact.",
    redactions: ["body.account_number"],
    caller_agent_id: "renewal.assessor",
    correlation_id: "corr-7c4be9a1d22e",
    occurred_at: iso(-6900),
  },
];

export const registry: RegistryEntry[] = [
  {
    agent_id: "intake.classifier",
    version: "v3",
    prompt_ref: "intake/classifier@v3",
    model_route: "claude-3.5-sonnet:eu",
    description: "Classifies inbound emails into commercial workstreams.",
    updated_at: iso(-604_800),
  },
  {
    agent_id: "renewal.assessor",
    version: "v2",
    prompt_ref: "renewal/assessor@v2",
    model_route: "claude-3.5-sonnet:eu",
    description: "Assesses renewal opportunities and proposes next actions.",
    updated_at: iso(-1_209_600),
  },
];

export const grants: GrantEntry[] = [
  {
    agent_id: "intake.classifier",
    tool_name: "crm.lookup",
    mode: "local",
    scope: "read:contacts",
    approval_required: false,
    granted_at: iso(-2_592_000),
  },
  {
    agent_id: "renewal.assessor",
    tool_name: "email.send",
    mode: "sandbox",
    scope: "send:outbound",
    approval_required: true,
    granted_at: iso(-2_592_000),
  },
];

export const routing: RoutingEntry[] = [
  {
    route_id: "rt-default",
    match: "agent:* ",
    provider: "anthropic",
    model: "claude-3.5-sonnet",
    budget_usd: 0.05,
    fallback: "rt-fallback",
  },
  {
    route_id: "rt-fallback",
    match: "tier:cheap",
    provider: "anthropic",
    model: "claude-3.5-haiku",
    budget_usd: 0.01,
    fallback: null,
  },
];

export const evalRuns: EvalRunSummary[] = [
  {
    run_id: "eval-2026-04-28-1830",
    fixture: "lighthouse.golden",
    status: "passed",
    pass_count: 14,
    fail_count: 0,
    duration_ms: 38_400,
    finished_at: iso(-39_600),
  },
  {
    run_id: "eval-2026-04-28-1900",
    fixture: "lighthouse.escalation",
    status: "failed",
    pass_count: 11,
    fail_count: 2,
    duration_ms: 41_900,
    finished_at: iso(-37_200),
  },
];

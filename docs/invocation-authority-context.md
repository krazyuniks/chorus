---
type: project-doc
status: planning
date: 2026-05-14
---

# Invocation Authority Context

## Purpose

This document is the Phase 2B-03 docs-first schema sketch for invocation
authority context. It extends
[ADR 0013](../adrs/0013-identity-authority-observability-boundaries.md), the
[observability and user-journey model](observability-user-journey-model.md),
and the [workload-principal model](workload-principal-model.md).

The model names the bounded context that proves why one Agent Runtime
invocation, and any later Tool Gateway request derived from it, had authority
to run under a tenant, workflow, agent version, task kind, model route, budget,
workload principal, and optional approval or policy-change reference.

No contract, migration, seed, signature mechanism, or runtime object is added
yet. The current Lighthouse path already carries the individual identifiers in
`AgentInvocationRequest`, `ToolGatewayRequest`, `decision_trail_entries`, and
`tool_action_audit`. A new executable object would be useful when Agent Runtime
and Tool Gateway become separate service boundaries, when authority must be
verified independently of direct Python calls, or when approval and policy
mutation work needs a durable `authority_context_id` join.

## Boundary Rules

- Authority context is application policy evidence, not authentication.
- Agent Runtime creates the agent-invocation authority context after resolving
  tenant policy, approved agent version, prompt reference, route version, and
  budget cap.
- Tool Gateway consumes either the relevant authority fields or a future
  `authority_context_id` plus tool-authority subset; it still enforces grants,
  schemas, modes, approvals, idempotency, and redaction locally.
- Temporal workflow code must not sign, inspect secrets, call external
  identity systems, or perform non-deterministic authority checks. Effectful
  creation or verification belongs in activities and service boundaries.
- Authority context is never prompt text. Agents may receive task input and
  contract expectations, but they do not receive connector credentials, cloud
  credentials, signed tokens, or ambient authority.
- Authority context belongs in typed request payloads and audit metadata. It
  does not belong in OpenTelemetry baggage.
- No authority context field may contain credentials, API keys, access tokens,
  raw prompts, raw model outputs, raw tool arguments, raw connector responses,
  raw lead/email content, customer names, email addresses, personal names,
  IP addresses, hostnames, filesystem paths, or unbounded rationale text.

## Agent Invocation Context Sketch

The following field set is the minimum local shape for a future structured
agent-invocation authority context:

```text
invocation_authority_context
  schema_version
  authority_context_id
  context_kind                 -- agent_invocation
  tenant_id
  correlation_id
  workflow_id
  workflow_type                -- lighthouse initially
  invocation_id
  parent_invocation_id         -- nullable
  agent_id
  agent_version
  agent_role
  task_kind
  prompt_reference
  prompt_hash
  provider_id
  model_id
  route_id
  route_version
  route_policy_ref             -- nullable safe policy/catalogue ref
  budget_cap_usd
  budget_currency              -- USD initially
  execution_engine             -- langgraph initially
  graph_version
  workload_principal_id        -- nullable until 2B workload sessions are executable
  workload_session_id          -- nullable; never baggage
  trust_domain                 -- local.chorus or fixture.chorus initially
  approval_id                  -- nullable
  policy_change_id             -- nullable
  issued_at
  expires_at
  trace_join                   -- safe OTel trace/span IDs and service refs only
  integrity                    -- optional future signed-envelope metadata
```

Field rules:

| Field family | Rule |
|---|---|
| Tenant and workflow | Values must match the activity request and persisted workflow evidence. Use stable IDs only. |
| Invocation | `invocation_id` is minted by Agent Runtime for the specific attempt. A fallback attempt gets a new invocation ID and references the failed attempt through `parent_invocation_id`. |
| Agent | `agent_id`, `agent_version`, `agent_role`, `prompt_reference`, and `prompt_hash` come from approved registry rows, not from model output or prompt text. |
| Route | `provider_id`, `model_id`, `route_id`, and `route_version` come from approved immutable route metadata. Provider credential state and secret refs are excluded. |
| Budget | `budget_cap_usd` is the policy cap used for enforcement. Observed cost remains decision-trail evidence, not authority input. |
| Workload | Workload references use the 2B-02 docs-first IDs. They are nullable until workload-session persistence exists. |
| Approval and policy | `approval_id` and `policy_change_id` are nullable until 2B-04 and 2B-05 make them executable. Store references, not approval rationale or policy diff bodies. |
| Expiry | `expires_at` should be short-lived and bounded to the invocation or activity attempt. It is service evidence, not Temporal workflow state. |
| Trace join | Include only `otel.trace_id`, `otel.span_id`, service name, workload principal ID, and trust domain when available. |
| Integrity | If a signed envelope is later added, store algorithm ID, key reference, issued-at, expires-at, and signature outside the canonical payload. Never store signing key material. |

## Tool Authority Context Sketch

Tool authority is derived from an agent invocation context, but the Tool Gateway
must still make its own grant and verdict decision. A future gateway-facing
shape should be narrower than the agent-invocation context:

```text
tool_authority_context
  schema_version
  authority_context_id
  parent_authority_context_id
  context_kind                 -- tool_request
  tenant_id
  correlation_id
  workflow_id
  invocation_id
  agent_id
  agent_version
  task_kind
  tool_name
  requested_mode               -- read | propose | write
  enforced_mode                -- nullable until verdict
  grant_id                     -- nullable until grant resolution
  grant_version                -- nullable until grant versioning exists
  approval_id                  -- nullable
  policy_change_id             -- nullable
  workload_principal_id
  workload_session_id
  trust_domain
  issued_at
  expires_at
  trace_join
  integrity
```

Field rules:

| Field family | Rule |
|---|---|
| Parent link | `parent_authority_context_id` links back to the Agent Runtime authority context when executable context exists. The current local path can continue joining by `invocation_id`. |
| Tool and mode | `tool_name` and `requested_mode` come from `ToolGatewayRequest`; `enforced_mode`, `grant_id`, and verdict fields are gateway outputs, not agent claims. |
| Arguments | Raw tool arguments are excluded. The gateway validates and redacts arguments under the existing tool contract and audit policy. |
| Approval | `approval_id` is nullable for current `approval_required` verdicts and becomes required only for future executable approval packages. |
| Connector | Connector invocation IDs are verdict/audit evidence, not authority input. |

## Lifecycle

1. Temporal activity invokes Agent Runtime with stable workflow and task fields.
2. Agent Runtime resolves tenant, agent version, prompt reference, route
   version, budget cap, execution graph, and invocation ID.
3. Agent Runtime can construct an invocation authority context for audit
   metadata before calling the graph/model adapter.
4. Agent Runtime records the authority summary with the decision trail,
   alongside existing graph, route, cost, latency, and OTel join metadata.
5. If a workflow later requests a tool action, the Tool Gateway receives the
   current request fields and can validate them against a future tool-authority
   context or join by `invocation_id` in the current local path.
6. Tool Gateway records the grant, mode, verdict, approval state, connector
   result, redaction state, and safe authority references in `tool_action_audit`.
7. BFF/UI projections may show safe references such as `authority_context_id`,
   route ID/version, provider/model, tool/mode, verdict, and expiry status.
   They must not expose signed payloads, raw arguments, raw prompts, raw
   outputs, approval rationale, or sensitive identity claims.

## Telemetry, Projection, and Audit Placement

| Plane | Allowed authority fields | Excluded fields |
|---|---|---|
| OTel resource attributes | Workload principal and trust-domain fields allowed by the workload-principal model. | Authority payloads, route policy bodies, approval refs, policy-change refs, signatures. |
| OTel span attributes | Stable join and bounded category fields already allowed by the observability model: tenant, correlation, workflow, invocation, agent, task kind, route ID/version, provider/model, tool name, requested/enforced mode, verdict, fallback state, graph version. | Raw prompts, raw outputs, raw tool arguments, raw connector responses, approval rationale, policy-change rationale, signatures, credential state, secret refs. |
| OTel baggage | Only the existing allow-list: tenant, correlation, workflow, actor session, and fixture run IDs. | Invocation IDs, route fields, provider/model fields, tool modes, approval IDs, policy-change IDs, authority-context IDs, signatures, authority state. |
| Postgres projections and BFF/UI | Safe read-only references, expiry status, bounded verdicts, route/provider summaries, and redaction labels. | Full authority packages, signed envelopes, raw arguments, raw prompts/outputs, full identity-provider claims. |
| Audit/accountability | Full structured authority context or a canonical summary plus `authority_context_id`, safe trace join metadata, workload refs, route refs, tool/mode refs, approval/policy-change refs, and integrity metadata. | Credentials, access tokens, signing keys, raw sensitive content, unredacted tool arguments, PII. |

## Promotion Criteria

Keep this docs-first until one of these happens:

- Agent Runtime and Tool Gateway become separate HTTP or message-based service
  boundaries and need verifiable authority context between processes;
- Tool Gateway needs to verify that a tool request was derived from an
  authorised Agent Runtime invocation rather than trusting in-process calls;
- 2B-04 approval packages need `approval_id` to bind to a specific invocation
  or tool request;
- 2B-05 policy mutations need `policy_change_id` to prove which route, prompt,
  budget, or grant version authorised a run;
- workload sessions become executable and runtime/gateway audit needs to bind
  caller workload identity to invocation authority.

When promoted, prefer a local deterministic Python object first. Add a JSON
Schema contract only if the authority context crosses a service boundary or is
validated by a release gate. If a signed envelope is required, keep signing in
effectful service/activity code, use canonical JSON over the non-secret
payload, store only key references and signatures, and add focused Agent
Runtime and Tool Gateway tests.

Promotion must not add AWS, production SSO, production cloud deployment,
credential entry, provider API keys, mutating admin UI, raw prompts/outputs,
raw tool arguments, raw sensitive content, or PII.

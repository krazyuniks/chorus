---
type: project-doc
status: planning
date: 2026-05-14
---

# Observability and User-Journey Data Model

## Purpose

This document is the Phase 2B-01 field-placement model promised by
[ADR 0013](../adrs/0013-identity-authority-observability-boundaries.md). It
defines which identifiers and fields belong in OpenTelemetry attributes or
baggage, which belong in Postgres projections and BFF/UI read models, which
belong only in audit/accountability records, and which actor/session
identifiers later Phase 2B work should introduce.

This is a docs-first schema sketch. No contract is added yet because no
cross-boundary payload changes are required for the current Lighthouse path.
Future implementation work should promote only stable service payloads into
`contracts/`; local projection tables and UI view models can remain Postgres
and BFF-owned until a second service consumes them as a contract. The companion
workload-principal model in
[`workload-principal-model.md`](workload-principal-model.md) defines the
2B-02 local workload identity, workload-session, tenant-scope, and future AWS
IAM mapping shape. The companion invocation-authority model in
[`invocation-authority-context.md`](invocation-authority-context.md) defines
the 2B-03 authority-context field set and where it may be carried.
The companion approval lifecycle model in
[`human-approval-audit-lifecycle.md`](human-approval-audit-lifecycle.md)
defines the 2B-04 approval package, reviewer actor refs, decision/SLA fields,
policy refs, workload refs, safe trace joins, and audit lifecycle for future
approval-required actions.
The companion policy-change workflow in
[`policy-change-governance-workflow.md`](policy-change-governance-workflow.md)
defines the 2B-05 policy-change package, target refs, before/after refs,
proposer/reviewer actor refs, approval refs, eval evidence refs, apply/rollback
refs, expiry/SLA, workload refs, safe trace joins, and audit lifecycle for
future prompt, route, budget, and grant mutation.
The companion sidecar evaluation in
[`llm-observability-sidecar-evaluation.md`](llm-observability-sidecar-evaluation.md)
defines the 2B-06 allowed export field set, forbidden data, trace/eval join
rules, retention and sampling assumptions, local authority split, and promotion
criteria for optional LangSmith, Langfuse, or similar tooling.

## Placement Rules

The default rule is that every material operation carries stable join keys, but
the plane that stores a field depends on the question it answers.

| Plane | Stores | Does not store |
|---|---|---|
| OpenTelemetry resource attributes | Low-cardinality workload identity and runtime environment fields used to understand which service emitted telemetry. | Business authority decisions, raw prompts, raw outputs, credentials, access tokens, or customer content. |
| OpenTelemetry span attributes | Operational and correlation fields needed to diagnose latency, errors, retries, dependency calls, graph execution, and workflow progress. | Canonical approval decisions, policy mutation evidence, raw tool arguments, raw email bodies, full actor identity, or secrets. |
| OpenTelemetry baggage | Minimal propagated join keys inside trusted Chorus service calls. | Provider/model choices, prompt references, approval decisions, policy state, raw sensitive content, PII, credentials, API keys, or access tokens. |
| Postgres projections and BFF/UI read models | Refresh-safe journey and reviewer evidence that is safe to inspect: workflow progress, UI/BFF route context, fixture context, safe actor-session references, and derived status. | Raw sensitive content, secret material, full authority packages, or data that is only needed for immutable accountability. |
| Audit/accountability records | Immutable evidence for authority-sensitive decisions: who or what was authorised, under which policy, with which prompt/model/tool/approval context, and why. | Operational metric streams or hosted tracing as the source of truth. |

Telemetry may be sampled, exported, or expired. Postgres audit remains
canonical for accountability, and Postgres projections remain canonical for the
BFF/UI inspection surface.

## OpenTelemetry Attributes

OpenTelemetry attributes are for operational diagnosis and correlation. They
must be safe if exported to a local or future optional observability backend.

### Resource Attributes

Resource attributes describe the workload emitting telemetry. Phase 1 already
uses OTel service attributes through the `opentelemetry-instrument` entrypoint.
Phase 2B should standardise these fields:

| Attribute | Meaning | Source |
|---|---|---|
| `service.name` | Running service, for example `chorus-bff`, `chorus-intake-poller`, `chorus-projection-worker`. | Compose/service configuration. |
| `service.namespace` | Stable namespace, normally `chorus`. | Service configuration. |
| `deployment.environment` | Local environment label, normally `local`. | Environment. |
| `service.version` | Build or repo version when available. | Build metadata. |
| `chorus.workload.principal_id` | Local workload principal ID, initially the service name. | Future workload-principal table or environment. |
| `chorus.workload.trust_domain` | Local trust domain, initially `local.chorus`. | Future workload-principal table or environment. |

Do not add host usernames, local filesystem paths containing personal names,
cloud credentials, secret refs, IP addresses, or full container environment
payloads as resource attributes.

### Span Attributes

Span attributes describe a single operation. Use them for joins, timings,
errors, retry diagnosis, and route inspection. Prefer stable IDs and bounded
categorical values.

| Attribute | Use | Notes |
|---|---|---|
| `chorus.tenant_id` | Tenant join key. | Existing span helper supports this. |
| `chorus.correlation_id` | Cross-surface workflow/business correlation. | Existing span helper supports this. |
| `chorus.workflow_id` | Temporal workflow join key. | Existing span helper supports this. |
| `chorus.workflow.type` | Workflow family such as `lighthouse`. | Low-cardinality. |
| `chorus.workflow.step` | Current workflow step. | Use bounded step names. |
| `chorus.invocation_id` | Agent invocation join key. | Set on Agent Runtime spans where available. |
| `chorus.agent.id` | Governed agent ID. | Stable logical agent, not a cloud identity. |
| `chorus.agent.version` | Governed agent version. | Safe to expose. |
| `chorus.agent.role` | Role such as `researcher` or `validator`. | Low-cardinality. |
| `chorus.task_kind` | Runtime task kind. | Low-cardinality. |
| `chorus.execution.engine` | Execution engine such as `langgraph`. | Low-cardinality. |
| `chorus.execution.graph_version` | Agent graph version. | Safe execution evidence. |
| `chorus.provider.id` | Selected provider ID. | Safe catalogue ID; no credential state. |
| `chorus.model.id` | Selected model ID. | Safe catalogue ID. |
| `chorus.route.id` | Model route ID. | Stable policy ID. |
| `chorus.route.version` | Immutable route version. | Use numeric or string value. |
| `chorus.fallback.applied` | Whether provider fallback occurred. | Boolean. |
| `chorus.fallback.reason` | Bounded reason such as `provider_timeout`. | Avoid free-text exception details. |
| `chorus.tool.name` | Tool name behind the gateway. | Bounded catalogue value. |
| `chorus.tool.requested_mode` | Requested mode. | Bounded value. |
| `chorus.tool.enforced_mode` | Enforced mode. | Bounded value. |
| `chorus.gateway.verdict` | Gateway verdict. | Bounded value. |
| `chorus.event.type` | Workflow or audit event type. | Bounded value. |
| `chorus.fixture.id` | Eval or replay fixture ID. | Safe local fixture label. |
| `chorus.actor.session_id` | Future local actor-session join key. | Opaque ID only; no email/name. |

Do not put prompt text, model output, raw lead email content, raw tool
arguments, connector responses, approval rationale, policy-change rationale,
customer names, email addresses, access tokens, API keys, provider credentials,
secret reference values, or unbounded exception text in span attributes.

Cost and latency should be metric values or existing decision-trail fields, not
high-cardinality span labels. If a span needs an operational error reason, use a
bounded enum and keep detailed accountability in audit.

## Propagated Baggage

Baggage is more sensitive than span attributes because it is propagated. Chorus
uses a strict allow-list and strips baggage at connector boundaries unless a
connector trust policy explicitly permits forwarding.

Allowed internal baggage keys:

| Baggage key | Meaning |
|---|---|
| `chorus.tenant_id` | Tenant join key. |
| `chorus.correlation_id` | Cross-surface correlation key. |
| `chorus.workflow_id` | Workflow join key when a request belongs to a workflow. |
| `chorus.actor_session_id` | Future opaque local reviewer/operator session ID. |
| `chorus.fixture_run_id` | Future eval or fixture replay session ID. |

Do not propagate `invocation_id`, `agent_id`, route fields, provider/model
fields, prompt references, tool modes, approval IDs, policy change IDs, or
authority context/state through baggage. Those values belong in typed request
payloads, audit records, or local projections. This prevents accidental leakage
to connectors and keeps business authority out of ambient context.

## Postgres Projections and BFF/UI Read Models

Projection data answers "what path did this workflow, reviewer, or fixture
take?" It should be safe for read-only UI inspection and refresh/reconnect.

### Existing Projection Fields

The current Phase 1 projection surface remains valid:

| Source | Fields that belong here |
|---|---|
| `workflow_read_models` | `tenant_id`, `workflow_id`, `correlation_id`, `lead_id`, `status`, `current_step`, safe `lead_summary`, `last_event_id`, `last_event_sequence`, `started_at`, `completed_at`, `updated_at`, and safe metadata. |
| `workflow_history_events` | `tenant_id`, `workflow_id`, `correlation_id`, `event_type`, `sequence`, `step`, `occurred_at`, contract-shaped event payload, source event ID, and OTel join metadata. |
| BFF workflow views | Workflow summaries, timelines, current status, step history, correlation IDs, and links into Temporal, Grafana, Redpanda, Mailpit, decision trail, and tool verdict views. |
| BFF decision/tool views | Safe projections of audit records: IDs, status, route/provider summaries, bounded verdicts, cost/latency summaries, and redaction labels. |

The UI may display safe subsets of audit data for review, but the projection is
not the authority store. A reviewer-friendly field in the UI does not make the
BFF an audit owner.

### Future Journey Projection Sketch

When Phase 2B adds actor/session evidence, introduce projection-owned records
that can be populated by the BFF without production SSO:

```text
actor_sessions
  tenant_id
  actor_session_id
  actor_type              -- human | system | fixture
  actor_subject_ref       -- opaque local ref, not email/name
  actor_display_label     -- optional local label such as reviewer-local
  started_at
  last_seen_at
  ended_at
  trust_domain            -- local.chorus initially
  auth_method             -- local-dev | fixture | future-sso
  metadata                -- safe, bounded UI metadata only

journey_events
  tenant_id
  journey_event_id
  actor_session_id
  correlation_id
  workflow_id
  invocation_id           -- nullable join key, not propagated baggage
  event_type              -- bounded UI/BFF event name
  route_id                -- UI route or BFF endpoint family
  surface                 -- bff | ui | eval | fixture
  occurred_at
  outcome                 -- viewed | submitted | replayed | disconnected
  metadata                -- safe filters/status only
```

Candidate BFF/UI views:

| View | Purpose | Backing data |
|---|---|---|
| Workflow journey timeline | Shows workflow progress plus reviewer touchpoints by correlation ID. | `workflow_history_events` joined to future `journey_events`. |
| Actor-session detail | Shows which safe UI/BFF surfaces a reviewer or fixture session used. | Future `actor_sessions` and `journey_events`. |
| Fixture replay context | Shows deterministic replay or eval path used to inspect a run. | Future `journey_events` with `surface='fixture'` or `surface='eval'`. |

Do not store raw request headers, IP addresses, full user-agent strings, access
tokens, cookies, raw form bodies, email addresses, or personal names in journey
projections. If production auth is added later, store an opaque subject
reference and keep identity-provider claims in the identity/approval audit
model according to retention policy.

## Audit-Only Accountability Fields

Audit records answer "who or what was authorised to do which
authority-sensitive action, under which policy, and why?" These fields must not
be carried in baggage and should only be projected into the UI as safe,
read-only subsets.

| Audit field family | Examples |
|---|---|
| Invocation authority | `authority_context_id`, `tenant_id`, `correlation_id`, `workflow_id`, `invocation_id`, `agent_id`, `agent_version`, `task_kind`, parent invocation, expiry, route ID/version, provider/model, budget cap, workload principal/session refs. |
| Prompt and output evidence | Prompt reference, prompt hash, contract refs, redacted input/output summaries, validation outcome, cost, duration. |
| Tool authority | Tool call ID, tool name, requested/enforced mode, grant ID/version, idempotency key, verdict, bounded reason, connector invocation ID. |
| Approval evidence | `approval_id`, approval package version, requested action, reviewer subject ref, reviewer role, decision, expiry, SLA, bounded reason category, policy refs, workload/session refs, and applied policy. |
| Policy mutation evidence | `policy_change_id`, target policy type, target object refs, before/after version refs, proposer and reviewer actor refs, approval refs where required, reason category, eval evidence refs, apply/rollback refs, expiry/SLA, workload/session refs, and timestamps. |
| Trace join metadata | `otel.trace_id`, `otel.span_id`, plus safe service/workload IDs at write time. |

Audit may contain redacted arguments or summaries when accountability requires
them, but it must still follow redaction policy. Raw sensitive content is not
made safe merely by storing it in audit.

## Future Actor and Session Identifiers

The next Phase 2B items should introduce these identifiers without production
SSO or AWS dependencies:

| Identifier | Owner | Purpose |
|---|---|---|
| `workload_principal_id` | Workload-principal model, then service configuration. | Names the running service or worker for workload authentication evidence. |
| `workload_session_id` | Runtime process/session metadata. | Distinguishes one running workload instance from another without cloud credentials. |
| `trust_domain` | Identity model. | Separates `local.chorus` from future cloud or hybrid trust domains. |
| `actor_session_id` | BFF/UI local session model. | Joins reviewer/operator/fixture journey events without storing personal identity. |
| `actor_subject_ref` | Future identity layer. | Opaque local or federated subject reference; not an email address or display name. |
| `approval_id` | Approval workflow. | Joins approval-required verdicts to approval packages and audit decisions. |
| `policy_change_id` | Policy mutation workflow. | Joins route, prompt, budget, and grant proposals to approvals, eval evidence, apply, and rollback. |
| `authority_context_id` | Invocation authority context. | Joins structured/signed authority context to runtime and gateway audit records. |
| `fixture_run_id` | Eval/fixture harness. | Groups local replay/eval journey events and evidence output. |

Future AWS fields such as role ARN, role session name, STS session tags, IAM
Roles Anywhere certificate subject, or external identity-provider reference are
mapping metadata defined in
[`workload-principal-model.md`](workload-principal-model.md). They are not
required for local 2B-01 evidence and must not be carried in telemetry baggage.

## Implementation Notes

- Keep the current Lighthouse Phase 1 spans and Postgres audit tables working.
- Add fields to OpenTelemetry helpers only when a service actually emits them.
- Prefer bounded enums and stable IDs over free text in telemetry.
- Add Postgres schema only when a Phase 2B implementation item starts writing
  workload sessions, actor sessions, journey events, approval packages, or
  policy changes.
- Promote schemas to `contracts/` only when a payload crosses a service
  boundary or must be validated by a release gate.
- Keep optional LLM observability sidecars derived from filtered OTel/eval data;
  never make them the accountability store, release gate, policy mutation path,
  prompt source of truth, or hosted local dependency.

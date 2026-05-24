---
type: project-doc
status: active
date: 2026-05-24
---

# Human Approval Identity and Audit Lifecycle

## Purpose

This document defines the approval package and audit lifecycle model. It
extends the [observability and user-journey model](observability-user-journey-model.md),
the [workload-principal model](workload-principal-model.md), and the
[invocation-authority context](invocation-authority-context.md).
The companion policy-change model in
[`policy-change-governance-workflow.md`](policy-change-governance-workflow.md)
defines the proposal, approval, apply, and rollback lifecycle for future
policy-change packages that may reference `approval_id`.

The current Tool Gateway can return an `approval_required` verdict when an
allowed grant requires a human decision before connector execution. That verdict
is audit-visible and, for write-mode calls, creates a durable approval package
inside the gateway authority boundary. This model defines the approval package
and audit lifecycle that executable work should use
without adding production SSO, AWS, credential entry, production connector
writes, raw sensitive content, or a mutating admin UI.

The local package path creates requested approval package rows with safe refs
and bounded categories for approval-required connector writes. The local
approved-apply path for those packages stays inside the Tool Gateway. Calendar
status keeps its read-only compatibility projection from the same package/apply
audit records. Reviewer decisions, BFF/UI queues, Temporal waits, production
identity, and production connector writes remain out of scope.

## Boundary Rules

- Approval is application authority evidence, not authentication by itself.
- The Tool Gateway remains the enforcement point for grants, argument schemas,
  requested/enforced mode, idempotency, redaction, approval state, and connector
  invocation.
- A reviewer identity is an opaque `actor_subject_ref` plus role and session
  references. It is not an email address, personal name, identity-provider claim
  dump, access token, or cloud credential.
- Approval does not give agents ambient connector authority. An approved package
  authorises only the specific action and authority context it references, and
  the gateway must re-check expiry, package state, grant state, idempotency, and
  policy references before any future apply step.
- Approval packages and approval audit records may carry stable IDs, bounded
  categories, redaction labels, policy references, workload/session references,
  and trace join metadata. They must not carry secrets, API keys, access tokens,
  provider credentials, raw prompts, raw model outputs, raw tool arguments, raw
  connector responses, raw approval rationale, raw enquiry/email content, customer
  names, email addresses, personal names, IP addresses, hostnames, filesystem
  paths, or unbounded free text.
- Approval IDs and approval state do not belong in propagated telemetry baggage.
  Traces can be joined from audit records through safe OTel trace/span IDs.

## Current Gateway Trigger

The current `approval_required` trigger is:

```text
tool_grants.allowed = true
tool_grants.approval_required = true
requested tenant + agent + tool + mode matches the grant
```

When that trigger fires for a write-mode call, the gateway:

1. validates the tool request and arguments;
2. resolves the grant;
3. returns a `GatewayVerdict` with `verdict = approval_required`;
4. keeps `enforced_mode` equal to the requested mode;
5. does not call the connector;
6. creates an `approval_package` row with safe subject/action refs and bounded
   policy refs;
7. writes a `tool_action_audit` row with redacted arguments and safe OTel
   metadata.

The verdict is not itself the approval decision. Approval packages are not
created for non-write calls unless a later design explicitly adds that surface.

## Approval Package Shape

The approval package is the durable, non-secret envelope created when an
authority-sensitive action needs review. It can later become a Postgres table or
contract when the gateway, BFF, or workflow starts writing or consuming it.

```text
approval_package
  schema_version
  approval_id
  approval_package_version
  tenant_id
  correlation_id
  workflow_id
  workflow_type
  invocation_id
  tool_call_id
  verdict_id
  source_audit_event_id
  authority_context_id          -- nullable until invocation context is executable
  tool_authority_context_id     -- nullable until tool context is executable
  agent_id
  agent_version
  task_kind
  requested_action              -- bounded action label, not raw arguments
  tool_name
  requested_mode                -- read | propose | write
  enforced_mode                 -- read | propose | write
  idempotency_key_ref           -- safe reference or hash, not raw payload
  redaction_policy_ref
  redaction_summary             -- for example fields_redacted, not values
  approval_state                -- requested | approved | denied | expired | cancelled | superseded
  decision                      -- nullable until decided
  reason_category               -- nullable bounded enum
  requested_at
  decision_due_at
  expires_at
  sla_policy_ref
  escalation_policy_ref         -- nullable
  reviewer_actor_subject_ref    -- nullable opaque subject ref
  reviewer_actor_session_id     -- nullable opaque session ref
  reviewer_role                 -- nullable bounded local role
  reviewer_trust_domain         -- local.chorus initially
  decision_at                   -- nullable
  requested_by_workload_principal_id
  requested_by_workload_session_id
  decided_by_workload_principal_id
  decided_by_workload_session_id
  trust_domain
  policy_version_refs
  trace_join
  metadata
```

Field rules:

| Field family | Rule |
|---|---|
| Approval identity | `approval_id` is an opaque generated ID. Do not derive it from reviewer, tenant, host, or customer data. |
| Tenant and workflow | `tenant_id`, `correlation_id`, and `workflow_id` must match the source Tool Gateway request and audit row. |
| Authority references | `invocation_id`, `tool_call_id`, `verdict_id`, `source_audit_event_id`, and future authority-context IDs bind the package to one exact request. |
| Requested action | Use a bounded action label such as `outbound_comms.message.write` or `calendar.create_hold.write`. Do not store raw tool arguments or connector payloads. |
| Tool mode | `requested_mode` comes from the tool call. `enforced_mode` comes from the gateway verdict and must be re-checked before any approved apply step. |
| Approval state | `requested` means the package exists but has no decision. Terminal states are `approved`, `denied`, `expired`, `cancelled`, and `superseded`. |
| Decision | `decision` is nullable until review. Allowed final values are `approved`, `denied`, `expired`, or `cancelled`. |
| Reason category | Use bounded categories only. Raw rationale stays out of the package and audit trail. |
| Reviewer identity | `reviewer_actor_subject_ref` is opaque. `reviewer_role` is a local approval role such as `uc1_reviewer`, `tool_risk_reviewer`, or `policy_reviewer`. |
| SLA and expiry | `decision_due_at` supports SLA reporting. `expires_at` is the hard authority boundary after which the package cannot authorise execution. |
| Policy refs | Store refs such as grant ID/version, route ID/version, prompt ref/hash, approval policy ref, or policy change ID when relevant. Store refs, not policy bodies or rationale. |
| Workload refs | Request and decision workload refs use the 2B-02 workload-principal/session IDs and remain nullable until executable sessions exist. |
| Trace join | Store only `otel.trace_id`, `otel.span_id`, service name, workload principal ID, and trust domain when available. |
| Metadata | Safe bounded labels only, for example fixture ID or source surface. No request headers, cookies, URLs with credentials, environment values, or free-text rationale. |

Suggested `reason_category` values:

```text
tool_write_risk
data_sensitivity
customer_impact
policy_exception
mode_escalation
connector_risk
duplicate_or_superseded
sla_expired
cancelled_by_requester
other_bounded
```

## Approval Audit Events

Approval audit should be append-only even if a future read model stores the
current package state. The current `audit_event` contract does not add an
approval category in this docs-only item. When promoted, approval work should
either extend the audit contract/table deliberately or add an approval-specific
append-only audit table. The minimum lifecycle events are:

| Event | Actor | Required outcome |
|---|---|---|
| `approval.requested` | `system` or `agent` via Tool Gateway | Package created, connector not invoked, source verdict is `approval_required`. |
| `approval.presented` | `system` or BFF workload | Optional read-model or UI queue exposure with safe fields only. |
| `approval.decided` | `human` or authorised system actor | Decision recorded with opaque reviewer subject ref, role, bounded reason category, and decision timestamp. |
| `approval.expired` | `system` | Package can no longer authorise execution after `expires_at` or SLA policy. |
| `approval.superseded` | `system` or policy actor | A newer package or policy change replaces the request before decision. |
| `approval.applied` | `system` via Tool Gateway | Future apply step rechecked package, grant, mode, expiry, and idempotency before connector execution. |

`approval.applied` is deliberately future-facing. It must remain behind the Tool
Gateway. A reviewer decision alone must not call a connector or mutate external
state.

## Lifecycle

1. A workflow activity calls the Tool Gateway with the current invocation and
   tool request fields.
2. The gateway validates arguments, resolves the grant, and finds
   `approval_required = true` for the requested tenant, agent, tool, and mode.
3. The gateway returns `approval_required`, writes the redacted
   `tool_action_audit` row, and creates an `approval_package` in the same
   authority boundary.
4. The package may be projected into a read-only approval queue using only safe
   fields: approval ID, tenant, workflow/correlation IDs, tool/action, mode,
   state, SLA/expiry, reviewer role requirement, and redaction labels.
5. A reviewer or authorised system actor records a decision with opaque subject
   ref, actor session ref, reviewer role, bounded reason category, decision
   timestamp, and safe workload/session refs.
6. If approved, an apply path re-enters the Tool Gateway. The gateway re-checks
   package state, expiry, idempotency key, grant state, requested and enforced
   mode, policy refs, tenant, workflow type, invocation/tool authority refs,
   and safe subject/action refs before any connector invocation. Calendar
   apply keeps calendar-specific status fields for the existing read-only
   projection, but the authority check is generic.
7. If denied, expired, cancelled, or superseded, the workflow should branch to a
   safe outcome such as propose-only or escalation, with explicit workflow and
   audit evidence.

## Telemetry, Projection, and Audit Placement

| Plane | Allowed approval fields | Excluded fields |
|---|---|---|
| OTel resource attributes | Workload principal and trust-domain fields already allowed by the workload-principal model. | Approval packages, reviewer identity details, decisions, rationale, policy bodies. |
| OTel span attributes | Bounded operational fields only when an executable approval service exists, for example approval state or expiry outcome on internal spans. | Raw rationale, actor identity claims, raw arguments, raw prompts/outputs, policy bodies, secrets, approval packages. |
| OTel baggage | None beyond the existing allow-list of tenant, correlation, workflow, actor session, and fixture run IDs. | Approval IDs, decisions, reviewer refs, tool modes, policy refs, rationale, authority state. |
| Postgres projections and BFF/UI | Safe approval queue/read-model fields, expiry status, bounded decision state, role requirement, and redaction labels. | Full package bodies, raw arguments, raw rationale, full actor claims, sensitive identity-provider data. |
| Audit/accountability | Full non-secret approval package summary, immutable lifecycle events, actor subject ref, role, decision, reason category, policy refs, workload/session refs, and trace joins. | Credentials, access tokens, raw sensitive content, raw prompts/outputs, unredacted tool arguments, raw rationale, PII. |

## Further Promotion Criteria

The local gateway package/apply path is active. Broaden the approval surface
only when one of these happens:

- a Temporal workflow waits for or reacts to approval decisions;
- BFF/UI adds a read-only approval queue or journey view;
- a local deterministic approval service records reviewer decisions;
- connector expansion needs executable approval evidence for risky
  writes;
- policy mutation needs approval actors and audit fields for change
  control.

For further promotion, keep the Postgres-backed package as the local source of
truth. Add a JSON Schema contract only when the approval package crosses a
service boundary or is validated by a release gate. Keep all AWS, production
SSO, production cloud deployment, identity-provider integration, credential
entry, mutating admin UI, and production connector writes out of the promotion
unless a later ADR explicitly changes the boundary.

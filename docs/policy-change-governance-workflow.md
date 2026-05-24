---
type: project-doc
status: planning
date: 2026-05-17
---

# Policy Change Governance Workflow

## Purpose

This document defines the policy mutation model. It extends the
[observability and user-journey model](observability-user-journey-model.md),
the [workload-principal model](workload-principal-model.md), the
[invocation-authority context](invocation-authority-context.md), and the
[human-approval lifecycle model](human-approval-audit-lifecycle.md).

The model defines how future Chorus work should propose, approve, apply, and
roll back authority-sensitive changes to prompt references, model routes,
budget caps, and tool grants without turning direct database mutation into the
normal operator path.

No contract, Postgres migration, seed, runtime apply service, credential path,
production provider call, production connector write, or mutating admin UI is
added by this item. The post-R3 local runtime keeps using the existing
seeded/local policy materialisation until a later ledger item deliberately
promotes this sketch into executable code.

## Boundary Rules

- Policy mutation is application authority, not authentication.
- A policy change package stores refs, versions, bounded categories, status,
  evaluator evidence refs, actor refs, workload refs, and trace joins. It does
  not store raw policy bodies when a stable object/version ref exists.
- Prompt text, model outputs, raw tool arguments, connector payloads, raw
  approval rationale, raw policy rationale, secrets, credentials, API keys,
  access tokens, provider credential state, identity-provider claim dumps, PII,
  customer content, hostnames, IP addresses, filesystem paths, request headers,
  cookies, and environment values are excluded from packages, telemetry
  baggage, projections, examples, and seeds.
- Agent Runtime remains the enforcement point for agent versions, prompt
  references, model routes, provider selection, graph execution, and budget
  caps.
- Tool Gateway remains the enforcement point for tool grants, argument schema
  validation, requested/enforced mode, approval state, idempotency, redaction,
  connector invocation, and action audit.
- Approval is a gate for selected policy changes, not a connector call. A
  reviewer decision cannot mutate policy by itself; an apply step must
  re-check package state, approval state, expiry, target refs, eval evidence,
  and idempotency.
- Policy-change IDs do not belong in OpenTelemetry baggage. Safe spans may
  carry bounded operational status when an executable policy-change service
  exists; accountability remains in audit.
- Temporal workflow code must not perform non-deterministic policy mutation,
  call identity providers, sign packages, or inspect secrets. Effectful apply
  and rollback work belongs in activities or service boundaries.

## Target Policy Types

The first governed targets are the policy surfaces already visible in Chorus:

| Target policy type | Current object refs | Version refs | Apply direction |
|---|---|---|---|
| `prompt_reference` | `agent_registry(tenant_id, agent_id, version)`, prompt reference, prompt hash. | Before/after prompt reference and hash, plus agent version when a new version is introduced. | Prefer creating or approving a new agent version/ref; do not store prompt text in the package. |
| `model_route` | `model_routing_policies.policy_id` for current runtime materialisation; `model_route_versions(route_id, route_version)` for immutable route evidence. | Before/after route ID/version, provider catalogue ID, provider ID, model ID, parameters ref/hash when later available. | Insert immutable route evidence first; later executable work can update the active materialisation only through the apply path. |
| `budget_cap` | `model_routing_policies.policy_id` and matching route-version refs. | Before/after budget cap and latency cap refs or values. | Treat budget changes as route changes when possible so eval evidence and rollback stay versioned. |
| `tool_grant` | `tool_grants.grant_id` plus `(tenant_id, agent_id, agent_version, tool_name, mode)`. | Before/after grant refs; future `grant_version` when grant versioning exists. | Keep grant mutation behind Tool Gateway policy ownership; do not bypass approval-required or redaction policy. |

The current `tool_grants` table is not versioned. Until a later implementation
adds grant versions, a policy change package should reference the stable
`grant_id` and tuple above, plus before/after safe field summaries. Do not
invent a mutable admin path around the table to make the model look complete.

## Policy Change Package Shape

The package is a future durable, non-secret envelope. It can later become a
Postgres table or JSON Schema contract when a service starts writing,
reviewing, applying, or projecting it.

```text
policy_change_package
  schema_version
  policy_change_id
  policy_change_package_version
  tenant_id
  correlation_id                    -- nullable; set when tied to a workflow/eval/incident
  workflow_id                       -- nullable
  workflow_type                     -- nullable
  target_policy_type                -- prompt_reference | model_route | budget_cap | tool_grant
  target_object_refs                -- stable refs only
  before_version_refs
  after_version_refs
  proposer_actor_subject_ref        -- opaque local/federated subject ref
  proposer_actor_session_id         -- nullable opaque session ref
  proposer_role                     -- bounded local role
  reviewer_actor_subject_ref        -- nullable until reviewed
  reviewer_actor_session_id         -- nullable
  reviewer_role                     -- nullable bounded local role
  approval_id                       -- nullable; required only when approval policy requires it
  approval_state_ref                -- nullable safe ref, not rationale
  change_state                      -- proposed | under_review | approved | rejected | applying | applied | apply_failed | rolled_back | expired | cancelled | superseded
  decision                          -- nullable until reviewed
  reason_category                   -- bounded enum
  eval_required
  eval_evidence_refs
  apply_ref                         -- nullable apply event/ref
  rollback_ref                      -- nullable rollback event/ref
  parent_policy_change_id           -- nullable, for rollback/follow-up
  supersedes_policy_change_id       -- nullable
  requested_at
  review_due_at
  expires_at
  approved_at                       -- nullable
  applied_at                        -- nullable
  rolled_back_at                    -- nullable
  requested_by_workload_principal_id
  requested_by_workload_session_id
  reviewed_by_workload_principal_id
  reviewed_by_workload_session_id
  applied_by_workload_principal_id
  applied_by_workload_session_id
  trust_domain                      -- local.chorus or fixture.chorus initially
  trace_join                        -- safe OTel trace/span IDs and service refs only
  metadata                          -- safe bounded labels only
```

Field rules:

| Field family | Rule |
|---|---|
| Change identity | `policy_change_id` is opaque and generated. Do not derive it from reviewer, tenant, host, prompt, provider, tool, or customer data. |
| Tenant and workflow | `tenant_id` is required. `correlation_id` and `workflow_id` are nullable because many policy changes are operator-initiated; set them only when the change is tied to a workflow, eval run, incident, or fixture. |
| Target refs | Store object refs and before/after refs. Do not store raw prompt bodies, raw route JSON bodies, raw tool arguments, credential refs containing secret values, or unbounded rationale. |
| Actor refs | Store opaque `actor_subject_ref`, actor session refs, role, and trust domain. Do not store email addresses, personal names, user profile data, or identity-provider claims. |
| Approval | `approval_id` binds to the 2B-04 approval package when policy requires a reviewer gate. Store approval refs, not raw approval rationale. |
| Reason category | Use a bounded enum. Raw policy rationale stays outside the package and audit trail. |
| Eval evidence | Store refs to eval fixtures, replay fixtures, eval run IDs, report IDs, or gate result IDs. Do not store raw prompts, raw model outputs, or full trace/export payloads. |
| Apply and rollback refs | Store append-only refs for apply and rollback events. Do not delete previous route, prompt, budget, or grant evidence. |
| Expiry and SLA | `review_due_at` supports queue/SLA reporting. `expires_at` is the hard authority boundary after which the package cannot authorise apply. |
| Workload refs | Use the 2B-02 workload-principal/session refs when executable. They remain nullable until workload sessions exist. |
| Trace join | Store only `otel.trace_id`, `otel.span_id`, service name, workload principal ID, and trust domain when available. |
| Metadata | Safe bounded labels only, for example fixture ID, evidence report ref, source surface, or command ref. |

Suggested `reason_category` values:

```text
eval_regression_fix
provider_degradation_response
cost_cap_adjustment
prompt_reference_update
tool_grant_adjustment
approval_policy_followup
security_or_safety_control
rollback
incident_response
routine_maintenance
other_bounded
```

## Lifecycle

1. **Propose.** A human or authorised automation creates a policy change
   package with target refs, before/after refs, reason category, expiry,
   proposer actor refs, workload refs, and safe trace joins. The package starts
   in `proposed` or `under_review`.
2. **Attach evidence.** The proposer attaches eval evidence refs or a
   documented exception ref. For route, prompt, budget, and grant changes, eval
   refs should normally include the affected UC1 fixture set or a later
   workflow-specific fixture set.
3. **Review.** A reviewer records a decision with opaque reviewer actor refs,
   reviewer role, bounded reason category, approval package ref when required,
   and decision timestamp. Rejections are terminal unless superseded by a new
   package.
4. **Apply.** A future apply service or activity re-checks package state,
   expiry, target refs, current before refs, approval state, eval evidence,
   workload authority, and idempotency before mutating any active policy
   materialisation. Apply writes an append-only `policy_change.applied` or
   `policy_change.apply_failed` audit event.
5. **Observe.** Projections may show safe queue and status fields. Runtime
   evidence should bind the applied `policy_change_id` to later invocation or
   gateway audit where that policy version authorised a run.
6. **Rollback.** Rollback is a governed change, not a destructive reset. It
   either re-applies the before refs through the same package's rollback path
   or creates a child package with `parent_policy_change_id`. Rollback writes an
   append-only event and leaves the failed/superseded policy evidence visible.
7. **Expire or supersede.** Packages that pass `expires_at` without apply become
   `expired`. A newer package targeting the same object can mark the previous
   package `superseded` through an audit event.

## Apply Semantics By Target

| Target | Future apply behaviour | Rollback behaviour |
|---|---|---|
| Prompt reference | Approve a new prompt ref/hash and bind it to a new or updated agent-version policy through Agent Runtime ownership. | Re-bind to the prior prompt ref/hash or agent version through a rollback package; do not erase the newer prompt evidence. |
| Model route | Insert or approve a new immutable `model_route_versions` row, then update active route materialisation only through the apply path until runtime directly selects route versions. | Mark the new route rolled back/disabled where supported and restore the previous approved route/materialisation. |
| Budget cap | Prefer a new route version carrying the budget cap. If a narrow cap materialisation exists later, update it only with before/after refs and eval evidence. | Restore the prior cap through the same governed path and record the rollback reason category. |
| Tool grant | Update grant authority only through Tool Gateway policy ownership. Future work should add `grant_version` before treating grant rollback as first-class. | Restore the previous grant state/version and keep approval-required/redaction policy evidence visible. |

## Policy Change Audit Events

Policy change audit should be append-only even if a future read model stores the
current package state.

| Event | Actor | Required outcome |
|---|---|---|
| `policy_change.proposed` | `human` or authorised system actor | Package created with target refs, before/after refs, proposer refs, reason category, expiry, and safe trace join. |
| `policy_change.evidence_attached` | `human` or authorised system actor | Eval/replay/report refs attached or exception ref recorded. |
| `policy_change.reviewed` | `human` or authorised system actor | Reviewer actor refs, role, decision, approval ref when required, and bounded reason category recorded. |
| `policy_change.approved` | `human` or authorised system actor | Package allowed to enter apply state, subject to re-checks. |
| `policy_change.rejected` | `human` or authorised system actor | Package denied and made terminal unless superseded. |
| `policy_change.applied` | `system` via policy apply boundary | Active materialisation changed after package, refs, approval, eval, expiry, and idempotency re-checks. |
| `policy_change.apply_failed` | `system` via policy apply boundary | Apply failed without partial hidden mutation; failure category and safe refs recorded. |
| `policy_change.rolled_back` | `system` via policy apply boundary | Prior refs restored or child rollback package applied. |
| `policy_change.expired` | `system` | Package can no longer authorise apply. |
| `policy_change.superseded` | `system` or policy actor | A newer package replaces this proposed change. |

## Telemetry, Projection, and Audit Placement

| Plane | Allowed policy-change fields | Excluded fields |
|---|---|---|
| OTel resource attributes | Workload principal and trust-domain fields already allowed by the workload-principal model. | Policy packages, reviewer/proposer identity details, policy bodies, rationale. |
| OTel span attributes | Bounded operational fields only when an executable apply service exists, for example target policy type, change state, apply outcome, or expiry outcome. | Raw diffs, raw prompts/outputs, raw tool arguments, policy bodies, approval rationale, actor claims, secrets, credential refs with values. |
| OTel baggage | None beyond the existing allow-list of tenant, correlation, workflow, actor session, and fixture run IDs. | Policy change IDs, target refs, before/after refs, approval IDs, decisions, route fields, prompt refs, tool modes, authority state. |
| Postgres projections and BFF/UI | Safe queue/status fields: policy change ID, target type, target object label, state, SLA/expiry, eval evidence presence, approval-required flag, apply/rollback status, and redaction labels. | Full package bodies, raw diffs, raw rationale, raw arguments, raw prompt/output text, identity-provider data. |
| Audit/accountability | Full non-secret package summary, immutable lifecycle events, target refs, before/after refs, actor refs, approval refs, eval evidence refs, apply/rollback refs, workload/session refs, and trace joins. | Credentials, access tokens, raw sensitive content, raw prompts/outputs, unredacted tool arguments, raw rationale, PII. |

## Promotion Criteria

Keep this docs-first until one of these happens:

- route, prompt, budget, or grant mutation becomes a normal operator workflow;
- Agent Runtime starts selecting directly from immutable route versions and
  needs an applied `policy_change_id` in invocation authority context;
- tool grants gain executable versioning or rollback semantics;
- approval packages need to gate policy mutation rather than only tool actions;
- BFF/UI adds a read-only policy-change queue or audit view;
- eval/replay release gates start emitting stable policy-change evidence refs.

When promoted, start with local deterministic Postgres persistence and focused
runtime/gateway/eval tests. Add JSON Schema only when the package crosses a
service boundary or is validated by a release gate. Keep AWS, production SSO,
production cloud deployment, production identity-provider integration,
credential entry, credential mutation, production provider calls, production
connector writes, mutating admin UI, raw prompts/outputs, raw tool arguments,
raw sensitive content, raw rationale, and PII out of the promotion unless a
later ADR explicitly changes the boundary.

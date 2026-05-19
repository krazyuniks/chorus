---
type: project-doc
status: planning
date: 2026-05-03
---

# Chorus - Phase 2 Plan

## Purpose

Phase 1 proved the Lighthouse slice: durable Temporal workflow execution,
explicit Agent Runtime identity, Tool Gateway authority, Postgres audit,
Redpanda projections, UI inspection, observability, eval, replay, and
governance/failure evidence.

Phase 2 turns that evidence slice into a stronger governed-platform exemplar.
The goal is not to replace Temporal with an agent framework. The goal is to
prove that the Phase 1 boundaries can support a first-class LangGraph agent
execution layer, controlled provider choice, governed runtime mutation,
connector expansion, and a second workflow without losing audit, evaluation,
replay, or authority controls.

## Planning Posture

Phase 2 is in progress. Phase 2A, Phase 2B, and Phase 2C are complete. Phase
2D has selected its second-workflow proof scope, added a contract baseline for
safe support intake, agent IO, ticket tool arguments, and workflow/eval enum
values, added the local ticket desk sandbox behind the Tool Gateway for
read/propose ticket actions, and added the smallest code-defined
`support_triage` Temporal runtime with replay evidence. The support-specific
eval and persisted evidence baseline now proves the happy-path trace joins
across workflow events, Agent Runtime decisions, Tool Gateway ticket verdicts,
and proposed case-update refs. Read-only support inspection remains planned.
Phase 1
remains the stable demo baseline until each Phase 2 milestone has its own
evidence, tests, and documentation.

The repository is now the authoritative planning surface. Historical vault
records under `/home/ryan/Work/vault/records/radianit/projects/chorus/` informed
this plan, especially the SDLC operating model, provider collaboration model,
storage deferrals, and production-readiness notes. Those records are not
runtime authority; this document and the ADRs are.

## Phase 2 Objective

Phase 2 should answer five reviewer questions that Phase 1 deliberately
deferred:

1. Where does a market-recognised agent framework fit without taking over
   durable business orchestration?
2. How does Chorus safely choose, change, fail over, and audit real model
   providers?
3. How are prompt, model-route, and tool-grant changes proposed, approved,
   rolled back, and evaluated?
4. Can the Tool Gateway mediate a new connector or integration protocol without
   giving agents ambient authority?
5. Can the same orchestration and governance pattern support a second business
   workflow without becoming a generic DSL or framework skeleton?

## Non-goals

- Production SaaS packaging.
- Production customer data.
- Production writes to closed third-party systems.
- Full cloud deployment as a default implementation track.
- Scylla migration unless Phase 2 evidence produces append-heavy retention
  pressure that Postgres cannot represent credibly.
- Runtime-editable workflow DSL before a second code-defined workflow proves
  which abstraction is actually needed.
- Agent-framework features that duplicate Temporal workflow state, Tool Gateway
  authority, Postgres audit, or eval/replay release controls.
- LangSmith, Langfuse, or similar tooling as a required hosted dependency.

## Design Principles

- Preserve the Phase 1 demo. Lighthouse must keep working while Phase 2 grows.
- Runtime policy stays outside prompts. Agent code does not pick providers,
  grant tools, or bypass eval gates.
- LangGraph is an agent execution engine inside Agent Runtime, not a second
  durable workflow owner.
- Mutations are governed workflow events. Model routes, prompts, and grants are
  changed through proposed, approved, audited, and reversible paths.
- Provider and connector failures are evidence paths, not log-only incidents.
- A second workflow proves reuse of contracts and boundaries; it does not start
  a general-purpose workflow platform by itself.
- New capabilities must extend the evidence map with code, contracts, tests,
  eval fixtures, UI/BFF inspection, and runbook entries.

## Phase 2 Milestones

| Phase | Milestone | Status | Exit evidence |
|---|---|---|---|
| 2A. Agent execution and provider governance | Add LangGraph as the first-class agent execution runtime inside Agent Runtime, then continue commercial-provider adapter boundaries, model-route promotion rules, failover/degradation policy, budget telemetry, and provider-failure fixtures while retaining the local structured boundary as the default runnable path. | complete | A reviewer can inspect which LangGraph execution path ran, why a provider/model was selected, and prove fallback behaviour under provider failure, timeout, rate-limit, and budget-exceeded fixtures without production provider calls. |
| 2B. Governed identity, observability, and runtime change control | Add the identity/authority data model, observability boundary model, and audited proposal/approval/rollback flows for prompt references, model routes, budget caps, and tool grants. Keep direct database mutation out of the normal operator path. | complete | A reviewer can inspect the docs-first human, workload, agent, invocation, approval, policy-change, correlation, sidecar-export, and field-placement models before executable runtime mutation is added. |
| 2C. Connector expansion and approval hardening | Add one new sandbox or protocol-backed connector behind the Tool Gateway, plus stronger approval, idempotency, retry, and compensation evidence for risky writes. | complete | ADR 0014 selects a local CalDAV calendar connector candidate. Calendar argument schemas and safe samples cover availability lookup, hold proposal, hold creation, and hold cancellation. A local Radicale sandbox and Tool Gateway-dispatched connector path covers availability lookup and hold proposal, create/cancel writes remain approval-required and create a minimal local approval package, an approved local apply path re-enters the gateway to prove idempotent VEVENT creation, transient retry classification, cancellation compensation, and compensation-failure escalation, and the BFF exposes safe read-only calendar status/audit refs derived from local approval and audit rows. Calendar eval fixtures and a Lighthouse workflow calendar branch remain deferred. |
| 2D. Second workflow proof | Add one adjacent business workflow that reuses Agent Runtime, Tool Gateway, contracts, projections, eval, and observability without introducing a workflow DSL. | in progress | ADR 0015 selects a local Support Desk Triage workflow as the second workflow candidate. Contract schemas, generated models, safe samples, enum baselines, and a Postgres-backed local ticket desk sandbox now exist for support intake, support agent IO, local ticket arguments, `support_triage` workflow events, Phase 2D eval contract values, ticket case lookup, duplicate lookup, and proposed case updates. A code-defined `support_triage` Temporal workflow now reuses Agent Runtime and Tool Gateway activity boundaries for a local read/propose happy path, is registered on the worker, and has focused replay evidence. The support eval fixture and persisted evidence baseline now prove workflow events, Agent Runtime decisions, Tool Gateway ticket verdicts, and proposed case-update refs join by safe tenant/correlation/workflow refs while `ticket.update_status` remains approval-required and unexecuted. Read-only support inspection remains planned while Lighthouse remains intact. |
| 2E. Production-readiness architecture pack | Decide which production concerns should remain design-only and which need thin executable evidence: AWS identity mapping, secrets, deployment topology, retention, backup/restore, incident integration, and managed observability. | planned | ADRs and docs distinguish implemented local evidence from production architecture, with any executable spikes gated and explicitly scoped. |

## Phase 2A Completed Workstream

Phase 2A started with provider and model governance. That work remains valid:
the provider contracts, route-version catalogue, and provider-keyed model
adapter registry are the policy foundation LangGraph should call into.

The 2A pivot has added LangGraph as the agent execution engine inside Agent
Runtime before implementing commercial provider adapters. This strengthens the
"orchestrated agentic platform" story without adding a second workflow too
early or letting an agent framework overtake Temporal. LangGraph execution,
decision-trail graph metadata, the disabled commercial provider adapter
boundary, provider-failure fallback fixture evidence, route-selection audit
metadata, read-only provider/graph inspection views, and docs/runbook/evidence
alignment are implemented. Provider timeout, rate-limit, and budget-exceeded
fixture coverage now closes 2A without production provider calls.

2A delivered:

- a LangGraph execution engine behind the existing `lighthouse.invoke_agent_runtime`
  activity boundary;
- graph execution metadata in decision-trail records, including execution
  engine and graph version;
- a provider catalogue contract and Postgres-backed route metadata that can
  represent local, commercial, and disabled providers;
- a model adapter interface behind the existing Agent Runtime boundary;
- at least one commercial-provider adapter boundary that remains disabled in
  local evidence and records missing-credential/provider-disabled metadata;
- deterministic fallback to the local structured boundary when a selected
  provider boundary fails or is disabled by policy;
- provider failure, timeout, rate-limit, and budget-exceeded fixtures;
- decision-trail fields that make selected provider, selected model, fallback
  reason, route version, cost estimate, and latency visible;
- eval assertions for route selection, fallback, budget, and validator route
  diversity where the fixture can prove it;
- read-only UI/BFF inspection of provider catalogue, route versions, and
  fallback evidence;
- runbook notes for local credential handling, disabled-provider operation, and
  provider-failure diagnosis.

2A does not implement a full provider-management product, LangGraph durable
execution, LangGraph checkpoint persistence, long-term graph memory,
LangGraph-hosted deployment, or LangSmith as a core dependency. Mutating route
approval belongs in 2B.

## Completed Workstream: 2B

Phase 2B is complete. ADR 0013 defines the local identity, authority,
observability, user-journey evidence, and audit boundaries before adding
mutating runtime controls. The docs-first models now cover observability and
user-journey field placement, workload principals and future AWS IAM mapping,
invocation authority, the human approval package/audit lifecycle, governed
policy mutation for prompt references, model routes, budget caps, and tool
grants, and optional LLM observability sidecar export. This work did not add
production SSO, AWS deployment, hosted observability, credential entry,
credential mutation, production identity-provider integration, mutating admin
UI, production provider calls, production connector writes, runtime approval
behaviour changes, runtime policy mutation behaviour changes, sidecar
dependencies, or exporter code.

## Phase 2B Backlog

Phase 2B makes the governance story more credible before adding another
connector or workflow. The important move is to separate identities, authority,
telemetry, user journey evidence, and audit instead of using one overloaded
"observability" or "agent" concept.

Identity and authority should stay provider-neutral in the local implementation
while preserving a clean future mapping to AWS IAM. A later AWS deployment
could map Chorus workload principals to ECS task roles, EKS pod identities,
Lambda execution roles, or IAM Roles Anywhere role sessions. Chorus should
therefore model workload principal, trust domain, assumed role/session
metadata, tenant scope, agent version, invocation authority, and approval actor
explicitly without making AWS a local dependency.

Observability should have three separate planes:

- Infrastructure telemetry: OpenTelemetry traces, metrics, logs, service
  health, saturation, retries, and dependency failures. This answers "is the
  platform healthy?" and is exported through the Grafana stack in local
  evidence.
- Application and user journey evidence: workflow progress, UI/BFF interaction
  context, fixture replay, reviewer paths, and business correlation by
  `correlation_id`, `workflow_id`, `invocation_id`, and future
  `actor_session_id`. This answers "what path did this workflow or reviewer
  take?" and should be safe to project into the UI.
- Audit/accountability: Postgres decision trail, tool action audit, approval
  audit, and policy change audit. This answers "who or what was authorised to
  do which authority-sensitive action, under which policy, and why?" It remains
  canonical even if traces are exported to an LLM observability tool.

LangSmith, Langfuse, or similar LLM observability tools may be evaluated as
optional trace/eval sidecars after the local OpenTelemetry and audit boundaries
are clear. They must not become the accountability store, the policy mutation
path, or a required hosted dependency.

| ID | Required item | Evidence artefact | Gate | Status | Notes |
|---|---|---|---|---|---|
| 2B-00 | Identity, authority, and observability boundary ADR | `adrs/`; `docs/architecture.md`; `docs/phase-2-plan.md` | doc review; `git diff --check` | complete | ADR 0013 defines human, workload, agent, invocation, approval, and policy principals; local authority context; future AWS IAM mapping; infrastructure telemetry, application/user journey evidence, audit/accountability, optional LLM observability sidecars, and context hygiene. Evidence: `git diff --check`, `just contracts-check`, `just eval`, and focused 2A tests on 2026-05-14. |
| 2B-01 | Observability and user-journey data model | `contracts/` or docs-first schema sketch; BFF/UI projection plan; runbook | `git diff --check` | complete | Added `docs/observability-user-journey-model.md` as a docs-first model covering OTel resource/span attributes, baggage allow-list, Postgres projection and BFF/UI journey sketches, audit-only field families, and future actor/session identifiers. No contracts or code changed. |
| 2B-02 | Workload principal and future AWS IAM mapping | persistence schema/docs; local seed; architecture mapping table | focused persistence tests if schema changes | complete | Added `docs/workload-principal-model.md` as a docs-first model for local workload principals, workload sessions, trust domains, tenant scope, safe telemetry placement, and future optional AWS IAM role, STS session, IAM Roles Anywhere, SPIFFE, and external identity-provider mapping metadata. No schema, seeds, contracts, AWS dependency, credentials, production SSO, or production deployment were added. |
| 2B-03 | Invocation authority context | Agent Runtime and Tool Gateway request context; contracts if needed; tests | focused runtime/gateway tests; `just eval` | complete | Added `docs/invocation-authority-context.md` as a docs-first model for agent invocation and tool authority context: tenant, correlation, workflow, invocation, agent ID/version, task kind, provider/model route ID/version, budget cap, requested tool/mode where applicable, parent invocation, expiry, workload principal/session refs, approval/policy-change refs, safe trace joins, and promotion criteria. No runtime object, contract, signature, schema, seeds, AWS dependency, credentials, production SSO, mutating admin UI, or workflow evidence change was added. |
| 2B-04 | Human approval identity and audit lifecycle | docs-first approval package and audit lifecycle; table/contract only if needed | `git diff --check`; smallest relevant `just` gate | complete | Added `docs/human-approval-audit-lifecycle.md` as a docs-first model that turns `approval_required` into the trigger for a future approval package with approval ID, tenant/correlation/workflow, invocation/tool authority refs, requested action, requested/enforced tool mode, opaque reviewer actor subject ref, reviewer role, decision, SLA/expiry, bounded reason category, policy refs, workload/session refs, and safe trace joins. No approval table, contract, BFF/UI queue, Temporal wait state, production SSO, identity-provider integration, credential entry, mutating admin UI, production connector write, seed, or runtime behaviour change was added. |
| 2B-05 | Governed policy mutation workflow | docs-first policy-change package and lifecycle; proposal table/apply path only if needed | `git diff --check`; smallest relevant `just` gate | complete | Added `docs/policy-change-governance-workflow.md` as a docs-first model for propose/approve/apply/rollback across prompt references, model routes, budget caps, and tool grants. It binds policy change ID, tenant, optional correlation/workflow refs, target policy type, target object refs, before/after version refs, proposer and reviewer actor subject refs, approval ID where required, reason category, eval evidence refs, apply/rollback refs, expiry/SLA, workload/session refs, and safe trace joins. No policy-change table, contract, seed, runtime apply path, production SSO, credential path, credential mutation, production provider call, production connector write, mutating admin UI, raw sensitive content, raw rationale, or PII was added. |
| 2B-06 | Optional LLM observability sidecar evaluation | docs/runbook spike notes; exporter decision | doc review; no hosted dependency required | complete | Added `docs/llm-observability-sidecar-evaluation.md` plus runbook spike notes. The decision is no default sidecar exporter. LangSmith, Langfuse, or similar tools may be opt-in filtered OTel/eval consumers only; Grafana/OTel, Postgres audit, Temporal replay, and `just eval` remain authoritative. No hosted dependency, exporter, SDK, credentials, contracts, schema, seeds, or runtime behaviour changed. |

## Phase 2C Backlog

Phase 2C started with a scope decision before connector code. The chosen
connector is sandbox/protocol-backed, stays behind the Tool Gateway, and
strengthens approval, idempotency, retry, compensation, audit, and safe
projection evidence without enabling production connector writes.

| ID | Required item | Evidence artefact | Gate | Status | Notes |
|---|---|---|---|---|---|
| 2C-00 | Connector expansion and approval-hardening scope ADR | ADR or docs-first scope note; `docs/phase-2-plan.md`; runbook/evidence-map update | doc review; `git diff --check`; smallest relevant `just` gate | complete | ADR 0014 selects a local Radicale/CalDAV calendar connector candidate for Lighthouse follow-up holds. It defines Tool Gateway, approval, idempotency, retry, compensation, projection, audit, eval, runbook, and evidence-map expectations before connector code. No connector code, contracts, sandbox service, production connector writes, credentials, provider calls, hosted dependency, mutating admin UI, runtime mutation path, raw sensitive content, raw prompts/outputs, raw tool arguments, raw approval/policy rationale, identity-provider claims, or PII were added. |
| 2C-01 | Calendar connector contracts and safe samples | `contracts/tools/`; generated models; samples; phase/runbook docs | `just contracts-check`; `git diff --check`; `uv run pytest tests/test_contracts.py` | complete | Added contract-only calendar argument schemas and safe representative samples for `calendar.lookup_availability`, `calendar.propose_hold`, `calendar.create_hold`, and `calendar.cancel_hold`, plus generated Pydantic models and ToolCall enum values. Samples use calendar refs, slot refs, hold refs, event UID refs, participant refs, bounded categories, and timestamps only. No connector runtime code, CalDAV sandbox service, production calendar provider calls, credentials, approval apply paths, runtime mutation paths, eval fixtures, workflow logic, or UI mutation paths were added. |
| 2C-02 | Local CalDAV sandbox and connector behind Tool Gateway | local Radicale or equivalent sandbox; connector module; gateway dispatch; focused connector/gateway tests | focused Tool Gateway/connector tests; `just contracts-check`; `git diff --check` | complete | Added a local Radicale sandbox, `RadicaleCalendarConnector`, Tool Gateway validation/dispatch for the ADR 0014 calendar tool family, seeded read/propose calendar grants, and approval-required create/cancel grants. Availability lookup and hold proposal execute against the local sandbox; writes do not invoke the connector. No approval apply path, production calendar provider, OAuth, credential entry, production connector write, Lighthouse workflow calendar branch, eval fixture, projection, or UI mutation path was added. |
| 2C-03 | Calendar approval package promotion for risky writes | local deterministic approval persistence or package shape only if needed; gateway tests | focused approval and Tool Gateway tests; `just eval` if behaviour changes | complete | Added `approval_packages` as minimal local deterministic persistence for `approval_required` calendar create/cancel writes. The gateway creates a requested package with safe refs and bounded categories only, includes the approval ID in the response/audit summary, and still does not invoke the connector. No reviewer decision path, apply path, workflow branch, UI mutation path, eval fixture, production calendar provider, OAuth, credential entry, or production connector write was added. |
| 2C-04 | Calendar idempotency, retry, and compensation evidence | gateway/connector/workflow code; replay/eval fixtures | focused tests; `just test-replay` if workflow changes; `just eval` | complete | Added a deterministic local approved calendar apply path that re-enters the Tool Gateway, checks approval package state, expiry, grant, idempotency key hash, tenant/correlation/workflow/invocation refs, and safe calendar refs before connector execution. Focused tests prove approved create writes one Radicale VEVENT and idempotent replay returns the persisted response, expired packages block before connector execution, transient connector failure is classified without caching success, cancellation compensation runs through the gateway, compensation failure records an escalation category, and duplicate VEVENT UIDs are idempotent only when the stored safe context matches. No reviewer decision UI, Lighthouse workflow branch, production calendar provider, OAuth, credential entry, production connector write, hosted observability dependency, eval fixture, projection, or mutating admin UI was added. |
| 2C-05 | Calendar projection, audit, runbook, and evidence-map closeout | BFF/UI read-only projection if needed; runbook; evidence map; Phase 2 plan | relevant focused gates; `git diff --check` | complete | Added a read-only BFF calendar status projection derived from `approval_packages` and matching Tool Gateway audit rows. It exposes safe approval/audit refs, calendar refs, projection status categories, retry/compensation/failure categories, grant/policy refs, and safe trace joins only. Runbook, evidence map, implementation plan, architecture/status docs, and Chorus vault handoff records now close out idempotent replay, compensation, and safe audit/projection inspection. No reviewer decision UI, Lighthouse workflow branch, production calendar provider, OAuth, credential entry, production connector write, hosted observability dependency, eval fixture, or mutating admin UI was added. |

## Phase 2D Backlog

Phase 2D should start with a scope decision before adding a second business
workflow. The workflow must reuse the Agent Runtime, Tool Gateway, contracts,
projections, eval, replay, and observability boundaries without introducing a
workflow DSL or replacing Temporal as durable state owner.

ADR 0015 selects a local Support Desk Triage workflow as the second workflow
proof. It is an adjacent operational workflow over support request triage,
severity classification, account/case context lookup, resolution planning,
response/case-update proposal, validation, completion, and escalation. It uses
`support_triage` as the future workflow type, keeps ticketing local-only and
Tool Gateway-mediated, starts future ticket writes as approval-required, and
keeps Lighthouse as the stable Phase 1 demo and regression baseline.

| ID | Required item | Evidence artefact | Gate | Status | Notes |
|---|---|---|---|---|---|
| 2D-00 | Second workflow proof scope ADR | ADR or docs-first scope note; `docs/phase-2-plan.md`; runbook/evidence-map update | doc review; `git diff --check`; smallest relevant `just` gate | complete | ADR 0015 selects Support Desk Triage as the local second workflow proof. It defines non-goals, reuse boundaries, required future contracts, replay/eval expectations, projection/audit/observability surfaces, runbook/evidence-map implications, and Lighthouse baseline protection. No second-workflow runtime code, contracts, migrations, seeds, UI routes, eval fixtures, replay histories, production connectors, reviewer decision UI, credential entry, policy mutation UI, hosted observability dependency, raw sensitive content, raw prompts/outputs, raw tool arguments, raw connector payloads, raw approval or policy rationale, identity-provider claims, attendee names, email addresses, or PII were added. |
| 2D-01 | Support workflow contract baseline and safe samples | `contracts/`; generated models; samples; phase/runbook docs | `just contracts-check`; `git diff --check`; focused contract tests | complete | Added contract-only support request intake and support agent IO schemas, local ticket argument schemas for case lookup, duplicate lookup, case-update proposal, and future approval-required status update, generated Pydantic models, safe samples, ToolCall enum values, support agent-role/decision-trail role values, `support_triage` workflow-event values, and Phase 2D eval contract values. No support workflow runtime code, Temporal activity registrations, migrations, seeds, BFF/UI routes, eval fixtures, replay histories, local ticket connector runtime, production connector providers, reviewer decision UI, credential entry, policy mutation UI, hosted observability dependency, raw sensitive content, raw prompts/outputs, raw tool arguments, raw connector payloads, raw approval or policy rationale, identity-provider claims, attendee names, email addresses, or PII were added. |
| 2D-02 | Local ticket desk sandbox and Tool Gateway dispatch baseline | local ticket connector code; gateway validation/dispatch; grants/seeds if needed; focused tests; runbook/evidence notes | focused Tool Gateway/connector tests; `just contracts-check`; `git diff --check`; persistence gate if migrations/seeds change | complete | Added a Postgres-backed local ticket desk sandbox, support agent/grant seeds, safe local ticket case seeds, Tool Gateway argument validation and connector dispatch for `ticket.lookup_case`, `ticket.lookup_duplicates`, and `ticket.propose_case_update`, plus an approval-required `ticket.update_status` grant that stops before connector execution. Focused tests cover local read/propose dispatch, proposed case-update persistence without case-status mutation, approval-required status update behaviour, and schema validation blocking before connector execution. No Support Temporal workflow runtime, activity registrations, BFF/UI routes, eval fixtures, replay histories, production ticketing providers, credential entry, reviewer decision UI, policy mutation UI, hosted observability dependency, workflow DSL, raw sensitive content, raw prompts/outputs, raw tool arguments, raw connector payloads, raw approval or policy rationale, identity-provider claims, attendee names, email addresses, or PII were added. |
| 2D-03 | Support workflow runtime and replay baseline | code-defined Temporal support workflow; activity registrations; focused replay/history fixture; docs/evidence notes | focused workflow tests; `just test-replay`; `just contracts-check`; `git diff --check`; `just eval` only if eval fixtures change | complete | Added the smallest code-defined `support_triage` Temporal workflow runtime and worker/activity registration needed for a local happy path. The workflow reuses the existing Agent Runtime activity for support classification/context/planning/validation, reuses the Tool Gateway activity for `ticket.lookup_case`, `ticket.lookup_duplicates`, and `ticket.propose_case_update`, records support workflow events with safe subject refs, and never calls `ticket.update_status`. Agent Runtime now validates the 2D-01 support agent contract through the local model boundary. Focused tests and replay history cover the happy path. No Support BFF/UI routes, eval fixtures, production ticketing providers, reviewer decision UI, credential entry, policy mutation UI, hosted observability dependencies, production connector writes, workflow DSL, raw sensitive content, raw prompts/outputs, raw tool arguments, raw connector payloads, raw approval or policy rationale, identity-provider claims, attendee names, email addresses, or PII were added. |
| 2D-04 | Support eval and persisted evidence baseline | support eval fixture; local persisted run/evidence assertions; runbook/evidence notes | focused eval/runtime tests; targeted support eval; `just test-replay`; `just contracts-check`; `git diff --check`; persistence gate | complete | Added the smallest support-specific eval and persisted evidence baseline for the `support_triage` happy path, using only safe refs and bounded categories. The support eval fixture asserts workflow path, final completion, support Agent Runtime decision evidence, ticket lookup/duplicate/proposal Tool Gateway verdicts, proposed case-update refs, no `ticket.update_status` call, no case-status mutation, and safe tenant/correlation/workflow trace joins. A new migration admits support agent roles into persisted decision-trail evidence, and a focused persistence test proves workflow events, support decisions, ticket audit rows, and local proposed case-update refs can be joined while the seeded `ticket.update_status` grant remains approval-required and unexecuted. No Support BFF/UI routes, production ticketing providers, reviewer decision UI, credential entry, policy mutation UI, hosted observability dependencies, production connector writes, ticket status execution, or workflow DSL work were added. |
| 2D-05 | Support read-only inspection path | safe BFF/UI support evidence projection if needed; runbook/evidence notes | focused BFF/UI tests; frontend gates if UI changes; `just contracts-check`; `git diff --check`; relevant persistence/eval checks | open | Add the smallest read-only inspection path for the existing `support_triage` happy-path evidence so a reviewer can inspect safe support workflow events, Agent Runtime decisions, ticket Tool Gateway verdicts, and proposed case-update refs by tenant/correlation/workflow refs. Do not add reviewer decision UI, mutating admin UI, production ticketing providers, credential entry, policy mutation UI, production connector writes, ticket status execution, generic workflow DSL work, or a top-level agent framework replacing Temporal. |

## Phase 2A Work Breakdown

| ID | Required item | Evidence artefact | Gate | Status | Notes |
|---|---|---|---|---|---|
| 2A-01 | Provider catalogue and route-version contract | `contracts/governance/`; generated models; samples; `tests/test_contracts.py` | `just contracts-check` | complete | Provider catalogue and immutable route-version schemas represent the local default path and disabled commercial-provider placeholders without enabling provider adapters or mutating admin. Evidence: `just contracts-check`, `just test`, `just test-replay`, `just lint` on 2026-05-03. |
| 2A-02 | Postgres route-version and provider catalogue migration | `infrastructure/postgres/migrations/`; seeds; `chorus/persistence/projection.py`; `tests/persistence/test_postgres_foundation.py` | `just test-persistence` | complete | Postgres now stores the Phase 2A provider catalogue, disabled commercial-provider placeholder, and immutable route-version rows mirrored from the current Phase 1 local route seeds without changing Lighthouse runtime lookup. Evidence: `just test-persistence`, `just contracts-check`, `just test`, `just lint` on 2026-05-04. |
| 2A-03 | Model adapter interface behind Agent Runtime | `chorus/agent_runtime/`; `tests/agent_runtime/test_runtime.py`; `docs/architecture.md` | `just test` | complete | Agent Runtime now resolves policy, selects a provider-specific model adapter from a registry, and keeps `lighthouse.invoke_agent_runtime` request/response unchanged. Only the local Lighthouse adapter is registered; commercial adapters and fallback execution remain deferred. Evidence: `uv run pytest tests/agent_runtime/test_runtime.py`, `just test`, `just lint` on 2026-05-04. |
| 2A-04 | LangGraph execution engine behind Agent Runtime | `pyproject.toml`; `chorus/agent_runtime/`; `tests/agent_runtime/test_runtime.py`; `docs/architecture.md` | focused tests; `just test`; `just lint` | complete | LangGraph is now a root dependency and the Agent Runtime invokes a compiled graph behind the existing `lighthouse.invoke_agent_runtime` activity. The graph uses `graph.invoke()` without checkpointer persistence and preserves `AgentInvocationRequest`/`AgentInvocationResponse`. The local Lighthouse adapter remains the only runnable model path. Evidence: `uv run pytest tests/agent_runtime/test_runtime.py`, `just test`, `just lint`, `just contracts-check`, `just test-replay` on 2026-05-07. |
| 2A-05 | Decision-trail evidence for graph execution | `chorus/agent_runtime/`; persistence projection if needed; eval fixture expectations if changed | focused tests; `just eval` | complete | Agent Runtime now writes execution engine, graph version, graph path, and graph path summary into `decision_trail_entries.metadata` alongside OTel IDs. `AgentInvocationRecord` remains the audit contract; LangGraph metadata is execution evidence, not the source of truth. Evidence: `uv run pytest tests/agent_runtime/test_runtime.py`, `just test`, `just lint-python`, `just eval`, and `just contracts-check` on 2026-05-07. |
| 2A-06 | Disabled-by-default commercial provider adapter | `chorus/agent_runtime/`; `tests/agent_runtime/test_runtime.py` | focused tests; `just eval` | complete | The default registry now includes a `commercial.example` adapter boundary that performs no production provider calls and remains disabled by default. If policy selects it without credentials, the LangGraph-backed path records provider-disabled metadata in the failed decision-trail entry. Evidence: `uv run pytest tests/agent_runtime/test_runtime.py`, `just test`, `just lint-python`, `just eval`, and `just contracts-check` on 2026-05-07. |
| 2A-07 | Provider failure and fallback fixture | `chorus/agent_runtime/`; `chorus/eval/`; `tests/agent_runtime/test_runtime.py`; `tests/eval/test_run.py` | focused tests; `just eval` | complete | Runtime fallback is policy-gated: the failed primary provider attempt is recorded, then the configured local fallback route runs through the same LangGraph graph with a new invocation ID. The eval fixture proves provider failure is visible, not swallowed. Evidence: `uv run pytest tests/agent_runtime/test_runtime.py tests/eval/test_run.py`, `uv run python -m chorus.eval.run --fixture chorus/eval/fixtures/lighthouse_provider_fallback.json`, `just contracts-gen`, `just contracts-check`, `just test`, `just test-replay`, `just eval`, `just lint-python`, and `git diff --check` on 2026-05-07. |
| 2A-08 | Decision-trail and audit evidence for route selection | persistence schema/runtime writes/UI projection | `just test`; `just test-frontend` | complete | Runtime resolution now joins approved immutable route-version metadata where available and records route ID, route version, provider catalogue, selected provider/model, fallback reason, cost, and latency into `decision_trail_entries.metadata`. The BFF decision-trail projection exposes provider/model, route version, and fallback state, and the UI decision tables show route version and fallback reason. Evidence: `uv run pytest tests/agent_runtime/test_runtime.py tests/bff/test_app_unit.py tests/bff/test_app.py tests/eval/test_run.py`, `uv run python -m chorus.eval.run --fixture chorus/eval/fixtures/lighthouse_provider_fallback.json`, `just test-frontend`, and Playwright fixture validation on 2026-05-07. |
| 2A-09 | Read-only BFF/UI provider and graph-execution views | `chorus/bff/`; `frontend/` | `just test-frontend`; `just test-e2e` | complete | The BFF exposes provider catalogue, provider model, immutable route-version, and graph-execution read endpoints. The UI adds dense read-only provider and graph-execution tables plus per-workflow graph evidence. Evidence: `uv run pytest tests/bff/test_app_unit.py tests/bff/test_app.py` (unit passed; Postgres-backed tests skipped locally when Postgres was unavailable), `npm --prefix frontend run build`, `just test-frontend`, `just test-e2e`, Playwright CLI browser validation, `just lint`, and `git diff --check` on 2026-05-08. |
| 2A-10 | Docs/runbook/evidence alignment | `README.md`; `docs/*`; ADRs | doc review; relevant gates | complete | README, architecture, governance guardrails, implementation plan, evidence map, and runbook now align on implemented Phase 2A evidence. The runbook includes provider catalogue, route-version, graph execution, disabled-provider, and provider-fallback inspection procedures. The docs state that disabled commercial routes, provider credentials, mutating admin controls, production commercial provider calls, and LangGraph durability are not implemented. Evidence: `just contracts-check`, `just lint`, `just test-frontend`, and `git diff --check` on 2026-05-08. |
| 2A-11 | Provider timeout, rate-limit, and budget degradation fixtures | `chorus/agent_runtime/`; `chorus/eval/`; `tests/agent_runtime/`; `tests/eval/`; docs if evidence surfaces change | focused tests; `just eval`; relevant replay if workflow behaviour changes | complete | Runtime fallback now covers provider timeout and rate-limit reasons from local fixture adapters, and Agent Runtime enforces route budget caps after adapter execution so budget-exceeded decisions are recorded before policy-gated local fallback. Added three Phase 2A eval fixtures. Evidence: `uv run pytest tests/agent_runtime/test_runtime.py tests/eval/test_run.py`, targeted provider-degradation eval fixture run, `just contracts-check`, `just eval`, and `git diff --check` on 2026-05-14. Replay was not run because no Temporal workflow logic changed. |

## Phase 2A Evidence Notes

- 2026-05-03: `2A-01` added `contracts/governance/provider_catalogue.schema.json`
  and `contracts/governance/model_route_version.schema.json`, representative
  samples, generated Pydantic models, and contract tests. The sample catalogue
  keeps `local/lighthouse-happy-path-v1` as the approved runnable path and uses
  a disabled commercial placeholder to prove credential and lifecycle metadata
  without implying an active adapter.
- 2026-05-03: Gates passed for `2A-01`: `just contracts-gen`,
  `just contracts-check`, `just test`, `just test-replay`, and `just lint`.
- 2026-05-04: `2A-02` added Postgres provider-governance tables:
  `provider_catalogues`, `provider_catalogue_providers`,
  `provider_catalogue_models`, and tenant-scoped immutable
  `model_route_versions`. The seed mirrors existing `model_routing_policies`
  rows for `local/lighthouse-happy-path-v1` into route version `1`, preserves
  the Phase 1 runtime lookup table unchanged, and keeps the commercial provider
  placeholder disabled with no adapter path.
- 2026-05-04: Gates passed for `2A-02`: `just test-persistence`,
  `just contracts-check`, `just test`, and `just lint`.
- 2026-05-04: `2A-03` introduced a typed Agent Runtime model-adapter
  interface, provider-keyed adapter registry, default local adapter registry,
  and runtime-store protocol for focused unit coverage. The stable Temporal
  activity boundary still accepts `AgentInvocationRequest` and returns
  `AgentInvocationResponse`; commercial provider adapters, disabled-provider
  handling, and fallback execution are not implemented by this item.
- 2026-05-04: Gates passed for `2A-03`: `uv run pytest
  tests/agent_runtime/test_runtime.py`, `just test`, and `just lint`.
- 2026-05-07: ADR 0012 pivoted Phase 2A to add LangGraph as the first-class
  agent execution engine inside Agent Runtime before continuing commercial
  provider adapters. The completed provider catalogue and model-adapter
  registry remain the policy/model boundary the graph should use.
- 2026-05-07: `2A-04` added `langgraph` as a Python dependency and introduced
  a compiled `LangGraphAgentExecutionEngine` inside `chorus.agent_runtime`.
  `AgentRuntime.invoke()` still sits behind the existing
  `lighthouse.invoke_agent_runtime` Temporal activity, keeps
  `AgentInvocationRequest` and `AgentInvocationResponse` unchanged, and calls
  the existing provider-keyed adapter registry from the graph node
  `invoke_model_adapter`. The first graph path is `prepare_context ->
  invoke_model_adapter -> normalise_result -> validate_contract ->
  final_response`; it uses `graph.invoke()` without LangGraph checkpoint
  persistence, durable execution, interrupts, long-term memory, LangGraph
  deployment, or LangSmith integration. The local
  `lighthouse-happy-path-v1` adapter remains the only runnable model path.
- 2026-05-07: Gates passed for `2A-04`: `uv run pytest
  tests/agent_runtime/test_runtime.py`, `just test`, `just lint`,
  `just contracts-check`, and `just test-replay`. The pytest and replay runs
  emitted an upstream LangGraph/LangChain pending-deprecation warning from
  `langgraph.cache.base`; no Chorus tests failed.
- 2026-05-07: `2A-05` added graph execution metadata to the Agent Runtime
  decision-trail write path. Successful invocations persist
  `agent_execution.engine`, `agent_execution.graph_version`,
  `agent_execution.graph_path`, and `agent_execution.graph_path_summary` in
  `decision_trail_entries.metadata`; failed invocations before graph completion
  still persist engine and graph version with an empty path. The generated
  `AgentInvocationRecord` schema and the stable `AgentInvocationRequest` /
  `AgentInvocationResponse` activity contract are unchanged.
- 2026-05-07: Gates passed for `2A-05`: `uv run pytest
  tests/agent_runtime/test_runtime.py`, `just test`, `just lint-python`,
  `just eval`, and `just contracts-check`. `just eval` skipped only the
  optional live persisted evidence assertion because no
  `CHORUS_EVAL_CORRELATION_ID` or workflow ID was supplied. The pytest runs
  emitted the upstream LangGraph/LangChain pending-deprecation warning from
  `langgraph.cache.base`; no Chorus tests failed.
- 2026-05-07: `2A-06` registered a disabled-by-default
  `CommercialExampleModelAdapter` behind the LangGraph-backed Agent Runtime.
  The adapter is keyed by `commercial.example`, requires no credentials for
  local Lighthouse runs, performs no production provider calls, and keeps the
  local `lighthouse-happy-path-v1` adapter as the only runnable model path.
  When routing policy selects `commercial.example/commercial-reasoner-v1`
  without `CHORUS_COMMERCIAL_LLM_API_KEY`, the runtime records a failed
  `AgentInvocationRecord` plus `decision_trail_entries.metadata` showing
  `provider_boundary.state=disabled`,
  `provider_boundary.reason=missing_credentials`, the required secret ref, and
  the LangGraph path `prepare_context -> invoke_model_adapter`.
- 2026-05-07: Gates passed for `2A-06`: `uv run pytest
  tests/agent_runtime/test_runtime.py`, `just test`, `just lint-python`,
  `just eval`, and `just contracts-check`. The focused pytest run skipped
  Postgres-backed tests when local Postgres was unavailable; `just test` later
  exercised the suite through its configured gate. `just eval` skipped only the
  optional live persisted evidence assertion because no
  `CHORUS_EVAL_CORRELATION_ID` or workflow ID was supplied. The pytest runs
  emitted the upstream LangGraph/LangChain pending-deprecation warning from
  `langgraph.cache.base`; no Chorus tests failed.
- 2026-05-07: `2A-07` added policy-gated provider fallback inside the
  LangGraph-backed Agent Runtime. A provider invocation failure records a
  failed primary decision with provider-failure metadata and the graph path
  through `prepare_context -> invoke_model_adapter`. If
  `fallback_policy.on_provider_error=fallback_route`, the runtime invokes the
  configured local fallback route through the same graph with a new invocation
  ID and records a second, successful decision with fallback metadata. The
  default local Lighthouse adapter remains the only production-runnable path,
  and no commercial provider calls or credential requirements were added.
- 2026-05-07: `2A-07` added
  `chorus/eval/fixtures/lighthouse_provider_fallback.json` plus eval-runner
  assertions for a failed `commercial.example/commercial-reasoner-v1` drafter
  decision followed by a successful `local/lighthouse-happy-path-v1` fallback
  decision. `contracts/eval/eval_fixture.schema.json` now allows Phase `2A`
  fixtures and the generated eval model was refreshed.
- 2026-05-07: `2A-08` added route-selection evidence without changing
  `AgentInvocationRequest`, `AgentInvocationResponse`, Temporal workflow
  ownership, or Tool Gateway authority. `AgentRuntimeStore.resolve()` now joins
  `model_route_versions` when the selected policy matches an approved immutable
  route version. Each decision-trail metadata row records route ID/version,
  provider catalogue, selection source, selected provider/model, task kind,
  budget, fallback reason, observed cost, and observed latency. The BFF
  decision-trail API projects provider/model, route version, fallback reason,
  and fallback-applied state; the frontend decision tables display route
  version and fallback reason. The provider-fallback eval check now names route
  selection and asserts cost/latency evidence on the failed primary and
  succeeding fallback decisions.
- 2026-05-08: `2A-09` exposed Phase 2A provider governance and LangGraph
  execution evidence through read-only BFF/UI surfaces. New BFF endpoints
  project provider catalogue rows, provider model declarations, immutable route
  versions, all graph executions, and per-workflow graph executions from
  existing Postgres read models and decision-trail metadata. The frontend adds
  read-only `Providers` and `Graph executions` inspection routes and includes
  graph execution evidence in workflow details. No mutating admin controls,
  credential entry, production provider calls, LangGraph durability, or new
  workflow paths were added.
- 2026-05-08: `2A-10` aligned README, architecture, governance guardrails,
  implementation plan, evidence map, and runbook with the implemented Phase 2A
  state. The runbook now documents BFF provider/graph endpoints, SQL inspection
  for provider catalogue, provider models, immutable route versions, graph
  execution metadata, disabled-provider metadata, and provider-fallback
  decisions. The aligned docs explicitly avoid presenting disabled commercial
  routes, provider credentials, mutating admin controls, production commercial
  provider calls, or LangGraph durability as implemented.
- 2026-05-14: `2A-11` extended provider degradation evidence beyond the
  original provider-error fallback fixture. `ProviderInvocationError` reason
  values now cover timeout and rate-limit fallback paths. Agent Runtime also
  enforces route budget caps after adapter execution, records
  `provider_budget.*` decision metadata on budget-exceeded attempts, and uses
  the same policy-gated local fallback path where allowed. New eval fixtures
  prove timeout, rate-limit, and budget-exceeded fallback evidence without
  production provider calls, credential entry, mutating provider admin,
  LangGraph checkpoint persistence, or LangGraph durable execution.
- 2026-05-14: Gates passed for `2A-11`: `uv run pytest
  tests/agent_runtime/test_runtime.py tests/eval/test_run.py`, targeted
  provider-degradation eval fixture run, `just contracts-check`, `just eval`,
  `just lint-python`, `just test-frontend`, and `git diff --check`. The
  focused pytest run skipped Postgres-backed tests where local Postgres was
  unavailable and emitted the upstream LangGraph/LangChain
  pending-deprecation warning from `langgraph.cache.base`; no Chorus tests
  failed. Replay was not run because no Temporal workflow logic changed.
- Phase 2A is complete. Phase 2B has completed `2B-00` through `2B-06`.

## Phase 2B Evidence Notes

- 2026-05-14: `2B-00` added ADR 0013 for identity, authority, observability,
  user-journey evidence, and audit boundaries. The ADR defines human,
  workload, agent, invocation, approval, and policy actors; separates workload
  authentication from Chorus business authority; preserves future AWS IAM role,
  STS session, IAM Roles Anywhere, and session-tag mapping without a local AWS
  dependency; separates infrastructure telemetry, application/user journey
  evidence, audit/accountability, and optional LLM observability sidecars; and
  states context-hygiene rules for trace headers and baggage. Architecture,
  implementation plan, evidence map, phase plan, and Chorus vault project
  records were aligned. No AWS implementation, production SSO, hosted
  observability dependency, credential entry, or mutating runtime admin was
  added.
- 2026-05-14: `2B-01` added a docs-first observability and user-journey data
  model in `docs/observability-user-journey-model.md`. It defines field
  placement for OTel resource attributes, span attributes, and propagated
  baggage; states a strict baggage allow-list; sketches future
  `actor_sessions` and `journey_events` projection records plus BFF/UI journey
  views; separates audit-only invocation, prompt/output, tool, approval,
  policy mutation, and trace-join field families; and names future identifiers
  including `workload_principal_id`, `workload_session_id`,
  `actor_session_id`, `approval_id`, `policy_change_id`,
  `authority_context_id`, and `fixture_run_id`. Architecture, runbook,
  implementation plan, evidence map, phase plan, and Chorus vault continuation
  records were aligned. No contracts, code, AWS implementation, production
  SSO, hosted observability dependency, credential entry, or mutating runtime
  admin was added.
- 2026-05-14: `2B-02` added
  `docs/workload-principal-model.md` as a docs-first workload identity model.
  It sketches `workload_principals`, `workload_sessions`, and optional future
  `workload_principal_aws_mappings` records; defines local trust domains,
  tenant-scope rules, safe OTel resource-attribute placement, and a
  Compose-service principal catalogue for the current local stack; and reserves
  nullable future metadata for IAM role ARN, STS session name and tag keys, IAM
  Roles Anywhere profile/trust-anchor/certificate-subject refs, SPIFFE ID, and
  external identity-provider refs. Architecture, evidence map, the 2B-01 field
  placement model, Phase 2 plan, and Chorus vault continuation records were
  aligned. No Postgres migration, seed, contract, AWS dependency, production
  SSO, cloud deployment, credentials, credential-entry UI, or runtime behaviour
  change was added.
- 2026-05-14: `2B-03` added
  `docs/invocation-authority-context.md` as a docs-first invocation-authority
  model. It sketches future `invocation_authority_context` and
  `tool_authority_context` shapes; binds tenant, correlation, workflow,
  invocation, agent ID/version, task kind, prompt reference/hash, provider,
  model, route ID/version, budget cap, requested tool/mode, parent invocation,
  expiry, workload principal/session refs, approval/policy-change refs, and
  safe trace joins; defines lifecycle and telemetry/projection/audit placement
  rules; and names promotion criteria for a local deterministic object,
  service-boundary contract, or signed envelope. Architecture, evidence map,
  implementation plan, the 2B-01/2B-02 companion docs, Phase 2 plan, and Chorus
  vault continuation records were aligned. No runtime object, contract,
  signature mechanism, Postgres migration, seed, AWS dependency, production
  SSO, cloud deployment, credentials, credential-entry UI, mutating admin UI,
  raw sensitive content, or workflow behaviour change was added.
- 2026-05-17: `2B-04` added
  `docs/human-approval-audit-lifecycle.md` as a docs-first approval identity
  and audit lifecycle model. It turns the current Tool Gateway
  `approval_required` verdict into the trigger for a future approval package
  with approval ID, tenant, correlation, workflow, invocation/tool authority
  refs, requested action, requested and enforced tool mode, opaque reviewer
  actor subject ref, reviewer role, decision, SLA/expiry, bounded reason
  category, policy refs, workload/session refs, and safe trace joins. It also
  defines append-only approval audit lifecycle events and promotion criteria
  for a future local deterministic implementation. Architecture, observability
  model, invocation-authority model, implementation plan, evidence map, README,
  Phase 2 plan, and Chorus vault continuation records were aligned. No
  approval table, contract, BFF/UI queue, Temporal wait state, Tool Gateway
  runtime change, eval fixture, AWS dependency, production SSO, cloud
  deployment, identity-provider integration, credential entry, mutating admin
  UI, production connector write, seed, raw sensitive content, raw rationale,
  or PII was added.
- 2026-05-17: `2B-05` added
  `docs/policy-change-governance-workflow.md` as a docs-first governed policy
  mutation model. It defines the future policy-change package and append-only
  lifecycle for prompt references, model routes, budget caps, and tool grants:
  propose, attach eval evidence, review/approve, apply, observe, roll back,
  expire, and supersede. The package binds policy change ID, tenant, optional
  correlation/workflow refs, target policy type, target object refs,
  before/after version refs, proposer and reviewer actor subject refs,
  approval ID where required, bounded reason category, eval evidence refs,
  apply/rollback refs, expiry/SLA, workload/session refs, and safe trace joins.
  It also states target-specific apply and rollback semantics for existing
  `agent_registry`, `model_routing_policies`, `model_route_versions`, and
  `tool_grants` policy surfaces. README, architecture, observability model,
  invocation-authority model, human-approval model, implementation plan,
  evidence map, Phase 2 plan, and Chorus vault continuation records were
  aligned. No policy-change table, contract, seed, runtime apply service,
  Tool Gateway behaviour change, eval fixture, AWS dependency, production SSO,
  cloud deployment, identity-provider integration, credential entry,
  credential mutation, production provider call, production connector write,
  mutating admin UI, raw sensitive content, raw rationale, or PII was added.
- 2026-05-17: `2B-06` added
  `docs/llm-observability-sidecar-evaluation.md` and runbook spike notes for
  optional LangSmith, Langfuse, or similar tooling. The exporter decision is
  no default sidecar exporter. A future sidecar may only be an opt-in filtered
  OTel/eval consumer for debugging, annotation, graph inspection, and
  experiment comparison. The model binds allowed resource, span, trace, eval,
  and join fields; forbidden raw data; safe trace/eval joins; retention and
  sampling assumptions; local Grafana/Postgres/eval authority; and promotion
  criteria. README, overview, architecture, observability model,
  implementation plan, evidence map, Phase 2 plan, runbook, and Chorus vault
  continuation records were aligned. No exporter, SDK, hosted observability
  dependency, credential path, contract, Postgres migration, seed, production
  provider call, production connector write, mutating admin UI, raw prompts or
  outputs, raw tool arguments, raw approval or policy rationale,
  identity-provider claims, PII, or runtime behaviour change was added.

## Phase 2C Evidence Notes

- 2026-05-17: `2C-00` added
  `adrs/0014-connector-expansion-approval-hardening-scope.md` as the Phase 2C
  connector-expansion scope decision. ADR 0014 selects a local Radicale/CalDAV
  calendar connector candidate for Lighthouse follow-up holds and defines the
  Tool Gateway, approval, idempotency, retry, compensation, projection, audit,
  eval, runbook, and evidence-map expectations before connector code. The ADR
  scopes availability lookup, hold proposal, hold creation, and hold
  cancellation as local-only CalDAV actions and keeps production calendar
  providers, OAuth, production SSO, credential entry, credential mutation,
  production connector writes, production provider calls, hosted observability
  dependencies, runtime mutation paths, mutating admin UI, raw sensitive
  content, raw prompts/outputs, raw tool arguments, raw approval or policy
  rationale, identity-provider claims, and PII out of scope. ADR index,
  architecture, evidence map, runbook, Phase 2 plan, and Chorus vault
  continuation records were aligned. No connector code, contracts, sandbox
  service, exporter, SDK, Postgres migration, seeds, runtime behaviour, eval
  fixtures, workflow logic, approval apply path, or UI implementation changed.
- 2026-05-18: `2C-01` added contract-only calendar connector argument schemas
  and safe representative samples for the ADR 0014 local CalDAV tool family:
  `calendar_availability_lookup_args`, `calendar_hold_proposal_args`,
  `calendar_hold_creation_args`, and `calendar_hold_cancellation_args`. The
  `ToolCall` tool-name enum now includes `calendar.lookup_availability`,
  `calendar.propose_hold`, `calendar.create_hold`, and
  `calendar.cancel_hold`; generated Pydantic models were refreshed and focused
  contract tests validate the new samples. The samples are ref-based and
  bounded: calendar refs, slot refs, hold refs, event UID refs, participant
  refs, policy/note/compensation refs, timestamps, and reason/status
  categories only. No connector runtime code, Radicale/CalDAV service,
  production calendar provider call, credential path, production provider call,
  approval apply path, runtime mutation path, eval fixture, workflow logic, UI
  mutation path, raw sensitive content, raw prompts/outputs, raw tool
  arguments, raw approval or policy rationale, identity-provider claims, or PII
  was added.
- 2026-05-18: `2C-02` added a local-only Radicale CalDAV sandbox and a
  contract-faithful calendar connector behind Tool Gateway dispatch. The
  local stack now includes `radicale` backed by
  `infrastructure/radicale/config` and anonymous local rights, and
  `chorus.connectors.calendar.RadicaleCalendarConnector` performs CalDAV/WebDAV
  availability lookup, hold proposal, hold creation, and hold cancellation
  using only safe refs and bounded categories. The Tool Gateway validates the
  2C-01 calendar argument contracts, dispatches read/propose actions to the
  connector after grant/mode/idempotency checks, and keeps create/cancel write
  grants `approval_required` so writes do not invoke the connector. Seeded
  grants, runbook inspection commands, evidence-map links, focused connector
  tests, and local sandbox inspection recipes were added. No approval apply
  path, executable approval package, production calendar provider, OAuth,
  credential entry, production connector write, Lighthouse workflow calendar
  branch, eval fixture, projection, UI mutation path, hosted observability
  dependency, raw sensitive content, raw prompts/outputs, raw connector
  payload, raw approval or policy rationale, identity-provider claims, attendee
  names, email addresses, or PII was added.
- 2026-05-18: `2C-03` added minimal local deterministic approval package
  persistence for approval-required calendar writes. The new
  `approval_packages` table records `requested` packages for
  `calendar.create_hold` and `calendar.cancel_hold` with approval ID,
  tenant/correlation/workflow refs, invocation/tool/verdict/source-audit refs,
  tool name, requested action, requested/enforced mode, idempotency key hash,
  redaction summary, SLA/expiry refs, grant/policy refs, nullable
  workload/session refs, and safe trace joins. The Tool Gateway creates the
  package only after the approval-required verdict and source audit row are
  built, includes the approval ID in the safe gateway response/audit summary,
  and still does not invoke the connector for calendar writes. Focused gateway
  tests cover package creation, idempotent replay, cancellation packages, and
  CRM approval staying package-free. No reviewer decision path, approval apply
  path, BFF/UI queue, mutating admin UI, Lighthouse workflow calendar branch,
  eval fixture, production calendar provider, OAuth, credential entry,
  production connector write, hosted observability dependency, raw sensitive
  content, raw prompts/outputs, raw tool arguments, raw connector payload, raw
  approval or policy rationale, identity-provider claims, attendee names, email
  addresses, or PII was added.
- 2026-05-18: `2C-04` added local-only calendar write evidence through the
  Tool Gateway. `ToolGateway.apply_approved_calendar_write()` consumes an
  already approved local calendar approval package, derives a deterministic
  apply idempotency key, re-checks package state, expiry, grant state,
  original idempotency key hash, tenant/correlation/workflow/invocation refs,
  agent/tool/mode refs, and package-bound safe calendar refs, then invokes the
  Radicale connector only from the gateway. The Radicale connector now treats a
  duplicate VEVENT UID as idempotent success only when the stored safe
  calendar/hold/slot/event/meeting/participant refs match; mismatched duplicate
  UIDs are blocked with a bounded failure category. Focused tests prove
  approved create writes one local VEVENT and replay returns the persisted
  gateway response, expired approval packages block before connector
  execution, transient connector failures are retry-classified without caching
  success, cancellation compensation runs through `calendar.cancel_hold` via
  the gateway, and failed compensation records a bounded escalation category.
  No reviewer decision path, reviewer UI, Lighthouse workflow calendar branch,
  eval fixture, projection, production calendar provider, OAuth, credential
  entry, production connector write, hosted observability dependency, raw
  sensitive content, raw prompts/outputs, raw tool arguments, raw connector
  payload, raw approval or policy rationale, identity-provider claims, attendee
  names, email addresses, or PII was added.
- 2026-05-18: `2C-05` added safe read-only calendar status projection and
  closed out the runbook/evidence-map inspection path. `ProjectionStore` now
  derives `CalendarProjectionReadModel` rows from local `approval_packages` and
  matching `tool_action_audit` apply rows, and the BFF exposes
  `/api/calendar/status` plus `/api/workflows/{workflow_id}/calendar/status`.
  The projection contains only approval/package refs, tenant/correlation/
  workflow refs, tool name, requested/enforced mode, idempotency key ref,
  slot/hold/event UID refs, approval state, grant/policy refs,
  retry/compensation/failure categories, bounded projection status categories,
  and safe trace joins. It does not expose raw event bodies, raw tool
  arguments, raw connector payloads, raw approval or policy rationale,
  attendee names, email addresses, identity-provider claims, credentials, API
  keys, access tokens, or PII. Runbook and evidence-map notes now document
  idempotent replay, compensation, safe audit inspection, and BFF projection
  inspection. No reviewer decision UI, Lighthouse workflow calendar branch,
  production calendar provider, OAuth, credential entry, production connector
  write, hosted observability dependency, eval fixture, or mutating admin UI
  was added.

## Phase 2D Evidence Notes

- 2026-05-18: `2D-00` added
  `adrs/0015-second-workflow-proof-scope.md` as the Phase 2D second-workflow
  scope decision. ADR 0015 selects a local Support Desk Triage workflow using
  future workflow type `support_triage`. The scope covers support request
  intake, classification/severity triage, account or case context lookup,
  resolution planning, response and case-update proposal, validation,
  completion, and escalation. The decision keeps the workflow code-defined in
  Temporal, places LangGraph inside Agent Runtime, keeps all support ticket
  actions behind the Tool Gateway, uses local-only ticketing expectations, and
  requires future contracts, replay/eval fixtures, projections, audit,
  observability, runbook, and evidence-map updates before runtime delivery.
  Lighthouse remains the stable Phase 1 demo and regression baseline. No
  second-workflow runtime code, contracts, migrations, seeds, BFF/UI routes,
  eval fixtures, replay histories, production connector providers, reviewer
  decision UI, credential entry, policy mutation UI, hosted observability
  dependency, raw sensitive content, raw prompts/outputs, raw tool arguments,
  raw connector payloads, raw approval or policy rationale, identity-provider
  claims, attendee names, email addresses, or PII was added.
- 2026-05-18: `2D-01` added the contract-only Support Desk Triage baseline.
  New schemas and safe samples cover support request intake, support agent IO,
  ticket case lookup, duplicate-case lookup, case-update proposal, and a future
  approval-required ticket status update. The `ToolCall` contract now includes
  ticket tool names, `AgentInvocationRecord` recognises support agent roles,
  `WorkflowEvent` can carry optional `workflow_type=support_triage`,
  support-specific step categories, and safe subject refs, and the eval fixture
  contract recognises Phase `2D` and `support_triage` as future contract
  values. Generated Pydantic models and focused contract tests were refreshed.
  Samples use only request refs, case refs, account refs, product refs,
  severity/status categories, idempotency refs, tenant/correlation/workflow
  refs, agent/tool refs, policy refs, and bounded verdict categories. No
  support workflow runtime code, Temporal activity registrations, migrations,
  seeds, BFF/UI routes, eval fixtures, replay histories, local ticket connector
  runtime, production connector providers, reviewer decision UI, credential
  entry, policy mutation UI, hosted observability dependency, raw sensitive
  content, raw prompts/outputs, raw tool arguments, raw connector payloads, raw
  approval or policy rationale, identity-provider claims, attendee names, email
  addresses, or PII was added.
- 2026-05-18: `2D-02` added the local-only ticket desk sandbox behind the Tool
  Gateway. `chorus.connectors.ticket.LocalTicketDeskConnector` stores and reads
  safe ticket case refs and proposed case-update refs in Postgres tables added
  by `007_local_ticket_desk_sandbox.sql`; demo seeds add support context and
  resolution-planner agents, read/propose ticket grants, an approval-required
  `ticket.update_status` write grant, and safe local ticket case refs. The Tool
  Gateway now validates all four 2D-01 ticket argument contracts, dispatches
  `ticket.lookup_case`, `ticket.lookup_duplicates`, and
  `ticket.propose_case_update` to the local connector when grants allow them,
  persists proposed case-update refs without mutating case status, and still
  stops `ticket.update_status` at `approval_required` before connector
  execution. Focused tests cover ticket lookup, duplicate lookup, proposal
  persistence, approval-required status updates, and schema validation blocking
  before connector execution. No Support Temporal workflow runtime, Temporal
  activity registrations, BFF/UI routes, eval fixtures, replay histories,
  production ticketing providers, reviewer decision UI, credential entry,
  policy mutation UI, hosted observability dependency, workflow DSL, raw
  sensitive content, raw prompts/outputs, raw tool arguments, raw connector
  payloads, raw approval or policy rationale, identity-provider claims,
  attendee names, email addresses, or PII was added.
- 2026-05-19: `2D-03` added the smallest code-defined Support Desk Triage
  runtime and replay baseline. `chorus.workflows.support.SupportTriageWorkflow`
  is registered by the worker alongside Lighthouse and calls the existing
  `lighthouse.invoke_agent_runtime` and `lighthouse.invoke_tool_gateway`
  activity boundaries for support classification, context lookup, resolution
  planning, validation, ticket case lookup, duplicate lookup, and proposed
  case-update dispatch. A support-specific workflow-event activity records
  safe `support_triage` events with request refs, subject refs, bounded step
  categories, and safe payload categories only. `chorus.agent_runtime` now
  validates `contracts/agents/support_agent_io.schema.json` through the local
  structured boundary and support model-route seeds; provider route-version
  evidence remains Lighthouse-only for this item. The workflow never calls
  `ticket.update_status`, and the seeded status update grant remains
  `approval_required` with no connector execution. Focused support workflow,
  activity, Agent Runtime, replay, contract, and persistence gates cover the
  runtime baseline and the new safe replay fixture
  `tests/workflows/fixtures/support_triage_happy_history.json`. No Support
  BFF/UI routes, eval fixtures, production ticketing providers, reviewer
  decision UI, credential entry, policy mutation UI, hosted observability
  dependencies, production connector writes, workflow DSL, raw sensitive
  content, raw prompts/outputs, raw tool arguments, raw connector payloads,
  raw approval or policy rationale, identity-provider claims, attendee names,
  email addresses, or PII were added.
- 2026-05-19: `2D-04` added the support eval and persisted evidence baseline
  for the existing `support_triage` happy path. The eval fixture
  `chorus/eval/fixtures/support_triage_happy_path.json` asserts the support
  path, final completion, support Agent Runtime decisions, ticket lookup,
  duplicate lookup, proposed case-update Tool Gateway verdicts, proposed
  `caseupd_support_001`, no `ticket.update_status` call, no case-status
  mutation, and safe tenant/correlation/workflow joins. The eval runner can
  also target persisted support evidence by workflow ID or correlation ID.
  Migration `009_support_eval_persisted_evidence_baseline.sql` aligns
  `decision_trail_entries` with support agent roles, and the focused
  persistence test proves workflow events, support decisions, ticket audit
  rows, and local proposed case-update refs can be joined using safe refs.
  `ticket.update_status` remains approval-required with no connector
  execution. No Support BFF/UI routes, production ticketing providers,
  reviewer decision UI, credential entry, policy mutation UI, hosted
  observability dependencies, production connector writes, ticket status
  execution, workflow DSL, raw sensitive content, raw prompts/outputs, raw
  tool arguments, raw connector payloads, raw approval or policy rationale,
  identity-provider claims, attendee names, email addresses, or PII were
  added.

## Current Handoff - 2026-05-19

Status:

- `2A-11` through `2C-05` are complete.
- `2D-00` is complete.
- `2D-01` is complete.
- `2D-02` is complete.
- `2D-03` is complete.
- `2D-04` is complete.
- Next ledger item: `2D-05` Support read-only inspection path.

Evidence added:

- `chorus/eval/fixtures/support_triage_happy_path.json` adds the support
  happy-path eval fixture with safe refs and bounded categories only.
- `chorus/eval/run.py` now has support-specific offline and optional live
  persisted evidence checks. It proves support workflow path, final completion,
  Agent Runtime decisions, ticket Tool Gateway verdicts, proposed
  case-update refs, no `ticket.update_status` action, no case-status mutation,
  and tenant/correlation/workflow trace joins.
- `infrastructure/postgres/migrations/009_support_eval_persisted_evidence_baseline.sql`
  admits support agent roles into `decision_trail_entries` so support runtime
  decisions can persist.
- `tests/eval/test_run.py` covers the support eval fixture.
- `tests/persistence/test_postgres_foundation.py` adds a persisted support
  evidence baseline that joins workflow events, support decisions, ticket
  audit rows, and the local proposed case-update row by safe refs while
  keeping `ticket.update_status` approval-required and unexecuted.
- Runbook, evidence map, implementation plan, architecture/status docs, and
  Chorus vault continuation records now point at `2D-05` while keeping the
  repo as the active source of truth.

Commands run:

- `python -m py_compile chorus/eval/run.py tests/eval/test_run.py tests/persistence/test_postgres_foundation.py`
- `uv run ruff check chorus/eval/run.py tests/eval/test_run.py tests/persistence/test_postgres_foundation.py`
- `uv run python -m chorus.eval.run --fixture chorus/eval/fixtures/support_triage_happy_path.json`
- `uv run pytest tests/eval/test_run.py -q`
- `uv run pytest tests/agent_runtime/test_runtime.py -k support -q`
- `uv run pytest tests/workflows/test_support_workflow.py -q`
- `uv run pytest tests/persistence/test_postgres_foundation.py -k support_eval_persisted_evidence -q`
- `just contracts-check`
- `just test-replay`
- `just test-persistence`
- `just eval`
- `git diff --check`
- `git -C /home/ryan/Work/vault diff --check -- records/radianit/projects/chorus/README.md records/radianit/projects/chorus/handoff-prompt.md records/radianit/projects/chorus/implementation-plan.md records/radianit/projects/chorus/learning/open-questions-phase-2.md`

Skipped gates:

- BFF/UI/frontend gates were skipped because no Support BFF route, UI route,
  or frontend code changed.
- Tool Gateway/connector-focused gates were skipped because 2D-04 did not
  change gateway dispatch or connector behaviour.
- Full `just test` was skipped in favour of focused eval/support runtime tests,
  replay, contracts, persistence, eval, lint, and diff checks.
- The optional live persisted eval check was skipped by `just eval` because no
  `CHORUS_EVAL_CORRELATION_ID` or `CHORUS_EVAL_WORKFLOW_ID` selector was
  supplied.
- `just test-persistence` completed, with the existing Redpanda projection test
  skipped by its fixture because Redpanda projection dependencies were not part
  of this change.

## Handoff Cadence

Each continuation prompt for Phase 2 should start by naming the milestone and
ledger item, then require the session to update this plan before handoff. If a
session updates project-memory material in
`/home/ryan/Work/vault/records/radianit/projects/chorus/`, it must keep the repo as
the source of truth and describe which vault files were synchronised.

This is a continuation-prompt driven workflow. A continuation is not complete
until the session has updated the `Next prompt` block below for the following
ledger item and included that exact copy-pasteable prompt in its final response.
The prompt should carry forward the same scope boundaries, required reading,
gate expectations, vault-sync rule, and "give the next prompt when you finish"
instruction.

Use this shape:

```text
Continue Chorus Phase <phase>: <ledger id and title>.

Read AGENTS.md, docs/architecture.md, adrs/, docs/phase-2-plan.md, and the
current git status first. If the work involves project metadata, also read
/home/ryan/Work/vault/records/radianit/projects/chorus/README.md and
/home/ryan/Work/vault/records/radianit/projects/chorus/handoff-prompt.md. Keep
Lighthouse Phase 1 working. Implement only this ledger item and its directly
required docs/tests. Use just recipes for gates. Update docs/phase-2-plan.md
with status/evidence notes before handoff. If vault records are touched, update
only Chorus project records and preserve unrelated vault changes. Report
commands run, any skipped gates, files changed, and the next ledger item.
Finish by giving the next continuation prompt verbatim, including this same
instruction to give the next prompt when finished.
```

Next prompt:

```text
Continue Chorus Phase 2D: 2D-05 Support read-only inspection path.

Read AGENTS.md, docs/architecture.md, adrs/, docs/phase-2-plan.md,
docs/implementation-plan.md, docs/evidence-map.md, docs/runbook.md, and current
git status first. Also read
/home/ryan/Work/vault/records/radianit/projects/chorus/README.md,
/home/ryan/Work/vault/records/radianit/projects/chorus/handoff-prompt.md, and
/home/ryan/Work/vault/records/radianit/projects/chorus/learning/open-questions-phase-2.md.
Also read docs/observability-user-journey-model.md,
docs/workload-principal-model.md, docs/invocation-authority-context.md,
docs/human-approval-audit-lifecycle.md,
docs/policy-change-governance-workflow.md, and
docs/llm-observability-sidecar-evaluation.md. Pay particular attention to
adrs/0011-phase-2-governed-platform-expansion.md,
adrs/0012-langgraph-agent-execution-runtime.md,
adrs/0013-identity-authority-observability-boundaries.md,
adrs/0014-connector-expansion-approval-hardening-scope.md,
adrs/0015-second-workflow-proof-scope.md, and the completed 2D-00, 2D-01,
2D-02, 2D-03, and 2D-04 handoff/evidence notes in docs/phase-2-plan.md.
Keep Lighthouse Phase 1 working and do not implement AWS, production SSO,
production cloud deployment, credential entry, production identity-provider
integration, production connector writes, credential mutation, production
provider calls, a hosted observability dependency, a mutating admin UI, a
generic workflow DSL, or a top-level agent framework replacing Temporal.
Implement only 2D-05: add the smallest read-only inspection path for the
existing `support_triage` happy-path evidence. Reuse the 2D-03 workflow
runtime, the 2D-04 eval/persisted evidence baseline, and the 2D-02 local ticket
read/propose gateway path; make safe support workflow events, Agent Runtime
decisions, Tool Gateway ticket verdicts, and proposed case-update refs
inspectable by tenant/correlation/workflow refs. Keep `ticket.update_status`
approval-required with no connector execution. Do not add reviewer decision UI,
mutating admin UI, production ticketing providers, credential entry, policy
mutation UI, hosted observability dependencies, production connector writes,
ticket status execution, generic workflow DSL work, or a top-level agent
framework replacing Temporal in this item. Bind only safe refs and bounded
categories in contracts, samples, examples, docs, audit, projections, fixtures,
tests, and UI/API responses: request refs, case refs, account refs, product
refs, severity/status categories, idempotency refs, tenant/correlation/workflow
refs, agent/tool refs, requested/enforced modes, verdict categories,
grant/policy refs, workflow step categories, eval fixture refs, proposed
case-update refs, and safe trace joins. Do not put secrets, credentials, API
keys, access tokens, raw sensitive content, raw prompts/outputs, raw tool
arguments, raw connector payloads, raw approval or policy rationale,
identity-provider claims, attendee names, email addresses, or PII in
contracts, telemetry baggage, projections, sidecar examples, audit examples,
seeds, samples, fixtures, eval fixtures, replay histories, API responses, or
UI views.
Update docs/phase-2-plan.md with status/evidence notes, update
runbook/evidence-map/implementation-plan notes if workflow, activity,
registration, replay, eval, persistence, BFF/UI, frontend, gate, or evidence
expectations change, and sync only the Chorus vault project records needed for
the continuation cadence. Run `just contracts-check`, focused Support
inspection/BFF tests, the relevant support eval command or `just eval`,
`git diff --check`, and the smallest additional relevant gate; run frontend
gates if UI changes, persistence gates if projections or persisted reads
change, Tool Gateway/connector gates only if gateway or connector behaviour
changes, and `just test-replay` only if workflow or replay behaviour changes.
Report files changed, commands run, skipped gates, and the next ledger item.
Finish by giving the next continuation prompt verbatim, including this same
instruction to give the next prompt when finished.
```

---
type: project-doc
status: archived
date: 2026-05-20
---

# Pre-Reset Phase History Archive (Phase 0 - Phase 2E)

This archive consolidates the chronological phase ledger that the Chorus
project accumulated before the 2026-05-19 transformation reset. R2 (the
documentation architecture refactor) demoted that detail out of the live
top-level docs so the repository reads as a ports-and-adapters exemplar.
Nothing here is deleted; it is preserved as historical evidence.

The archive has two parts:

- **Part 1 - Phase 2 Plan.** The former `docs/phase-2-plan.md`: the Phase 2
  governed-platform expansion plan and the Phase 2A through Phase 2E
  evidence ledger.
- **Part 2 - Implementation Plan.** The former `docs/implementation-plan.md`:
  the Phase 0 through Phase 1C delivery plan, work breakdown, and completion
  ledgers.

This document is frozen. The live roadmap is
[`engineering-reset-roadmap.md`](engineering-reset-roadmap.md); the live
top-level docs are `../README.md`, `../overview.md`, `../architecture.md`,
`../evidence-map.md`, and `../runbook.md`. The relative links inside the two
parts below were written for the `docs/` directory: from this archived path,
ADR links resolve under `../../adrs/`, and sibling-document links resolve
under `../` (and under `parked-phase-2e/` for the parked Phase 2E pack).

---

# Part 1 - Phase 2 Plan

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

Phase 2 remains in progress. Phase 2A, Phase 2B, Phase 2C, and Phase 2D are
complete. Phase 2D selected its second-workflow proof scope, added a contract
baseline for safe support intake, agent IO, ticket tool arguments, and
workflow/eval enum values, added the local ticket desk sandbox behind the Tool
Gateway for read/propose ticket actions, added the smallest code-defined
`support_triage` Temporal runtime with replay evidence, added support eval and
persisted evidence joins, and added a safe read-only BFF inspection path for
the existing support happy-path evidence. Phase 2E has started with ADR 0016 as
the docs-first production-readiness architecture pack scope decision, and has
completed the production identity/IAM mapping and secrets/credential handling
architecture artefacts plus the deployment topology and backup/restore/DR
architecture artefacts, and the retention/audit storage architecture artefact.
Phase 1 remains the stable demo baseline until each Phase 2 milestone has its
own evidence, tests, and documentation.

On 2026-05-19 development paused for the transformation reset in
[`docs/transformation/`](transformation/). The reset keeps existing technical
evidence but stops the one-item continuation cadence. Before more feature work,
Chorus must select or refine a real client-facing domain, define ubiquitous
language, restructure the documentation around local POC value, and separate
optional Amazon/Terraform deployment into its own later phase.

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
6. Which production-readiness concerns belong in architecture artefacts first,
   and which later need thin executable evidence?

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
- Production-readiness runtime work before the relevant architecture artefact
  and evidence expectations are explicit.

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
| 2D. Second workflow proof | Add one adjacent business workflow that reuses Agent Runtime, Tool Gateway, contracts, projections, eval, and observability without introducing a workflow DSL. | complete | ADR 0015 selects a local Support Desk Triage workflow as the second workflow candidate. Contract schemas, generated models, safe samples, enum baselines, and a Postgres-backed local ticket desk sandbox exist for support intake, support agent IO, local ticket arguments, `support_triage` workflow events, Phase 2D eval contract values, ticket case lookup, duplicate lookup, and proposed case updates. A code-defined `support_triage` Temporal workflow reuses Agent Runtime and Tool Gateway activity boundaries for a local read/propose happy path, is registered on the worker, and has focused replay evidence. The support eval fixture, persisted evidence baseline, and read-only BFF inspection path prove workflow events, Agent Runtime decisions, Tool Gateway ticket verdicts, proposed case-update refs, and the `ticket.update_status` approval-required boundary can be inspected by safe tenant/correlation/workflow refs while Lighthouse remains intact. |
| 2E. Production-readiness architecture pack | Decide which production concerns should remain design-only and which need thin executable evidence: production identity/IAM mapping, secrets, deployment topology, backup/restore and DR, retention and audit storage, incident/on-call integration, managed observability, and production provider or connector hardening. | in progress | ADR 0016 defines the docs-first scope, non-goals, required future artefacts, evidence expectations, and backlog shape before production-readiness code. 2E-01 adds the production identity and IAM mapping architecture, preserving Chorus business authority in Agent Runtime, Tool Gateway, approval audit, policy-change audit, and eval gates while mapping future human, workload, agent, invocation, approval, and policy principals to production trust domains, tenant/RBAC boundaries, IAM roles or equivalent workload identity, STS session rules, IAM Roles Anywhere, SPIFFE/SPIRE, and external IdP refs. 2E-02 adds the secrets and credential handling architecture for secret refs, bounded credential categories, local-to-production configuration, runtime injection boundaries, rotation, revocation, break-glass, audit/evidence refs, safe field rules, and promotion criteria. 2E-03 adds the deployment topology architecture for future service topology, environment classes, deployment unit boundaries, trust zones, ingress/egress, data-store and event-stream placement, managed-versus-self-hosted decisions, and IaC spike criteria. 2E-04 adds backup, restore, and DR architecture for RPO/RTO classes, authoritative store order, backup scope, restore responsibilities and dependency order, Temporal/application Postgres/event/projection/telemetry/eval/secrets/config handling, restore drills, safe field rules, promotion criteria, and backlog implications. 2E-05 adds retention and audit storage architecture for retention classes, audit ownership, Postgres-first audit posture, scaling signals, archive/export criteria, delete/expire/hold categories, append-store evaluation triggers, restore/DR interactions, safe field rules, and promotion criteria. Future executable spikes must be gated and explicitly scoped. |

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
| 2D-05 | Support read-only inspection path | safe BFF support evidence projection; runbook/evidence notes | focused BFF tests; `just contracts-check`; `git diff --check`; relevant persistence/eval checks | complete | Added the smallest read-only BFF inspection path for existing `support_triage` happy-path evidence. A reviewer can inspect safe support workflow event categories, Agent Runtime decision refs, ticket Tool Gateway verdict categories, proposed case-update refs, and the approval-required `ticket.update_status` write boundary by tenant/correlation/workflow refs. No Support UI route, reviewer decision UI, mutating admin UI, production ticketing providers, credential entry, policy mutation UI, production connector writes, ticket status execution, generic workflow DSL work, or top-level agent framework replacing Temporal was added. |

## Phase 2E Backlog

Phase 2E should keep production-readiness work docs-first until the local
evidence surface proves which concerns need executable spikes. Production
identity, secrets, deployment, backup/restore, retention, incident integration,
managed observability, and provider or connector hardening should be scoped
explicitly before any runtime behaviour changes. ADR 0016 fixes the first
boundary: the production-readiness pack may add ADRs, diagrams, checklists,
runbook sections, evidence-map rows, and phase-plan backlog items, but it does
not add migrations, services, credentials, cloud resources, production
connectors, hosted observability exporters, mutating admin paths, reviewer
decision paths, policy apply paths, ticket status execution, production
provider calls, or runtime behaviour changes.

| ID | Required item | Evidence artefact | Gate | Status | Notes |
|---|---|---|---|---|---|
| 2E-00 | Production-readiness architecture pack scope ADR | ADR 0016; phase plan; architecture/evidence/runbook updates | doc review; `just contracts-check`; `git diff --check`; smallest relevant docs gate | complete | ADR 0016 defines the scope, non-goals, safe-data rules, required future artefacts, evidence expectations, and ordered backlog shape for production identity/IAM mapping, secrets and credential handling, deployment topology, backup/restore and DR, retention and audit storage, incident/on-call integration, managed observability, and production provider or connector hardening. It is architecture-only: no migrations, services, credentials, cloud resources, production connectors, hosted observability exporters, mutating admin paths, reviewer decision paths, policy apply paths, ticket status execution, production provider calls, or runtime behaviour changes were added. |
| 2E-01 | Production identity and IAM mapping architecture | `docs/production-identity-iam-mapping.md`; phase/architecture/evidence/runbook notes | doc review; `just contracts-check`; `just doctor-quick`; `git diff --check`; focused docs alignment check | complete | Added the docs-first production identity and IAM mapping artefact. It maps human, workload, agent, invocation, approval, and policy principals to future production trust domains, tenant/RBAC boundaries, IAM roles or equivalent workload identity, STS session-name/tag rules, IAM Roles Anywhere, SPIFFE/SPIRE, and external IdP refs while keeping Chorus business authority in Agent Runtime, Tool Gateway, approval audit, policy-change audit, and eval gates. No AWS, production SSO, identity-provider integration, credentials, migrations, seeds, runtime enforcement, tenant-admin UI, reviewer decision path, policy apply path, production connector, hosted observability exporter, production provider call, or runtime behaviour change was added. |
| 2E-02 | Secrets and credential handling architecture | `docs/secrets-credential-handling.md`; phase/architecture/evidence/runbook notes | doc review; `just contracts-check`; `just doctor-quick`; `git diff --check`; focused docs alignment check | complete | Added the docs-first secrets and credential handling artefact. It defines credential categories, secret-ref naming rules, secret-ref catalogue shape, local-to-production configuration boundary, runtime injection boundaries, rotation/revocation lifecycle, break-glass controls, audit/evidence refs, forbidden-data checklist, required future artefacts, evidence expectations, safe field rules, promotion criteria, and backlog implications. No secret-manager integration, credential entry, credential mutation, actual credentials, provider keys, connector credentials, signing keys, identity-provider client secrets, cloud resources, production SSO, production identity-provider integration, IAM enforcement, production connectors, hosted observability exporters, production provider calls, migrations, services, runtime enforcement changes, or runtime behaviour changes were added. |
| 2E-03 | Deployment topology architecture | `docs/deployment-topology-architecture.md`; phase/architecture/evidence/runbook notes | doc review; `just contracts-check`; `just doctor-quick`; `git diff --check`; focused docs alignment check | complete | Added the docs-first deployment topology artefact. It defines future production service topology, environment classes, deployment unit boundaries, network and trust zones, ingress and egress boundaries, data-store and event-stream placement, component placement, local-to-production boundaries, managed-versus-self-hosted decision rules, IaC spike criteria, evidence expectations, safe field rules, promotion criteria, and backlog implications. No cloud resources, Terraform, Kubernetes/ECS/EKS/Lambda work, DNS, certificates, deployment automation, network resources, managed databases, production SSO, identity-provider integration, secret-manager integration, credential entry, credential mutation, production connectors, hosted observability exporters, production provider calls, migrations, services, runtime enforcement changes, or runtime behaviour changes were added. |
| 2E-04 | Backup, restore, and DR architecture | `docs/backup-restore-dr-architecture.md`; phase/architecture/evidence/runbook notes | doc review; `just contracts-check`; `just doctor-quick`; `git diff --check`; focused docs alignment check | complete | Added the docs-first backup, restore, and DR artefact. It defines RPO/RTO classes, authoritative store order, backup scope by data class, restore responsibility by component, restore dependency order, Temporal persistence handling, application Postgres/audit handling, event-stream and schema-registry handling, projection rebuild rules, telemetry store treatment, eval/replay artefact handling, secret metadata versus secret value handling, configuration/deployment refs, restore drill model, synthetic/local evidence expectations, safe field rules, promotion criteria, and backlog implications. No backup automation, restore automation, replication setup, PITR configuration, managed database configuration, managed event stream, object storage resource, cloud resource, Terraform, Kubernetes/ECS/EKS/Lambda work, DNS, certificate, network resource, deployment automation, production SSO, production identity-provider integration, IAM enforcement, secret-manager integration, credential entry, credential mutation, production connector, hosted observability exporter, production provider call, migration, service, runtime enforcement change, or runtime behaviour change was added. |
| 2E-05 | Retention and audit storage architecture | `docs/retention-audit-storage-architecture.md`; phase/architecture/evidence/runbook notes | doc review; `just contracts-check`; `just doctor-quick`; `git diff --check`; focused docs alignment check | complete | Added the docs-first retention and audit storage artefact. It defines retention classes for telemetry, journey projections, audit/accountability, decision-trail and Tool Gateway audit records, approval and policy-change packages, eval/replay artefacts, connector evidence, event-stream/schema evidence, secret metadata lifecycle evidence, backup/restore/DR evidence, and incident/on-call evidence. It defines audit-storage ownership, Postgres-first retention posture, audit scaling signals, archival/export criteria, delete/expire/hold categories, Scylla or append-store evaluation triggers, restore/DR interactions, safe field rules, synthetic/local evidence expectations, promotion criteria, and backlog implications. No retention automation, archive/export job, long-retention store, Scylla implementation, migration, managed database, object storage resource, cloud resource, hosted exporter, service, runtime enforcement change, or runtime behaviour change was added. |
| 2E-06 | Incident and on-call integration architecture | docs-first incident/on-call artefact; runbook notes | doc review; `just contracts-check`; `just doctor-quick`; `git diff --check`; smallest relevant docs gate | open | Define severity categories, incident refs, escalation lifecycle, change-freeze expectations, post-incident evidence, and incident-to-policy-change linkage before pager integration, alert routing, incident workflows, or production incident tooling. |
| 2E-07 | Managed observability architecture | docs-first managed observability artefact; exporter allow-list notes | doc review; `just contracts-check`; `just doctor-quick`; `git diff --check`; smallest relevant docs gate | open | Map local Grafana/OTel evidence to managed telemetry or optional sidecar export while preserving Postgres audit, Temporal replay, and `just eval` as authoritative. Do not add hosted exporters, managed dependencies, sidecar SDKs, credentials, or runtime export behaviour. |
| 2E-08 | Production provider and connector hardening architecture | docs-first provider/connector hardening artefact; runbook/evidence notes | doc review; `just contracts-check`; `just doctor-quick`; `git diff --check`; smallest relevant docs gate | open | Define readiness gates for real provider adapters and production connector providers: credential refs, rate limits, retries, circuit breakers, kill switches, approval, idempotency, eval, replay where relevant, and rollback. Do not add production provider calls, production connector writes, credentials, or production adapters. |

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
- 2026-05-19: `2D-05` added the smallest read-only Support Desk Triage
  inspection path. `chorus.persistence.ProjectionStore` now builds safe support
  inspection summaries from persisted workflow events, Agent Runtime decision
  trail rows, Tool Gateway ticket audit rows, proposed local case-update refs,
  and the seeded `ticket.update_status` grant boundary. The BFF exposes
  read-only support inspection endpoints filtered by tenant plus optional
  workflow or correlation refs:
  `/api/support/inspections?workflow_id=<workflow-ref>&correlation_id=<correlation-ref>`
  and `/api/workflows/<workflow-ref>/support/inspection`. Responses expose only
  bounded categories and safe refs, including support workflow step categories,
  agent/tool refs, requested/enforced modes, verdict categories, grant/policy
  refs, trace joins, proposed case-update refs, and the approval-required
  status-write boundary. Focused BFF unit coverage proves the endpoints return
  safe inspection views and do not expose a status execution path; the live BFF
  fixture seeds the same persisted support refs when Postgres is available. No
  Support UI route, reviewer decision UI, mutating admin UI, production
  ticketing providers, credential entry, policy mutation UI, hosted
  observability dependencies, production connector writes, ticket status
  execution, workflow DSL, raw sensitive content, raw prompts/outputs, raw tool
  arguments, raw connector payloads, raw approval or policy rationale,
  identity-provider claims, attendee names, email addresses, or PII were added.

## Phase 2E Evidence Notes

- 2026-05-19: `2E-00` added
  `adrs/0016-production-readiness-architecture-pack-scope.md` as the
  production-readiness architecture pack scope decision. ADR 0016 defines the
  scope, non-goals, safe-data rules, required future artefacts, evidence
  expectations, and ordered backlog shape for production identity/IAM mapping,
  secrets and credential handling, deployment topology, backup/restore and DR,
  retention and audit storage, incident/on-call integration, managed
  observability, and production provider or connector hardening. The decision
  keeps Phase 2E architecture-first: it may add ADRs, diagrams, checklists,
  runbook sections, evidence-map rows, and phase-plan backlog items, but it
  does not add migrations, services, credentials, cloud resources, production
  connectors, hosted observability exporters, mutating admin paths, reviewer
  decision paths, policy apply paths, ticket status execution, production
  provider calls, or runtime behaviour changes. Architecture, implementation
  plan, evidence map, runbook, ADR index, and Chorus vault continuation records
  were aligned.
- 2026-05-19: `2E-01` added
  `docs/production-identity-iam-mapping.md` as the production identity and IAM
  mapping architecture artefact. The document maps Chorus human, workload,
  agent, invocation, approval, and policy principals to future production trust
  domains, tenant/RBAC boundaries, IAM roles or equivalent workload identity,
  safe STS session-name and session-tag rules, IAM Roles Anywhere,
  SPIFFE/SPIRE, and external identity-provider refs. It keeps IAM and external
  IdPs as authentication/resource-scope mechanisms while preserving Chorus
  business authority in Agent Runtime, Tool Gateway, approval audit,
  policy-change audit, and eval gates. It also defines non-goals, safe field
  rules, required future artefacts, evidence expectations, promotion criteria,
  and backlog implications for 2E-02 through 2E-08. Architecture,
  implementation plan, evidence map, runbook, and Chorus vault continuation
  records were aligned. No migration, service, credential, cloud resource,
  production SSO, production identity-provider integration, tenant-admin UI,
  mutating admin path, reviewer decision path, policy apply path, runtime
  enforcement change, production connector, hosted observability exporter,
  production provider call, or runtime behaviour change was added.
- 2026-05-19: `2E-02` added
  `docs/secrets-credential-handling.md` as the secrets and credential handling
  architecture artefact. The document defines future credential categories,
  secret-ref naming rules, secret-ref catalogue shape, local-to-production
  configuration boundary, runtime injection boundaries, rotation and
  revocation lifecycle, break-glass controls, audit and evidence refs,
  forbidden-data checklist, required future artefacts, evidence expectations,
  safe field rules, promotion criteria, and backlog implications for provider,
  connector, database, signing, identity-provider, observability, and workload
  identity credentials. It keeps credential handling architecture-only and
  uses secret refs and bounded categories only. Architecture, implementation
  plan, evidence map, runbook, and Chorus vault continuation records were
  aligned. No secret-manager integration, credential entry, credential
  mutation, actual credential, provider key, connector credential, signing key,
  identity-provider client secret, cloud resource, production SSO, production
  identity-provider integration, IAM enforcement, production connector, hosted
  observability exporter, production provider call, migration, service,
  runtime enforcement change, or runtime behaviour change was added.
- 2026-05-19: `2E-03` added
  `docs/deployment-topology-architecture.md` as the deployment topology
  architecture artefact. The document defines the future production service
  topology, environment classes, deployment unit boundaries, network and trust
  zones, ingress and egress boundaries, data-store and event-stream placement,
  Temporal, Agent Runtime, Tool Gateway, BFF/UI, projection, connector,
  observability, identity, and secret-injection placement,
  local-to-production boundaries, managed-versus-self-hosted decision rules,
  IaC spike criteria, evidence expectations, safe field rules, promotion
  criteria, and backlog implications. It keeps deployment architecture-only
  and uses service refs, workload refs, zone refs, deployment refs, store refs,
  stream refs, secret refs, provider refs, connector refs, and bounded
  categories only. Architecture, implementation plan, evidence map, runbook,
  README, overview, agent guide, and Chorus vault continuation records were
  aligned. No cloud resource, Terraform, Kubernetes/ECS/EKS/Lambda work, DNS,
  certificate, deployment automation, network resource, managed database,
  production SSO, production identity-provider integration, IAM enforcement,
  secret-manager integration, credential entry, credential mutation,
  production connector, hosted observability exporter, production provider
  call, migration, service, runtime enforcement change, or runtime behaviour
  change was added.
- 2026-05-19: `2E-04` added
  `docs/backup-restore-dr-architecture.md` as the backup, restore, and DR
  architecture artefact. The document defines future RPO/RTO classes,
  authoritative store order, backup scope by data class, restore responsibility
  by component, restore dependency order, Temporal persistence handling,
  application Postgres and audit handling, event-stream and schema-registry
  handling, projection rebuild rules, telemetry treatment, eval/replay artefact
  handling, secret metadata versus secret value handling,
  configuration/deployment refs, restore drill models, synthetic/local evidence
  expectations, safe field rules, promotion criteria, and backlog implications.
  It keeps recovery architecture-only and uses safe refs and bounded categories
  only. Architecture, implementation plan, evidence map, runbook, README,
  overview, agent guide, and Chorus vault continuation records were aligned. No
  backup automation, restore tooling, replication, PITR policy, managed database
  configuration, managed event stream, object storage resource, cloud resource,
  Terraform, Kubernetes/ECS/EKS/Lambda work, DNS, certificate, network resource,
  deployment automation, production SSO, production identity-provider
  integration, IAM enforcement, secret-manager integration, credential entry,
  credential mutation, production connector, hosted observability exporter,
  production provider call, migration, service, runtime enforcement change, or
  runtime behaviour change was added.
- 2026-05-19: `2E-05` added
  `docs/retention-audit-storage-architecture.md` as the retention and audit
  storage architecture artefact. The document defines future retention classes
  for telemetry, application/user journey projections, audit/accountability,
  decision trail, Tool Gateway audit, approval packages, policy-change
  packages, eval/replay artefacts, connector evidence, event-stream/schema
  evidence, secret metadata lifecycle evidence, backup/restore/DR evidence,
  incident/on-call evidence, and optional sidecar exports. It defines
  audit-storage ownership, the Postgres-first audit-retention posture, audit
  scaling signals, archive/export criteria, delete/expire/hold categories,
  Scylla or append-store evaluation triggers, restore/DR interactions,
  synthetic/local evidence expectations, safe field rules, promotion criteria,
  and backlog implications. It keeps retention architecture-only and uses safe
  refs and bounded categories only. Architecture, implementation plan,
  evidence map, runbook, README, overview, agent guide, and Chorus vault
  continuation records were aligned. No retention automation, archive/export
  job, long-retention store, Scylla implementation, migration, managed
  database, object storage resource, cloud resource, Terraform,
  Kubernetes/ECS/EKS/Lambda work, DNS, certificate, network resource,
  deployment automation, production SSO, production identity-provider
  integration, IAM enforcement, secret-manager integration, credential entry,
  credential mutation, production connector, hosted observability exporter,
  production provider call, service, runtime enforcement change, or runtime
  behaviour change was added.

## Current Handoff - 2026-05-19

Status:

- `2A-11` through `2C-05` are complete.
- `2D-00` is complete.
- `2D-01` is complete.
- `2D-02` is complete.
- `2D-03` is complete.
- `2D-04` is complete.
- `2D-05` is complete.
- `2E-00` is complete.
- `2E-01` is complete.
- `2E-02` is complete.
- `2E-03` is complete.
- `2E-04` is complete.
- `2E-05` is complete.
- Development pause: use [`docs/transformation/`](transformation/) before
  selecting the next implementation item. Remaining `2E-06` through `2E-08`
  architecture docs should be batched or closed during the reset, not advanced
  through the old one-item continuation cadence.

Evidence added:

- `docs/retention-audit-storage-architecture.md` defines retention and audit
  storage architecture for future retention classes, evidence retention matrix,
  audit-storage ownership, Postgres-first audit posture, scaling signals,
  archive/export criteria, delete/expire/hold categories, Scylla or append-store
  evaluation triggers, restore/DR interactions, safe field rules, promotion
  criteria, and backlog implications using safe refs and bounded categories
  only.
- `docs/phase-2-plan.md` marks `2E-05` complete, records evidence notes, and
  points the next handoff at incident and on-call integration architecture.
- Architecture, implementation plan, evidence map, runbook, README/overview,
  and agent-guide notes now link the 2E-05 artefact and keep retention and
  audit storage mapped as architecture, not implemented behaviour.
- Chorus vault continuation records were synchronised only for the project
  status and next continuation prompt.

Commands run:

- `just contracts-check`
- `just doctor-quick`
- `rg -n "2E-05|2E-06|retention-audit-storage|Retention and audit|audit storage|Postgres-first|incident and on-call|Incident and on-call" AGENTS.md README.md docs/architecture.md docs/evidence-map.md docs/implementation-plan.md docs/overview.md docs/phase-2-plan.md docs/runbook.md docs/retention-audit-storage-architecture.md /home/ryan/Work/vault/records/radianit/projects/chorus`
- `git diff --check`
- `git -C /home/ryan/Work/vault diff --check -- records/radianit/projects/chorus/README.md records/radianit/projects/chorus/handoff-prompt.md records/radianit/projects/chorus/learning/open-questions-phase-2.md`

Skipped gates:

- Runtime, replay, eval, persistence, BFF/UI, frontend, Tool Gateway, and
  connector gates were skipped because `2E-05` added only architecture docs,
  evidence, runbook, and continuation updates with no runtime, contract,
  schema, service, connector, persistence, UI, workflow, retention, archive,
  export, or storage behaviour changes.
- Full `just test`, `just lint`, `just test-replay`, `just eval`,
  `just test-persistence`, `just test-frontend`, and `just test-e2e` were
  skipped in favour of the docs-first gates above.

## Handoff Cadence

The old continuation-prompt driven workflow is retired for the reset period.
Future sessions should use checkpoint-sized tasks from
[`docs/transformation/engineering-reset-roadmap.md`](transformation/engineering-reset-roadmap.md).
If vault records are touched, update only Chorus project records and preserve
unrelated vault changes. Handoffs should record files changed, gates run,
skipped gates, and the next reset checkpoint, but they should not copy a large
next prompt into every response.
---

# Part 2 - Implementation Plan

## Scope Lock

Implementation happens in this repository. Architecture, contracts, code, tests, eval fixtures, and operational docs move together.

Phase 1 builds one evidence-grade vertical slice for Lighthouse, including the happy path and the governance/failure fixtures needed by the architecture evidence map. It also packages the architecture, governance, and evidence artefacts needed to explain the pattern. It does not build a generic agent framework, a SaaS product, production auth, real third-party integrations, cloud deployment, Scylla storage, or a second workflow.

**1A is the first public ship-checkpoint.** Phases 1B (governance/failure fixtures) and 1C (review packaging) are committed continuations that extend the 1A baseline; they are not gating the first usable architecture review.

Phase 2 planning is open through [`phase-2-plan.md`](phase-2-plan.md), [ADR 0011](../adrs/0011-phase-2-governed-platform-expansion.md), [ADR 0012](../adrs/0012-langgraph-agent-execution-runtime.md), [ADR 0013](../adrs/0013-identity-authority-observability-boundaries.md), [ADR 0014](../adrs/0014-connector-expansion-approval-hardening-scope.md), [ADR 0015](../adrs/0015-second-workflow-proof-scope.md), and [ADR 0016](../adrs/0016-production-readiness-architecture-pack-scope.md). Phase 2A has delivered provider/model-governance groundwork, LangGraph execution inside Agent Runtime, provider failure/timeout/rate-limit/budget fallback evidence, route-selection metadata, read-only BFF/UI provider and graph inspection, and docs/runbook/evidence alignment. Phase 2B has delivered docs-first identity, authority, approval, policy-change, and optional sidecar boundaries. Phase 2C has delivered the local CalDAV calendar connector candidate: contract-only calendar argument schemas, a local Radicale sandbox, Tool Gateway-dispatched connector paths for read/propose actions, minimal approval package persistence while writes remain approval-required, approved local apply evidence for idempotent create, retry classification, cancellation compensation, compensation-failure escalation, and safe read-only calendar status/audit projection. Phase 2D has selected local Support Desk Triage as the second workflow proof scope, added the safe support intake, support agent IO, ticket argument, workflow-event, and eval enum baseline, added a Postgres-backed local ticket desk sandbox behind the Tool Gateway for read/propose ticket actions while status writes remain approval-required, added the code-defined `support_triage` Temporal workflow runtime plus replay baseline, added the support eval plus persisted evidence baseline, and added the safe read-only Support BFF inspection path. Phase 2E has started with ADR 0016, which scopes the production-readiness architecture pack before any production-readiness code; 2E-01 has added the docs-first production identity and IAM mapping architecture, 2E-02 has added the docs-first secrets and credential handling architecture, 2E-03 has added the docs-first deployment topology architecture, and 2E-04 has added the docs-first backup, restore, and DR architecture. Later workstreams cover the remaining production-readiness architecture artefacts.

## Phases and Milestones

| Phase | Milestone | Status | Exit criteria |
|---|---|---|---|
| 0. Foundation | Docs, ADRs, architecture/governance artefacts, local dev contract, contracts, and service layout exist. | done | README explains run/review path; architecture, guardrails, evidence map, and ADRs are linked. |
| 1A. Lighthouse happy-path slice | Send fixture lead email through Mailpit, run Temporal workflow, invoke governed agents, mediate at least one tool action, project state, stream progress, and show audit trail. | done | A reviewer can run one command, send the fixture lead to Mailpit SMTP, see workflow state advance through the BFF/UI, inspect Temporal/Redpanda/Grafana/audit by correlation ID, and run the happy-path eval. |
| 1B. Governance and failure evidence | Add blocked write, low-confidence research, validator rejection, connector failure, retry/exhaustion, and escalation paths. | done | Failure fixtures produce expected workflow branches, audit verdicts, DLQ or escalation records, and passing trace/eval checks. |
| 1C. Review packaging | Tighten README, screenshots or screencast notes, demo script, architecture links, governance evidence, and project-facing summary. | done | Asynchronous reviewers can answer the evidence-map questions in under 15 minutes; guided demo fits 3 minutes without opening an editor. |
| 2. Governed platform expansion | Planned LangGraph agent execution, provider/model governance, governed identity and runtime change control, observability/user-journey boundaries, connector expansion, second workflow proof, and production-readiness architecture. | in progress | Phase 2 milestones are documented, each with evidence gates; Phase 2A documentation distinguishes implemented LangGraph/provider evidence from deferred production provider calls and LangGraph durability, Phase 2B owns the identity/authority and observability boundary design before mutating runtime controls, Phase 2C has a completed local CalDAV connector proof with contract schemas, Radicale sandbox, Tool Gateway read/propose dispatch, approval package persistence, approved local idempotency/retry/compensation evidence, and safe read-only calendar projection/audit inspection, Phase 2D has selected local Support Desk Triage, added support/ticket contracts, local ticket desk Tool Gateway dispatch, a code-defined support workflow runtime, replay evidence, support eval, persisted evidence, and safe read-only Support BFF inspection, and Phase 2E has a docs-first production-readiness architecture pack scope decision plus production identity/IAM mapping, secrets/credential handling, deployment topology, and backup/restore/DR architecture before production-readiness code. |

## Definition of Delivered

A workstream is delivered only when every scoped item in the completion ledger
is `done`, or explicitly `deferred` with an owner, reason, impact, and follow-up
phase. Producing a subset of code, a placeholder boundary, host-only command, or
focused test is partial evidence, not delivery.

Status values are constrained:

| Status | Meaning |
|---|---|
| `open` | Required work has not started. |
| `in_progress` | Work is actively being changed in the current stream. |
| `blocked` | Work cannot proceed until a named dependency is resolved. |
| `partial` | Some scoped artefacts exist, but at least one required item is missing or not evidenced. |
| `done` | Required artefact exists, docs are aligned, and the named gate/evidence passes. |
| `deferred` | Deliberately moved out of the phase with owner, reason, impact, and follow-up phase documented. |

The outcome criteria for each workstream are:

- all required code/config/schema/docs artefacts exist in the repo;
- cross-boundary payloads are contract-shaped and validated;
- integration points consumed by downstream workstreams are runnable, not only described;
- observability, audit, and `doctor` hooks are present where the scope requires them;
- relevant tests/gates have run and failures are recorded;
- docs state the actual implementation state and do not promote placeholders to delivery.

The outcome criteria for Phase 1A are stricter than individual workstream
completion: the Mailpit-triggered Lighthouse happy path must run through the
local stack, write workflow events and decision/tool audit evidence, project
state for refresh-safe reads, expose progress/inspection surfaces, and pass the
happy-path eval by correlation ID.

## Detailed Work Breakdown

Items are tagged with the phase that owns them. **(Phase 0)** items must complete before Phase 1 begins. **(Phase 1A)** items are the first public ship-checkpoint. **(Phase 1B)** items extend failure-fixture evidence. **(Phase 1C)** items finalise review packaging.

1. **(Phase 0) Developer workflow and service layout** — *delivered (Workstream F first pass)*
   - Create docs tree, ADR tree, architecture/governance artefact set, service layout, Compose skeleton, command runner, and `doctor` command contract.
   - Phase 0A scaffold finishing pass landed alongside Workstream F's opening shipment: `.env.example` + parameterised `compose.yml` with `chown-init`; `scripts/dc` wrapper and `scripts/first-time-setup.sh` host bootstrap; prek-driven `.pre-commit-config.yaml`; `.editorconfig`/`.dockerignore`/`.gitattributes`; `services/_template/` (Dockerfile + pyproject + README); CI workflows (`ci.yml`, `eval.yml`, `replay.yml`) with dependabot, issue/PR templates; `SECURITY.md`/`CONTRIBUTING.md`/`CHANGELOG.md`; README badges + first-time-setup section; `docs/runbook.md` (the Workstream F operational artefact); `frontend/` scaffold (React 19 + Vite 8 + TS + TanStack Router/Query + Tailwind v4 + Radix) seeded with the vendored Dense design family (no external dependency, no `@radianit/*` references).
   - Exit check: repo opens cleanly, docs are linked, local prerequisites are explicit, and a fresh clone reaches `just up` via one bootstrap command.

2. **(Phase 0) Contracts first**
   - Define JSON Schemas for lead intake, workflow events, agent invocation records, tool calls, gateway verdicts, audit events, and eval fixture expectations.
   - Generate Pydantic models and add sample validation/drift checks.
   - Current state: the initial Phase 0 contract set, representative samples, generated Pydantic models, and `just contracts-check` drift gate are implemented.
   - Exit check: contract CI fails on schema/model/sample drift.

3. **(Phase 0) Public evidence map**
   - Draft `docs/evidence-map.md` mapping architecture capabilities to specific Chorus artefacts: enterprise guardrails, provider governance, prompt/model/tool change control, safety/eval lifecycle, observability, and operational adoption.
   - Cross-link each row to the supporting doc/code/test location (initially doc-only; code links populate during 1A).
   - Exit check: a reviewer can read the map and locate evidence for each responsibility without searching.

4. **(Phase 1A) Persistence and projection** — *delivered (Workstream A)*
   - Add Postgres schema for tenants, agent registry, model policy, tool grants, workflow read model, decision trail, episodic history, and outbox.
   - Add RLS and tenant-isolation tests for two seeded tenants.
   - Current state: the Phase 1A storage foundation migration, checksum-protected migration runner, idempotent two-tenant seed data, read-model/projection adapter, transactional outbox lifecycle, Redpanda relay, Redpanda projection consumer, real-Postgres RLS/fail-closed tests, outbox transition tests, idempotent projection tests, and real-Redpanda publish/consume projection tests are implemented.
   - Exit check: read model survives refresh/reconnect, tenant leakage tests fail closed, outbox rows relay to Redpanda, and consumed workflow events project into Postgres idempotently.

5. **(Phase 1A) Temporal workflow** — *delivered (Workstream B)*
   - Implement Lighthouse workflow states: intake, research/qualification, draft, validate, propose/send, escalate.
   - Keep workflow logic deterministic and push IO into activities.
   - Current state: the deterministic workflow module, Mailpit parser, activity boundaries, worker CLI, replay fixture, and focused workflow tests exist. The worker now also runs as the `chorus-intake-poller` Compose service under `opentelemetry-instrument`, `doctor` verifies the `lighthouse` Temporal task queue via `DescribeTaskQueue`, event contracts declare Schema Registry subjects, workflow/activity boundaries stamp correlation span attributes, workflow outbox rows capture active OTel IDs in `metadata`, and worker metrics flow through the OTel collector rather than a side `/metrics` endpoint.
   - Exit check: happy-path workflow replay test passes, the worker runs in the local stack, Temporal can discover the `lighthouse` task queue, and the workflow/activity path emits contract, audit, and observability evidence by correlation ID.

6. **(Phase 1A) Agent Runtime** — *delivered (Workstream C)*
   - Resolve agent version, prompt reference, lifecycle state, model route, budget caps, tenant policy, and invocation ID before each agent call.
   - Capture decision-trail records with correlation IDs.
   - Current state: `chorus.agent_runtime` resolves active tenant policy, approved agent versions, prompt references/hashes, approved model routes, and budget caps from Workstream A's Postgres tables. `lighthouse.invoke_agent_runtime` uses that runtime behind Workstream B's stable activity boundary, returns generated-contract Lighthouse agent output, and persists `AgentInvocationRecord`-shaped decision-trail rows with active OTel IDs in `metadata`. The happy path uses the local `lighthouse-happy-path-v1` structured model boundary. Phase 2A adds LangGraph execution evidence, route-selection metadata, a disabled-by-default `commercial.example` adapter boundary that records provider-disabled metadata but performs no production provider calls, provider-failure fallback fixture evidence, and read-only BFF/UI provider and graph-execution inspection.
   - Exit check: reviewer can inspect which agent/model/prompt ran and why.

7. **(Phase 1A) Tool Gateway and local connector service**
   - Build one gateway in front of a local connector service running **real software** (no mocks, no hand-rolled fakes per project policy): Mailpit for SMTP capture, real public APIs for company research, and a Postgres-backed local CRM service implementing the connector contract end-to-end.
   - Enforce grants, argument schemas, modes, idempotency, redaction, approval hook, and audit events.
   - Current state: `chorus.tool_gateway` implements the `lighthouse.invoke_tool_gateway` activity internals behind Workstream B's stable boundary. It validates generated `ToolCall`, `GatewayVerdict`, `AuditEvent`, and `EmailMessageArgs` contracts; resolves `tool_grants`; enforces allow, block, write-to-propose downgrade, and approval-required decisions; redacts audit arguments; enforces idempotency; writes `tool_action_audit` with OTel metadata; and routes permitted calls to local connectors. `chorus.connectors.local` provides Mailpit SMTP outbound capture, a Postgres-backed local CRM table, and an environment-gated Companies House connector.
   - Exit check: at least one allowed action and one blocked/downgraded action are visible in audit, and the email-send path produces a real Mailpit-captured message.

8. **(Phase 1A) Events, outbox, and UI progress**
   - Publish schema-governed events through outbox to Redpanda.
   - Feed Postgres projection and SSE progress from the event stream.
   - Exit check: UI progress, Redpanda topic events, and read model agree by correlation ID.

9. **(Phase 1A) Lighthouse UI and read-only admin**
   - Provide the Mailpit-triggered workflow run list/detail, dev-only fixture replay, workflow timeline, decision trail, tool verdicts, runtime registry, grants, and routing views.
   - Keep the UI dense, plain, and data-first.
   - Exit check: the 3-minute demo can be performed without opening an editor.

10. **(Phase 1A) Observability and assurance** — *delivered (Workstream F plus eval closeout)*
    - Add OpenTelemetry traces/logs/metrics, Grafana dashboard, and happy-path eval fixtures.
    - Current state: Workstream F provides the local observability substrate and cross-surface correlation recipe. `just eval` runs the Lighthouse happy-path and Phase 1B governance/failure fixtures, validates contract-shaped workflow/agent/tool evidence, and optionally inspects persisted Postgres evidence for a supplied workflow/correlation ID.
    - Exit check: Temporal, Redpanda, Grafana, UI, and audit views can be correlated from one workflow ID; happy-path eval passes.

11. **(Phase 1A) Phase 1A documentation pass** — *delivered (Phase 1A closeout)*
    - Update README, overview, architecture, governance guardrails, runbook, demo script, and evidence map to reflect the implemented slice.
    - Current state: documentation names the implemented Phase 1A happy path and makes the 3-minute Mailpit → Temporal → Redpanda/projection → BFF/UI/Grafana/audit → eval review path explicit. Later Phase 1C packaging updates the same docs to include completed Phase 1B governance/failure evidence.
    - Exit check: docs describe the current code and no deferred feature is presented as implemented.

12. **(Phase 1C) Architecture artefact packaging — final pass**
    - Update `docs/evidence-map.md` (drafted in Phase 0) to cross-link every row to its now-implemented evidence: code paths, eval fixtures, audit views, dashboards, ADRs.
    - Exit check: an architecture reviewer can see both the working system and the programme-level adoption model in one navigation pass.

13. **(Phase 2) Governed platform expansion — in progress**
    - Follow [`phase-2-plan.md`](phase-2-plan.md) for the milestone order:
      LangGraph agent execution plus provider/model governance, governed
      identity/authority and runtime change control, observability/user-journey
      boundaries, connector expansion, second workflow proof, and
      production-readiness architecture.
    - Phase 2A is complete through provider timeout, rate-limit, and budget
      degradation fixture coverage.
    - Phase 2B opened with an ADR and docs pass for human, workload, agent,
      invocation, approval, and policy actor identity; local authority context;
      future AWS IAM role mapping; infrastructure telemetry; application/user
      journey evidence; optional LLM observability sidecars; and canonical audit
      boundaries.
    - Phase 2B item `2B-01` adds the docs-first observability and user-journey
      data model: OTel attribute/baggage placement rules, Postgres
      projection/BFF/UI sketch, audit-only field families, and future
      actor/session identifiers.
    - Phase 2B item `2B-02` added the docs-first workload-principal and future
      AWS IAM mapping model: local workload principals, workload sessions,
      trust domains, tenant scope, safe telemetry placement, and nullable
      future IAM role/STS session/IAM Roles Anywhere/SPIFFE/external IdP
      mapping metadata without local AWS dependencies or credentials.
    - Phase 2B item `2B-03` added the docs-first invocation-authority context
      model: Agent Runtime invocation authority, Tool Gateway tool-authority
      subsets, parent invocation, expiry, workload refs, approval/policy-change
      refs, and safe trace joins without adding runtime contracts, signatures,
      AWS dependencies, credentials, or raw sensitive content.
    - Phase 2B item `2B-04` added the docs-first human-approval audit
      lifecycle model: `approval_required` becomes the trigger for a future
      approval package with approval ID, reviewer actor subject ref, reviewer
      role, decision, SLA/expiry, reason category, policy refs,
      workload/session refs, invocation/tool authority refs, and safe trace
      joins. No approval table, contract, BFF/UI queue, Temporal wait state,
      production SSO, credential entry, mutating admin UI, or connector write
      path was added.
    - Phase 2B item `2B-05` added the docs-first governed policy mutation
      workflow model: prompt references, model routes, budget caps, and tool
      grants move through a future propose, approve, apply, and rollback
      package with policy change ID, target refs, before/after refs, proposer
      and reviewer actor refs, approval refs where required, reason category,
      eval evidence refs, apply/rollback refs, expiry/SLA, workload/session
      refs, and safe trace joins. No policy-change table, contract, seed,
      runtime apply path, production provider call, credential mutation, or
      mutating admin UI was added.
    - Phase 2B item `2B-06` added the optional LLM observability sidecar
      evaluation: LangSmith, Langfuse, or similar tools may consume only
      filtered OTel and eval-derived fields through an opt-in exporter. They
      are not the accountability store, release gate, policy mutation path,
      prompt authority, or required local dependency. No exporter, SDK,
      contract, migration, seed, hosted observability dependency, credential
      path, or runtime behaviour change was added.
    - Phase 2C item `2C-00` added ADR 0014 as the connector expansion and
      approval-hardening scope decision. The chosen candidate is a local
      Radicale/CalDAV calendar connector for Lighthouse follow-up holds, with
      required Tool Gateway, approval, idempotency, retry, compensation,
      projection, audit, eval, runbook, and evidence-map expectations before
      connector code. No calendar contract, connector code, sandbox service,
      production connector write, credential entry, hosted dependency, runtime
      mutation path, or mutating UI was added.
    - Phase 2C item `2C-01` added contract-only calendar argument schemas,
      safe samples, generated models, and ToolCall enum values for
      availability lookup, hold proposal, hold creation, and hold cancellation.
      No connector code, sandbox service, approval apply path, production
      connector write, credential entry, runtime mutation path, workflow logic,
      eval fixture, or UI mutation path was added.
    - Phase 2C item `2C-02` added the local Radicale sandbox, the
      `RadicaleCalendarConnector`, Tool Gateway validation/dispatch for the
      calendar tool family, seeded read/propose calendar grants, and
      approval-required create/cancel grants. Availability lookup and hold
      proposal can execute locally; calendar writes still stop at
      `approval_required`. No approval apply path, production calendar
      provider, OAuth, credential entry, Lighthouse workflow branch, eval
      fixture, projection, UI mutation path, or production connector write was
      added.
    - Phase 2C item `2C-03` added the minimal local deterministic
      `approval_packages` table and Tool Gateway package creation for
      approval-required calendar create/cancel writes. Packages bind approval
      ID, tenant/correlation/workflow refs, invocation/tool/verdict/source
      audit refs, requested action, mode, idempotency key hash, redaction
      summary, SLA/expiry refs, grant/policy refs, nullable workload/session
      refs, and safe trace joins. Calendar writes still stop at
      `approval_required`; no reviewer decision path, approval apply path,
      production connector write, credential entry, workflow branch, eval
      fixture, projection, UI mutation path, or mutating admin UI was added.
    - Phase 2C item `2C-04` added local approved calendar apply evidence inside
      the Tool Gateway. An already approved package can re-enter the gateway;
      the gateway checks package state, expiry, grant, original idempotency key
      hash, tenant/correlation/workflow/invocation refs, agent/tool/mode refs,
      and safe calendar refs before invoking Radicale. Focused tests prove
      idempotent local VEVENT creation, transient retry classification without
      caching success, cancellation compensation through the gateway,
      compensation-failure escalation, and duplicate UID context checks. No
      reviewer decision path, reviewer UI, Lighthouse workflow calendar branch,
      eval fixture, projection, production calendar provider, OAuth, credential
      entry, production connector write, hosted observability dependency, or
      mutating admin UI was added.
    - Phase 2C item `2C-05` added read-only calendar status projection through
      the BFF. The projection is derived from `approval_packages` and matching
      Tool Gateway apply audit rows, exposes only safe approval/audit refs,
      calendar refs, bounded status and retry/compensation/failure categories,
      grant/policy refs, and trace joins, and documents idempotent replay,
      compensation, and safe inspection in the runbook/evidence map. No
      reviewer decision UI, Lighthouse workflow calendar branch, eval fixture,
      production calendar provider, OAuth, credential entry, production
      connector write, hosted observability dependency, or mutating admin UI
      was added.
    - Phase 2D item `2D-00` added ADR 0015 as the second workflow proof scope
      decision. The selected candidate is local Support Desk Triage using
      future workflow type `support_triage`, with support request intake,
      classification/severity triage, account or case context lookup,
      resolution planning, response and case-update proposal, validation,
      completion, and escalation. It must reuse Temporal, Agent Runtime,
      LangGraph inside Agent Runtime, Tool Gateway, Postgres, Redpanda,
      BFF/UI read-only projections, eval/replay, and OTel/Grafana boundaries
      without adding a workflow DSL. No second-workflow code, contracts,
      migrations, seeds, UI routes, eval fixtures, replay histories, production
      connector provider, credential path, hosted dependency, mutating admin UI,
      raw sensitive content, raw prompts/outputs, raw tool arguments, raw
      connector payloads, raw approval or policy rationale, identity-provider
      claims, email addresses, or PII was added.
    - Phase 2D item `2D-01` added contract-only support request intake,
      support agent IO, local ticket tool argument schemas, generated Pydantic
      models, safe samples, and ToolCall/workflow/eval enum values for the
      future `support_triage` proof. Ticket contracts cover case lookup,
      duplicate lookup, case-update proposal, and a future approval-required
      status update using safe refs and bounded categories only. No support
      workflow runtime, Temporal activity registration, migration, seed, local
      ticket connector runtime, BFF/UI route, eval fixture, replay history,
      production ticketing provider, credential path, hosted dependency,
      mutating admin UI, raw sensitive content, raw prompts/outputs, raw tool
      arguments, raw connector payloads, raw approval or policy rationale,
      identity-provider claims, email addresses, or PII was added.
    - Phase 2D item `2D-02` added a Postgres-backed local ticket desk sandbox
      behind the Tool Gateway. The gateway validates all four ticket argument
      contracts, dispatches `ticket.lookup_case`, `ticket.lookup_duplicates`,
      and `ticket.propose_case_update` for seeded support agents/grants, and
      keeps `ticket.update_status` approval-required with no connector
      execution path. Local ticket tables and seeds contain only request refs,
      case refs, account refs, product refs, severity/status categories,
      idempotency/policy refs, connector invocation refs, and safe metadata.
      No support workflow runtime, Temporal activity registration, BFF/UI
      route, eval fixture, replay history, production ticketing provider,
      credential path, hosted dependency, mutating admin UI, raw sensitive
      content, raw prompts/outputs, raw tool arguments, raw connector payloads,
      raw approval or policy rationale, identity-provider claims, email
      addresses, or PII was added.
    - Phase 2D item `2D-03` added the smallest code-defined
      `support_triage` Temporal runtime and replay baseline. The worker
      registers `SupportTriageWorkflow` beside Lighthouse and adds a
      support-specific workflow-event activity. The workflow reuses
      `lighthouse.invoke_agent_runtime` for support classification, context
      lookup, resolution planning, and validation, and reuses
      `lighthouse.invoke_tool_gateway` for ticket case lookup, duplicate
      lookup, and proposed case-update dispatch. Agent Runtime now validates
      `contracts/agents/support_agent_io.schema.json` through the local
      structured boundary and support local route seeds. `ticket.update_status`
      remains approval-required with no connector execution, and provider
      route-version evidence remains Lighthouse-only for this item. No Support
      BFF/UI route, eval fixture, production ticketing provider, reviewer
      decision UI, credential path, hosted dependency, mutating admin UI,
      production connector write, workflow DSL, raw sensitive content, raw
      prompts/outputs, raw tool arguments, raw connector payloads, raw approval
      or policy rationale, identity-provider claims, email addresses, or PII
      was added.
    - Phase 2D item `2D-04` added the support eval and persisted evidence
      baseline for the existing `support_triage` happy path. The eval fixture
      asserts the support path, final completion, support Agent Runtime
      decisions, ticket lookup/duplicate/proposal Tool Gateway verdicts,
      proposed case-update refs, no `ticket.update_status` call, no case-status
      mutation, and safe tenant/correlation/workflow joins. The persistence
      baseline admits support agent roles in `decision_trail_entries` and tests
      that workflow events, support decisions, ticket audit rows, and local
      proposed case-update refs can be joined by safe refs. No Support BFF/UI
      route, production ticketing provider, reviewer decision UI, credential
      path, hosted dependency, mutating admin UI, production connector write,
      ticket status execution, workflow DSL, raw sensitive content, raw
      prompts/outputs, raw tool arguments, raw connector payloads, raw approval
      or policy rationale, identity-provider claims, email addresses, or PII
      was added.
    - Phase 2D item `2D-05` added the safe read-only Support BFF inspection
      path for the existing `support_triage` happy-path evidence. The
      projection aggregates support workflow events from `outbox_events`,
      support Agent Runtime decisions, ticket Tool Gateway verdicts, proposed
      case-update refs, and the approval-required `ticket.update_status` grant
      by safe tenant/correlation/workflow refs. No Support UI route,
      production ticketing provider, reviewer decision UI, credential path,
      hosted dependency, mutating admin UI, production connector write, ticket
      status execution, workflow DSL, raw sensitive content, raw prompts or
      outputs, raw tool arguments, raw connector payloads, raw approval or
      policy rationale, identity-provider claims, email addresses, or PII was
      added.
    - Phase 2E item `2E-00` added ADR 0016 as the production-readiness
      architecture pack scope decision. It defines the future artefact and
      evidence shape for production identity/IAM mapping, secrets and
      credential handling, deployment topology, backup/restore and DR,
      retention and audit storage, incident/on-call integration, managed
      observability, and production provider or connector hardening. No
      migration, service, credential, cloud resource, production connector,
      hosted observability exporter, mutating admin path, reviewer decision
      path, policy apply path, ticket status execution, production provider
      call, or runtime behaviour change was added.
    - Phase 2E item `2E-01` added
      [`production-identity-iam-mapping.md`](production-identity-iam-mapping.md)
      as the production identity and IAM mapping architecture artefact. It
      maps human, workload, agent, invocation, approval, and policy principals
      to future trust domains, tenant/RBAC boundaries, IAM roles or equivalent
      workload identity, safe STS session-name and tag rules, IAM Roles
      Anywhere, SPIFFE/SPIRE, and external IdP refs while keeping business
      authority in Agent Runtime, Tool Gateway, approval audit, policy-change
      audit, and eval gates. No AWS, production SSO, identity-provider
      integration, credential, cloud resource, tenant-admin UI, runtime
      enforcement, production connector, hosted exporter, production provider
      call, or runtime behaviour change was added.
    - Phase 2E item `2E-02` added
      [`secrets-credential-handling.md`](secrets-credential-handling.md) as
      the secrets and credential handling architecture artefact. It defines
      future credential categories, secret-ref naming rules, secret-ref
      catalogue shape, local-to-production configuration boundary, runtime
      injection boundaries, rotation/revocation lifecycle, break-glass
      controls, audit/evidence refs, forbidden-data checklist, required future
      artefacts, evidence expectations, safe field rules, promotion criteria,
      and backlog implications. No secret-manager integration, credential
      entry, credential mutation, actual credential, provider key, connector
      credential, signing key, identity-provider client secret, cloud resource,
      production SSO, IAM enforcement, hosted exporter, production provider
      call, migration, service, runtime enforcement, or runtime behaviour
      change was added.
    - Phase 2E item `2E-03` added
      [`deployment-topology-architecture.md`](deployment-topology-architecture.md)
      as the deployment topology architecture artefact. It defines future
      production service topology, environment classes, deployment unit
      boundaries, network and trust zones, ingress and egress boundaries,
      data-store and event-stream placement, component placement,
      local-to-production boundaries, managed-versus-self-hosted decision
      rules, IaC spike criteria, evidence expectations, safe field rules,
      promotion criteria, and backlog implications. No cloud resource,
      Terraform, Kubernetes/ECS/EKS/Lambda work, DNS, certificate, deployment
      automation, network resource, managed database, production SSO,
      identity-provider integration, IAM enforcement, secret-manager
      integration, credential entry, credential mutation, production connector,
      hosted observability exporter, production provider call, migration,
      service, runtime enforcement, or runtime behaviour change was added.
    - Phase 2E item `2E-04` added
      [`backup-restore-dr-architecture.md`](backup-restore-dr-architecture.md)
      as the backup, restore, and DR architecture artefact. It defines future
      RPO/RTO classes, authoritative store order, backup scope by data class,
      restore responsibility by component, restore dependency order, Temporal
      persistence handling, application Postgres and audit handling,
      event-stream and schema-registry handling, projection rebuild rules,
      telemetry treatment, eval/replay artefact handling, secret metadata
      versus secret value handling, configuration/deployment refs, restore
      drill models, synthetic/local evidence expectations, safe field rules,
      promotion criteria, and backlog implications. No backup automation,
      restore tooling, replication, PITR policy, managed database
      configuration, managed event stream, object storage resource, cloud
      resource, Terraform, Kubernetes/ECS/EKS/Lambda work, DNS, certificate,
      network resource, deployment automation, production SSO,
      identity-provider integration, IAM enforcement, secret-manager
      integration, credential entry, credential mutation, production connector,
      hosted observability exporter, production provider call, migration,
      service, runtime enforcement, or runtime behaviour change was added.
    - Phase 2E item `2E-05` added
      [`retention-audit-storage-architecture.md`](retention-audit-storage-architecture.md)
      as the retention and audit storage architecture artefact. It defines
      future retention classes for telemetry, journey projections,
      audit/accountability, decision trail, Tool Gateway audit, approval and
      policy-change packages, eval/replay artefacts, connector evidence,
      event-stream/schema evidence, secret metadata lifecycle evidence,
      backup/restore/DR evidence, incident/on-call evidence, and optional
      sidecar exports. It also defines audit-storage ownership,
      Postgres-first audit posture, scaling signals, archive/export criteria,
      delete/expire/hold categories, Scylla or append-store evaluation
      triggers, restore/DR interactions, synthetic/local evidence
      expectations, safe field rules, promotion criteria, and backlog
      implications. No retention automation, archive/export job,
      long-retention store, Scylla implementation, migration, managed
      database, object storage resource, cloud resource, hosted exporter,
      service, runtime enforcement, or runtime behaviour change was added.
    - Exit check for the planning pass: the Phase 2 roadmap, ADR, scope
      boundaries, backlog ledger, and handoff cadence are documented before
      implementation starts.

## Phase 1B Governance Failure Work Breakdown

Each fixture is a thin vertical slice that exercises one failure mode end-to-end:
a workflow branch, the agent or gateway decision that triggers it, the audit
row that proves authority was enforced, a replay fixture that demonstrates
deterministic re-execution, and an eval fixture that asserts the path/outcome.
Cross-boundary contracts are frozen after Phase 1A, so fixtures do not require
schema changes — they extend behaviour and seeded policy/audit.

| Fixture | Intended behaviour | Triggering signal |
|---|---|---|
| G-01 Low-confidence research → deeper-research loop | Researcher returns `recommended_next_step="deeper_research"` (or sub-threshold confidence) and the workflow re-runs the researcher with an enriched prompt before falling through to qualification. Bounded by a max-loop counter to escalate after N attempts. | Agent contract `recommended_next_step` (already present); confidence threshold. |
| G-02 Validator rejection → redraft loop | Validator returns `recommended_next_step="redraft"` with a structured reason and the workflow re-enters the drafter with the reason payload. Bounded loop that escalates on exhaustion. | Agent contract `recommended_next_step="redraft"` (already present). |
| G-03 Forbidden write → gateway block | A second seeded tenant or agent has a `block`-mode tool grant for `email.send_response`. Workflow asks for `write`, gateway downgrades to `propose` (already implemented) or blocks; audit row carries the verdict and reason. | Tool grant seed addition; gateway `block` verdict already implemented. |
| G-04 Connector failure → compensation/escalation | Mailpit (or local CRM) connector raises a transient error class, workflow retries within Temporal policy, then enters a compensation activity that records the failed action and escalates. | Connector exception class + activity wrapper; existing retry policy. |
| G-05 Retry exhaustion → DLQ/escalation evidence | Persistent activity failure exhausts the workflow retry policy; workflow catches the exception, marks an outbox row terminal `dlq`, writes a DLQ-shaped audit row, and escalates. | Temporal activity exhaustion; persistence DLQ marker. |
| G-06 Eval and replay coverage | Per-fixture eval assertion file under `chorus/eval/fixtures/` and per-fixture replay history under `tests/workflows/fixtures/`. | Lands incrementally with each of G-01..G-05. |

### Phase 1B Parallelisation Map

This section is retained as delivery history. Phase 1B is complete; the
current reviewer-facing package is [`governance-evidence.md`](governance-evidence.md)
plus the completion ledger below.

The merge-conflict pinch is `chorus/workflows/lighthouse.py`. Each fixture
edits one branch zone in that file; concurrent sessions are safe when their
zones do not overlap. The agent runtime and tool gateway modules are the
secondary collision points.

| Fixture | `lighthouse.py` zone | Other primary file | Collides with |
|---|---|---|---|
| G-01 | research/qualification (lines 92–134) | `chorus/agent_runtime/runtime.py` (deeper-research prompt path) | G-02 only on shared loop-counter helper |
| G-02 | validation (lines 169–198) + drafter re-entry | `chorus/agent_runtime/runtime.py` (validator reason payload) | G-01 only on shared loop-counter helper |
| G-03 | gateway-verdict branch (lines 200–233; reads existing `block` path) | `infrastructure/postgres/seeds/` (new grant), `chorus/tool_gateway/gateway.py` (assertion only) | G-04 on `chorus/tool_gateway/gateway.py` |
| G-04 | gateway-verdict branch + new compensation activity | `chorus/tool_gateway/gateway.py` (connector error class), `chorus/workflows/activities.py` (compensation activity) | G-03 on gateway error path; G-05 on `activities.py` |
| G-05 | agent-runtime retry exhaustion catch + activity-owned DLQ marker | `chorus/workflows/activities.py` (DLQ marker), `chorus/persistence/outbox.py` (DLQ shape) | Everything — structural |
| G-06 | none (additive files) | `chorus/eval/fixtures/<name>.json`, `tests/workflows/fixtures/<name>_history.json` | Per-fixture, no cross-collision |

Historical sequencing used while the fixtures were landing:

1. **Wave A (parallel, 2–3 sessions).** Pick fixtures whose zones do not
   overlap with the in-flight one. If G-01 is in-flight, run **G-02** and
   **G-03** concurrently — `validation`, `gateway-verdict-read`, and
   `research-qualification` are distant zones in `lighthouse.py`.
2. **Wave B (after Wave A merges).** Run **G-04** alone or with G-06 prep
   work. G-04 touches the gateway-verdict branch and `activities.py`; let
   the wave-A fixtures settle so the gateway branch has one author.
3. **Wave C (serial, last).** Run **G-05**. It adds the retry-exhaustion
   evidence path across workflow, activities, and outbox persistence, so it
   only needs to land once and merging it earlier forces every other fixture
   to rebase.
4. **Continuous (G-06).** Each fixture session lands its own eval/replay
   artefacts in step 3 of its branch — they are file-disjoint by design.

### Phase 1C Packaging Ledger

Phase 1C packages the implemented Phase 1A and Phase 1B evidence for
asynchronous review:

- **C-01 (Phase 1C).** Final pass on `docs/evidence-map.md` to cross-link
  every row to landed evidence. Status: done.
- **C-02 (Phase 1C).** README narrative tighten + first-time-reviewer
  checklist. Status: done.
- **C-03 (Phase 1C).** `docs/demo-script.md` walkthrough of the happy
  path with screenshots/screencast notes (Mailpit → Temporal → BFF →
  Grafana → audit by correlation ID). Status: done with script-based capture
  notes; screenshot/screencast stills are optional packaging artefacts.
- **C-04 (Phase 1C).** Governance-evidence narrative — block, retry,
  validator-rejection, deeper-research stories. Status: done in
  [`docs/governance-evidence.md`](governance-evidence.md), which packages
  G-01 through G-05 by review question, trigger, durable evidence, and gate.
- **C-05 (Phase 1C).** Project-facing summary in README and overview.
  Status: done.

### Phase 1B Completion Ledger

| ID | Required item | Evidence artefact | Gate | Status | Notes |
|---|---|---|---|---|---|
| G-01 | Low-confidence research → deeper-research loop with bounded escalation | `chorus/workflows/lighthouse.py`; `chorus/agent_runtime/runtime.py`; `tests/workflows/fixtures/lighthouse_low_confidence_history.json`; `chorus/eval/fixtures/lighthouse_low_confidence.json` | `just test-replay`; `just eval` | done | Workflow records the low-confidence branch, retries once with enriched research input, escalates after retry exhaustion, and eval asserts two researcher decisions plus the enriched second attempt. |
| G-02 | Validator rejection → redraft loop with structured reason | `chorus/workflows/lighthouse.py`; `chorus/agent_runtime/runtime.py`; `tests/workflows/fixtures/lighthouse_validator_redraft_history.json`; `chorus/eval/fixtures/lighthouse_validator_redraft.json`; `tests/workflows/test_lighthouse_workflow.py`; `docs/fixtures/lead-validator-redraft.eml`; `scripts/generate_validator_redraft_history.py` | `just test-replay`; `just eval` | done | Bounded redraft loop (max 2 attempts) with `validator_reason` payload threaded back into the drafter input. |
| G-03 | Forbidden write fixture (gateway block / write→propose downgrade) | `infrastructure/postgres/seeds/001_demo_tenants.sql`; `chorus/tool_gateway/gateway.py`; `tests/workflows/fixtures/lighthouse_forbidden_write_history.json`; `chorus/eval/fixtures/lighthouse_forbidden_write.json` | `just eval`; `just test-replay`; `just test-persistence`; `just contracts-check` | done | `tenant_demo_alt` seeds an explicit denied `email.send_response/write` grant; gateway blocks that exact denied write before downgrade and persists redacted audit evidence. `just test-persistence` skipped because local Postgres was unavailable to the test fixture. |
| G-04 | Connector failure → compensation/escalation | `chorus/connectors/local.py`; `chorus/tool_gateway/gateway.py`; `chorus/workflows/activities.py` (compensation); `chorus/workflows/lighthouse.py`; eval/replay fixtures | `just test-replay`; `just eval` | done | Fixture-scoped Mailpit connector marker raises a transient connector error, the gateway activity retries, the compensation activity records the failed `email.propose_response` action, and the workflow escalates. |
| G-05 | Retry exhaustion → DLQ/escalation evidence | `chorus/workflows/lighthouse.py`; `chorus/workflows/activities.py`; `chorus/persistence/outbox.py` (DLQ marker); `infrastructure/postgres/migrations/004_outbox_dlq_status.sql`; `chorus/eval/fixtures/lighthouse_retry_exhaustion.json`; `tests/workflows/fixtures/lighthouse_retry_exhaustion_history.json` | `just test-replay`; `just eval`; `just test-persistence` | done | Agent-runtime retry exhaustion records a terminal outbox `dlq` row plus `workflow.retry_exhausted.dlq_recorded` audit evidence, then escalates. |
| G-06 | Trace/eval fixtures assert all five governance paths | `chorus/eval/fixtures/`; `tests/workflows/fixtures/` | `just eval`; `just test-replay` | done | Eval and replay coverage now exists for low-confidence research, validator redraft, forbidden write, connector failure compensation, and retry-exhaustion DLQ escalation. |

## Parallel Workstreams

Phase 0 is largely serial: the service layout and contracts must exist before parallel branches can land cleanly. Two strands can overlap once the basic scaffold is up: 0A (Compose + justfile + doctor stub) and 0B (contract drafting + public evidence map + documentation adjustments).

Phase 1A is parallelisable across six workstreams once contracts are stable. Each workstream is its own git branch (or git worktree, mirroring the `~/Work/<project>-worktrees/<branchname>/` convention used elsewhere) merged into `main` as integration points come up green.

| Workstream | Output | Integration point | Dependency |
|---|---|---|---|
| A — Persistence + projection | Postgres schemas, RLS, tenant tests, projection worker path, transactional outbox, Redpanda relay. | Complete. Workstream B can append `workflow_event` rows through `ProjectionStore.record_workflow_event()`; BFF/UI can read `workflow_read_models` without storage policy logic. | Contracts (Phase 0). |
| B — Temporal workflows + activities | Complete. Lighthouse state machine, replay test, deterministic activity boundary, SMTP-receive poll activity, worker CLI, poll-once CLI, containerised worker runtime, task-queue discovery, event subjects, and workflow trace/audit metadata are implemented. | Activities call Agent Runtime and Tool Gateway through stable interfaces. | Contracts (Phase 0); A's outbox shape; F's observability contract. |
| C — Agent Runtime + model boundary | Complete. Agent identity resolution, runtime policy, decision-trail capture, and local structured model boundary are wired behind `lighthouse.invoke_agent_runtime`. | Activity invocation interface; decision-trail rows. | Contracts (Phase 0); A's decision-trail schema; B's worker/runtime boundary. |
| D — Tool Gateway + local connectors | Grants, argument schemas, modes, redaction, idempotency, audit; local connector service against real software (Mailpit, public APIs, local CRM). | Activity invocation interface; tool audit rows. | Contracts (Phase 0); A's tool-audit schema. |
| E — BFF + UI | Lead intake, SSE progress, timeline view, decision-trail view, registry/grants/routing views. | Read-model endpoints; SSE topic. | Contracts (Phase 0); A's read model. |
| F — Observability + ops | OpenTelemetry, Grafana dashboards, doctor command, runbook, dev-loop scaffolding (env handling, scripts, pre-commit, services template, CI). | Cross-cutting; integrates after each workstream lands. | Workstreams A–E producing trace data. |

Workstreams A–C run on the longest critical path (storage + workflow + agent runtime). D, E, F start in parallel as soon as their consumed contracts are stable. Phase 1B governance fixtures attach to A–E once the happy-path runs end-to-end; their parallelisation map and completion ledger live in §"Phase 1B Governance Failure Work Breakdown".

## Phase 1A Completion Ledger

Update this ledger as part of every continuation handoff. A row reaches `done`
only when the evidence artefact exists and the gate has run or the reason it
could not run is recorded in the handoff.

### Workstream A — Persistence and Projection

| ID | Required item | Evidence artefact | Gate | Status | Notes |
|---|---|---|---|---|---|
| A-01 | Postgres tenant, registry, model policy, grant, read-model, audit, history, and outbox schema | `infrastructure/postgres/migrations/001_phase_1a_persistence_foundation.sql` | `just test-persistence` | done | |
| A-02 | Idempotent two-tenant seed data | `infrastructure/postgres/seeds/001_demo_tenants.sql` | `just db-migrate`; `just test-persistence` | done | Seed grows with runtime roles. |
| A-03 | Tenant isolation and RLS fail-closed tests | `tests/persistence/test_postgres_foundation.py` | `just test-persistence` | done | Requires live Postgres. |
| A-04 | Transactional outbox lifecycle | `chorus/persistence/outbox.py`; `tests/persistence/test_postgres_foundation.py` | `just test-persistence` | done | |
| A-05 | Redpanda relay and projection consumer | `chorus/persistence/redpanda.py`; `tests/persistence/test_redpanda_projection.py` | `just test-persistence` | done | Requires live Redpanda. |
| A-06 | Runtime policy read models for BFF/admin inspection | `chorus/persistence/projection.py` | `just test-persistence` | done | |

### Workstream B — Temporal Workflow and Activities

| ID | Required item | Evidence artefact | Gate | Status | Notes |
|---|---|---|---|---|---|
| B-01 | Deterministic Lighthouse state machine | `chorus/workflows/lighthouse.py`; `tests/workflows/test_lighthouse_workflow.py` | `just test-replay`; focused workflow tests | done | |
| B-02 | Contract-shaped workflow event activity | `chorus/workflows/activities.py`; `tests/workflows/test_activities.py` | `just test` | done | Writes through `ProjectionStore.record_workflow_event()`. |
| B-03 | Mailpit HTTP intake, lead parsing, Message-ID dedupe, stable workflow ID, and correlation ID minting | `chorus/workflows/mailpit.py`; `tests/workflows/test_mailpit_intake.py` | focused workflow tests | done | |
| B-04 | Host worker and intake CLI recipes | `chorus/workflows/worker.py`; `chorus/workflows/intake.py`; `justfile` | `just --list`; focused CLI smoke where applicable | done | Host-only is not the final runtime evidence. |
| B-05 | Containerised worker runtime under Compose and service template instrumentation | `services/intake-poller/Dockerfile`; `services/intake-poller/pyproject.toml`; `compose.yml` | `just doctor`; `scripts/dc config` | done | Runs `chorus.workflows.worker` under `opentelemetry-instrument`. |
| B-06 | Temporal worker discovery probe for `lighthouse` task queue | `chorus/doctor.py` | `just doctor` | done | Uses Temporal `DescribeTaskQueue`; no extra port. |
| B-07 | Canonical event schema subjects pinned and checked | `contracts/events/*.schema.json`; `chorus/doctor.py`; schema registration path | `just contracts-check`; `just doctor` | done | `just schemas-register` registers declared subjects. |
| B-08 | Workflow/activity trace propagation and boundary span attributes | `chorus/workflows/worker.py`; `chorus/workflows/mailpit.py`; `chorus/workflows/activities.py` | trace inspection; `just doctor` where possible | done | Required attributes: `chorus.tenant_id`, `chorus.correlation_id`, `chorus.workflow_id`. |
| B-09 | Worker metrics posture documented or implemented | `docs/runbook.md`; optional Prometheus target file | `just doctor` or Grafana/Prometheus inspection | done | OTel metrics flow through the collector; no side `/metrics` app. |
| B-10 | Audit/write trace ID capture for workflow event path | `chorus/workflows/activities.py`; persistence/outbox metadata path | focused tests; trace/audit inspection | done | `outbox_events.metadata` carries `current_otel_ids()` for workflow event writes. |

### Workstream C — Agent Runtime and Model Boundary

| ID | Required item | Evidence artefact | Gate | Status | Notes |
|---|---|---|---|---|---|
| C-01 | Resolve active tenant policy | `chorus/agent_runtime/runtime.py`; `tests/agent_runtime/test_runtime.py` | focused runtime tests | done | Verified with live Postgres runtime tests. |
| C-02 | Resolve approved agent identity, version, lifecycle, owner, capability tags, prompt reference, and prompt hash from registry | `chorus/agent_runtime/runtime.py`; seed data | focused runtime tests; `just test-persistence` | done | |
| C-03 | Resolve approved model route, parameters, fallback policy, and budget cap from policy tables | `chorus/agent_runtime/runtime.py`; seed data | focused runtime tests | done | |
| C-04 | Create invocation IDs and preserve correlation/workflow IDs | `chorus/agent_runtime/runtime.py` | focused runtime tests | done | |
| C-05 | Invoke Phase 1A provider/model boundary for happy path | `chorus/agent_runtime/runtime.py` | focused runtime tests | done | Local structured boundary; commercial SDK adapters deferred. |
| C-06 | Validate Lighthouse agent output contract | `contracts/agents/lighthouse_agent_io.schema.json`; generated models; runtime tests | `just contracts-check`; focused runtime tests | done | |
| C-07 | Persist generated-contract decision-trail records to Postgres | `decision_trail_entries`; `tests/agent_runtime/test_runtime.py` | focused runtime tests; `just test-persistence` | done | Live run persisted four decision rows with OTel metadata. |
| C-08 | Wire `lighthouse.invoke_agent_runtime` activity to runtime without changing workflow interface | `chorus/workflows/activities.py`; activity integration test | focused runtime/activity tests | done | Verified through Mailpit-triggered workflow run. |
| C-09 | Update docs/runbook/evidence map for implemented runtime boundary | `docs/architecture.md`; `docs/runbook.md`; `docs/evidence-map.md`; `services/agent-runtime/README.md` | doc review; relevant gates | done | |

### Workstream D — Tool Gateway and Local Connectors

| ID | Required item | Evidence artefact | Gate | Status | Notes |
|---|---|---|---|---|---|
| D-01 | Gateway request validation against generated tool contracts | `contracts/tools/`; `chorus/tool_gateway/gateway.py` | focused gateway tests; `just contracts-check` | done | Validates generated `ToolCall`, `GatewayVerdict`, `AuditEvent`, and `EmailMessageArgs`. |
| D-02 | Grant lookup and mode enforcement by `(agent_id, tenant_id, tool, mode)` | `chorus/tool_gateway/gateway.py`; `tool_grants` seed | focused gateway tests | done | Covers allowed proposal, write downgrade, approval-required, and block. |
| D-03 | Redaction, idempotency, approval hook, and explicit verdicts | `chorus/tool_gateway/gateway.py`; audit rows | focused gateway tests | done | Audit arguments are policy-redacted; idempotency returns persisted response without re-invoking connectors. |
| D-04 | Local connector service backed by real local/sandbox software | `chorus/connectors/local.py`; `infrastructure/postgres/migrations/003_local_connector_crm.sql`; `services/connectors-local/` | connector/gateway tests | done | Mailpit SMTP connector, Postgres-backed local CRM, and environment-gated Companies House connector. |
| D-05 | Tool/action audit persistence and OTel metadata capture | `tool_action_audit`; `chorus/tool_gateway/gateway.py` | focused gateway tests; trace/audit inspection | done | `metadata` captures `current_otel_ids()` when active. |
| D-06 | Outbound email proposal/send path captured in Mailpit | `chorus/connectors/local.py`; `tests/tool_gateway/test_mailpit_connector.py` | connector/gateway tests | done | Live Mailpit test skips when Mailpit is unavailable; local validation records the run result in the handoff. |

### Workstream E — BFF and UI

| ID | Required item | Evidence artefact | Gate | Status | Notes |
|---|---|---|---|---|---|
| E-01 | BFF read endpoints over workflow projections | `chorus/bff/app.py`; `services/bff/`; `tests/bff/test_app.py`; `tests/bff/test_app_unit.py` | `just test`; `tests/bff` | done | Endpoints expose `workflow_read_models`, `workflow_history_events`, `decision_trail_entries`, `tool_action_audit`, and the runtime policy snapshot under `/api/*` against a real Postgres connection. |
| E-02 | SSE progress stream backed by projections/events | `chorus/bff/app.py` `_progress_events`; `tests/bff/test_app.py::test_bff_progress_sse_streams_projection_events_once` | `just test`; live-Postgres SSE smoke | done | `/api/progress` polls `list_recent_workflow_history` and emits `event: progress` SSE frames; `?workflow_id=` / `?correlation_id=` filters scope to a single run; `?once=true` makes the stream terminate for tests. The read model remains the source of truth. |
| E-03 | Workflow run list/detail and timeline | `frontend/src/routes/index.tsx`; `frontend/src/routes/workflows.$workflowId.tsx`; `frontend/src/api/queries.ts`; `frontend/src/api/sse.ts`; `frontend/src/api/queries.test.ts` | `just test-frontend`; `just test-e2e` | done | Run list and detail queries route through `/api/*`; SSE events invalidate TanStack Query keys for live progress; refresh re-fetches the projection. |
| E-04 | Decision trail, tool verdict, runtime registry, grants, and routing inspection views | `frontend/src/routes/decision-trail.tsx`; `frontend/src/routes/tool-verdicts.tsx`; `frontend/src/routes/registry.tsx`; `frontend/src/routes/grants.tsx`; `frontend/src/routes/routing.tsx` | `just test-frontend` | done | All five inspection views are read-only TanStack tables backed by `/api/decision-trail`, `/api/tool-verdicts`, and `/api/runtime/{registry,grants,routing}`. |
| E-05 | UI survives refresh/reconnect from read model | `frontend/src/routes/workflows.$workflowId.tsx`; `frontend/tests/e2e/smoke.spec.ts::"workflow detail rehydrates from the read model after a refresh"`; `frontend/src/api/queries.test.ts` | `just test-e2e`; `just test-frontend` | done | Every route fetches projections on mount, so `page.reload()` rebuilds the view; SSE merely invalidates query caches. |

### Workstream F — Observability and Ops

| ID | Required item | Evidence artefact | Gate | Status | Notes |
|---|---|---|---|---|---|
| F-01 | Dev-loop scaffold, service template, CI, hooks, and runbook baseline | project scaffold files; CI config | `just doctor-quick`; hooks | done | |
| F-02 | OTel collector, Tempo, Loki, Prometheus, and Grafana provisioning | `compose.yml`; `infrastructure/` | `just doctor` | done | `chorus-intake-poller` is the first service running under the template `opentelemetry-instrument` entrypoint; logs reach Loki via the fluent path, traces reach Tempo, OTel-native metrics reach Prometheus through the collector. |
| F-03 | Grafana dashboards for workflow, gateway, projection, and agent decisions | `infrastructure/grafana/dashboards/` | `just doctor`; dashboard inspection | done | Empty until producers write data. |
| F-04 | Strict doctor probes for completed runtime contracts | `chorus/doctor.py` | `just doctor` | done | Schema-registry strict check fails-closed on declared `x-subject`; `_describe_temporal_task_queue` probes the `lighthouse` queue via `DescribeTaskQueue`. |
| F-05 | Cross-surface correlation by workflow/correlation ID | runbook; OTel/audit metadata; dashboards; `docs/evidence-map.md` | E2E/eval inspection | done | Evidence-map row "Cross-surface correlation by workflow/correlation ID" cites runbook procedure plus the four surfaces. |
| F-06 | Promote operational ADRs when implementation matches them | `adrs/0009-*`; `adrs/0010-*` | doc review | done | Both ADRs moved from `proposed` to `accepted`; bodies updated to cite the implemented evidence. |

### Phase 1A Assurance and Documentation Closeout

| ID | Required item | Evidence artefact | Gate | Status | Notes |
|---|---|---|---|---|---|
| Z-01 | Happy-path eval fixture asserts path, outcome, events, decision trail, tool verdict/audit, cost, latency, and correlation ID | `chorus/eval/run.py`; `chorus/eval/fixtures/lighthouse_happy_path.json`; `tests/eval/test_run.py` | `just eval`; focused eval tests | done | Default run is deterministic and contract-shaped; `CHORUS_EVAL_CORRELATION_ID` or `CHORUS_EVAL_WORKFLOW_ID` adds persisted Postgres evidence checks. |
| Z-02 | Live eval requirements documented without requiring unavailable substrate | `docs/runbook.md`; `README.md`; `docs/architecture.md` | doc review; `just eval` | done | Full live evidence requires a Mailpit-triggered workflow, Postgres evidence, relay/projection, decision trail, and tool audit rows. |
| Z-03 | Phase 1A closeout docs match the implemented happy-path slice | `README.md`; `docs/overview.md`; `docs/architecture.md`; `docs/governance-guardrails.md`; `docs/evidence-map.md`; `docs/runbook.md`; `docs/demo-script.md` | doc review | done | Superseded by the Phase 1C packaging pass for shipped Phase 1B governance/failure evidence. |

### Workstream F status

| Deliverable | State |
|---|---|
| Dev-loop scaffolding (env, `scripts/dc`, first-time setup, prek hooks, editor/dockerignore/gitattributes) | done |
| `services/_template/` (Dockerfile, pyproject, README) | done |
| CI gates (`ci.yml`, `eval.yml`, `replay.yml`, dependabot, issue/PR templates) | done |
| Project-meta (`SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, README badges) | done |
| `frontend/` scaffold seeded with vendored Dense design family | done (Workstream E pre-load) |
| `chorus.doctor` extended to verify Workstream F contract | done |
| `docs/runbook.md` | done (initial; grows with the slice) |
| OpenTelemetry collector pipeline wired through to running services | done — `chorus-intake-poller` runs under the template `opentelemetry-instrument` ENTRYPOINT in `compose.yml`; the worker attaches `temporalio.contrib.opentelemetry.TracingInterceptor`; workflow/activity boundaries call `chorus.observability.set_current_span_attributes()`; audit-write code calls `current_otel_ids()` into `outbox_events.metadata`. Tempo/Loki/Prometheus backends, Grafana datasource provisioning, fluentforward receiver, `file_sd_configs` for per-service Prometheus targets, and the per-service onboarding checklist (services/_template/README.md) all in place |
| Grafana dashboards (workflow timeline, gateway verdicts, projection lag, agent decisions) | done — provisioned via `infrastructure/grafana/{provisioning,dashboards}` against Postgres, Tempo, Loki, and Prometheus datasources. Tempo carries `tracesToLogsV2`/`tracesToMetrics`/`serviceMap` wiring; Loki carries `derivedFields` for `trace_id=…` → Tempo. Empty tables surface as empty panels until Workstreams B/C/D produce data |
| Cross-surface correlation (Temporal ↔ Redpanda ↔ Grafana ↔ UI ↔ audit by workflow ID) | done — evidence-map row "Cross-surface correlation by workflow/correlation ID" filed in `docs/evidence-map.md`; `correlation_id` variable on every dashboard; Tempo span attributes `chorus.tenant_id`/`chorus.correlation_id`/`chorus.workflow_id` stamped at workflow/activity boundaries; `metadata->>'otel.trace_id'` joins Postgres audit rows to Tempo; runbook §"Cross-surface correlation" carries the recipe |
| Phase 1A `doctor` extension (service health, migration readiness, schema registration, workflow worker readiness) | done — `--quick` flag, layered readiness sweeps, Postgres migration check via Workstream A's `schema_migrations` table, TCP/HTTP probes for Redpanda Schema Registry, Temporal frontend, Mailpit, OTel collector, BFF, frontend dev server. Schema-registry check fails-closed on declared `x-subject` values (B-07); Temporal `lighthouse` task-queue discovered via `DescribeTaskQueue` with worker-poller count check (B-06) |
| Operational ADRs — local-only operating model + observability pipeline | accepted ([ADR 0009](../adrs/0009-local-only-operating-model.md), [ADR 0010](../adrs/0010-observability-pipeline.md)) |
| Pyright strict in `just lint` and pre-commit | done |
| Runbook operational procedures (stuck workflow, denied tool audit, contract regeneration, stack reset) | done |

Each workstream description is structured to be a self-contained agent-session prompt: scope, outputs, integration points, and dependency on other workstreams. A parallel-development run launches one agent per workstream against its own branch, all synchronising via the contracts directory and integration points.

## Deferred After Phase 1

- Second business workflow.
- Real third-party connectors.
- Runtime workflow DSL.
- Production auth/SSO.
- Scylla implementation.
- Production cloud deployment and backup/disaster-recovery automation.
- Production identity/IAM implementation, secrets handling, deployment
  topology, retention, DR, incident integration, managed observability, and
  production provider/connector hardening until the relevant Phase 2E
  architecture item explicitly opens them.
- Production commercial provider calls and credential-entry UI until a later
  Phase 2 item explicitly opens them.
- Mutating provider, prompt, route, or grant admin controls before executable
  change-control work explicitly opens them.
- LangGraph checkpoint persistence, durable execution, hosted deployment,
  long-term graph memory, and LangSmith/Langfuse as required dependencies.

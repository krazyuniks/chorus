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
The goal is not to build a generic agent framework. The goal is to prove that
the Phase 1 boundaries can support controlled provider choice, governed runtime
mutation, connector expansion, and a second workflow without losing audit,
evaluation, replay, or authority controls.

## Planning Posture

Phase 2 is planned and 2A has started with contract-only provider governance
work. Phase 1 remains the stable demo baseline until each Phase 2 milestone has
its own evidence, tests, and documentation.

The repository is now the authoritative planning surface. Historical vault
records under `/home/ryan/Work/vault/records/work/projects/chorus/` informed
this plan, especially the SDLC operating model, provider collaboration model,
storage deferrals, and production-readiness notes. Those records are not
runtime authority; this document and the ADRs are.

## Phase 2 Objective

Phase 2 should answer four reviewer questions that Phase 1 deliberately
deferred:

1. How does Chorus safely choose, change, fail over, and audit real model
   providers?
2. How are prompt, model-route, and tool-grant changes proposed, approved,
   rolled back, and evaluated?
3. Can the Tool Gateway mediate a new connector or integration protocol without
   giving agents ambient authority?
4. Can the same orchestration and governance pattern support a second business
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
- Broad framework features that do not improve the evidence map.

## Design Principles

- Preserve the Phase 1 demo. Lighthouse must keep working while Phase 2 grows.
- Runtime policy stays outside prompts. Agent code does not pick providers,
  grant tools, or bypass eval gates.
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
| 2A. Provider and model governance | Add commercial-provider adapter boundaries, model-route promotion rules, failover/degradation policy, budget telemetry, and provider-failure fixtures while retaining the local structured boundary as the default runnable path. | in progress | A reviewer can inspect why a provider/model was selected, prove fallback behaviour under a provider failure fixture, and run eval coverage before and after a route change. |
| 2B. Governed runtime change control | Add audited proposal/approval/rollback flows for prompt references, model routes, budget caps, and tool grants. Keep direct database mutation out of the normal operator path. | planned | A reviewer can propose, approve, apply, inspect, and roll back a policy change with decision trail, audit events, and eval evidence. |
| 2C. Connector expansion and approval hardening | Add one new sandbox or protocol-backed connector behind the Tool Gateway, plus stronger approval, idempotency, retry, and compensation evidence for risky writes. | planned | The connector is usable only through the gateway; approval-required and denied paths are visible in audit, workflow history, and eval fixtures. |
| 2D. Second workflow proof | Add one adjacent business workflow that reuses Agent Runtime, Tool Gateway, contracts, projections, eval, and observability without introducing a workflow DSL. | planned | The second workflow has its own contracts, replay fixtures, eval fixtures, UI inspection path, and cross-surface correlation, while Lighthouse remains intact. |
| 2E. Production-readiness architecture pack | Decide which production concerns should remain design-only and which need thin executable evidence: auth/RBAC, secrets, deployment topology, retention, backup/restore, and incident integration. | planned | ADRs and docs distinguish implemented local evidence from production architecture, with any executable spikes gated and explicitly scoped. |

## Recommended First Workstream: 2A

Start Phase 2 with provider and model governance. It is the smallest expansion
that directly strengthens the "orchestrated agentic platform" story without
adding a second workflow too early.

2A should deliver:

- a provider catalogue contract and Postgres-backed route metadata that can
  represent local, commercial, and disabled providers;
- a model adapter interface behind the existing Agent Runtime boundary;
- at least one commercial-provider adapter path that is disabled unless
  credentials are explicitly supplied;
- deterministic fallback to the local structured boundary when credentials are
  absent or a provider is disabled;
- provider failure, timeout, rate-limit, and budget-exceeded fixtures;
- decision-trail fields that make selected provider, selected model, fallback
  reason, route version, cost estimate, and latency visible;
- eval assertions for route selection, fallback, budget, and validator route
  diversity where the fixture can prove it;
- read-only UI/BFF inspection of provider catalogue, route versions, and
  fallback evidence;
- runbook notes for local credential handling, disabled-provider operation, and
  provider-failure diagnosis.

2A should not implement a full provider-management product. Mutating route
approval belongs in 2B.

## Phase 2A Work Breakdown

| ID | Required item | Evidence artefact | Gate | Status | Notes |
|---|---|---|---|---|---|
| 2A-01 | Provider catalogue and route-version contract | `contracts/governance/`; generated models; samples; `tests/test_contracts.py` | `just contracts-check` | complete | Provider catalogue and immutable route-version schemas represent the local default path and disabled commercial-provider placeholders without enabling provider adapters or mutating admin. Evidence: `just contracts-check`, `just test`, `just test-replay`, `just lint` on 2026-05-03. |
| 2A-02 | Postgres route-version and provider catalogue migration | `infrastructure/postgres/migrations/`; seeds | `just test-persistence` | open | Preserve current Phase 1 route seeds. |
| 2A-03 | Model adapter interface behind Agent Runtime | `chorus/agent_runtime/` | `just test` | open | Workflow activity contract should remain stable. |
| 2A-04 | Disabled-by-default commercial provider adapter | `chorus/agent_runtime/` | focused tests; `just eval` | open | Must run without credentials by falling back or reporting disabled state. |
| 2A-05 | Provider failure and fallback fixture | eval/replay fixture where workflow behaviour changes | `just test-replay`; `just eval` | open | Fixture should prove provider failure is visible, not swallowed. |
| 2A-06 | Decision-trail and audit evidence for route selection | persistence schema/runtime writes/UI projection | `just test`; `just test-frontend` | open | Capture route version, provider/model, fallback reason, cost, latency. |
| 2A-07 | Read-only BFF/UI provider governance views | `chorus/bff/`; `frontend/` | `just test-frontend`; `just test-e2e` | open | Inspection only; no mutating admin yet. |
| 2A-08 | Docs/runbook/evidence alignment | `README.md`; `docs/*`; ADRs | doc review; relevant gates | open | Do not present disabled commercial routes as implemented production use. |

## Phase 2A Evidence Notes

- 2026-05-03: `2A-01` added `contracts/governance/provider_catalogue.schema.json`
  and `contracts/governance/model_route_version.schema.json`, representative
  samples, generated Pydantic models, and contract tests. The sample catalogue
  keeps `local/lighthouse-happy-path-v1` as the approved runnable path and uses
  a disabled commercial placeholder to prove credential and lifecycle metadata
  without implying an active adapter.
- 2026-05-03: Gates passed for `2A-01`: `just contracts-gen`,
  `just contracts-check`, `just test`, `just test-replay`, and `just lint`.
- Next ledger item: `2A-02` Postgres route-version and provider catalogue
  migration.

## Handoff Cadence

Each continuation prompt for Phase 2 should start by naming the milestone and
ledger item, then require the session to update this plan before handoff.

Use this shape:

```text
Continue Chorus Phase 2A: <ledger id and title>.

Read AGENTS.md, docs/architecture.md, adrs/, docs/phase-2-plan.md, and the
current git status first. Keep Lighthouse Phase 1 working. Implement only this
ledger item and its directly required docs/tests. Use just recipes for gates.
Update docs/phase-2-plan.md with status/evidence notes before handoff.
Report commands run, any skipped gates, and the next ledger item.
```

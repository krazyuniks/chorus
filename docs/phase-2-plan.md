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

Phase 2 is planned and 2A has started with contract-only provider governance
work. Phase 1 remains the stable demo baseline until each Phase 2 milestone has
its own evidence, tests, and documentation.

The repository is now the authoritative planning surface. Historical vault
records under `/home/ryan/Work/vault/records/work/projects/chorus/` informed
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
- LangSmith as a required hosted dependency.

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
| 2A. Agent execution and provider governance | Add LangGraph as the first-class agent execution runtime inside Agent Runtime, then continue commercial-provider adapter boundaries, model-route promotion rules, failover/degradation policy, budget telemetry, and provider-failure fixtures while retaining the local structured boundary as the default runnable path. | in progress | A reviewer can inspect which LangGraph execution path ran, why a provider/model was selected, prove fallback behaviour under a provider failure fixture, and run eval coverage before and after a route change. |
| 2B. Governed runtime change control | Add audited proposal/approval/rollback flows for prompt references, model routes, budget caps, and tool grants. Keep direct database mutation out of the normal operator path. | planned | A reviewer can propose, approve, apply, inspect, and roll back a policy change with decision trail, audit events, and eval evidence. |
| 2C. Connector expansion and approval hardening | Add one new sandbox or protocol-backed connector behind the Tool Gateway, plus stronger approval, idempotency, retry, and compensation evidence for risky writes. | planned | The connector is usable only through the gateway; approval-required and denied paths are visible in audit, workflow history, and eval fixtures. |
| 2D. Second workflow proof | Add one adjacent business workflow that reuses Agent Runtime, Tool Gateway, contracts, projections, eval, and observability without introducing a workflow DSL. | planned | The second workflow has its own contracts, replay fixtures, eval fixtures, UI inspection path, and cross-surface correlation, while Lighthouse remains intact. |
| 2E. Production-readiness architecture pack | Decide which production concerns should remain design-only and which need thin executable evidence: auth/RBAC, secrets, deployment topology, retention, backup/restore, and incident integration. | planned | ADRs and docs distinguish implemented local evidence from production architecture, with any executable spikes gated and explicitly scoped. |

## Recommended Current Workstream: 2A

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
alignment are implemented. The next ledger item is provider timeout,
rate-limit, and budget degradation fixture coverage without production provider
calls.

2A should deliver:

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

2A should not implement a full provider-management product, LangGraph durable
execution, LangGraph checkpoint persistence, long-term graph memory,
LangGraph-hosted deployment, or LangSmith as a core dependency. Mutating route
approval belongs in 2B.

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
| 2A-11 | Provider timeout, rate-limit, and budget degradation fixtures | `chorus/agent_runtime/`; `chorus/eval/`; `tests/agent_runtime/`; `tests/eval/`; docs if evidence surfaces change | focused tests; `just eval`; relevant replay if workflow behaviour changes | open | Extend provider-degradation evidence beyond the provider-error fallback fixture. Keep fixtures local/disabled-provider based; do not add production provider calls, credential entry, mutating route admin, or LangGraph durability. |

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
- Next ledger item: `2A-11` Provider timeout, rate-limit, and budget
  degradation fixtures.

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

Next prompt:

```text
Continue Chorus Phase 2A: 2A-11 Provider timeout, rate-limit, and budget degradation fixtures.

Read AGENTS.md, docs/architecture.md, adrs/0012-langgraph-agent-execution-runtime.md,
docs/phase-2-plan.md, and the current git status first. Keep Lighthouse Phase 1
working. Extend the provider-degradation evidence beyond the provider-error
fallback fixture to cover timeout, rate-limit, and budget-exceeded paths where
the current Agent Runtime boundary can represent them. Keep fixtures
local/disabled-provider based unless the docs and ADRs explicitly open a real
provider adapter. Do not add credential entry, mutating provider admin,
production commercial provider calls, LangGraph checkpoint persistence, or
LangGraph durable execution. Run focused Agent Runtime/eval tests plus relevant
just gates. Update docs/phase-2-plan.md with status/evidence notes before
handoff. Report commands run, any skipped gates, and the next ledger item.
```

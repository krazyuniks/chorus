---
type: project-doc
status: design-freeze
date: 2026-04-28
---

# Chorus - Implementation Plan

## Scope Lock

Implementation happens in this repository. Architecture, contracts, code, tests, eval fixtures, and operational docs move together.

Phase 1 builds one evidence-grade vertical slice for Lighthouse, including the happy path and the governance/failure fixtures needed by the architecture evidence map. It also packages the architecture, governance, and evidence artefacts needed to explain the pattern. It does not build a generic agent framework, a SaaS product, production auth, real third-party integrations, cloud deployment, Scylla storage, or a second workflow.

**1A is the first public ship-checkpoint.** Phases 1B (governance/failure fixtures) and 1C (review packaging) are committed continuations that extend the 1A baseline; they are not gating the first usable architecture review.

## Phases and Milestones

| Phase | Milestone | Status | Exit criteria |
|---|---|---|---|
| 0. Foundation | Docs, ADRs, architecture/governance artefacts, local dev contract, contracts, and service layout exist. | done | README explains run/review path; architecture, guardrails, evidence map, and ADRs are linked. |
| 1A. Lighthouse happy-path slice | Send fixture lead email through Mailpit, run Temporal workflow, invoke governed agents, mediate at least one tool action, project state, stream progress, and show audit trail. | done | A reviewer can run one command, send the fixture lead to Mailpit SMTP, see workflow state advance through the BFF/UI, inspect Temporal/Redpanda/Grafana/audit by correlation ID, and run the happy-path eval. |
| 1B. Governance and failure evidence | Add blocked write, low-confidence research, validator rejection, connector failure, retry/exhaustion, and escalation paths. | open | Failure fixtures produce expected workflow branches, audit verdicts, DLQ or escalation records, and passing trace/eval checks. |
| 1C. Review packaging | Tighten README, screenshots or screencast notes, demo script, architecture links, governance evidence, and project-facing summary. | open | Asynchronous reviewers can answer the evidence-map questions in under 15 minutes; guided demo fits 3 minutes without opening an editor. |

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
   - Phase 0A scaffold finishing pass landed alongside Workstream F's opening shipment: `.env.example` + parameterised `compose.yml` with `chown-init`; `scripts/dc` wrapper and `scripts/first-time-setup.sh` host bootstrap; prek-driven `.pre-commit-config.yaml`; `.editorconfig`/`.dockerignore`/`.gitattributes`; `services/_template/` (Dockerfile + pyproject + README); CI workflows (`ci.yml`, `eval.yml`, `replay.yml`) with dependabot, issue/PR templates; `SECURITY.md`/`CONTRIBUTING.md`/`CHANGELOG.md`; README badges + first-time-setup section; `docs/runbook.md` (the Workstream F operational artefact); `frontend/` scaffold (React 19 + Vite 8 + TS + TanStack Router/Query + Tailwind v4 + Radix) seeded with the Dense design family vendored wholesale from a sibling design system project (no external dependency, no `@radianit/*` references).
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
   - Current state: `chorus.agent_runtime` resolves active tenant policy, approved agent versions, prompt references/hashes, approved model routes, and budget caps from Workstream A's Postgres tables. `lighthouse.invoke_agent_runtime` uses that runtime behind Workstream B's stable activity boundary, returns generated-contract Lighthouse agent output, and persists `AgentInvocationRecord`-shaped decision-trail rows with active OTel IDs in `metadata`. The happy path uses the local `lighthouse-happy-path-v1` structured model boundary; commercial provider SDK adapters remain deferred behind the same boundary.
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
    - Current state: Workstream F provides the local observability substrate and cross-surface correlation recipe. `just eval` runs the Phase 1A Lighthouse happy-path fixture, validates contract-shaped workflow/agent/tool evidence, and optionally inspects persisted Postgres evidence for a supplied workflow/correlation ID.
    - Exit check: Temporal, Redpanda, Grafana, UI, and audit views can be correlated from one workflow ID; happy-path eval passes.

11. **(Phase 1A) Phase 1A documentation pass** — *delivered (Phase 1A closeout)*
    - Update README, overview, architecture, governance guardrails, runbook, demo script, and evidence map to reflect the implemented slice.
    - Current state: documentation names the implemented Phase 1A happy path, marks Phase 1B governance/failure fixtures as open, and makes the 3-minute Mailpit → Temporal → Redpanda/projection → BFF/UI/Grafana/audit → eval review path explicit.
    - Exit check: docs describe the current code and no deferred feature is presented as implemented.

12. **(Phase 1C) Architecture artefact packaging — final pass**
    - Update `docs/evidence-map.md` (drafted in Phase 0) to cross-link every row to its now-implemented evidence: code paths, eval fixtures, audit views, dashboards, ADRs.
    - Exit check: an architecture reviewer can see both the working system and the programme-level adoption model in one navigation pass.

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
| G-05 Retry exhaustion → DLQ/escalation evidence | Persistent activity failure exhausts the workflow retry policy; workflow catches the exception, marks an outbox row as `failed`, writes a DLQ-shaped audit row, and escalates. | Temporal activity exhaustion; new persistence DLQ marker. |
| G-06 Eval and replay coverage | Per-fixture eval assertion file under `chorus/eval/fixtures/` and per-fixture replay history under `tests/workflows/fixtures/`. | Lands incrementally with each of G-01..G-05. |

### Phase 1B Parallelisation Map

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
| G-05 | module-level retry policy + try/except wrapping every activity | `chorus/workflows/activities.py` (DLQ marker), `chorus/persistence/outbox.py` (DLQ shape) | Everything — structural |
| G-06 | none (additive files) | `chorus/eval/fixtures/<name>.json`, `tests/workflows/fixtures/<name>_history.json` | Per-fixture, no cross-collision |

Recommended sequencing once the in-flight 1B fixture lands cleanly:

1. **Wave A (parallel, 2–3 sessions).** Pick fixtures whose zones do not
   overlap with the in-flight one. If G-01 is in-flight, run **G-02** and
   **G-03** concurrently — `validation`, `gateway-verdict-read`, and
   `research-qualification` are distant zones in `lighthouse.py`.
2. **Wave B (after Wave A merges).** Run **G-04** alone or with G-06 prep
   work. G-04 touches the gateway-verdict branch and `activities.py`; let
   the wave-A fixtures settle so the gateway branch has one author.
3. **Wave C (serial, last).** Run **G-05**. It rewraps every activity call
   site and changes the retry policy module-globally, so it only needs to
   land once and merging it earlier forces every other fixture to rebase.
4. **Continuous (G-06).** Each fixture session lands its own eval/replay
   artefacts in step 3 of its branch — they are file-disjoint by design.

### Phase 1B → 1C overlap

Phase 1C work is unblocked once the demo path is *stable*, not once every
1B fixture has landed. The Phase 1A happy path is already demo-stable, so
Phase 1C streams that depend only on the happy path can start the moment
the first 1B fixture validates without breaking the happy-path replay
test. Concretely:

- **C-01 (Phase 1C).** Final pass on `docs/evidence-map.md` to cross-link
  every Phase 1A row to landed evidence. Unblocked now; can start in
  parallel with Wave A.
- **C-02 (Phase 1C).** README narrative tighten + first-time-reviewer
  checklist. Unblocked now.
- **C-03 (Phase 1C).** `docs/demo-script.md` walkthrough of the happy
  path with screenshots/screencast notes (Mailpit → Temporal → BFF →
  Grafana → audit by correlation ID). Unblocked now; defer screenshots
  until Wave A merges so the UI is stable.
- **C-04 (Phase 1C).** Governance-evidence narrative — block, retry,
  validator-rejection, deeper-research stories. Blocked on G-01..G-05;
  starts after Wave B.
- **C-05 (Phase 1C).** Project-facing summary in README and overview.
  Unblocked now.

C-01/C-02/C-03/C-05 are editorial-voice work and should land through one
session to keep framing consistent. Run them sequentially in a single
1C session running alongside the parallel 1B sessions.

Worktree convention for parallel 1B sessions:
`~/Work/chorus-worktrees/phase-1b-<fixture>/` with branch
`phase-1b/<fixture>` (e.g. `phase-1b/g-02-validator-redraft`). Each
session merges into `main` after `just doctor`, `just test`,
`just test-replay`, and the new eval fixture pass.

### Phase 1B Completion Ledger

| ID | Required item | Evidence artefact | Gate | Status | Notes |
|---|---|---|---|---|---|
| G-01 | Low-confidence research → deeper-research loop with bounded escalation | `chorus/workflows/lighthouse.py`; `chorus/agent_runtime/runtime.py`; `tests/workflows/fixtures/lighthouse_low_confidence_history.json`; `chorus/eval/fixtures/lighthouse_low_confidence.json` | `just test-replay`; `just eval` | open | Agent contract already supports `recommended_next_step="deeper_research"`. |
| G-02 | Validator rejection → redraft loop with structured reason | `chorus/workflows/lighthouse.py`; `chorus/agent_runtime/runtime.py`; `tests/workflows/fixtures/lighthouse_validator_redraft_history.json`; `chorus/eval/fixtures/lighthouse_validator_redraft.json` | `just test-replay`; `just eval` | open | Agent contract already supports `recommended_next_step="redraft"`. |
| G-03 | Forbidden write fixture (gateway block / write→propose downgrade) | `infrastructure/postgres/seeds/`; `chorus/tool_gateway/gateway.py` (assertion); `tests/workflows/fixtures/lighthouse_forbidden_write_history.json`; `chorus/eval/fixtures/lighthouse_forbidden_write.json` | `just eval`; `just test-persistence` | open | Reuses existing block/downgrade code; primarily a seed + assertion fixture. |
| G-04 | Connector failure → compensation/escalation | `chorus/connectors/local.py`; `chorus/workflows/activities.py` (compensation); `chorus/workflows/lighthouse.py`; eval/replay fixtures | `just test-replay`; `just eval` | open | Add a transient-failure injection toggle on the connector for fixture replay. |
| G-05 | Retry exhaustion → DLQ/escalation evidence | `chorus/workflows/lighthouse.py`; `chorus/workflows/activities.py`; `chorus/persistence/outbox.py` (DLQ marker); eval/replay fixtures | `just test-replay`; `just eval`; `just test-persistence` | open | Structural — last in sequence to avoid forcing every other fixture to rebase. |
| G-06 | Trace/eval fixtures assert all five governance paths | `chorus/eval/fixtures/`; `tests/workflows/fixtures/` | `just eval`; `just test-replay` | open | Lands incrementally with G-01..G-05. |

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
| Z-03 | Phase 1A docs match implemented slice and do not present Phase 1B fixtures as shipped | `README.md`; `docs/overview.md`; `docs/architecture.md`; `docs/governance-guardrails.md`; `docs/evidence-map.md`; `docs/runbook.md`; `docs/demo-script.md` | doc review | done | 3-minute review path is explicit. |

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

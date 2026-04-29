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

| Phase | Milestone | Exit criteria |
|---|---|---|
| 0. Foundation | Docs, ADRs, architecture/governance artefacts, local dev contract, contracts, and service layout exist. | README explains run/review path; architecture, guardrails, evidence map, and ADRs are linked. |
| 1A. Lighthouse happy-path slice | Send fixture lead email through Mailpit, run Temporal workflow, invoke governed agents, mediate at least one tool action, project state, stream progress, and show audit trail. | A reviewer can run one command, send the fixture lead to Mailpit SMTP, see workflow state advance, inspect Temporal/Redpanda/Grafana/audit by correlation ID, and run the happy-path eval. |
| 1B. Governance and failure evidence | Add blocked write, low-confidence research, validator rejection, connector failure, retry/exhaustion, and escalation paths. | Failure fixtures produce expected workflow branches, audit verdicts, DLQ or escalation records, and passing trace/eval checks. |
| 1C. Review packaging | Tighten README, screenshots or screencast notes, demo script, architecture links, governance evidence, and project-facing summary. | Asynchronous reviewers can answer the evidence-map questions in under 15 minutes; guided demo fits 3 minutes without opening an editor. |

## Detailed Work Breakdown

Items are tagged with the phase that owns them. **(Phase 0)** items must complete before Phase 1 begins. **(Phase 1A)** items are the first public ship-checkpoint. **(Phase 1B)** items extend failure-fixture evidence. **(Phase 1C)** items finalise review packaging.

1. **(Phase 0) Developer workflow and service layout**
   - Create docs tree, ADR tree, architecture/governance artefact set, service layout, Compose skeleton, command runner, and `doctor` command contract.
   - Exit check: repo opens cleanly, docs are linked, and local prerequisites are explicit.

2. **(Phase 0) Contracts first**
   - Define JSON Schemas for lead intake, workflow events, agent invocation records, tool calls, gateway verdicts, audit events, and eval fixture expectations.
   - Generate Pydantic models and add sample validation/drift checks.
   - Current state: the initial Phase 0 contract set, representative samples, generated Pydantic models, and `just contracts-check` drift gate are implemented.
   - Exit check: contract CI fails on schema/model/sample drift.

3. **(Phase 0) Public evidence map**
   - Draft `docs/evidence-map.md` mapping architecture capabilities to specific Chorus artefacts: enterprise guardrails, provider governance, prompt/model/tool change control, safety/eval lifecycle, observability, and operational adoption.
   - Cross-link each row to the supporting doc/code/test location (initially doc-only; code links populate during 1A).
   - Exit check: a reviewer can read the map and locate evidence for each responsibility without searching.

4. **(Phase 1A) Persistence and projection**
   - Add Postgres schema for tenants, agent registry, model policy, tool grants, workflow read model, decision trail, episodic history, and outbox.
   - Add RLS and tenant-isolation tests for two seeded tenants.
   - Current state: the Phase 1A storage foundation migration, two-tenant seed data, migration runner, minimal projection/read-model adapter, outbox shape, and real-Postgres RLS/fail-closed tests are implemented.
   - Exit check: read model survives refresh/reconnect and tenant leakage tests fail closed.

5. **(Phase 1A) Temporal workflow**
   - Implement Lighthouse workflow states: intake, research/qualification, draft, validate, propose/send, escalate.
   - Keep workflow logic deterministic and push IO into activities.
   - Exit check: happy-path workflow replay test passes and Temporal Console shows the state machine clearly.

6. **(Phase 1A) Agent Runtime**
   - Resolve agent version, prompt reference, lifecycle state, model route, budget caps, tenant policy, and invocation ID before each agent call.
   - Capture decision-trail records with correlation IDs.
   - Exit check: reviewer can inspect which agent/model/prompt ran and why.

7. **(Phase 1A) Tool Gateway and local connector service**
   - Build one gateway in front of a local connector service running **real software** (no mocks, no hand-rolled fakes per project policy): Mailpit for SMTP capture, real public APIs for company research, and a Postgres-backed local CRM service implementing the connector contract end-to-end.
   - Enforce grants, argument schemas, modes, idempotency, redaction, approval hook, and audit events.
   - Exit check: at least one allowed action and one blocked/downgraded action are visible in audit, and the email-send path produces a real Mailpit-captured message.

8. **(Phase 1A) Events, outbox, and UI progress**
   - Publish schema-governed events through outbox to Redpanda.
   - Feed Postgres projection and SSE progress from the event stream.
   - Exit check: UI progress, Redpanda topic events, and read model agree by correlation ID.

9. **(Phase 1A) Lighthouse UI and read-only admin**
   - Provide the Mailpit-triggered workflow run list/detail, dev-only fixture replay, workflow timeline, decision trail, tool verdicts, runtime registry, grants, and routing views.
   - Keep the UI dense, plain, and data-first.
   - Exit check: the 3-minute demo can be performed without opening an editor.

10. **(Phase 1A) Observability and assurance**
    - Add OpenTelemetry traces/logs/metrics, Grafana dashboard, and happy-path eval fixtures.
    - Exit check: Temporal, Redpanda, Grafana, UI, and audit views can be correlated from one workflow ID; happy-path eval passes.

11. **(Phase 1A) Phase 1A documentation pass**
    - Update README, overview, architecture, governance guardrails, runbook, demo script, and evidence map to reflect the implemented slice.
    - Exit check: docs describe the current code and no deferred feature is presented as implemented.

12. **(Phase 1C) Architecture artefact packaging — final pass**
    - Update `docs/evidence-map.md` (drafted in Phase 0) to cross-link every row to its now-implemented evidence: code paths, eval fixtures, audit views, dashboards, ADRs.
    - Exit check: an architecture reviewer can see both the working system and the programme-level adoption model in one navigation pass.

## Phase 1B Governance Failure Work Breakdown

- Add low-confidence research branch and deeper-research activity.
- Add validator rejection loop with structured reason.
- Add connector failure fixture and compensation or escalation path.
- Add forbidden write fixture with block or proposal downgrade.
- Add retry exhaustion and DLQ/escalation evidence.
- Extend trace/eval fixtures to assert all governance paths.

## Parallel Workstreams

Phase 0 is largely serial: the service layout and contracts must exist before parallel branches can land cleanly. Two strands can overlap once the basic scaffold is up: 0A (Compose + justfile + doctor stub) and 0B (contract drafting + public evidence map + documentation adjustments).

Phase 1A is parallelisable across six workstreams once contracts are stable. Each workstream is its own git branch (or git worktree, mirroring the `~/Work/<project>-worktrees/<branchname>/` convention used elsewhere) merged into `main` as integration points come up green.

| Workstream | Output | Integration point | Dependency |
|---|---|---|---|
| A — Persistence + projection | Postgres schemas, RLS, tenant tests, projection workers, outbox. | Read-model endpoints exposed for BFF; outbox publishes to Redpanda. | Contracts (Phase 0). |
| B — Temporal workflows + activities | Lighthouse state machine, replay test, deterministic activity boundary, SMTP-receive poll activity (reads Mailpit HTTP API, dedupes by Message-ID, starts Lighthouse per new lead — see ADR 0008). | Activities call Agent Runtime and Tool Gateway through stable interfaces. | Contracts (Phase 0); A's outbox shape. |
| C — Agent Runtime + model boundary | Agent identity resolution, runtime policy, decision-trail capture, model router with provider catalogue. | Activity invocation interface; decision-trail rows. | Contracts (Phase 0); A's decision-trail schema. |
| D — Tool Gateway + local connectors | Grants, argument schemas, modes, redaction, idempotency, audit; local connector service against real software (Mailpit, public APIs, local CRM). | Activity invocation interface; tool audit rows. | Contracts (Phase 0); A's tool-audit schema. |
| E — BFF + UI | Lead intake, SSE progress, timeline view, decision-trail view, registry/grants/routing views. | Read-model endpoints; SSE topic. | Contracts (Phase 0); A's read model. |
| F — Observability + ops | OpenTelemetry, Grafana dashboards, doctor command, runbook. | Cross-cutting; integrates after each workstream lands. | Workstreams A–E producing trace data. |

Workstreams A–C run on the longest critical path (storage + workflow + agent runtime). D, E, F start in parallel as soon as their consumed contracts are stable. Phase 1B governance fixtures (Workstream G) attach to A–E once the happy-path runs end-to-end.

Each workstream description is structured to be a self-contained agent-session prompt: scope, outputs, integration points, and dependency on other workstreams. A parallel-development run launches one agent per workstream against its own branch, all synchronising via the contracts directory and integration points.

## Deferred After Phase 1

- Second business workflow.
- Real third-party connectors.
- Runtime workflow DSL.
- Production auth/SSO.
- Scylla implementation.
- Production cloud deployment and backup/disaster-recovery automation.

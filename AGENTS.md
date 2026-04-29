# Chorus - Agent Guide

> For the full system design, read [docs/architecture.md](./docs/architecture.md). For delivery phasing and workstream boundaries, read [docs/implementation-plan.md](./docs/implementation-plan.md).

## Authority Order

When a task concerns architecture, runtime behaviour, contracts, governance, or implementation direction, use this order:

1. [docs/architecture.md](./docs/architecture.md)
2. [adrs/](./adrs/)
3. [docs/governance-guardrails.md](./docs/governance-guardrails.md)
4. [docs/implementation-plan.md](./docs/implementation-plan.md)
5. [docs/evidence-map.md](./docs/evidence-map.md)
6. [README.md](./README.md)
7. This file

Architecture and docs move with code. If behaviour, boundaries, contracts, commands, or evidence surfaces change, update the matching docs in the same work.

## Project Shape

Chorus is a reference implementation of governed multi-agent workflow orchestration for enterprise operational processes. Chorus is the architecture artefact; Lighthouse is the Phase 1 proof scenario.

Phase 1 implements one evidence-grade vertical slice: an inbound lead email enters through Mailpit, starts a durable Temporal Lighthouse workflow, invokes governed agents, mediates tool actions through a Tool Gateway, persists audit/projection state in Postgres, emits schema-governed events through Redpanda, and exposes progress/evidence through the BFF/UI and eval harness.

The repo is currently design-frozen for Phase 1 and in Phase 0/1A scaffold work. Do not broaden scope into a generic agent framework, SaaS product, cloud deployment, production auth, or a second workflow unless the project docs are explicitly changed.

## How To Run Commands

Use `just` for project tasks and discovery.

```bash
just --list
just doctor
just contracts-check
just test
just lint
```

Prefer existing recipes over ad-hoc commands. Use `uv run ...` only for focused Python commands when no `just` recipe exists or when the recipe itself documents that invocation. Frontend commands run from `frontend/` only when the relevant `just` recipe is missing.

Do not run `just down-volumes` unless explicitly requested; it destroys local data.

## Stack

| Concern | Technology |
|---|---|
| Durable orchestration | Temporal Python SDK |
| Agent runtime | Python, FastAPI, PydanticAI |
| Tool mediation | FastAPI Tool Gateway |
| Storage | Postgres |
| Events | Redpanda Community Edition + Schema Registry |
| Contracts | JSON Schema -> generated Pydantic |
| Frontend | React, Vite, TypeScript, TanStack, Tailwind |
| BFF | FastAPI + server-sent events |
| Local connectors | Mailpit, Companies House/public APIs, Postgres-backed local CRM |
| Observability | OpenTelemetry + Grafana stack |
| Assurance | pytest, Vitest, Playwright, Temporal replay, trace/eval fixtures |

## Core Rules

**Evidence before breadth.** Build the narrow Lighthouse slice with inspectable controls before adding generic framework capability.

**No mocks for architecture evidence.** Infrastructure and connector behaviour must use real software in sandbox/local mode. Mailpit, Postgres, Redpanda, Temporal, and local connector services are part of the proof.

**Contracts are canonical.** Cross-boundary payloads belong in `contracts/` as JSON Schema. Generated Pydantic models, samples, and drift checks move with schema changes.

**Temporal owns workflow state.** Workflow code must stay deterministic: no random values, wall-clock reads, network IO, database IO, model calls, or connector calls inside workflow logic. Effectful work belongs in activities. Workflow changes need replay coverage.

**Agents have no ambient authority.** Agents reason and propose. Connectors are invoked only through the Tool Gateway, which owns grants, argument schema validation, mode enforcement, redaction, idempotency, approval hooks, verdicts, and audit events.

**Audit and telemetry are separate.** Postgres decision trail and tool audit records answer accountability questions. OpenTelemetry/Grafana/console surfaces answer operational questions. Every material operation carries a correlation ID.

**Evaluation is a release control.** Agent, prompt, model-route, workflow, gateway, and governance changes require relevant eval or replay coverage, or a documented exception in the architecture/evidence docs.

## Component Boundaries

| Component | Owns | Does not own |
|---|---|---|
| Lighthouse UI | Workflow progress, decision trail, tool verdict, registry/grants/routing inspection, eval views. | Workflow state, policy mutation, connector calls. |
| BFF | Read endpoints, SSE progress stream, UI-facing projections. | Orchestration, model calls, connector calls. |
| Intake poller | Mailpit polling, Message-ID dedupe, lead parsing, workflow start. | Business decisions after workflow start. |
| Temporal workflow | Durable state machine, retries, timers, waits, branches, escalation flow. | IO, model calls, database writes, connector calls inside deterministic workflow code. |
| Agent Runtime | Agent registry resolution, prompt references, model routing, budgets, invocation IDs, decision-trail capture. | External action authority. |
| Tool Gateway | Grants, schemas, modes, redaction, idempotency, approvals, verdicts, action audit. | Agent reasoning, model routing, workflow state. |
| Local connectors | Contract-faithful CRM, research, email proposal/send in sandbox/local mode. | Production writes to closed third-party systems. |
| Projection worker | Redpanda consumption and Postgres read-model updates. | Critical workflow state. |
| Eval harness | Fixture execution and assertions over path, outcome, authority, cost, latency, and evidence. | Runtime policy mutation. |

## Frontend Guidance

The UI is a dense, data-first inspection surface, not a marketing page.

- No card layouts.
- No decorative hero sections.
- No mutating admin UI for registry, routing, or grants in Phase 1.
- Use tables, timelines, plain text, filters, and read-only detail views optimised for architecture review.
- UI state must survive refresh/reconnect by reading projections; SSE is a progress stream, not the source of truth.
- Use `playwright-cli` for browser validation when UI behaviour changes.

## Testing And Gates

Use the smallest gate that proves the change, then run broader gates before handing off meaningful implementation work.

| Command | Purpose |
|---|---|
| `just doctor` | Scaffold/runtime readiness checks. |
| `just contracts-check` | Contract scaffold and later schema/model/sample drift checks. |
| `just test` | Python tests. |
| `just test-replay` | Temporal replay tests. |
| `just test-frontend` | Frontend test suite. |
| `just test-e2e` | Playwright E2E tests. |
| `just eval` | Trace/eval fixtures. |
| `just lint` | Python and frontend linting. |

When code changes, update the matching docs and run the relevant gates. If a documented command is scaffold-only or not yet implemented for Phase 1A, say that plainly in the handoff.

## Local Runtime

`compose.yml` defines the local evidence substrate:

- Postgres: `localhost:5432`
- Redpanda Kafka API: `localhost:9092`
- Redpanda Schema Registry: `localhost:8081`
- Redpanda Console: `http://localhost:8080`
- Temporal: `localhost:7233`
- Temporal UI: `http://localhost:8233`
- Mailpit SMTP: `localhost:1025`
- Mailpit UI/API: `http://localhost:8025`
- Grafana: `http://localhost:3001`
- OTLP: `localhost:4317` and `localhost:4318`

Use `just up`, `just status`, and `just logs <service>` for normal local operations.

## Git And Scope

Keep edits scoped to the requested work and respect existing user changes in the worktree. Conventional commits are preferred. Do not add AI attribution to commits, docs, or generated artefacts.

Do not commit secrets, provider keys, real customer data, production credentials, or private records. Phase 1 uses local/sandbox data only.

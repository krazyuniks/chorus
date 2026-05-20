# Chorus - Agent Guide

> For the architectural thesis, read [docs/transformation/](./docs/transformation/) and [docs/architecture.md](./docs/architecture.md). For the project overview, read [docs/overview.md](./docs/overview.md). For the reset phases, read [docs/transformation/engineering-reset-roadmap.md](./docs/transformation/engineering-reset-roadmap.md).

## Authority Order

When a task concerns architecture, runtime behaviour, contracts, governance, or implementation direction, use this order:

1. [docs/transformation/](./docs/transformation/) - the reset bundle, the architectural authority
2. [docs/architecture.md](./docs/architecture.md)
3. [docs/overview.md](./docs/overview.md)
4. the R1 product and domain artefacts in [docs/](./docs/) (`product-brief.md`, `domain-model.md`, `r1-*.md`)
5. [adrs/](./adrs/)
6. [docs/evidence-map.md](./docs/evidence-map.md)
7. [docs/runbook.md](./docs/runbook.md)
8. [README.md](./README.md)
9. This file

Architecture and docs move with code. If behaviour, boundaries, contracts, commands, or evidence surfaces change, update the matching docs in the same work.

## Project Shape

Chorus is a hexagonal, ports-and-adapters exemplar for governed agentic systems, with data-contract-first design at every port. Six named ports - intake, LLM provider, connector, audit / transcript, projection sink, observability sink - separate the domain core from the outside world. The thesis is in [docs/transformation/engineering-thesis.md](./docs/transformation/engineering-thesis.md); the architecture reference is [docs/architecture.md](./docs/architecture.md).

The project is in a transformation reset. R0.5 (the design codification of the thesis), R1 (product and domain reframing), R2 (documentation architecture refactor), and the ADR writing pass are complete; the reset decisions are recorded in ADRs 0017 to 0020. The next phase is R3 (contract and code terminology refactor), then R4 (local POC readiness across UC1, UC2, UC3). Work from the reset bundle and [docs/transformation/engineering-reset-roadmap.md](./docs/transformation/engineering-reset-roadmap.md); do not resume any pre-reset continuation cadence.

The runtime code is the pre-reset implementation: a durable Temporal workflow (Lighthouse), an Agent Runtime, a Tool Gateway, Postgres audit and projections, Redpanda events, a read-only BFF and UI, and an OpenTelemetry and Grafana stack. It exercises all six ports but still carries pre-reset names. R3 moves the code onto the named-port surface; the four engineering smells R3 resolves are in [docs/transformation/code-refactor-directions.md](./docs/transformation/code-refactor-directions.md). The pre-reset phase history (Phase 0 through Phase 2E) is preserved in [docs/transformation/phase-2-archive.md](./docs/transformation/phase-2-archive.md). Do not broaden scope into a top-level agent framework replacing Temporal, a SaaS product, a production customer-data path, production deployment, production SSO, credential entry, or a workflow DSL unless the project docs and ADRs explicitly change.

## How To Run Commands

Use `just` for project tasks and discovery.

```bash
just --list
just doctor
just contracts-check
just test
just lint
```

Prefer existing recipes over ad-hoc commands. Use `uv run ...` only for focused Python commands when no `just` recipe exists or when the recipe itself documents that invocation. Frontend commands run from `frontend/` only when the relevant `just` recipe is missing; the frontend uses **npm** (not pnpm).

Do not run `just down-volumes` unless explicitly requested; it destroys local data.

## First-Time Setup

`./scripts/first-time-setup.sh` is the idempotent host bootstrap. It installs `just`, `uv`, Python 3.14, `prek`, runs `uv sync --all-extras`, copies `.env.example` to `.env` if missing, and registers prek-managed git hooks. Re-run any time host tooling changes.

`scripts/dc` is the canonical wrapper for `docker compose`: it sources `.env`, exports `UID`/`GID` from the host, and execs `docker compose`. Use `scripts/dc` (or recipes that route through it) instead of bare `docker compose` so environment handling stays consistent across the stack.

`compose.yml` parameterises every credential, port, and image tag through `${VAR:-default}`. Override values by editing `.env`; see `.env.example` for the full set. The `chown-init` service rewrites bind-mounted ownership on startup so files created inside containers stay owned by the host user.

## Pre-commit Gate

`.pre-commit-config.yaml` is prek-compatible (drop-in for `pre-commit`). Builtins enforce hygiene; local hooks run `just lint`, `just contracts-check`, and JSON syntax over `contracts/`. Register with `just install-hooks`; reproduce CI locally with `just hooks`. Do not bypass with `--no-verify` (project policy).

## CI

`.github/workflows/ci.yml` runs lint, contracts-check, doctor, Python tests, and frontend lint/test on every push and PR. `replay.yml` and `eval.yml` run their respective gates for the deterministic replay and governance/eval evidence package. Treat a red CI as the same severity as a red local `just doctor`; both signal a workstream contract slipping.

## Service Template

`services/_template/` is the canonical scaffold for new Python services. Copy the directory, rename it, customise `Dockerfile` `CMD`/`EXPOSE`, declare deps in `pyproject.toml`, and wire the service into `compose.yml`. The template is multi-stage uv-based, runs as a non-root user matching `${UID}:${GID}`, and inherits ruff config from the root.

## Stack

| Concern | Technology |
|---|---|
| Durable orchestration | Temporal Python SDK |
| Agent runtime | Python, FastAPI boundary, LangGraph inside Agent Runtime |
| Tool mediation | FastAPI Tool Gateway |
| Storage | Postgres |
| Events | Redpanda Community Edition + Schema Registry |
| Contracts | JSON Schema -> generated Pydantic |
| Frontend | React, Vite, TypeScript, TanStack, Tailwind |
| BFF | FastAPI + server-sent events |
| Local connectors | Mailpit, Companies House/public APIs, Postgres-backed local CRM, Radicale-backed local CalDAV sandbox, Postgres-backed local ticket desk sandbox |
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

When code changes, update the matching docs and run the relevant gates. If a documented command is unavailable because the live stack is not running, or because a named post-Phase-1 deferral is still out of scope, say that plainly in the handoff.

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
- Radicale / CalDAV sandbox: `http://localhost:5232`
- Grafana: `http://localhost:3001`
- OTLP: `localhost:4317` and `localhost:4318`

Use `just up`, `just status`, and `just logs <service>` for normal local operations.

## Git And Scope

Keep edits scoped to the requested work and respect existing user changes in the worktree. Conventional commits are preferred. Do not add AI attribution to commits, docs, or generated artefacts.

Do not commit secrets, provider keys, real customer data, production credentials, or private records. Phase 1 uses local/sandbox data only.

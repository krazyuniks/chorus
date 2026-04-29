# Chorus

<!-- TODO: replace <owner> when the repo is published -->
[![ci](https://github.com/<owner>/chorus/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/<owner>/chorus/actions/workflows/ci.yml)
[![contracts](https://github.com/<owner>/chorus/actions/workflows/ci.yml/badge.svg?branch=main&job=contracts-check)](https://github.com/<owner>/chorus/actions/workflows/ci.yml)
[![doctor](https://github.com/<owner>/chorus/actions/workflows/ci.yml/badge.svg?branch=main&job=doctor)](https://github.com/<owner>/chorus/actions/workflows/ci.yml)
[![tests](https://github.com/<owner>/chorus/actions/workflows/ci.yml/badge.svg?branch=main&job=test-python)](https://github.com/<owner>/chorus/actions/workflows/ci.yml)
[![replay](https://github.com/<owner>/chorus/actions/workflows/replay.yml/badge.svg?branch=main)](https://github.com/<owner>/chorus/actions/workflows/replay.yml)
[![eval](https://github.com/<owner>/chorus/actions/workflows/eval.yml/badge.svg?branch=main)](https://github.com/<owner>/chorus/actions/workflows/eval.yml)

Chorus is a reference implementation of governed multi-agent workflow orchestration for enterprise operational processes. It demonstrates how agentic AI can be integrated into a business process without losing durable orchestration, explicit authority boundaries, traceability, safety controls, and regression discipline.

The Phase 1 business slice is **Lighthouse**, an inbound-lead concierge for a fictional small business: a customer email arrives, agents intake, research, qualify, draft, validate, and either propose-and-send or escalate.

Chorus is the architecture artefact. Lighthouse is the proof scenario.

## Status

Design-frozen 2026-04-29. Phase 0 foundation scaffolding and the initial contract gate are in place. Phase 1A has started with the Postgres persistence foundation: tenant-scoped registry/policy/grant tables, workflow projections, decision trail, tool/action audit, episodic history, transactional outbox, demo tenant seeds, and RLS isolation tests. Phase 1A (the first public ship-checkpoint) builds the Lighthouse vertical slice end-to-end. See [`docs/implementation-plan.md`](docs/implementation-plan.md) for phasing and the parallel-workstream model.

## First-time setup

```zsh
./scripts/first-time-setup.sh && just up && just doctor
```

`first-time-setup.sh` provisions the local toolchain (uv, just, hooks); `just up` brings the Compose substrate online; `just doctor` verifies scaffold readiness.

## Daily commands

```zsh
just up                # bring the local stack online
just status            # show Compose service state
just logs <service>    # tail logs for a specific service
just doctor            # scaffold and runtime readiness checks
just contracts-check   # JSON Schema, generated model, and sample drift gate
just test              # Python tests
just lint              # Python and frontend linters
just demo              # send the fixture lead through Mailpit (Phase 1A)
```

`just --list` is the discovery command. See [`AGENTS.md`](AGENTS.md) for the full gate hierarchy and which gate proves which kind of change.

## Review path

For an asynchronous reviewer (~15 minutes):

1. [`docs/overview.md`](docs/overview.md) — project brief, review path, demo shape, and decision-record pointer.
2. [`docs/evidence-map.md`](docs/evidence-map.md) — engineering claims and where to inspect the supporting artefacts.
3. [`docs/architecture.md`](docs/architecture.md) — principles-first architecture reference: domain language, boundaries, runtime flow, contracts, testing, operations, and deferrals.
4. [`docs/governance-guardrails.md`](docs/governance-guardrails.md) — enterprise governance posture and control matrix.
5. [`adrs/`](adrs/) — accepted Phase 1 architectural decision record.

## Stack

Temporal (Python SDK) for durable orchestration. Python + FastAPI + PydanticAI agent runtime. Postgres for audit, policy materialisation, outbox, and projections. Redpanda Community Edition for schema-governed event distribution. React + Vite + TypeScript + TanStack frontend with FastAPI + SSE BFF. JSON Schema → generated Pydantic for contracts. Mailpit (SMTP capture and intake), Companies House API (research), and a Postgres-backed local CRM service as the connector substrate — real software, sandbox boundary, no mocks. OpenTelemetry + Grafana for observability. pytest, Vitest, Playwright, Temporal replay, and trace/eval fixtures for assurance.

## Principles

- **Governed agent adoption, not autonomous agent novelty.** Evidence value is in the controls.
- **No mocks, no hand-rolled fakes.** Connectors run real software in sandbox or local mode.
- **Evidence-first scope.** One vertical slice with convincing boundaries beats a broad framework skeleton.
- **Documentation in lock-step with code.** The artefact set evolves with the implementation.
- **Deferrals are explicit.** What's out of Phase 1 is named, not implied.

## Demo

Phase 1A's demo trigger is real SMTP intake via Mailpit. A real email addressed to `leads@chorus.local` is sent to Mailpit's local SMTP port `1025`; a Temporal poller activity reads new messages, deduplicates by Message-ID, and starts a Lighthouse workflow per new lead. See [ADR 0008](adrs/0008-email-intake-via-mailpit.md). A polished screencast is deferred to backlog until the application reaches a holistic working state.

## Local persistence

Postgres migrations live in [`infrastructure/postgres/migrations`](infrastructure/postgres/migrations). Demo tenant seed data lives in [`infrastructure/postgres/seeds`](infrastructure/postgres/seeds). Apply them with `just db-migrate` after the local Postgres service is running. The persistence tests use real Postgres and can be run with `just test-persistence`; set `CHORUS_TEST_ADMIN_DATABASE_URL` when the local Postgres host port is not `5432`.

## License

MIT. See [`LICENSE`](LICENSE).

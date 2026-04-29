# Chorus

[![ci](https://github.com/krazyuniks/chorus/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/krazyuniks/chorus/actions/workflows/ci.yml)
[![contracts](https://github.com/krazyuniks/chorus/actions/workflows/ci.yml/badge.svg?branch=main&job=contracts-check)](https://github.com/krazyuniks/chorus/actions/workflows/ci.yml)
[![doctor](https://github.com/krazyuniks/chorus/actions/workflows/ci.yml/badge.svg?branch=main&job=doctor)](https://github.com/krazyuniks/chorus/actions/workflows/ci.yml)
[![tests](https://github.com/krazyuniks/chorus/actions/workflows/ci.yml/badge.svg?branch=main&job=test-python)](https://github.com/krazyuniks/chorus/actions/workflows/ci.yml)
[![replay](https://github.com/krazyuniks/chorus/actions/workflows/replay.yml/badge.svg?branch=main)](https://github.com/krazyuniks/chorus/actions/workflows/replay.yml)
[![eval](https://github.com/krazyuniks/chorus/actions/workflows/eval.yml/badge.svg?branch=main)](https://github.com/krazyuniks/chorus/actions/workflows/eval.yml)

Chorus is a reference implementation of governed multi-agent workflow orchestration for enterprise operational processes. It demonstrates how agentic AI can be integrated into a business process without losing durable orchestration, explicit authority boundaries, traceability, safety controls, and regression discipline.

The Phase 1 business slice is **Lighthouse**, an inbound-lead concierge for a fictional small business: a customer email arrives, agents intake, research, qualify, draft, validate, and either propose-and-send or escalate.

Chorus is the architecture artefact. Lighthouse is the proof scenario.

## Status

Design-frozen 2026-04-29. Phase 1A is the current first public ship-checkpoint: Postgres persistence/projections, Mailpit intake, the Temporal Lighthouse workflow, Agent Runtime, Tool Gateway, BFF/UI inspection surfaces, OpenTelemetry/Grafana scaffolding, and the happy-path eval are implemented. Phase 1B governance/failure fixtures remain open and are not presented as shipped evidence. See [`docs/implementation-plan.md`](docs/implementation-plan.md) for phasing and the workstream ledger.

## First-time setup

```zsh
./scripts/first-time-setup.sh && just up && just doctor
```

`first-time-setup.sh` provisions the local toolchain (uv, just, hooks); `just up` brings the Compose substrate online; `just doctor` verifies scaffold readiness.

## Daily commands

```zsh
just up                # bring the local stack online
just db-migrate        # apply Postgres migrations and demo seed
just schemas-register  # register Redpanda Schema Registry subjects
just status            # show Compose service state
just logs <service>    # tail logs for a specific service
just doctor            # scaffold and runtime readiness checks
just contracts-check   # JSON Schema, generated model, and sample drift gate
just test              # Python tests
just lint              # Python and frontend linters
just demo              # send the fixture lead through Mailpit (Phase 1A)
just worker            # run the Lighthouse Temporal worker
just intake-once       # poll Mailpit once and start workflows for new leads
just relay-once        # publish pending workflow events to Redpanda
just project-once      # project Redpanda workflow events into Postgres read models
just eval              # run the Phase 1A happy-path eval fixture
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

Phase 1A's demo trigger is real SMTP intake via Mailpit. A real email addressed to `leads@chorus.local` is sent to Mailpit's local SMTP port `1025`; the Mailpit poll activity reads messages through the HTTP API, deduplicates by Message-ID using a stable Message-ID-derived Temporal workflow ID, and starts a Lighthouse workflow per new lead. Run `just up`, `just db-migrate`, `just schemas-register`, then use `just demo`, `just intake-once`, `just relay-once`, and `just project-once` to trigger and project the run. Inspect the BFF/UI, Temporal, Redpanda, Grafana, decision trail, and tool audit by `correlation_id`, then run `just eval`. See [ADR 0008](adrs/0008-email-intake-via-mailpit.md) and [`docs/demo-script.md`](docs/demo-script.md).

`just eval` always runs the deterministic Phase 1A happy-path fixture. To assert a live run's persisted Postgres evidence as well, pass the workflow join key after the relay/projection path has processed events:

```zsh
CHORUS_EVAL_CORRELATION_ID=<correlation-id> just eval
```

## Local persistence

Postgres migrations live in [`infrastructure/postgres/migrations`](infrastructure/postgres/migrations). Demo tenant seed data lives in [`infrastructure/postgres/seeds`](infrastructure/postgres/seeds). Apply them with `just db-migrate` after the local Postgres service is running. The migration and seed path is idempotent and checksum-protected.

Activities should append `workflow_event` rows through `ProjectionStore.record_workflow_event()`. The outbox relay claims due rows with `FOR UPDATE SKIP LOCKED`, marks them `publishing`, publishes canonical `workflow_event` payloads to Redpanda, then marks rows `sent` or `failed` with retry metadata. The projection worker consumes Redpanda workflow events and applies `ProjectionStore.apply_workflow_event()` idempotently into `workflow_read_models` and `workflow_history_events`.

The Lighthouse workflow emits `lead.received`, `workflow.started`, step started/completed, and terminal workflow events through the `lighthouse.record_workflow_event` activity. The workflow never writes projections directly; the BFF/UI observe progress through Workstream A read models after the outbox relay and projection worker have processed those events.

The persistence tests use real Postgres and Redpanda. Run the full Workstream A gate with `just test-persistence` when the default ports are available; set `CHORUS_TEST_ADMIN_DATABASE_URL` and `CHORUS_REDPANDA_BOOTSTRAP_SERVERS` when the local Compose ports are overridden.

## License

MIT. See [`LICENSE`](LICENSE).

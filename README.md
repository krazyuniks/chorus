# Chorus

Chorus is a reference implementation of governed multi-agent workflow orchestration for enterprise operational processes. It demonstrates how agentic AI can be integrated into a business process without losing durable orchestration, explicit authority boundaries, traceability, safety controls, and regression discipline.

The Phase 1 business slice is **Lighthouse**, an inbound-lead concierge for a fictional small business: a customer email arrives, agents intake, research, qualify, draft, validate, and either propose-and-send or escalate.

Chorus is the architecture artefact. Lighthouse is the proof scenario.

## Status

Design-frozen 2026-04-29. Phase 0 foundation scaffolding is underway. Phase 1A (the first public ship-checkpoint) builds the Lighthouse vertical slice end-to-end. See [`docs/implementation-plan.md`](docs/implementation-plan.md) for phasing and the parallel-workstream model.

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

## License

MIT. See [`LICENSE`](LICENSE).

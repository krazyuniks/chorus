# Chorus

[![ci](https://github.com/krazyuniks/chorus/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/krazyuniks/chorus/actions/workflows/ci.yml)
[![contracts](https://github.com/krazyuniks/chorus/actions/workflows/ci.yml/badge.svg?branch=main&job=contracts-check)](https://github.com/krazyuniks/chorus/actions/workflows/ci.yml)
[![doctor](https://github.com/krazyuniks/chorus/actions/workflows/ci.yml/badge.svg?branch=main&job=doctor)](https://github.com/krazyuniks/chorus/actions/workflows/ci.yml)
[![tests](https://github.com/krazyuniks/chorus/actions/workflows/ci.yml/badge.svg?branch=main&job=test-python)](https://github.com/krazyuniks/chorus/actions/workflows/ci.yml)
[![replay](https://github.com/krazyuniks/chorus/actions/workflows/replay.yml/badge.svg?branch=main)](https://github.com/krazyuniks/chorus/actions/workflows/replay.yml)
[![eval](https://github.com/krazyuniks/chorus/actions/workflows/eval.yml/badge.svg?branch=main)](https://github.com/krazyuniks/chorus/actions/workflows/eval.yml)

Chorus is a reference implementation of governed multi-agent workflow orchestration for enterprise operational processes. It demonstrates how agentic AI can participate in a business process without losing durable orchestration, explicit authority boundaries, traceability, safety controls, and regression discipline.

The Phase 1 business slice is **Lighthouse**, an inbound-lead concierge for a fictional small business: a customer email arrives, agents intake, research, qualify, draft, validate, and either propose-and-send or escalate.

Chorus is the architecture artefact. Lighthouse is the proof scenario.

## Status

Transformation reset opened on 2026-05-19. Feature development and the
one-item Phase 2E continuation cadence are paused while the project is
refocused around a stronger client-facing domain, ubiquitous language,
contract-first business logic, local POC readiness, and a separate optional
deployment phase. See [`docs/transformation/`](docs/transformation/) for the
active reset bundle and use it before resuming development.

Design-frozen for Phase 1 on 2026-04-29. Phase 1A, Phase 1B, and Phase 1C are implemented: Postgres persistence/projections, Mailpit intake, the Temporal Lighthouse workflow, Agent Runtime, Tool Gateway, BFF/UI inspection surfaces, OpenTelemetry/Grafana scaffolding, the happy-path eval, governance/failure fixtures, and the asynchronous review package are shipped evidence.

Phase 2 planning opened on 2026-05-03 and pivoted on 2026-05-07 to make LangGraph the first-class agent execution runtime inside the existing Agent Runtime boundary. Phase 2A is complete: the provider/model-governance groundwork remains in place; LangGraph execution, decision-trail graph metadata, the disabled commercial provider adapter boundary, provider-failure/timeout/rate-limit/budget fallback fixture evidence, route-selection audit metadata, read-only BFF/UI provider and graph-execution views, and the matching docs/runbook/evidence alignment are implemented. Phase 2B is complete: ADR 0013 defines the identity, authority, observability, user-journey, and audit boundary; the docs-first observability, workload-principal, invocation-authority, human-approval audit lifecycle, policy-change governance workflow, and optional LLM observability sidecar evaluation are complete. Phase 2C is complete: ADR 0014 selects a local CalDAV calendar connector candidate for connector expansion and approval hardening; calendar argument schemas, a local Radicale sandbox, Tool Gateway-dispatched read/propose paths, approval-required write packages, approved local apply evidence for idempotent create/retry/compensation, and safe read-only BFF calendar status/audit projection are implemented. Phase 2D is complete: ADR 0015 selects local Support Desk Triage as the second workflow proof; safe support/ticket contracts, a Postgres-backed local ticket desk sandbox behind the Tool Gateway, the code-defined `support_triage` Temporal workflow runtime and replay baseline, support eval plus persisted evidence, and a safe read-only Support BFF inspection path now cover ticket lookup, duplicate lookup, proposed case updates, workflow events, Agent Runtime decisions, ticket Tool Gateway verdicts, proposed case-update refs, and the approval-required ticket status write boundary while ticket status writes remain unexecuted. Phase 2E has started docs-first: ADR 0016 scopes the production-readiness architecture pack for production identity/IAM mapping, secrets, deployment topology, backup/restore and DR, retention and audit storage, incident/on-call integration, managed observability, and production provider or connector hardening before any production-readiness code; 2E-01 adds the production identity and IAM mapping architecture, 2E-02 adds the secrets and credential handling architecture, 2E-03 adds the deployment topology architecture, 2E-04 adds the backup, restore, and DR architecture, and 2E-05 adds the retention and audit storage architecture. Support UI routes, production commercial provider calls, credential entry, credential mutation, production SSO, production identity-provider integration, production connector writes, mutating admin controls, hosted observability dependencies, Lighthouse calendar workflow branches, calendar eval fixtures, LangGraph durability, cloud resources, secret-manager integration, deployment automation, backup automation, restore tooling, retention jobs, archive/export jobs, long-retention store implementation, and runtime production-readiness behaviour remain out of scope. See [`docs/phase-2-plan.md`](docs/phase-2-plan.md), [`docs/production-identity-iam-mapping.md`](docs/production-identity-iam-mapping.md), [`docs/secrets-credential-handling.md`](docs/secrets-credential-handling.md), [`docs/deployment-topology-architecture.md`](docs/deployment-topology-architecture.md), [`docs/backup-restore-dr-architecture.md`](docs/backup-restore-dr-architecture.md), [`docs/retention-audit-storage-architecture.md`](docs/retention-audit-storage-architecture.md), [ADR 0011](adrs/0011-phase-2-governed-platform-expansion.md), [ADR 0012](adrs/0012-langgraph-agent-execution-runtime.md), [ADR 0013](adrs/0013-identity-authority-observability-boundaries.md), [ADR 0014](adrs/0014-connector-expansion-approval-hardening-scope.md), [ADR 0015](adrs/0015-second-workflow-proof-scope.md), [ADR 0016](adrs/0016-production-readiness-architecture-pack-scope.md), and [`docs/implementation-plan.md`](docs/implementation-plan.md) for the current scope.

## First-time setup

```zsh
./scripts/first-time-setup.sh && just up && just doctor
```

`first-time-setup.sh` provisions the local toolchain (uv, just, hooks); `just up` brings the Compose substrate online; `just doctor` verifies scaffold readiness.

## First-time reviewer checklist

1. Read [`docs/overview.md`](docs/overview.md), then [`docs/evidence-map.md`](docs/evidence-map.md), before opening implementation files.
2. Bring the stack to the review baseline: `./scripts/first-time-setup.sh && just up && just db-migrate && just schemas-register && just doctor`.
3. Trigger one Lighthouse run: `just demo && just intake-once && just relay-once && just project-once`.
4. Inspect the run by `correlation_id` in the Lighthouse UI/BFF, Temporal UI, Redpanda Console, Grafana, `decision_trail_entries`, and `tool_action_audit`.
5. Run the release-style check: `just eval`. For a live run after projection, use `CHORUS_EVAL_CORRELATION_ID=<correlation-id> just eval`.

The walkthrough in [`docs/demo-script.md`](docs/demo-script.md) keeps the happy-path demo to three minutes. [`docs/governance-evidence.md`](docs/governance-evidence.md) packages the Phase 1B failure and authority fixtures for follow-up inspection.

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
just demo              # send the fixture lead through Mailpit
just worker            # run the Lighthouse Temporal worker
just intake-once       # poll Mailpit once and start workflows for new leads
just relay-once        # publish pending workflow events to Redpanda
just project-once      # project Redpanda workflow events into Postgres read models
just eval              # run the happy-path, Phase 1B governance, Phase 2A provider-fallback, and Phase 2D support eval fixtures
```

`just --list` is the discovery command. See [`AGENTS.md`](AGENTS.md) for the full gate hierarchy and which gate proves which kind of change.

## Review path

For an asynchronous reviewer (~15 minutes):

1. [`docs/overview.md`](docs/overview.md) — project brief, review path, demo shape, and decision-record pointer.
2. [`docs/evidence-map.md`](docs/evidence-map.md) — engineering claims and where to inspect the supporting artefacts.
3. [`docs/governance-evidence.md`](docs/governance-evidence.md) — packaged Phase 1B failure and authority evidence.
4. [`docs/architecture.md`](docs/architecture.md) — principles-first architecture reference: domain language, boundaries, runtime flow, contracts, testing, operations, and deferrals.
5. [`docs/phase-2-plan.md`](docs/phase-2-plan.md) — planned governed-platform expansion after the Phase 1 evidence baseline.
6. [`docs/governance-guardrails.md`](docs/governance-guardrails.md) — enterprise governance posture and control matrix.
7. [`docs/runbook.md`](docs/runbook.md) — concrete local commands and cross-surface correlation recipe.
8. [`adrs/`](adrs/) — accepted architectural decision record.

## Stack

Temporal Python SDK for durable business workflow orchestration. Custom Python Agent Runtime with LangGraph for per-invocation agent execution inside that boundary. Postgres for audit, policy materialisation, outbox, provider catalogue, local CRM/ticket sandboxes, and projections. Redpanda Community Edition for schema-governed event distribution. React + Vite + TypeScript + TanStack frontend with FastAPI + SSE BFF. JSON Schema → generated Pydantic for contracts. Mailpit (SMTP capture and intake), Companies House API (research), a Postgres-backed local CRM service, a Radicale-backed local CalDAV sandbox, and a Postgres-backed local ticket desk sandbox as the connector substrate — real software, sandbox boundary, no mocks. OpenTelemetry + Grafana for observability. pytest, Vitest, Playwright, Temporal replay, and trace/eval fixtures for assurance.

## Principles

- **Governed agent adoption, not autonomous agent novelty.** Evidence value is in the controls.
- **Agent framework inside the boundary.** LangGraph belongs inside Agent Runtime; Temporal remains the durable workflow owner and Tool Gateway remains the action authority.
- **No mocks, no hand-rolled fakes.** Connectors run real software in sandbox or local mode.
- **Evidence-first scope.** One vertical slice with convincing boundaries beats a broad framework skeleton.
- **Documentation in lock-step with code.** The artefact set evolves with the implementation.
- **Deferrals are explicit.** What's out of Phase 1 is named, not implied.

## Demo

The demo trigger is real SMTP intake via Mailpit. A real email addressed to `leads@chorus.local` is sent to Mailpit's local SMTP port `1025`; the Mailpit poll activity reads messages through the HTTP API, deduplicates by Message-ID using a stable Message-ID-derived Temporal workflow ID, and starts a Lighthouse workflow per new lead. Run `just up`, `just db-migrate`, `just schemas-register`, then use `just demo`, `just intake-once`, `just relay-once`, and `just project-once` to trigger and project the run. Inspect the BFF/UI, Temporal, Redpanda, Grafana, decision trail, and tool audit by `correlation_id`, then run `just eval`. See [ADR 0008](adrs/0008-email-intake-via-mailpit.md), [`docs/demo-script.md`](docs/demo-script.md), and [`docs/governance-evidence.md`](docs/governance-evidence.md).

`just eval` runs the deterministic happy-path fixture and all Phase 1B governance/failure fixtures. To assert a live demo run's persisted Postgres evidence as well, pass the workflow join key after the relay/projection path has processed events; the live assertion is applied to the default happy-path fixture while the governance fixtures remain deterministic unless selected explicitly:

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

---
type: project-doc
status: phase-0
date: 2026-04-29
---

# Chorus - Local Runbook

This runbook covers the **local sandbox** runtime only. Phase 1 is design-frozen
to local/sandbox operation; production deployment, on-call rotation, and
incident response are explicit Phase 1 deferrals (see
[implementation-plan.md](./implementation-plan.md)). The runbook is the
Workstream F operational artefact; it grows with the slice.

## First-time host setup

```bash
./scripts/first-time-setup.sh
```

Idempotent. Installs `just`, `uv`, Python 3.14, `prek`; verifies Docker and
`gh` are present; runs `uv sync --all-extras`; copies `.env.example` to `.env`
if missing; registers prek-managed git hooks. Re-run any time host tooling
changes.

## Bring the stack up

```bash
just env       # ensure .env exists
just up        # docker compose up -d via scripts/dc
just status    # confirm services healthy
just doctor    # verify scaffold + workstream F + compose validity
```

`scripts/dc` is the canonical wrapper: it sources `.env`, exports `UID`/`GID`
from the host, and execs `docker compose`. Use it in scripts and ad-hoc
operations to keep environment handling consistent.

## Daily commands

| Command | Purpose |
|---|---|
| `just up` / `just down` | Bring the substrate up or down. |
| `just status` | Compose service status. |
| `just logs <service>` | Tail logs for one service. |
| `just doctor` | Scaffold + dev-loop readiness check. |
| `just contracts-check` | Schema/model/sample drift gate. |
| `just db-migrate` | Apply Postgres migrations and demo seed (Workstream A). |
| `just test` / `just test-replay` / `just test-persistence` | Python gates. |
| `just test-frontend` / `just test-e2e` | Frontend gates. |
| `just lint` / `just fmt` | Linters and formatters across Python and frontend. |
| `just hooks` | Run every prek hook against the whole tree. |
| `just demo` | Send the fixture lead via Mailpit (Phase 1A). |

## Local endpoints

| Service | URL / port |
|---|---|
| Postgres | `localhost:${CHORUS_PG_PORT:-5432}` |
| Redpanda Kafka API | `localhost:${REDPANDA_KAFKA_PORT:-9092}` |
| Redpanda Schema Registry | `localhost:${REDPANDA_SCHEMA_REGISTRY_PORT:-8081}` |
| Redpanda Console | `http://localhost:${REDPANDA_CONSOLE_PORT:-8080}` |
| Temporal | `localhost:${TEMPORAL_PORT:-7233}` |
| Temporal UI | `http://localhost:${TEMPORAL_UI_PORT:-8233}` |
| Mailpit SMTP | `localhost:${MAILPIT_SMTP_PORT:-1025}` |
| Mailpit UI / HTTP API | `http://localhost:${MAILPIT_HTTP_PORT:-8025}` |
| Grafana | `http://localhost:${GRAFANA_PORT:-3001}` |
| OTLP gRPC / HTTP | `localhost:${OTEL_GRPC_PORT:-4317}` / `localhost:${OTEL_HTTP_PORT:-4318}` |
| BFF | `localhost:${BFF_PORT:-8000}` |
| Frontend | `http://localhost:${FRONTEND_PORT:-5173}` |

Override any of these in `.env`. Compose interpolates at config time; rerun
`just doctor` after edits to catch typos.

## Common failure modes

### Permission denied on bind-mounted files

The `chown-init` service rewrites ownership on `infrastructure/` and `tmp/` at
container startup. If a service writes elsewhere under the workspace and
hits root-owned paths, extend `chown-init` in `compose.yml` rather than
chowning by hand.

### Port already allocated

Another local stack is bound to the default port. Set the relevant
`*_PORT` variable in `.env`; defaults are documented in `.env.example`.

### `just doctor` fails on missing path

Each Workstream lands files in a known layout; the doctor's required-paths
list mirrors that contract. Treat a missing-path failure as a workstream
contract violation, not a doctor bug. Fix the missing artefact or update
`chorus/doctor.py` if the contract has legitimately moved.

### Docker compose fails validation

Run `./scripts/dc config` directly to see the rendered compose file. The
most common cause is an unset variable that lacks a `${VAR:-default}`
fallback; add the default in `compose.yml` and document it in `.env.example`.

### Pre-commit hooks reject a commit

Run `just hooks` to reproduce the failure outside the commit boundary.
Builtins are auto-fix where possible; lint and contracts gates require
addressing the reported issue. Never bypass with `--no-verify` (project
policy).

## Observability surfaces

Phase 1A ships OpenTelemetry traces/logs/metrics through the OTel collector
into Grafana. Workstream F's exit criterion is that Temporal, Redpanda,
Grafana, the UI, and the audit views can be correlated from one workflow ID.
Until those surfaces land, the runbook is intentionally thin.

## CI gates

The `.github/workflows/ci.yml` pipeline runs lint, contracts-check, doctor,
Python tests, and frontend lint/test on every push and PR. `eval.yml` and
`replay.yml` run their respective gates with `continue-on-error` until the
fixtures land in Phase 1A. Treat a red CI as the same severity as a red
local `just doctor`; both signal a project-level contract slipping.

## Deferrals (Phase 1)

- Production deployment, secret management, on-call rotation, incident response.
- Real third-party connectors and credentials.
- Cloud-hosted observability backends.

These are documented in [implementation-plan.md §Deferred After Phase 1](./implementation-plan.md).

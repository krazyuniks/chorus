# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/). Versioning will follow semantic versioning once Phase 1A ships its first tagged release.

## [Unreleased]

### Added

- Phase 0 architecture and governance documentation: `docs/overview.md`, `docs/architecture.md`, `docs/governance-guardrails.md`, `docs/evidence-map.md`, and `docs/implementation-plan.md`.
- ADRs 0001 through 0008 covering the accepted Phase 1 architectural decisions.
- Contracts skeleton under `contracts/` with the initial Phase 0 schema set, representative samples, and the JSON Schema to Pydantic generation gate exposed as `just contracts-check`.
- Local runtime substrate via `compose.yml` (Postgres, Redpanda Community Edition, Schema Registry, Redpanda Console, Temporal, Mailpit, Grafana, OpenTelemetry collector).
- `justfile` task runner with recipes for stack lifecycle, doctor, contracts, tests, replay, eval, lint, and format.
- `chorus.doctor` Phase 0 readiness command and `chorus.contracts` scaffold (drift gate + generation entry points).
- **Workstream F first pass — dev-loop scaffolding:** `.env.example` and parameterised `compose.yml` (every credential, port, image, UID/GID through `${VAR:-default}`); `chown-init` service for bind-mount ownership; `scripts/dc` wrapper sourcing `.env` + exporting host UID/GID; `scripts/first-time-setup.sh` idempotent host bootstrap (just, uv, Python 3.14, prek); prek-driven `.pre-commit-config.yaml` with hygiene + `just lint`/`just contracts-check`/contracts JSON validation; `.editorconfig`, `.dockerignore`, `.gitattributes`.
- **Workstream F first pass — services template:** `services/_template/` (multi-stage uv Dockerfile, pyproject stub inheriting root ruff config, README) as the canonical scaffold for new Python services.
- **Workstream F first pass — CI gates:** `.github/workflows/ci.yml` (lint-python, contracts-check, doctor, test-python, lint-frontend, test-frontend), `eval.yml` and `replay.yml` (continue-on-error until fixtures land), `dependabot.yml`, issue and PR templates.
- **Workstream F first pass — operational artefacts:** `docs/runbook.md` (local-runtime ops; the named Workstream F deliverable), `chorus.doctor` extended to verify Workstream F + Workstream A contracts in named sections.
- **Workstream E pre-load:** `frontend/` scaffold (React 19, Vite 8, TypeScript, TanStack Router/Query, Tailwind v4, Radix, Vitest, Playwright) with the Dense design family, contracts, and tokens vendored wholesale from a sibling design system project. No external `@radianit/*` references; the frontend is a self-contained npm app.
- Repository hygiene: `SECURITY.md`, `CONTRIBUTING.md`, this changelog, README badges and first-time-setup section.

### Changed

- README updated with CI badges, first-time setup guidance, and a daily-commands reference for reviewers.
- **Workstream F second pass:** `chorus.doctor` gained a `--quick` flag (path/executable/compose-validate only) and a default mode with layered readiness sweeps for Postgres migrations, Redpanda Schema Registry, Temporal frontend, Mailpit HTTP API, OpenTelemetry collector, BFF, and frontend dev server. Each sweep skips with a reason when its backend is unreachable. CI now invokes `just doctor-quick`.
- **Workstream F second pass:** Pyright strict added to the gate. `just lint` runs ruff check, ruff format check, and pyright; `just typecheck` runs pyright in isolation; `.pre-commit-config.yaml` enforces ruff + pyright + frontend tsc; CI gains a pyright step.
- **Workstream F second pass:** Runbook expanded with operational procedures — stuck-workflow terminate vs reset, reading the Tool Gateway audit for a denied call, regenerating Pydantic models after a contract change, reset-the-local-stack recovery.

### Added (Workstream F second pass)

- ADR 0009 (proposed): local-only operating model for Phase 1, codifying the deferral surface and consolidating the operating-model assumptions across ADRs 0001/0007/0008.
- `just doctor-quick` and `just typecheck` recipes; `just lint-python` and `just lint-frontend` now compose into `just lint`.

### Added (Workstream F third pass)

- ADR 0010 (proposed): observability pipeline shape — OpenTelemetry auto-instrumentation, Tempo/Loki/Prometheus stack, W3C trace context propagation, audit ↔ trace join via `correlation_id` plus `otel.trace_id`/`otel.span_id` in audit metadata. Pre-commits the contract that B/C/D/E follow on landing.
- `infrastructure/grafana/` provisioning: Postgres datasource (`chorus-postgres`) and four dashboards loaded automatically by Grafana on `just up` — workflow timeline, Tool Gateway verdicts, projection lag, and agent decisions. Every dashboard exposes `$tenant` and `$correlation` variables to scope panels to a single workflow for the audit ↔ Grafana cross-surface trail. Tempo/Loki/Prometheus datasources land with the OTel pipeline (ADR 0010).
- `chorus.doctor` schema-registry check enumerates `contracts/events/*.schema.json`, classifies declared `x-subject` values against the registry's `/subjects` listing, and reports informationally until Workstream B pins canonical subject names. When a schema declares `x-subject` and the registry is reachable but the subject is missing, the check fails with a contract-violation message.

### Added (Workstream F fifth pass)

- **Zero-touch service onboarding into the observability plane.** The OpenTelemetry collector's `fluentforward` receiver is now permanently on (port `${OTEL_FLUENTD_PORT:-24224}`, host-bound so the docker daemon's fluentd logging driver can reach it from the application services' compose entries) and joins `otlp` on the logs pipeline; auto-instrumented services keep emitting OTLP logs in parallel, fluent is the structured-stdout fallback for anything that bypasses the SDK. Prometheus's central `config.yaml` switches to `file_sd_configs` against `/etc/prometheus/targets/*.yml` (mounted from `infrastructure/prometheus/targets/`); a single per-service file activates `/metrics` scraping with a 30-second refresh, no Prometheus restart, no edit to the central config. The relabel rule promotes the per-target `service` label to the standard `job` label so existing dashboards work unchanged.
- **Per-service onboarding checklist** added to `services/_template/README.md` (§ "Observability onboarding") and to `docs/runbook.md` (§ "Onboarding a Phase 1A service"). Four steps: stable `container_name: chorus-<role>`, fluentd logging block, Prometheus targets file, boundary span attributes for `chorus.tenant_id` / `chorus.correlation_id` / `chorus.workflow_id` so Tempo's `tracesToLogsV2` / `tracesToMetrics` rules join straight into Loki and Prometheus.
- `chorus.doctor` structural drift list now requires `infrastructure/prometheus/targets/README.md`. `.env.example` gains `OTEL_FLUENTD_PORT=24224`.

### Added (Workstream F fourth pass)

- **Compose-side OpenTelemetry pipeline** per ADR 0010. `compose.yml` adds Tempo (`grafana/tempo`), Loki (`grafana/loki`), and Prometheus (`prom/prometheus`) services with healthchecks, named volumes, and 24h retention. `infrastructure/{tempo,loki,prometheus}/config.yaml` carry the minimal local-mode config for each. `infrastructure/otel/config.yaml` is rewritten: traces export to Tempo via OTLP/gRPC, logs to Loki via the `loki` exporter, metrics to a Prometheus scrape target on `:8889`. The `debug` exporter remains on every pipeline so `docker logs chorus-otel-collector` still surfaces what is forwarded.
- **Grafana datasource provisioning** extended with Tempo, Loki, and Prometheus alongside Postgres. The Tempo datasource carries `tracesToLogsV2` (Tempo→Loki by `chorus.tenant_id`/`workflow_id`/`correlation_id` span attributes), `tracesToMetrics`, `serviceMap`, and `nodeGraph` wired to Prometheus; Loki carries a `derivedFields` rule that turns log-line `trace_id=…` into a Tempo link.
- **Service auto-instrumentation** baked into `services/_template/`. The Dockerfile runs `opentelemetry-bootstrap -a install` after dependency resolution so per-library auto-instrumentation packages match the actual venv contents, sets `OTEL_*` env defaults (resource attributes `service.namespace=chorus`, `deployment.environment=local`, `service.version=${SERVICE_VERSION}`, OTLP endpoint `http://otel-collector:4317`, W3C `tracecontext,baggage` propagators), and uses `opentelemetry-instrument` as the runtime ENTRYPOINT so per-service customisation is limited to `EXPOSE`, `OTEL_SERVICE_NAME`, and `CMD`. `pyproject.toml` carries `opentelemetry-distro[otlp]` as the auto-instrumentation bedrock.
- **`chorus.observability.current_otel_ids()`** helper (ADR 0010 §4) for capturing the active span's `trace_id`/`span_id` into audit and decision-trail row `metadata` jsonb. Lazily imports the OTel API so persistence and contract code that does not need instrumentation is unaffected; returns an empty dict when no SDK is installed or no span is active.
- `chorus.doctor` extended with HTTP readiness probes for Tempo (`/ready`), Loki (`/ready`), and Prometheus (`/-/ready`) in the same layered shape as the existing sweeps. New paths added to the structural drift list. New env vars (`TEMPO_*`, `LOKI_*`, `PROMETHEUS_*`, `OTEL_PROMETHEUS_PORT`) added to `.env.example`.
- `CONTRIBUTING.md` parallel-session note: explicit `git add <paths>` only — never `git add -A` or `git add .` — so concurrent workstream sessions do not sweep each other's in-flight files into a wrongly-titled commit.

### Removed

- Earlier internal "Chorus SDLC operating model" scope draft (superseded by `docs/implementation-plan.md`).

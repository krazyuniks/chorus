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

### Removed

- Earlier internal "Chorus SDLC operating model" scope draft (superseded by `docs/implementation-plan.md`).

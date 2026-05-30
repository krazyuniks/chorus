# Chorus — task runner
# Common operations for the local stack and the reset POC slice.
#
# `just --list` shows all available commands.
#
# `dc` wraps `docker compose`: it sources `.env`, exports UID/GID from the
# host, then invokes `docker compose`. Recipes route through it so the env
# model stays consistent without requiring direnv.

set shell := ["zsh", "-cu"]
set dotenv-load
set positional-arguments

dc := "./scripts/dc"

# Default: list available commands.
default:
    @just --list

# ----- Setup -----

# Run the first-time host bootstrap (just, uv, Python 3.14, prek, .env).
setup:
    ./scripts/first-time-setup.sh

# Ensure .env exists by copying .env.example if missing.
env:
    @if [[ ! -f .env && -f .env.example ]]; then cp .env.example .env && echo "[OK] .env created from .env.example"; else echo "[OK] .env already present"; fi

# Register prek-managed git hooks.
install-hooks:
    prek install

# Run every prek hook against the whole tree.
hooks:
    prek run --all-files

# ----- Local stack -----

# Bring up the runtime substrate (Postgres, Redpanda, Temporal, Mailpit, Grafana, OTel).
up:
    {{dc}} up -d --build

# Tear the stack down.
down:
    {{dc}} down

# Tear the stack down including volumes (destroys data).
down-volumes:
    {{dc}} down -v

# Show the status of the stack.
status:
    {{dc}} ps

# Tail logs for all services or a specific one (e.g. `just logs temporal`).
logs *service:
    {{dc}} logs -f {{service}}

# Inspect the local CalDAV sandbox collection without printing event bodies.
caldav-event-refs:
    {{dc}} exec radicale sh -lc 'find /data/collections/collection-root/cal_uc1_local_followup -type f -name "evt_*.ics" -exec basename {} \; 2>/dev/null || true'

# Probe the local CalDAV sandbox collection over WebDAV.
caldav-propfind:
    curl -sS -X PROPFIND -H 'Depth: 1' http://localhost:${CALDAV_SANDBOX_PORT:-5232}/cal_uc1_local_followup/

# ----- Health -----

# Verify scaffold and required live-stack prerequisites; fails when required services are unhealthy.
doctor:
    uv run python -m chorus.doctor

# Verify scaffold paths/executables/compose only — no runtime probes. Used by CI and pre-commit.
doctor-quick:
    uv run python -m chorus.doctor --quick

# Verify per-service pyprojects cover service-owned Chorus runtime imports.
service-import-contracts:
    uv run python -m chorus.doctor.service_import_contracts

# Verify repo-local environment keys and non-secret values match .env.example.
env-check:
    uv run python -m chorus.doctor.env_drift

# Apply Postgres migrations and idempotent local demo seed data.
db-migrate:
    uv run python -m chorus.persistence.migrate

# Register event JSON Schemas with Redpanda Schema Registry.
schemas-register:
    uv run python -m chorus.persistence.redpanda register-schemas

# Relay one pending outbox batch to Redpanda.
relay-once:
    uv run python -m chorus.persistence.redpanda relay-once

# Project one Redpanda workflow-event batch into Postgres read models.
project-once:
    uv run python -m chorus.persistence.redpanda project-once

# ----- Demo -----

# Send a fixture enquiry email through Mailpit and watch the workflow execute.
demo fixture="docs/fixtures/enquiry-acme.eml":
    uv run python -m chorus.demo.send_fixture {{fixture}}

# Run the Chorus Temporal worker.
worker:
    uv run python -m chorus.workflows.worker

# Poll Mailpit once and start one UC1 workflow per new Message-ID.
intake-once:
    uv run python -m chorus.workflows.intake

# Run the BFF (read endpoints + SSE) on the host for focused dev.
bff:
    uv run uvicorn chorus.bff.app:app --host 0.0.0.0 --port ${BFF_PORT:-8000} --reload

# Run the frontend Vite dev server.
frontend-dev:
    cd frontend && npm run dev

# ----- Contracts -----

# Generate Pydantic models from JSON Schema contracts when schemas exist.
contracts-gen:
    uv run python -m chorus.contracts.gen

# Verify contract schema, generated-model, and sample drift checks.
contracts-check:
    uv run python -m chorus.contracts.check

# ----- Tests -----

# Run all Python tests.
test:
    uv run pytest

# Run Postgres persistence and tenant-isolation tests.
test-persistence:
    uv run pytest tests/persistence

# Run Temporal replay tests.
test-replay:
    uv run pytest tests/workflows -k replay

# Run frontend tests.
test-frontend:
    cd frontend && npm test -- --run

# Run E2E tests via Playwright.
test-e2e:
    cd frontend && npm run test:e2e

# ----- Eval -----

# Run eval fixtures.
eval:
    uv run python -m chorus.eval.run

# ----- Lint / format -----

# Run environment drift checks, linters, and type-checkers.
lint: env-check lint-python lint-frontend

# Run Python ruff lint + format check + service import contracts + pyright strict.
lint-python: service-import-contracts
    uv run ruff check .
    uv run ruff format --check .
    uv run pyright

# Run frontend type-check.
lint-frontend:
    cd frontend && npm run lint

# Run pyright strict over the Python tree.
typecheck:
    uv run pyright

# Format (Python + frontend).
fmt:
    uv run ruff format .
    cd frontend && npm run fmt

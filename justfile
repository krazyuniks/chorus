# Chorus — task runner
# Common operations for the local stack and the Phase 1 vertical slice.
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

# ----- Health -----

# Verify Phase 0 scaffold and probe the live local stack (skips probes for services that aren't up).
doctor:
    uv run python -m chorus.doctor

# Verify scaffold paths/executables/compose only — no runtime probes. Used by CI and pre-commit.
doctor-quick:
    uv run python -m chorus.doctor --quick

# Apply Postgres migrations and idempotent Phase 1A demo seed data.
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

# Send a fixture lead email through Mailpit and watch the workflow execute.
# (Phase 1A — the SMTP-receive trigger and Lighthouse workflow ship together.)
demo fixture="docs/fixtures/lead-acme.eml":
    uv run python -m chorus.demo.send_fixture {{fixture}}

# Run the Lighthouse Temporal worker.
worker:
    uv run python -m chorus.workflows.worker

# Poll Mailpit once and start one Lighthouse workflow per new lead Message-ID.
intake-once:
    uv run python -m chorus.workflows.intake

# Run the Lighthouse BFF (read endpoints + SSE) on the host for focused dev.
bff:
    uv run uvicorn chorus.bff.app:app --host 0.0.0.0 --port ${BFF_PORT:-8000} --reload

# Run the frontend Vite dev server.
frontend-dev:
    cd frontend && npm run dev

# ----- Contracts -----

# Generate Pydantic models from JSON Schema contracts when schemas exist.
contracts-gen:
    uv run python -m chorus.contracts.gen

# Verify the contract scaffold. Phase 1A adds schema/model/sample drift checks.
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

# Run trace/eval fixtures: happy path plus Phase 1B governance/failure fixtures.
eval:
    uv run python -m chorus.eval.run

# ----- Lint / format -----

# Run linters (Python ruff + pyright, frontend tsc).
lint: lint-python lint-frontend

# Run Python ruff lint + format check + pyright strict.
lint-python:
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

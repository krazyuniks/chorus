# Chorus — task runner
# Common operations for the local stack and the Phase 1 vertical slice.
#
# `just --list` shows all available commands.

set shell := ["zsh", "-cu"]

# Default: list available commands.
default:
    @just --list

# ----- Local stack -----

# Bring up the runtime substrate (Postgres, Redpanda, Temporal, Mailpit, Grafana, OTel).
up:
    docker compose up -d

# Tear the stack down.
down:
    docker compose down

# Tear the stack down including volumes (destroys data).
down-volumes:
    docker compose down -v

# Show the status of the stack.
status:
    docker compose ps

# Tail logs for all services or a specific one (e.g. `just logs temporal`).
logs *service:
    docker compose logs -f {{service}}

# ----- Health -----

# Verify Phase 0 scaffold; Phase 1A adds service health, migrations, schemas, and workflow readiness.
doctor:
    uv run python -m chorus.doctor

# ----- Demo -----

# Send a fixture lead email through Mailpit and watch the workflow execute.
# (Phase 1A — the SMTP-receive trigger and Lighthouse workflow ship together.)
demo fixture="docs/fixtures/lead-acme.eml":
    uv run python -m chorus.demo.send_fixture {{fixture}}

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

# Run Temporal replay tests.
test-replay:
    uv run pytest tests/workflows -k replay

# Run frontend tests.
test-frontend:
    cd frontend && pnpm test

# Run E2E tests via Playwright.
test-e2e:
    cd frontend && pnpm test:e2e

# ----- Eval -----

# Run trace/eval fixtures. Phase 1A adds happy path; Phase 1B adds governance fixtures.
eval:
    uv run python -m chorus.eval.run

# ----- Lint / format -----

# Run linters (Python + frontend).
lint:
    uv run ruff check .
    cd frontend && pnpm lint

# Format (Python + frontend).
fmt:
    uv run ruff format .
    cd frontend && pnpm fmt

"""Phase 0 + Phase 1A readiness checks for the Chorus local runtime contract.

Doctor is the single command a reviewer or contributor runs to verify the
project layout and the local stack are ready for the Lighthouse slice.

Two modes:

- ``--quick`` runs path/executable/compose-validate checks only. No network,
  no database, no docker daemon required beyond ``docker compose config``.
  This is the cheap sanity check used by pre-commit and CI.
- default mode adds **layered readiness sweeps** that probe the running
  stack: Postgres migration state, Redpanda schema registry, Temporal
  frontend, BFF and frontend HTTP endpoints. Each layer reports ``skip``
  with the reason when its backend is unreachable, and ``fail`` only when
  the backend is reachable but the contract it owns is not satisfied.

When a workstream lands new structural files, append their paths to the
matching list so drift is caught before it reaches CI. When a workstream
exposes a runtime contract (e.g. an ``/_health`` endpoint, a registered
schema), add a layered check below.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import psycopg
from psycopg import Connection

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Structural contracts (path existence)
# ---------------------------------------------------------------------------

# Phase 0 scaffold — documentation, ADRs, contracts, service stubs.
PHASE_0_PATHS = [
    "README.md",
    "compose.yml",
    "justfile",
    "pyproject.toml",
    "docs/overview.md",
    "docs/architecture.md",
    "docs/evidence-map.md",
    "docs/fixtures/lead-acme.eml",
    "docs/governance-guardrails.md",
    "docs/implementation-plan.md",
    "docs/runbook.md",
    "adrs/README.md",
    "contracts/events",
    "contracts/agents",
    "contracts/tools",
    "contracts/eval",
    "services/bff",
    "services/intake-poller",
    "services/agent-runtime",
    "services/tool-gateway",
    "services/connectors-local",
    "services/projection-worker",
    "workflows",
    "frontend",
    "eval",
    "infrastructure/otel/config.yaml",
]

# Workstream F (Observability + ops) — developer experience, CI, services
# template, and meta files. Phase 0A finishing scaffold lives here.
WORKSTREAM_F_PATHS = [
    ".env.example",
    ".editorconfig",
    ".dockerignore",
    ".gitattributes",
    ".pre-commit-config.yaml",
    "scripts/dc",
    "scripts/first-time-setup.sh",
    "services/_template/Dockerfile",
    "services/_template/pyproject.toml",
    "services/_template/README.md",
    ".github/workflows/ci.yml",
    ".github/workflows/eval.yml",
    ".github/workflows/replay.yml",
    ".github/dependabot.yml",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "frontend/package.json",
    "frontend/vite.config.ts",
    "frontend/tsconfig.json",
    "frontend/src/main.tsx",
    "frontend/src/design-system/tokens/foundation.css",
    "infrastructure/grafana/provisioning/datasources/chorus.yaml",
    "infrastructure/grafana/provisioning/dashboards/chorus.yaml",
    "infrastructure/grafana/dashboards/workflow-timeline.json",
    "infrastructure/grafana/dashboards/gateway-verdicts.json",
    "infrastructure/grafana/dashboards/projection-lag.json",
    "infrastructure/grafana/dashboards/agent-decisions.json",
    "infrastructure/tempo/config.yaml",
    "infrastructure/loki/config.yaml",
    "infrastructure/prometheus/config.yaml",
    "infrastructure/prometheus/targets/README.md",
    "chorus/observability/__init__.py",
]

# Workstream A (Persistence + projection) — Postgres migrations, seeds,
# persistence module. Owned by the Workstream A session.
WORKSTREAM_A_PATHS = [
    "infrastructure/postgres/README.md",
    "infrastructure/postgres/migrations/001_phase_1a_persistence_foundation.sql",
    "infrastructure/postgres/seeds/001_demo_tenants.sql",
    "chorus/persistence/__init__.py",
    "chorus/persistence/migrate.py",
    "chorus/persistence/outbox.py",
    "chorus/persistence/projection.py",
    "chorus/persistence/redpanda.py",
    "tests/persistence/test_postgres_foundation.py",
    "tests/persistence/test_redpanda_projection.py",
]

WORKSTREAM_B_PATHS = [
    "chorus/workflows/lighthouse.py",
    "chorus/workflows/activities.py",
    "chorus/workflows/mailpit.py",
    "chorus/workflows/intake.py",
    "chorus/workflows/worker.py",
    "chorus/workflows/types.py",
    "services/intake-poller/Dockerfile",
    "services/intake-poller/pyproject.toml",
    "tests/workflows/test_activities.py",
    "tests/workflows/test_lighthouse_workflow.py",
    "tests/workflows/test_mailpit_intake.py",
    "tests/workflows/fixtures/lighthouse_happy_history.json",
]

REQUIRED_PATHS = PHASE_0_PATHS + WORKSTREAM_F_PATHS + WORKSTREAM_A_PATHS + WORKSTREAM_B_PATHS


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------


def _ok(message: str) -> None:
    print(f"ok    - {message}")


def _fail(message: str) -> None:
    print(f"fail  - {message}")


def _skip(message: str) -> None:
    print(f"skip  - {message}")


def _section(title: str) -> None:
    print(f"\n# {title}")


# ---------------------------------------------------------------------------
# Quick (offline) checks
# ---------------------------------------------------------------------------


def _check_executable(relative: str) -> bool:
    path = ROOT / relative
    return path.exists() and path.stat().st_mode & 0o111 != 0


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )


def check_paths() -> int:
    failures = 0
    for section, paths in (
        ("phase 0", PHASE_0_PATHS),
        ("workstream F", WORKSTREAM_F_PATHS),
        ("workstream A", WORKSTREAM_A_PATHS),
        ("workstream B", WORKSTREAM_B_PATHS),
    ):
        _section(section)
        for relative in paths:
            if (ROOT / relative).exists():
                _ok(relative)
            else:
                _fail(f"missing {relative}")
                failures += 1
    return failures


def check_executables() -> int:
    failures = 0
    _section("executables")
    for relative in ("scripts/dc", "scripts/first-time-setup.sh"):
        if _check_executable(relative):
            _ok(f"{relative} is executable")
        elif (ROOT / relative).exists():
            _fail(f"{relative} exists but is not executable")
            failures += 1
    return failures


def check_compose() -> int:
    _section("compose")
    result = _run(["docker", "compose", "config", "--quiet"])
    if result.returncode == 0:
        _ok("compose.yml validates")
        return 0
    _fail("compose.yml failed validation")
    if result.stderr.strip():
        print(result.stderr.strip())
    return 1


# ---------------------------------------------------------------------------
# Layered readiness sweeps (online)
# ---------------------------------------------------------------------------


def _tcp_reachable(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_get(url: str, timeout: float = 1.5) -> tuple[int | None, str | None]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except urllib.error.URLError, OSError, ValueError:
        return None, None


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _applied_migrations(conn: Connection[Any]) -> set[str]:
    rows = conn.execute("SELECT filename FROM schema_migrations").fetchall()
    return {str(r[0]) for r in rows}


def check_postgres_migrations() -> int:
    _section("postgres migrations (workstream A contract)")
    pg_port = _env_int("CHORUS_PG_PORT", 5432)
    if not _tcp_reachable("localhost", pg_port):
        _skip(f"postgres not reachable on localhost:{pg_port} (run 'just up')")
        return 0

    from chorus.persistence.migrate import (
        MIGRATIONS_DIR,
        database_url_from_env,
        sql_files,
    )

    expected = [f.filename for f in sql_files(MIGRATIONS_DIR)]
    if not expected:
        _skip("no migration files present yet")
        return 0

    try:
        with psycopg.connect(database_url_from_env(), connect_timeout=2) as conn:
            row = conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone()
            if row is None or row[0] is None:
                _fail("schema_migrations table missing — run 'just db-migrate'")
                return 1
            applied = _applied_migrations(conn)
    except psycopg.Error as exc:
        _fail(f"postgres reachable but query failed: {exc}")
        return 1

    failures = 0
    for filename in expected:
        if filename in applied:
            _ok(f"migration applied: {filename}")
        else:
            _fail(f"migration not applied: {filename} — run 'just db-migrate'")
            failures += 1
    return failures


def check_temporal() -> int:
    _section("temporal (workstream B contract)")
    port = _env_int("TEMPORAL_PORT", 7233)
    ui_port = _env_int("TEMPORAL_UI_PORT", 8233)
    if not _tcp_reachable("localhost", port):
        _skip(f"temporal frontend not reachable on localhost:{port} (run 'just up')")
        return 0
    _ok(f"temporal frontend reachable on localhost:{port}")
    if _tcp_reachable("localhost", ui_port):
        _ok(f"temporal UI reachable on localhost:{ui_port}")
    else:
        _skip(f"temporal UI not reachable on localhost:{ui_port}")
    task_queue = os.environ.get("LIGHTHOUSE_TASK_QUEUE", "lighthouse")
    try:
        pollers = asyncio.run(_describe_temporal_task_queue(task_queue=task_queue))
    except Exception as exc:
        _fail(f"temporal task queue '{task_queue}' discovery failed: {exc}")
        return 1
    if pollers > 0:
        _ok(f"temporal task queue '{task_queue}' has {pollers} worker poller(s)")
        return 0
    _fail(f"temporal task queue '{task_queue}' has no worker pollers")
    return 1


async def _describe_temporal_task_queue(*, task_queue: str) -> int:
    from temporalio.api.enums.v1 import TaskQueueType
    from temporalio.api.taskqueue.v1 import TaskQueue
    from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest
    from temporalio.client import Client

    target_host = f"localhost:{_env_int('TEMPORAL_PORT', 7233)}"
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    client = await Client.connect(target_host, namespace=namespace)
    response = await client.workflow_service.describe_task_queue(
        DescribeTaskQueueRequest(
            namespace=namespace,
            task_queue=TaskQueue(name=task_queue),
            task_queue_type=TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW,
            report_pollers=True,
        )
    )
    return len(response.pollers)


def _expected_event_subjects() -> dict[str, str | None]:
    """Map contracts/events/*.schema.json to their declared registry subject.

    A schema opts into the strict check by setting ``x-subject`` at top level
    (string) or ``x-subjects`` (list of strings). Schemas without that
    declaration are reported informationally and never fail the check;
    Workstream B owns adding the field when it pins the canonical subject
    name for each event.
    """

    import json

    expected: dict[str, str | None] = {}
    for path in sorted((ROOT / "contracts" / "events").glob("*.schema.json")):
        try:
            data = json.loads(path.read_text())
        except OSError, json.JSONDecodeError:
            expected[path.name] = None
            continue
        subject = data.get("x-subject")
        if isinstance(subject, str) and subject:
            expected[path.name] = subject
        else:
            expected[path.name] = None
    return expected


def check_schema_registry() -> int:
    _section("redpanda schema registry (workstream B + A contract)")
    port = _env_int("REDPANDA_SCHEMA_REGISTRY_PORT", 8081)
    if not _tcp_reachable("localhost", port):
        _skip(f"schema registry not reachable on localhost:{port} (run 'just up')")
        return 0
    status, body = _http_get(f"http://localhost:{port}/subjects")
    if status != 200:
        _fail(f"schema registry on localhost:{port} returned status {status}")
        return 1
    _ok(f"schema registry responding on localhost:{port}")

    import json as _json

    try:
        registered = set(_json.loads(body or "[]"))
    except _json.JSONDecodeError:
        _fail("schema registry /subjects returned non-JSON body")
        return 1

    expected = _expected_event_subjects()
    if not expected:
        _skip("no event contracts under contracts/events to verify")
        return 0

    failures = 0
    declared = {name: subj for name, subj in expected.items() if subj}
    undeclared = [name for name, subj in expected.items() if not subj]

    if not declared and not registered:
        _skip(
            "no x-subject declared on event contracts and no subjects registered "
            "(workstream B has not yet pinned canonical subject names)"
        )
    elif not declared and registered:
        _skip(
            f"{len(registered)} subject(s) registered but no contract declares "
            "x-subject — declare in contracts/events/*.schema.json to enable strict drift check"
        )
        for subject in sorted(registered):
            print(f"info  - registry subject: {subject}")
    else:
        for name, subject in declared.items():
            if subject in registered:
                _ok(f"{name}: subject '{subject}' registered")
            else:
                _fail(f"{name}: subject '{subject}' missing from registry")
                failures += 1

    for name in undeclared:
        print(f"info  - {name}: no x-subject declared (informational)")

    return failures


def check_mailpit() -> int:
    _section("mailpit (workstream B + D contract)")
    port = _env_int("MAILPIT_HTTP_PORT", 8025)
    if not _tcp_reachable("localhost", port):
        _skip(f"mailpit not reachable on localhost:{port} (run 'just up')")
        return 0
    status, _ = _http_get(f"http://localhost:{port}/api/v1/info")
    if status == 200:
        _ok(f"mailpit HTTP API responding on localhost:{port}")
        return 0
    _fail(f"mailpit on localhost:{port} returned status {status}")
    return 1


def check_bff() -> int:
    _section("bff (workstream E contract)")
    port = _env_int("BFF_PORT", 8000)
    if not _tcp_reachable("localhost", port):
        _skip(f"bff not reachable on localhost:{port} (workstream E pending)")
        return 0
    status, _ = _http_get(f"http://localhost:{port}/health")
    if status == 200:
        _ok(f"bff /health responding on localhost:{port}")
        return 0
    _fail(f"bff on localhost:{port} /health returned status {status}")
    return 1


def check_frontend_dev() -> int:
    _section("frontend dev server (workstream E)")
    port = _env_int("FRONTEND_PORT", 5173)
    if not _tcp_reachable("localhost", port):
        _skip(f"frontend dev server not reachable on localhost:{port} (run 'npm run dev')")
        return 0
    _ok(f"frontend dev server reachable on localhost:{port}")
    return 0


def check_otel() -> int:
    _section("otel collector (workstream F)")
    grpc_port = _env_int("OTEL_GRPC_PORT", 4317)
    http_port = _env_int("OTEL_HTTP_PORT", 4318)
    grpc_up = _tcp_reachable("localhost", grpc_port)
    http_up = _tcp_reachable("localhost", http_port)
    if not grpc_up and not http_up:
        _skip(f"otel collector not reachable on localhost:{grpc_port}/{http_port} (run 'just up')")
        return 0
    if grpc_up:
        _ok(f"otel collector gRPC reachable on localhost:{grpc_port}")
    else:
        _fail(f"otel collector gRPC not reachable on localhost:{grpc_port}")
    if http_up:
        _ok(f"otel collector HTTP reachable on localhost:{http_port}")
    else:
        _fail(f"otel collector HTTP not reachable on localhost:{http_port}")
    return 0 if grpc_up and http_up else 1


def check_tempo() -> int:
    _section("tempo (workstream F — traces backend)")
    port = _env_int("TEMPO_HTTP_PORT", 3200)
    if not _tcp_reachable("localhost", port):
        _skip(f"tempo not reachable on localhost:{port} (run 'just up')")
        return 0
    status, _ = _http_get(f"http://localhost:{port}/ready")
    if status == 200:
        _ok(f"tempo /ready responding on localhost:{port}")
        return 0
    _fail(f"tempo on localhost:{port} /ready returned status {status}")
    return 1


def check_loki() -> int:
    _section("loki (workstream F — logs backend)")
    port = _env_int("LOKI_HTTP_PORT", 3100)
    if not _tcp_reachable("localhost", port):
        _skip(f"loki not reachable on localhost:{port} (run 'just up')")
        return 0
    status, _ = _http_get(f"http://localhost:{port}/ready")
    if status == 200:
        _ok(f"loki /ready responding on localhost:{port}")
        return 0
    _fail(f"loki on localhost:{port} /ready returned status {status}")
    return 1


def check_prometheus() -> int:
    _section("prometheus (workstream F — metrics backend)")
    port = _env_int("PROMETHEUS_HTTP_PORT", 9090)
    if not _tcp_reachable("localhost", port):
        _skip(f"prometheus not reachable on localhost:{port} (run 'just up')")
        return 0
    status, _ = _http_get(f"http://localhost:{port}/-/ready")
    if status == 200:
        _ok(f"prometheus /-/ready responding on localhost:{port}")
        return 0
    _fail(f"prometheus on localhost:{port} /-/ready returned status {status}")
    return 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the Chorus local runtime contract.",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help=(
            "Run path/executable/compose checks only. Skips runtime probes — "
            "used by pre-commit and CI."
        ),
    )
    args = parser.parse_args(argv)

    failures = 0
    print("Chorus doctor - Phase 0 scaffold + Phase 1A readiness")

    failures += check_paths()
    failures += check_executables()
    failures += check_compose()

    if not args.quick:
        failures += check_postgres_migrations()
        failures += check_temporal()
        failures += check_schema_registry()
        failures += check_mailpit()
        failures += check_otel()
        failures += check_tempo()
        failures += check_loki()
        failures += check_prometheus()
        failures += check_bff()
        failures += check_frontend_dev()

    if failures:
        print(f"\n{failures} check(s) failed")
        return 1

    if args.quick:
        print("\nQuick checks passed. Run 'just doctor' (without --quick) to probe the live stack.")
    else:
        print(
            "\nAll checks passed. Skipped probes mark workstreams whose runtime "
            "contracts have not yet landed; rerun once 'just up' has those services."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

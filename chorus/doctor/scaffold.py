"""Repo-shape, executable, and compose validation - the offline doctor checks.

These checks run in both `--quick` mode (used by pre-commit and CI) and the
default mode. They require no network, no database, and no docker daemon
beyond `docker compose config`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from chorus.doctor._reporting import fail, ok, section

ROOT = Path(__file__).resolve().parents[2]

# Current project shape - documentation, ADRs, contracts, service stubs.
PROJECT_PATHS = [
    "README.md",
    "compose.yml",
    "justfile",
    "pyproject.toml",
    "docs/overview.md",
    "docs/architecture.md",
    "docs/evidence-map.md",
    "docs/fixtures/enquiry-acme.eml",
    "docs/runbook.md",
    "docs/transformation/r4-implementation-backlog.md",
    "adrs/README.md",
    "adrs/0017-langgraph-removed-from-agent-execution.md",
    "adrs/0018-llm-provider-port.md",
    "adrs/0019-audit-ports-and-replay-eval.md",
    "adrs/0020-domain-refocus-uk-regulated-use-cases.md",
    "contracts/intake",
    "contracts/llm_provider",
    "contracts/connector",
    "contracts/audit",
    "contracts/projection",
    "contracts/observability",
    "contracts/eval",
    "services/bff",
    "services/intake-poller",
    "services/agent-runtime",
    "services/tool-gateway",
    "services/connectors-local",
    "services/projection-worker",
    "frontend",
    "infrastructure/otel/config.yaml",
]

# Developer experience, CI, service template, and meta files.
DEVEX_PATHS = [
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

# Persistence, projection, and audit storage surface.
PERSISTENCE_PATHS = [
    "infrastructure/postgres/README.md",
    "infrastructure/postgres/migrations/001_current_state_baseline.sql",
    "infrastructure/postgres/seeds/001_demo_tenants.sql",
    "infrastructure/postgres/seeds/002_provider_governance.sql",
    "infrastructure/postgres/seeds/003_uc1_connector_reference_data.sql",
    "infrastructure/postgres/seeds/004_uc1_policy_snapshots.sql",
    "chorus/persistence/__init__.py",
    "chorus/persistence/migrate.py",
    "chorus/persistence/outbox.py",
    "chorus/persistence/projection.py",
    "chorus/persistence/audit_port.py",
    "chorus/persistence/runtime_policy.py",
    "chorus/persistence/provider_governance.py",
    "chorus/persistence/replay_runs.py",
    "chorus/persistence/uc1_connectors.py",
    "chorus/persistence/redpanda.py",
    "tests/persistence/test_postgres_foundation.py",
    "tests/persistence/test_redpanda_projection.py",
]

WORKFLOW_PATHS = [
    "chorus/workflows/spine.py",
    "chorus/workflows/uc1.py",
    "chorus/workflows/activities.py",
    "chorus/workflows/mailpit.py",
    "chorus/workflows/intake.py",
    "chorus/workflows/worker.py",
    "chorus/workflows/types.py",
    "services/intake-poller/Dockerfile",
    "services/intake-poller/pyproject.toml",
    "tests/workflows/test_activities.py",
    "tests/workflows/test_uc1_workflow.py",
    "tests/workflows/test_mailpit_intake.py",
]

BFF_UI_PATHS = [
    "chorus/bff/__init__.py",
    "chorus/bff/app.py",
    "services/bff/Dockerfile",
    "services/bff/pyproject.toml",
    "tests/bff/test_app.py",
    "frontend/src/api/queries.ts",
]

REQUIRED_PATHS = PROJECT_PATHS + DEVEX_PATHS + PERSISTENCE_PATHS + WORKFLOW_PATHS + BFF_UI_PATHS


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
    for sect, paths in (
        ("project", PROJECT_PATHS),
        ("devex", DEVEX_PATHS),
        ("persistence", PERSISTENCE_PATHS),
        ("workflow", WORKFLOW_PATHS),
        ("bff ui", BFF_UI_PATHS),
    ):
        section(sect)
        for relative in paths:
            if (ROOT / relative).exists():
                ok(relative)
            else:
                fail(f"missing {relative}")
                failures += 1
    return failures


def check_executables() -> int:
    failures = 0
    section("executables")
    for relative in ("scripts/dc", "scripts/first-time-setup.sh"):
        if _check_executable(relative):
            ok(f"{relative} is executable")
        elif (ROOT / relative).exists():
            fail(f"{relative} exists but is not executable")
            failures += 1
    return failures


def check_compose() -> int:
    section("compose")
    result = _run([str(ROOT / "scripts/dc"), "config", "--quiet"])
    if result.returncode == 0:
        ok("compose.yml validates")
        return 0
    fail("compose.yml failed validation through scripts/dc")
    if result.stderr.strip():
        print(result.stderr.strip())
    return 1

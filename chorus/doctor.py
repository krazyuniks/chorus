"""Phase 0 scaffold checks for the Chorus local runtime contract.

Doctor is the single command a reviewer or contributor runs to verify the
project layout is intact. Each section corresponds to a phase or workstream
contract: when a workstream lands new structural files, append their paths
here so drift is caught before it reaches CI.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

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
]

# Workstream A (Persistence + projection) — Postgres migrations, seeds,
# persistence module. Owned by the Workstream A session.
WORKSTREAM_A_PATHS = [
    "infrastructure/postgres/README.md",
    "infrastructure/postgres/migrations/001_phase_1a_persistence_foundation.sql",
    "infrastructure/postgres/seeds/001_demo_tenants.sql",
    "chorus/persistence/__init__.py",
    "chorus/persistence/migrate.py",
    "chorus/persistence/projection.py",
    "tests/persistence/test_postgres_foundation.py",
]

REQUIRED_PATHS = PHASE_0_PATHS + WORKSTREAM_F_PATHS + WORKSTREAM_A_PATHS


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )


def _ok(message: str) -> None:
    print(f"ok - {message}")


def _fail(message: str) -> None:
    print(f"fail - {message}")


def _check_executable(relative: str) -> bool:
    path = ROOT / relative
    return path.exists() and path.stat().st_mode & 0o111 != 0


def main() -> int:
    failures = 0

    print("Chorus doctor - Phase 0 scaffold + Workstream F dev loop")

    for section, paths in (
        ("phase 0", PHASE_0_PATHS),
        ("workstream F", WORKSTREAM_F_PATHS),
        ("workstream A", WORKSTREAM_A_PATHS),
    ):
        print(f"\n# {section}")
        for relative in paths:
            if (ROOT / relative).exists():
                _ok(relative)
            else:
                _fail(f"missing {relative}")
                failures += 1

    print("\n# executables")
    for relative in ("scripts/dc", "scripts/first-time-setup.sh"):
        if _check_executable(relative):
            _ok(f"{relative} is executable")
        elif (ROOT / relative).exists():
            _fail(f"{relative} exists but is not executable")
            failures += 1

    print("\n# compose")
    compose = _run(["docker", "compose", "config", "--quiet"])
    if compose.returncode == 0:
        _ok("compose.yml validates")
    else:
        _fail("compose.yml failed validation")
        if compose.stderr.strip():
            print(compose.stderr.strip())
        failures += 1

    if failures:
        print(f"\n{failures} check(s) failed")
        return 1

    print("\nPhase 0 scaffold checks passed.")
    print(
        "Phase 1A extends doctor with service health, migrations, schema registration, "
        "and workflow readiness."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

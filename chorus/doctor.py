"""Phase 0 scaffold checks for the Chorus local runtime contract."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    "README.md",
    "compose.yml",
    "justfile",
    "pyproject.toml",
    "docs/overview.md",
    "docs/architecture.md",
    "docs/evidence-map.md",
    "docs/fixtures/lead-acme.eml",
    "docs/governance-guardrails.md",
    "docs/sdlc-operating-model.md",
    "docs/implementation-plan.md",
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


def main() -> int:
    failures = 0

    print("Chorus doctor - Phase 0 scaffold")

    for relative in REQUIRED_PATHS:
        if (ROOT / relative).exists():
            _ok(relative)
        else:
            _fail(f"missing {relative}")
            failures += 1

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

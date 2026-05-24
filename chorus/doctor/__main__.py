"""CLI entry point for `python -m chorus.doctor`.

Sequences the scaffold check and the live-port probes; the per-port modules
hold the actual probe logic. `--quick` skips the live probes and leaves
only the scaffold checks (used by pre-commit and CI).
"""

from __future__ import annotations

import argparse
import sys

from chorus.doctor.connector_port import check_mailpit
from chorus.doctor.observability_port import (
    check_loki,
    check_otel,
    check_prometheus,
    check_tempo,
)
from chorus.doctor.projection_port import check_postgres_migrations, check_schema_registry
from chorus.doctor.scaffold import check_compose, check_executables, check_paths
from chorus.doctor.ui import check_bff, check_frontend_dev
from chorus.doctor.workflow_runtime import check_temporal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the Chorus local runtime contract.",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help=(
            "Run path/executable/compose checks only. Skips runtime probes - "
            "used by pre-commit and CI."
        ),
    )
    args = parser.parse_args(argv)

    failures = 0
    print("Chorus doctor - runtime, evidence, and planning readiness")

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
            "\nAll checks passed. Skipped probes mark runtime surfaces that are not "
            "currently reachable; rerun after 'just up' when live evidence is required."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

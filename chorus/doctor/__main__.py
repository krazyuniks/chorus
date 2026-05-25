"""CLI entry point for `python -m chorus.doctor`.

Sequences the scaffold check and the live-port probes; the per-port modules
hold the actual probe logic. `--quick` skips the live probes and leaves
only the scaffold checks (used by pre-commit and CI).
"""

from __future__ import annotations

import argparse
import sys

from chorus.doctor._env import load_local_env
from chorus.doctor.connector_port import check_mailpit, check_radicale
from chorus.doctor.observability_port import (
    check_loki,
    check_otel,
    check_prometheus,
    check_tempo,
)
from chorus.doctor.projection_port import (
    check_postgres_migrations,
    check_redpanda_bootstrap,
    check_schema_registry,
)
from chorus.doctor.scaffold import check_compose, check_executables, check_paths
from chorus.doctor.service_import_contracts import check_service_import_contracts_command
from chorus.doctor.stack_health import check_compose_runtime
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
    load_local_env()

    failures = 0
    print("Chorus doctor - runtime, evidence, and planning readiness")

    failures += check_paths()
    failures += check_executables()
    failures += check_compose()
    failures += check_service_import_contracts_command()

    if not args.quick:
        stack_failures = 0
        stack_failures += check_compose_runtime()
        stack_failures += check_postgres_migrations()
        stack_failures += check_redpanda_bootstrap()
        stack_failures += check_schema_registry()
        stack_failures += check_mailpit()
        stack_failures += check_radicale()
        stack_failures += check_temporal()
        failures += stack_failures

        if stack_failures == 0:
            failures += check_otel()
            failures += check_tempo()
            failures += check_loki()
            failures += check_prometheus()
            failures += check_bff()
            failures += check_frontend_dev()
        else:
            print("\nRequired stack prerequisites failed; downstream optional probes were not run.")

    if failures:
        print(f"\n{failures} check(s) failed")
        return 1

    if args.quick:
        print("\nQuick checks passed. Run 'just doctor' (without --quick) to probe the live stack.")
    else:
        print(
            "\nAll required stack checks passed. Optional UI/dev probes are "
            "reported as informational when their development servers are not running."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

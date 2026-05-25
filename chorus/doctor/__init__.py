"""Readiness checks for the Chorus local runtime and planning contract.

After the R3 F decomposition, doctor is a small package: `scaffold` holds
the static repo-shape checks, `stack_health` owns required Compose substrate
checks, and one module per live-probe class mirrors the post-A contract layout.

`uv run python -m chorus.doctor` (defined in :mod:`chorus.doctor.__main__`)
is the single CLI entry point. The package surface is the
individual `check_*` functions each module exposes; the entry point sequences
them.
"""

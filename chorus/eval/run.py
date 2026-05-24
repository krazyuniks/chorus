"""Invariant + replay eval runner (ADR 0019).

`assert` (default) loads each fixture, plays its scenario through the
recorded-replay route, and asserts the current UC1 invariant suite over
the captured-run artefacts. Per ADR 0019 the path-enumeration era is
retired and the invariants are the substrate.

`replay` loads a captured transcript fixture (or, in future R4 cross-
provider mode, a captured transcript by id from the audit-port transcripts
table) and re-executes it through the chosen route catalogue entry, then
compares the resulting structured output to the captured one.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from chorus.contracts.generated.eval.eval_fixture import EvalFixture
from chorus.eval.invariants import run_invariants
from chorus.eval.replay import load_transcript, replay_transcript
from chorus.eval.scenario_player import play_scenario
from chorus.eval.types import EvalCheck

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="cmd")

    assert_parser = subparsers.add_parser(
        "assert",
        help="Run the UC1 invariant suite over fixture-driven captured runs.",
    )
    assert_parser.add_argument(
        "--fixture",
        action="append",
        type=Path,
        help=("Eval fixture JSON to execute. Defaults to every fixture in chorus/eval/fixtures/."),
    )

    replay_parser = subparsers.add_parser(
        "replay",
        help=(
            "Re-execute a captured transcript through the route catalogue and "
            "verify the structured output matches the captured one."
        ),
    )
    replay_parser.add_argument(
        "--transcript",
        type=Path,
        required=True,
        help="Path to a captured transcript JSON fixture.",
    )
    replay_parser.add_argument(
        "--route",
        default=None,
        help=(
            "Route catalogue entry to replay through. Defaults to the "
            "transcript's captured route id."
        ),
    )

    args = parser.parse_args(list(argv) if argv is not None else None)
    cmd = args.cmd or "assert"
    if cmd == "assert":
        return _run_assert(args)
    if cmd == "replay":
        return _run_replay(args)
    parser.error(f"unknown command: {cmd}")
    return 2  # pragma: no cover - argparse exits


def _run_assert(args: argparse.Namespace) -> int:
    fixture_arg = getattr(args, "fixture", None)
    fixture_paths: list[Path] = (
        list(fixture_arg) if fixture_arg else sorted(FIXTURE_DIR.glob("*.json"))
    )
    failed = False
    for index, fixture_path in enumerate(fixture_paths):
        fixture = load_fixture(fixture_path)
        run = play_scenario(fixture)
        checks = run_invariants(run)
        if index > 0:
            print()
        _print_report(fixture_id=fixture.fixture_id, name=fixture.name, checks=checks)
        failed = failed or any(check.status == "fail" for check in checks)
    return 1 if failed else 0


def _run_replay(args: argparse.Namespace) -> int:
    transcript = load_transcript(args.transcript)
    checks = replay_transcript(transcript, route_id=args.route)
    _print_report(
        fixture_id=transcript.invocation_id,
        name=f"replay through route {args.route or transcript.route_id!r}",
        checks=checks,
    )
    return 1 if any(check.status == "fail" for check in checks) else 0


def load_fixture(path: Path) -> EvalFixture:
    data = json.loads(path.read_text(encoding="utf-8"))
    return EvalFixture.model_validate(data)


def _print_report(*, fixture_id: str, name: str, checks: Sequence[EvalCheck]) -> None:
    print(f"=== {fixture_id} - {name} ===")
    for check in checks:
        print(f"  [{check.status}] {check.name}: {check.detail}")


if __name__ == "__main__":
    sys.exit(main())

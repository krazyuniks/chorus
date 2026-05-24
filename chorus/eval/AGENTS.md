# Eval Implementation Instructions

This package owns the invariant-based eval runner (ADR 0019) plus the
captured-transcript replay subcommand. Path-enumeration fixtures retired in
R3 G; the invariants now do the asserting.

## Rules

- Keep fixtures JSON Schema-governed by `contracts/eval/eval_fixture.schema.json`.
- A fixture describes its `workflow_type`, a use-case-owned `scenario`
  identifier, and the expected `outcome_category` (`propose` | `escalate` |
  `dlq`). The current UC1 recorded-replay player supports `happy_path`,
  `deeper_context`, `validator_redraft`, and `retry_exhaustion`; UC2 and UC3
  fixtures should use their own domain scenario labels once their runtime
  slices land. The invariants assert audit, transcript, connector, and
  projection shape directly.
- Add or update architecture-wide checks in `common_invariants.py` when an
  audit field, port boundary, or replay property becomes load-bearing across
  use cases.
- Add or update conduct hooks in per-use-case modules under `use_cases/`
  (`uc1_conduct.py` today; UC2 and UC3 should mirror that shape later).
- Keep deterministic fixture execution available without live provider calls.
  The scenario player drives the recorded-replay route only.
- Live persisted-evidence assertions should plug into the same invariant
  surface; do not add a parallel path-enumeration eval.
- Update `tests/eval/test_run.py` when adding fixture scenarios or new
  invariant assertions.

## Local Map

- `run.py` is the CLI entry point: `assert` (default) runs the invariant
  suite over fixture-driven captured runs; `replay` re-executes a captured
  transcript through the recorded-replay route and verifies the structured
  output matches.
- `scenario_player.py` drives current UC1 scenarios through the recorded-
  replay adapter and assembles the captured-run artefacts (decision-trail
  rows, transcripts, tool-action audit, projection events) the invariants
  consume. UC2 and UC3 fixture validation is contract/model breadth only until
  their runtime slices add playback.
- `common_invariants.py` holds the architecture-wide invariant checks:
  cross-port payload validity, governed-decision provenance, audit
  completeness, observability emission, connector authority discipline, and
  projection convergence.
- `use_cases/uc1_conduct.py` holds the current UC1 conduct hooks for enquiry
  qualification. UC2 and UC3 conduct modules should sit beside it when their
  runtime slices land.
- `invariants.py` composes the current UC1 suite and keeps the runner-facing
  imports stable.
- `replay.py` loads a captured transcript fixture, re-executes it through
  the route catalogue, and builds the safe replay-run evidence record used by
  persistence / BFF inspection.
- `fixtures/` carries the active fixtures (`uc1_happy_path.json`,
  `uc1_validator_redraft.json`) plus the captured transcript fixtures
  under `fixtures/transcripts/` the replay subcommand re-executes.

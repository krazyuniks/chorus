# Eval Implementation Instructions

This package owns the invariant-based eval runner (ADR 0019) plus the
captured-transcript replay subcommand. Path-enumeration fixtures retired in
R3 G; the invariants now do the asserting.

## Rules

- Keep fixtures JSON Schema-governed by `contracts/eval/eval_fixture.schema.json`.
- A fixture describes its scenario (`happy_path` | `deeper_context` |
  `validator_redraft` | `retry_exhaustion`) plus the expected
  `outcome_category` (`propose` | `escalate` | `dlq`). The invariants
  assert audit, transcript, connector, and projection shape directly.
- Add or update invariants in `invariants.py` when a new conduct hook,
  audit field, or replay property becomes load-bearing for UC1/UC2/UC3.
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
- `scenario_player.py` drives a fixture's scenario through the recorded-
  replay adapter and assembles the captured-run artefacts (decision-trail
  rows, transcripts, tool-action audit, projection events) the invariants
  consume.
- `invariants.py` holds the UC1 invariant suite: cross-port payload
  validity, governed-decision provenance, audit completeness, observability
  emission, UC1 conduct hooks, connector authority discipline, projection
  convergence.
- `replay.py` loads a captured transcript fixture and re-executes it
  through the route catalogue.
- `fixtures/` carries the active fixtures (`uc1_happy_path.json`,
  `uc1_validator_redraft.json`) plus the captured transcript fixtures
  under `fixtures/transcripts/` the replay subcommand re-executes.

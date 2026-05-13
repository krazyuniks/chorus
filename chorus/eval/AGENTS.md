# Eval Implementation Instructions

This package owns the deterministic eval runner and eval fixtures for workflow,
authority, route-selection, cost, latency, and persisted-evidence checks.

## Rules

- Keep fixtures JSON Schema-governed by `contracts/eval/eval_fixture.schema.json`.
- Add or update fixtures when workflow path, agent output contract, provider
  routing, fallback, authority, budget, or audit expectations change.
- Eval fixtures should assert behaviour and evidence, not just final text.
- Keep deterministic fixture execution available without live provider calls.
- Live persisted-evidence checks must be optional and keyed by
  `CHORUS_EVAL_CORRELATION_ID` or `CHORUS_EVAL_WORKFLOW_ID`.
- Do not hide governance failures behind permissive fixture expectations.
- Update `tests/eval/test_run.py` when adding fixture classes or new assertion
  semantics.

## Local Map

- `run.py` contains the eval runner, deterministic fixture execution, persisted
  evidence loading, and assertion helpers.
- `fixtures/` contains Lighthouse happy-path, governance/failure, and Phase 2A
  provider-governance fixture JSON files.

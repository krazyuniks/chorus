# Eval

Trace and behavioural eval fixtures for the Lighthouse workflow.

Each fixture asserts:

- Expected workflow path through the state machine.
- Final outcome.
- Governance invariants. Phase 1A checks the happy-path allowed tool action;
  Phase 1B adds blocked writes, low-confidence research, validator rejection,
  connector failure, and retry-exhaustion DLQ evidence.
- Cost and latency budgets.
- Emitted contracts (event payloads, decision-trail rows, audit events).

Fixtures are JSON Schema-governed and run in CI. They are the regression boundary for agent / prompt / model-route changes — see [governance-guardrails.md](../docs/governance-guardrails.md).

`just eval` runs the Lighthouse happy-path fixture and all Phase 1B governance/failure fixtures from `chorus/eval/fixtures/`. It always executes deterministic contract-shaped checks. When `CHORUS_EVAL_CORRELATION_ID` or `CHORUS_EVAL_WORKFLOW_ID` is set on the default path, it also inspects persisted Postgres evidence for the live happy-path workflow. Target a specific live governance/failure run with `uv run python -m chorus.eval.run --fixture chorus/eval/fixtures/<fixture>.json`.

See [ADR 0007 — trace/eval harness](../adrs/0007-trace-evaluation-harness.md).

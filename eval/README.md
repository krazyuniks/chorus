# Eval

Trace and behavioural eval fixtures for the Lighthouse workflow.

Each fixture asserts:

- Expected workflow path through the state machine.
- Final outcome.
- Governance invariants. Phase 1A checks the happy-path allowed tool action;
  Phase 1B adds blocked writes and validator rejection.
- Cost and latency budgets.
- Emitted contracts (event payloads, decision-trail rows, audit events).

Fixtures are JSON Schema-governed and run in CI. They are the regression boundary for agent / prompt / model-route changes — see [governance-guardrails.md](../docs/governance-guardrails.md).

Phase 1A: `just eval` runs the Lighthouse happy-path fixture from `chorus/eval/fixtures/lighthouse_happy_path.json`. It always executes a deterministic contract-shaped check and, when `CHORUS_EVAL_CORRELATION_ID` or `CHORUS_EVAL_WORKFLOW_ID` is set, also inspects the persisted Postgres evidence for that live workflow. Phase 1B adds governance and failure fixtures.

See [ADR 0007 — trace/eval harness](../adrs/0007-trace-evaluation-harness.md).

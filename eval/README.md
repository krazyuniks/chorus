# Eval

Trace and behavioural eval fixtures for the Lighthouse workflow.

Each fixture asserts:

- Expected workflow path through the state machine.
- Final outcome.
- Governance invariants (allowed actions, blocked writes, validator behaviour).
- Cost and latency budgets.
- Emitted contracts (event payloads, decision-trail rows, audit events).

Fixtures are JSON Schema-governed and run in CI. They are the regression boundary for agent / prompt / model-route changes — see [governance-guardrails.md](../docs/governance-guardrails.md).

Phase 1A: happy-path fixture (Workstream F). Phase 1B: governance and failure fixtures (Workstream G).

See [ADR 0007 — trace/eval harness](../adrs/0007-trace-evaluation-harness.md).

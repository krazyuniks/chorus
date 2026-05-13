# Eval

Trace and behavioural eval implementation lives in
[`../../chorus/eval/`](../../chorus/eval/). This page is documentation; local
implementation rules for the eval package live in
[`../../chorus/eval/AGENTS.md`](../../chorus/eval/AGENTS.md).

Each fixture asserts:

- Expected workflow path through the state machine.
- Final outcome.
- Governance invariants. Phase 1A checks the happy-path allowed tool action;
  Phase 1B adds blocked writes, low-confidence research, validator rejection,
  connector failure, and retry-exhaustion DLQ evidence.
- Cost and latency budgets.
- Emitted contracts, including event payloads, decision-trail rows, and audit
  events.

Fixtures are JSON Schema-governed and run in CI. They are the regression
boundary for agent, prompt, provider, and model-route changes. See
[governance-guardrails.md](../governance-guardrails.md).

`just eval` runs the Lighthouse happy-path fixture, Phase 1B governance/failure
fixtures, and current Phase 2A provider-governance fixtures from
`chorus/eval/fixtures/`. It always executes deterministic contract-shaped
checks. When `CHORUS_EVAL_CORRELATION_ID` or `CHORUS_EVAL_WORKFLOW_ID` is set
on the default path, it also inspects persisted Postgres evidence for the live
happy-path workflow. Target a specific live governance/failure run with:

```bash
uv run python -m chorus.eval.run --fixture chorus/eval/fixtures/<fixture>.json
```

See [ADR 0007 - trace/eval harness](../../adrs/0007-trace-evaluation-harness.md).

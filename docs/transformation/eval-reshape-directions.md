---
type: project-doc
status: active
date: 2026-05-24
---

# Eval Direction

Eval is a release control. It asserts architectural invariants over captured
run artefacts and uses transcript replay to compare provider behaviour.

## Invariant Suite

The invariant suite applies to every captured run.

| Invariant | What it asserts |
|---|---|
| Cross-port payload validity | Every payload crossing a named port validates against the current contract. |
| Governed-decision provenance | Every agent decision has a decision-trail record with policy snapshot reference, route metadata, agent identity, and safe input/output summaries. |
| Replay stability | A captured transcript can replay against the same route and produce an equivalent structured result. |
| Connector authority discipline | Every connector call has a grant check, mode decision, argument validation, verdict, and audit record. |
| Audit completeness | Decision-trail, transcript, and Tool Gateway audit surfaces cover every LLM invocation and connector call. |
| Projection convergence | Replaying the same events converges to the same read model. |
| Observability emission | Workflow runs emit bounded operational telemetry with stable correlation identifiers. |

Per-use-case conduct invariants sit on top of the common suite:

- UC1: FCA general-insurance-distribution conduct hooks.
- UC2: SRA conflict, KYC, AML, and engagement-boundary hooks.
- UC3: FCA COBS 9 suitability, PROD, Consumer Duty, vulnerability, and advice
  boundary hooks.

## Scenario Coverage

Each use case needs at least:

- one happy-path fixture;
- one conduct-relevant branch fixture;
- one replayable transcript fixture for provider comparison.

Branches are represented because they prove conduct and authority, not because
every possible path needs its own expected ledger.

## Replay Comparison

Replay comparison is tiered.

| Tier | Meaning |
|---|---|
| Hard fail | Schema invalid, missing policy snapshot, missing required conduct hook, unsafe tool/action, or missing audit/transcript evidence. |
| Decision fail | Terminal verdict, route category, or regulated outcome differs under the same policy snapshot. |
| Review finding | Rationale, confidence, optional field, evidence selection, or recommended next step diverges materially. |
| Metric | Token, latency, retry, and cost deltas. |

Exact structured-data equality is useful only for deterministic recorded replay
and narrow fields. It is not the main cross-provider acceptance criterion.

## R4 Requirements

R4 must:

- keep eval assertions over audit/transcript artefacts, not in-test
  bookkeeping;
- refactor common invariants away from UC1-only assumptions;
- add per-use-case conduct invariant modules;
- store replay run records that link original invocation, alternate route,
  comparator result, and metrics;
- avoid replay side effects through connector dry-run or recorded-action
  handling.

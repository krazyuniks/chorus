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
- UC2: SRA conflict, KYC, AML, engagement-boundary hooks, and the
  approval-gated `engagement_letter.send` conduct boundary. Focused invariant
  code exists over safe synthetic captured-run artefacts, and a schema-only
  synthetic UC2 fixture is present under `chorus/eval/fixtures/uc2/`; full UC2
  fixture playback remains a later P4 slice.
- UC3: FCA COBS 9 suitability, PROD, Consumer Duty, vulnerability, and advice
  boundary hooks, plus the approval-gated `suitability_report.issue` conduct
  boundary. Focused invariant code exists over safe synthetic captured-run
  artefacts, and a schema-only synthetic UC3 fixture is present under
  `chorus/eval/fixtures/uc3/`; full UC3 fixture playback remains a later
  slice.

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

The current P3 replay-run record surface is intentionally narrow:
`contracts/eval/replay_run_record.schema.json`, Postgres
`replay_run_records`, and the BFF replay-run view persist the original
invocation/transcript refs, original and alternate route metadata, safe
policy/prompt/response-schema lineage refs, comparator status/result payload,
safe skipped/error reasons, and token/cost/latency metrics. The hard-fail
tier is now implemented for schema-invalid replay output, missing policy
snapshot evidence, missing required UC1 conduct hooks, unsafe action
proposals, missing audit/transcript linkage, route-governance mismatch, and
provider-port replay errors. The decision-fail tier is now implemented for
bounded UC1 qualification decision divergence under the same policy snapshot:
terminal verdict / route category, regulated outcome, required approval
decision fields where present, and connector-action category evidence
available in replay-safe records. The review-finding tier is now implemented
for non-terminal UC1 qualification divergence under the same policy snapshot:
recommended-next-step, confidence band / material confidence delta, rationale
presence or text-change evidence without storing rationale text, optional
structured fields, and safe evidence-selection refs. The metrics-only tier is
now implemented for token, latency, retry-count, provider-cost, and safe
provider-metadata deltas after semantic tiers agree; the comparator stores
bounded reason codes and field names only.

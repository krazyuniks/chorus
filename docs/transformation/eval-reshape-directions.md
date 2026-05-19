---
type: project-doc
status: active
date: 2026-05-19
---

# Eval Reshape Directions

The current eval suite is shaped by path enumeration: a fixture per
expected behavioural branch, including low-confidence, validator redraft,
connector failure, retry exhaustion, and provider fallback. Each fixture
hand-builds the expected evidence shape.

Under the ports-and-adapters thesis, that shape is the wrong one. The
properties that matter are not "did we follow this exact branch" but "did
the architecture's invariants hold". This document records the direction
of the eval reshape that lands in R3 / R4. It is not a refactor plan, only
a shape statement.

## From Path Enumeration To Invariants

### What is wrong with path enumeration

Path enumeration eval treats each branch as a separate test. The fixture
hard-codes which agent ran in which step, which tool was called with
which arguments, which audit row appeared, which projection row updated.
Adding a use case duplicates the entire path-enumeration tree. Changing a
single step's contract requires rewriting every fixture that touched it.

Worse, path-enumeration eval cannot tell the difference between "the
architecture's discipline held on this run" and "this exact happy path
matched the expected ledger". It catches divergence, but it does not
prove invariants.

### What invariant-based eval looks like

The eval suite under the thesis asserts a small set of invariants that
must hold on every run, regardless of which branch was taken.

| Invariant | What it asserts |
|---|---|
| Cross-port payload validity | Every payload that crossed a named port validates against that port's current contract. No payload reached the domain core or an adapter without contract validation. |
| Governed-decision provenance | Every agent decision in the run has a structured decision-trail record with policy snapshot reference, route metadata, agent identity, and input / output summaries. No decision is unattributed. |
| Replay stability | The captured transcript for the run can be replayed against the same provider plus model combination and produces an equivalent result (modulo provider-side non-determinism the route catalogue declares allowed). |
| Connector authority discipline | Every connector port call has a grant check, a mode decision, an argument validation, and a verdict record. No tool call bypassed the Tool Gateway. |
| Audit completeness | For every workflow run, the decision-trail and transcript ports between them cover every LLM invocation and every connector call. Neither port has gaps. |
| Projection convergence | The projection sink derives a stable read-model state from the event stream plus the workflow run; replaying the same events twice produces the same read-model. |
| Observability emission | Every workflow run emits the expected trace / metric / log envelope through the observability sink, with stable correlation identifiers. |

Each invariant applies to every run. They do not enumerate branches; they
constrain the architecture's behaviour on any branch.

### Per-Use-Case Shape: One Happy Path Each

On top of the invariant suite, each confirmed use case gets exactly one
happy path:

- UK insurance broking inbound quote qualification - happy path.
- UK legal services intake plus conflict check - happy path (once R1
  confirms).
- UK wealth management / IFA inbound enquiry - happy path (once R1
  confirms).

One happy path per use case is enough to exercise the named ports under
that use case's contracts. The invariant suite then proves the
architecture's properties across all paths the system actually takes
during the run, including any failure or escalation branches.

Branches that today have their own fixtures (low-confidence, validator
redraft, connector failure, retry exhaustion, provider fallback) become
invariant assertions over actual runs that trigger those branches, not
separate fixtures.

## Replay-As-Comparison As A First-Class Eval Shape

The replay-as-eval-substrate pattern (see `engineering-thesis.md`)
produces a second eval shape that is structurally different from the
invariant suite.

### Shape

```
eval replay --provider <name> --model <id> --invocation-id <uuid>
```

The command:

1. loads the captured transcript for `<invocation-id>`;
2. re-routes the invocation through the LLM provider port against
   `<provider>` plus `<model>` (or the route name those map to);
3. captures the replayed result through the transcript port (with a
   replay-of-<original-id> reference);
4. compares the replay to the original.

### Comparison shape

The comparison reports, per invocation:

- contract validity of the replay against the same schemas;
- decision agreement under the same policy snapshot;
- tool-call divergence (set difference and ordering);
- response-shape divergence;
- cost delta;
- latency delta.

Aggregated across many invocations from many runs, the replay-eval
output is a cross-provider quality report. The same data structure that
captures one invocation under one route can answer questions like
"would gpt-5.4-mini have made the same call as DeepSeek V4-Flash on
these 200 captured insurance broking intakes".

### Where replay-eval fits

Replay-eval is not part of the invariant suite. It runs on demand. It is
the project's continuous cross-provider model-quality surface.

It can be wired into CI for a small canonical set of captured
invocations (a "replay smoke") to detect regressions when the LLM
provider port adapter changes or when a new route is added to the
catalogue.

## Operational Consequences

The shape change has operational consequences that R3 must honour.

- The transcript port captures enough route, model, parameter, and
  message-history metadata to be replay-source-of-truth.
- The connector port supports a dry-run mode on captured replays, so
  replay does not duplicate side effects.
- The invariant assertions are written against the audit ports'
  records, not against in-test bookkeeping.
- Fixtures shrink to one happy path per use case plus the canonical
  replay set. Branch-enumeration fixtures retire.
- The eval CLI grows the `replay` subcommand. Existing offline / live
  modes stay for the invariant suite.

## Out Of Scope For This Document

No code changes happen in R0.5. This document records the eval shape
that R3 / R4 must implement. The matching ADR is part of the post-R2 ADR
writing pass (audit ports plus replay-eval).

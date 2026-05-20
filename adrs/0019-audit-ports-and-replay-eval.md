---
type: adr
status: accepted
date: 2026-05-20
---

# ADR 0019 - Audit ports and replay as eval substrate

## Context

ADR 0005 established Postgres-first storage; the audit surface was a single
store with `decision_trail_entries` and `tool_action_audit` tables. ADR 0007
established a trace and evaluation harness as a Phase 1 requirement; the eval
suite grew as path-enumeration fixtures, one per expected behavioural branch,
each hand-building the expected evidence shape.

The transformation reset makes two changes to this surface. It splits the
audit surface into two named ports, because a single audit stream cannot serve
both compliance and engineering without distorting one of them. And it makes
replay-as-eval-substrate a first-class eval mode.
`transformation/code-refactor-directions.md` (Smell 4) names the single
audit stream and the path-enumeration fixtures as pre-thesis carryovers;
`transformation/eval-reshape-directions.md` sets out the target shape.

## Decision

### Two audit ports

Split the audit surface into two named ports.

The structured decision-trail port is the compliance record: who decided what,
under which policy, on what input, with what output. Its records carry
workflow correlation references, agent identity and version, a policy snapshot
reference, input and output summaries, tool calls in summary form, timestamps,
and cost. It is structured, queryable, and stable.

The full-fidelity transcript port is the engineering record: the full message
sequence sent to the LLM provider, the full tool-call and tool-result
sequence, the full response body, the route catalogue entry, the model
parameters as called, and token counts. It is dense and is not queried
directly for compliance. Its job is to make the invocation replayable.

### Replay as eval substrate

The transcript port stores enough about every captured invocation to replay
that invocation against an alternate provider and model. A captured transcript
can be re-routed through the LLM provider port (ADR 0018) and compared to the
original on contract validity, decision agreement under the same policy
snapshot, tool-call divergence, response-shape divergence, and cost and
latency deltas.

Cross-provider replay is a first-class eval mode, invoked as
`eval replay --provider <name> --model <id> --invocation-id <uuid>`.

### Invariant-based eval

Eval moves from path enumeration to a small set of invariants asserted on
every run, regardless of which branch was taken: cross-port payload validity,
governed-decision provenance, replay stability, connector authority
discipline, audit completeness, projection convergence, and observability
emission. On top of the invariant suite, each use case gets exactly one happy
path.

The audit completeness invariant is load-bearing: for every workflow run, the
decision-trail port and the transcript port between them cover every LLM
invocation and every connector call, with no gaps.

## Consequences

- R3 splits the single Postgres audit store into the decision-trail port and
  the transcript port. Both remain Postgres-backed under ADR 0005; storage
  could split later without changing either port.
- The transcript port must capture enough route, model, parameter, and
  message-history metadata to be the replay source of truth.
- The connector port must support a dry-run mode on captured replays so replay
  does not duplicate side effects.
- The eval harness gains a `replay` subcommand. The branch-enumeration
  fixtures - low-confidence research, validator redraft, connector failure,
  retry exhaustion, provider fallback - retire and become invariant assertions
  over real runs that trigger those branches.
- ADR 0007's eval harness is reshaped, not removed.
- A small canonical replay set can run in CI as a replay smoke to catch
  regressions when the LLM provider port adapter changes or a route is added.

## Alternatives considered

### Keep a single audit store with a kind discriminator

Rejected. A single stream cannot serve both readers without distorting one.
The compliance reader needs a structured, stable, queryable record; the
engineering reader needs a dense, full-fidelity, replayable record. Query
patterns, retention, and consumers differ. A discriminator column hides that
divergence rather than resolving it.

### Keep path-enumeration eval

Rejected. It duplicates the entire fixture tree for each new use case, and a
single contract change forces a rewrite of every fixture that touched the
step. It also cannot distinguish the architecture's discipline holding on a
run from a specific happy path matching the expected ledger.

### Treat replay as a separate research tool

Rejected. Replay is the eval substrate, not a side capability. Making it a
first-class eval mode is what bounds the standard objection to a
provider-agnostic architecture - hallucination and quality risk on cheaper
providers - because divergence becomes observable on real, in-domain
invocations rather than synthetic benchmarks.

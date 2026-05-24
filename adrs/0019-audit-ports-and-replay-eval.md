---
type: adr
status: accepted
date: 2026-05-20
---

# ADR 0019 - Audit Ports And Replay Eval

## Decision

The audit surface is split into two named ports.

The decision-trail port is the compliance and accountability record. It stores
structured summaries: workflow correlation, agent identity and version, policy
snapshot reference, safe input and output summaries, tool-call summaries,
timestamps, outcome, cost, and route metadata.

The transcript port is the engineering replay record. It stores the full
message sequence sent to the LLM provider, tool-call and tool-result sequence,
full response body, route catalogue entry, model parameters, and token counts
where reported.

Replay is an eval substrate. A captured transcript can be re-routed through
the LLM provider port against an alternate route and compared on schema
validity, conduct hooks, decision agreement, tool-call divergence, response
shape, latency, token usage, and cost.

## Consequences

- The eval harness asserts invariants over captured-run artefacts rather than
  maintaining one expected ledger per branch.
- Every LLM invocation must have both a decision-trail record and a transcript
  record.
- Every connector call must have a Tool Gateway audit row.
- R4 cross-provider replay needs a comparator with severity tiers, not exact
  output equality as the main criterion.

## Constraints

- The UI and BFF read safe summaries; raw transcripts remain an engineering
  evidence surface.
- Replay must not duplicate connector side effects.
- Eval cannot bypass audit/transcript evidence assembled through the ports.

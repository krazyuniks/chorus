---
type: adr
status: accepted
date: 2026-05-20
---

# ADR 0017 - LangGraph removed from the agent execution path

## Context

ADR 0012 promoted LangGraph to the first-class agent execution framework
inside the Agent Runtime. Its stated reason was a portfolio gap: Chorus had a
strong orchestration and governance boundary but did not show a
market-recognised agent framework inside it. ADR 0012 itself scoped out every
LangGraph feature that overlapped Temporal, the Tool Gateway, and the audit
store, and reduced LangGraph to a compiled graph over a short, linear
invocation sequence.

The 2026-05-19 transformation reset declared the architectural thesis: Chorus
is a hexagonal, ports-and-adapters exemplar for governed agentic systems, with
contract-first design at every port. Under the thesis the agent reasoning path
is domain-core territory, and a thesis constraint is explicit: agent code
cannot reach past the LLM provider port, and there is no direct provider SDK
use outside that port's adapter.

`transformation/code-refactor-directions.md` (Smell 4) and
`transformation/context-and-intent.md` name LangGraph as a pre-thesis decision
adopted without the ports-and-adapters argument that would have constrained
it. ADR 0012 was a portfolio decision, not an architectural one.

## Decision

Reverse ADR 0012. Remove LangGraph from the agent execution path.

Agent reasoning runs through the LLM provider port directly (see ADR 0018).
The graph-shaped sequence ADR 0012 described - prepare context, invoke,
normalise, validate, final response - becomes a plain, deterministic sequence
in domain code. It does not need a graph framework: it has no branching, no
durable execution, and no human-in-the-loop, and the features that would
justify a graph framework are owned elsewhere by the thesis.

The Agent Runtime is not deleted. Its governance responsibilities - tenant
policy, approved agent version, prompt reference, model route, budget,
invocation identity, and decision-trail capture - are retained. They are
reframed as the domain-side caller of the LLM provider port, on the domain
side of the hexagon.

LangGraph leaves the dependency set.

## Consequences

- R3 removes the compiled graph from `chorus/agent_runtime/`; the invocation
  sequence becomes plain domain code.
- Decision-trail metadata no longer records a graph engine or graph version.
  It records the route catalogue entry instead (see ADR 0018).
- The Phase 2A graph-execution inspection surfaces (the graph-executions BFF
  route and its read model) retire with the graph.
- Eval and replay continue to prove the invocation path. The graph-metadata
  assertions retire with the graph; eval moves to the invariant-based shape in
  ADR 0019.
- ADR 0012 is superseded by this ADR.
- The portfolio gap ADR 0012 cited is not reopened. The exemplar value of
  Chorus is the ports-and-adapters thesis being load-bearing, not the presence
  of a named third-party framework.

## Alternatives considered

### Keep LangGraph as an LLM provider port adapter

Rejected. LangGraph is an orchestration and graph framework, not a provider
transport. Placing it behind the LLM provider port would misrepresent the
port, whose adapter is a provider transport, and would keep the dependency for
no architectural gain.

### Keep LangGraph for future durable or human-in-the-loop features

Rejected. Those features overlap Temporal (durability, retries, waits) and the
Tool Gateway approval hooks (human-in-the-loop), which the thesis already
owns. ADR 0012 had already scoped them out, so they were never a live reason
to carry the dependency.

### Keep ADR 0012 as accepted

Rejected. It contradicts the thesis. The reset names it directly as a
pre-thesis carryover, and leaving a third-party framework on the domain side
of the hexagon for portfolio reasons would weaken the exemplar rather than
strengthen it.

---
type: adr
status: accepted
date: 2026-05-07
---

# ADR 0012 - LangGraph inside Agent Runtime

## Context

Phase 1 proved the Chorus governance spine with a custom Python Agent Runtime:
Temporal owns durable Lighthouse workflow state, the Agent Runtime resolves
governed invocation identity, the Tool Gateway owns action authority, and
Postgres/Redpanda/eval provide evidence.

Phase 2A started with provider/model governance. The provider catalogue,
route-version tables, and provider-keyed model adapter registry are useful, but
they leave a gap in the exemplar story: Chorus has a strong orchestration and
governance boundary, yet it does not show a market-recognised agent execution
framework inside that boundary.

LangGraph is a reasonable fit for that missing layer if it is scoped carefully.
Its graph state, nodes, conditional edges, and tool-calling patterns can make
agent execution first-class. Its durable execution, checkpointing,
human-in-the-loop, memory, and deployment features overlap with responsibilities
that Chorus deliberately assigns to Temporal, Postgres audit, the Tool Gateway,
and local eval gates.

## Decision

Promote LangGraph to the first-class agent execution framework inside the
Agent Runtime boundary.

The ownership model is:

- Temporal remains the durable business workflow owner.
- Agent Runtime remains the governance boundary for tenant policy, approved
  agent version, prompt reference/hash, model route, budget, invocation ID,
  output contract, and decision-trail capture.
- LangGraph owns the per-invocation agent execution graph inside Agent Runtime.
- Model adapters remain the provider/model call boundary selected by runtime
  policy.
- Tool Gateway remains the only authority path for external actions.
- Postgres decision trail and `tool_action_audit` remain the accountability
  record.

The first LangGraph implementation should use a compiled graph invoked from the
existing `lighthouse.invoke_agent_runtime` Temporal activity. It should not use
LangGraph checkpoint persistence, durable execution, interrupts,
human-in-the-loop, long-term memory, LangGraph deployment, or LangSmith as a
core dependency.

The first graph should be deliberately narrow:

```text
prepare_context
  -> invoke_model_adapter
  -> normalise_result
  -> validate_contract
  -> final_response
```

This makes LangGraph real in the stack while preserving the Phase 1 evidence
baseline and Temporal replay boundary.

## Consequences

- Phase 2A is pivoted from provider/model governance alone to agent execution
  and provider governance.
- The current model adapter registry remains valuable; LangGraph will call into
  it rather than replacing provider policy.
- The current custom Agent Runtime is not removed. It becomes the governance
  shell around a LangGraph-backed execution engine.
- Decision-trail metadata should identify the execution engine and graph
  version so reviewers can see that LangGraph was used for agent execution.
- Tests and eval fixtures must continue to prove that workflow branches,
  gateway authority, contracts, audit, and cost/latency evidence are preserved.
- LangSmith remains optional future tooling for development observability or
  evaluation comparison. It is not part of the core local evidence stack.

## Alternatives considered

### Replace Temporal with LangGraph durable execution

Rejected. It would move business workflow durability, replay, retries, waits,
and visible failure branches away from the architecture's strongest evidence
surface. It would also create migration churn without improving the Tool
Gateway or audit story.

### Keep the custom Agent Runtime and only add provider adapters

Rejected as the Phase 2A direction. Provider adapters improve governance, but
they do not address the portfolio gap around first-class agent-framework
experience.

### Add LangSmith as the main agent observability layer

Rejected for the core stack. LangSmith is useful for traces, prompt iteration,
datasets, and eval comparison, but Chorus already separates operational
telemetry from audit accountability. The local exemplar should keep
OpenTelemetry/Grafana and Postgres audit as the default evidence surfaces.

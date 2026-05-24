---
type: adr
status: accepted
date: 2026-05-20
---

# ADR 0017 - Agent Execution Without LangGraph

## Decision

Agent reasoning runs as plain domain code inside the Agent Runtime. The Agent
Runtime calls the LLM provider port directly and does not depend on LangGraph
or another graph framework.

The Agent Runtime owns tenant policy resolution, approved agent version,
prompt reference, model route, budget cap, invocation identity, decision-trail
capture, and transcript capture. It does not own workflow durability, approval
waits, connector authority, or provider transport.

## Consequences

- Workflow durability, retries, waits, and escalation stay with Temporal and
  the workflow spine.
- Human approval and connector side effects stay with the Tool Gateway and
  connector port.
- Provider SDK calls stay behind the LLM provider port.
- Eval and replay prove the invocation path through port invariants rather
  than graph-engine metadata.

## Constraints

- Do not add an agent framework unless it has a concrete role that the workflow
  spine, Tool Gateway, and LLM provider port do not already own.
- Do not let agent execution code call provider SDKs directly.
- Do not put workflow state or connector authority inside the agent runtime.

# Agent Runtime Implementation Instructions

This package owns governed agent invocation inside the Agent Runtime boundary.
LangGraph runs inside this package as a per-invocation execution engine; it does
not own durable business workflow state.

## Rules

- Keep Temporal as the durable workflow owner. Do not add long-running business
  process state to LangGraph.
- Resolve agent identity, prompt reference, model route, budget, provider, and
  invocation ID before model execution.
- Preserve generated contract validation for agent inputs, outputs, and
  `AgentInvocationRecord`.
- Record decision-trail evidence for every invocation attempt, including
  provider/model route metadata, fallback reason, cost, latency, and graph
  execution metadata where available.
- Keep provider/model selection in runtime policy, not prompt text.
- Do not grant connector or tool authority here. External actions remain behind
  the Tool Gateway.
- Commercial provider adapters must stay disabled unless credentials and policy
  explicitly enable them.
- Runtime, provider, route, prompt, or graph changes require focused runtime
  tests and relevant eval coverage.

## Local Map

- `runtime.py` contains the runtime store, adapter registry, local/commercial
  adapter boundaries, LangGraph execution engine, fallback handling, and
  decision-trail persistence.

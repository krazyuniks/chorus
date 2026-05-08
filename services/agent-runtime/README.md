# Agent Runtime

Resolves agent identity and policy before each invocation:

- Agent version + lifecycle state (registry lookup).
- Prompt reference (Git-tracked, hashed at invocation).
- Tenant policy (RLS-scoped).
- Model route (provider catalogue — see [governance-guardrails.md](../../docs/governance-guardrails.md)).
- Budget caps (per invocation, per workflow).
- Invocation ID (correlated with workflow run).

Captures decision-trail records into Postgres for every invocation.

Owns no connector authority — tool calls go through the Tool Gateway.

Workstream B fixed the Temporal boundary as `lighthouse.invoke_agent_runtime`: it accepts a contract-shaped request and returns output validated against `contracts/agents/lighthouse_agent_io.schema.json`. Phase 1A workstream **C** implemented registry lookup, prompt/model policy resolution, local structured model invocation, generated `AgentInvocationRecord` validation, and decision-trail persistence behind that boundary.

Phase 2A pivots this service boundary to use LangGraph as the first-class
per-invocation agent execution runtime inside Agent Runtime. Temporal still
owns the durable Lighthouse workflow and Tool Gateway still owns connector
authority. Item `2A-04` now invokes the local model adapter through the
LangGraph path `prepare_context -> invoke_model_adapter -> normalise_result ->
validate_contract -> final_response` without LangGraph checkpoint persistence,
durable execution, interrupts, long-term memory, LangGraph deployment, or
LangSmith integration.

Item `2A-05` records the execution engine, graph version, graph path, and graph
path summary in the `decision_trail_entries.metadata` jsonb column alongside
the existing OTel trace/span join IDs. The generated `AgentInvocationRecord`
remains the audit contract; LangGraph metadata is execution evidence, not a
second audit source of truth.

The current happy path uses the local `lighthouse-happy-path-v1` model boundary from seeded routing policy. Phase 2A also registers a disabled-by-default `commercial.example` adapter boundary that records provider-disabled decision metadata and performs no production provider calls. Item `2A-07` adds policy-gated fallback evidence: a provider invocation failure is recorded as a failed primary decision, and an explicit fallback route can then invoke the local model boundary through the same LangGraph graph with a new invocation ID.

Item `2A-08` records route-selection evidence in `decision_trail_entries.metadata`: route ID/version where an approved immutable route version matches the selected policy, provider catalogue, selection source, selected provider/model, task kind, budget, fallback reason, observed cost, and observed latency. The BFF decision-trail projection exposes provider/model, route version, and fallback state for reviewer inspection. Adding LangGraph, provider adapters, or route-selection metadata must not give agents connector or tool authority.

See [implementation-plan.md](../../docs/implementation-plan.md).

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

Workstream B fixed the Temporal boundary as `lighthouse.invoke_agent_runtime`: it accepts a contract-shaped request and returns output validated against `contracts/agents/lighthouse_agent_io.schema.json`. Phase 1A workstream **C** now implements that boundary in `chorus.agent_runtime`: registry lookup, prompt/model policy resolution, local structured model invocation, generated `AgentInvocationRecord` validation, and decision-trail persistence.

The current happy path uses the local `lighthouse-happy-path-v1` model boundary from seeded routing policy. Commercial provider SDK adapters remain deferred behind the same boundary; adding them must not give agents connector or tool authority.

See [implementation-plan.md](../../docs/implementation-plan.md).

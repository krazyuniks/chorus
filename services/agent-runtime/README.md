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

Workstream B has fixed the Temporal boundary as `lighthouse.invoke_agent_runtime`: it accepts a contract-shaped request and returns output validated against `contracts/agents/lighthouse_agent_io.schema.json`. Phase 1A workstream **C** owns replacing the placeholder implementation with registry lookup, prompt/model policy resolution, provider calls, and decision-trail persistence without changing the workflow.

See [implementation-plan.md](../../docs/implementation-plan.md).

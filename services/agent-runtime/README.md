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

Phase 1A workstream **C** (Agent Runtime + model boundary). See [implementation-plan.md](../../docs/implementation-plan.md).

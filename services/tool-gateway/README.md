# Tool Gateway

Central enforcement point for all external action authority. For every tool call:

- Validates the grant `(agent_id, tenant_id, tool, mode)`.
- Validates argument JSON Schema.
- Enforces mode (`read` / `propose` / `write`) against the requested action.
- Applies redaction policy.
- Enforces idempotency keys.
- Triggers approval flows for risky writes.
- Emits an audit event to Postgres + Redpanda regardless of outcome.

Owns no agent reasoning. Owns no workflow state. Owns nothing except the gate.

See [ADR 0004 — Agent Runtime and Tool Gateway](../../adrs/0004-agent-runtime-and-tool-gateway.md).

Phase 1A workstream **D** (Tool Gateway + local connectors). See [implementation-plan.md](../../docs/implementation-plan.md).

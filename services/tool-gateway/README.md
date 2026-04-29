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

Workstream D implements the boundary in `chorus.tool_gateway`. The Temporal
activity `lighthouse.invoke_tool_gateway` now:

- validates generated `ToolCall`, `GatewayVerdict`, `AuditEvent`, and outbound
  email argument contracts;
- resolves `tool_grants` for `(agent_id, tenant_id, tool, mode)`;
- enforces allow, block, write-to-propose downgrade, and approval-required
  decisions;
- redacts audit arguments by grant policy;
- returns an idempotent persisted response for replayed keys;
- writes `tool_action_audit` with OTel metadata where active;
- invokes local connectors only after the gateway verdict permits it.

See [implementation-plan.md](../../docs/implementation-plan.md).

# Tool Gateway Implementation Instructions

This package owns the governed authority boundary for external tool actions.
Agents and LangGraph may request or propose actions; this package decides
whether a connector may execute them.

## Rules

- Validate tool arguments before any connector invocation.
- Resolve grants by `(tenant_id, agent_id, tool_name, mode)`.
- Honour explicit denies before downgrade or fallback logic.
- Enforce `read`, `propose`, and `write` modes. Downgrade writes to proposals
  only when grant policy allows it.
- Do not call connectors when the verdict is `block` or `approval_required`.
- Always write `tool_action_audit` for decided calls and connector failures.
- Apply redaction policy before persisting audited arguments.
- Preserve idempotency behaviour: replayed successful keys return the persisted
  response without invoking a connector again.
- Keep agent reasoning, model routing, and workflow state out of this package.

## Local Map

- `gateway.py` contains `ToolGateway`, `ToolGatewayStore`, the `ToolConnector`
  protocol, `LocalToolConnector`, grant decisions, verdict construction, audit
  writes, redaction, and connector dispatch.

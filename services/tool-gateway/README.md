# Tool Gateway

The Tool Gateway is the connector port authority layer.

For every tool call it:

- validates the grant `(agent_id, tenant_id, tool, mode)`;
- validates argument JSON Schema;
- enforces mode (`read`, `propose`, `write`);
- applies redaction policy;
- enforces idempotency keys;
- creates or checks approval packages for risky writes;
- dispatches through `ConnectorRegistry`;
- writes a tool-action audit row regardless of verdict.

The gateway owns no agent reasoning and no workflow state. Connectors are
invoked only after the gateway verdict permits execution.

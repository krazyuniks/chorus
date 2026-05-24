# Connector Implementation Instructions

This package contains the connector adapter registry and the UC1 sandbox
connector adapters used behind the Tool Gateway. After R3 D the gateway
dispatches through `ConnectorRegistry`; new connectors register an adapter
without editing the gateway.

## Rules

- Connectors must not be invoked directly by workflows, agents, or the BFF.
  Route calls through the Tool Gateway. The gateway resolves each call to an
  adapter via the registry.
- Keep connectors contract-faithful to real external behaviour. Do not add
  mocks as architecture evidence.
- Fail closed when required credentials are absent.
- Preserve tenant and correlation metadata in outbound calls where the target
  system supports it.
- Raise typed connector errors so Temporal activity retries and workflow
  compensation paths can classify failures.
- Do not write to production third-party systems from the local POC path.

## Local Map

- `types.py` defines the `ConnectorAdapter` Protocol, the `ToolSpec`
  primitive, the `ConnectorContext`, the `ConnectorRegistry`, the
  `ConnectorResult` shape, and the typed connector error hierarchy.
- `__init__.py` exposes the registry plus the `default_registry(conn)`
  factory wiring all adapters at the composition root.
- `uc1.py` holds the six UC1 sandbox adapters: `sandbox-crm`
  (quoting-queue routing), `sandbox-referral-inbox`,
  `sandbox-decline-ledger`, `sandbox-outbound-comms` (Mailpit-backed
  missing-data-request send, gated in write mode), `sandbox-customer-profile`
  (read-only profile + vulnerability markers), `sandbox-product-catalogue`
  (read-only target-market data).
- `calendar.py` carries the Radicale-backed CalDAV adapter
  (`CalendarAdapter`) wrapping `RadicaleCalendarConnector`. Kept post-R3 E
  for the UC2 / UC3 approval-required write surfaces.
- `local.py` is a thin stub after R3 E: the pre-reset Mailpit / local CRM /
  company-research connectors retired with the Lighthouse workflow.

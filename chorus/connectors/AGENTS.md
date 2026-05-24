# Connector Implementation Instructions

This package contains the connector adapter registry and the sandbox
connector adapters used behind the Tool Gateway. The gateway dispatches
through `ConnectorRegistry`; new connectors register an adapter without editing
the gateway.

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
  (persistence-backed quoting-queue routing), `sandbox-referral-inbox`
  (persistence-backed referral routing), `sandbox-decline-ledger`
  (persistence-backed decline records), `sandbox-outbound-comms`
  (Mailpit-backed missing-data-request send, gated in write mode),
  `sandbox-customer-profile` (Postgres-seeded read-only profile +
  vulnerability markers), `sandbox-product-catalogue` (Postgres-seeded
  read-only target-market data).
- `uc2.py` holds the four UC2 sandbox adapter families:
  `sandbox-conflict-check`, `sandbox-kyc-bo`, `sandbox-aml-record-store`, and
  `sandbox-engagement-letter-store`. They return deterministic synthetic
  refs and bounded statuses only; they do not call production legal, AML,
  identity, Companies House, sanctions, document-management,
  matter-management, email, or e-signature services.
- `calendar.py` carries the Radicale-backed CalDAV adapter
  (`CalendarAdapter`) wrapping `RadicaleCalendarConnector` for
  approval-required write surfaces.
- `local.py` is a compatibility module for local connector imports.

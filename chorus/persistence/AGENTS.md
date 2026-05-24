# Persistence Implementation Instructions

This package owns Postgres persistence adapters, the outbox lifecycle,
projection writes, migrations helpers, and Redpanda relay/consumer utilities.
After the R3 F decomposition the read surfaces are split per port.

## Rules

- Keep JSON Schema contracts as the source of cross-boundary payload shapes.
- Preserve tenant scoping and RLS context before tenant-owned reads or writes.
- Audit/accountability data belongs in Postgres decision trail, tool audit, and
  workflow/audit rows. OpenTelemetry IDs are join metadata, not the audit source
  of truth.
- Outbox writes must remain transactionally aligned with service-owned state.
- Projection consumers must be idempotent under Redpanda redelivery.
- Do not make Temporal workflow state depend on projections; projections are
  read models.
- Persistence changes require focused persistence tests and relevant contract
  checks.
- Each port read surface lives in its own module. Do not re-merge stores; if a
  new read crosses port boundaries, compose at the call site.

## Local Map

- `projection.py` owns the projection port: workflow event outbox + history +
  read-model write side (`record_workflow_event`, `apply_workflow_event`,
  `append_outbox_event`), the workflow read surface (`list_workflows`,
  `get_workflow`, `list_workflow_history`, `list_recent_workflow_history`), and
  the calendar projection (`list_calendar_projections`) that derives from
  approval packages joined with tool-action audit.
- `audit_port.py` owns the decision-trail and tool-action audit read surface:
  `AuditPortStore.list_decision_trail`, `AuditPortStore.list_tool_action_audit`.
- `runtime_policy.py` owns the runtime-policy snapshot:
  `PolicySnapshotStore.snapshot` composes agent registry + model routing
  policies + tool grants + immutable policy snapshot rows for a tenant.
- `provider_governance.py` owns the provider catalogue + route-version
  snapshot: `ProviderGovernanceStore.snapshot` composes provider catalogues +
  providers + provider models + route versions.
- `uc1_connectors.py` owns the local UC1 connector-side records for quoting
  queue, referral inbox, decline ledger, customer-profile lookup data, and
  product-catalogue lookup data.
- `_query.py` holds the shared row-fetch helper and tenant-context setter.
- `outbox.py` contains outbox claim, publish, retry, and DLQ lifecycle helpers.
- `redpanda.py` contains relay and projection-worker utilities.
- `migrate.py` contains migration and database URL helpers.

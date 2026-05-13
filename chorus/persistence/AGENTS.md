# Persistence Implementation Instructions

This package owns Postgres persistence adapters, the outbox lifecycle,
projection writes, migrations helpers, and Redpanda relay/consumer utilities.

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

## Local Map

- `projection.py` contains workflow projections, decision-trail views, gateway
  audit views, registry/routing/grant views, and provider-governance reads.
- `outbox.py` contains outbox claim, publish, retry, and DLQ lifecycle helpers.
- `redpanda.py` contains relay and projection-worker utilities.
- `migrate.py` contains migration and database URL helpers.

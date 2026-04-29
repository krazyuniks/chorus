# Local Connector Service

Contract-faithful CRM, company research, email proposal, and email-send modules backed by **real software** in sandbox/local mode (no mocks, no hand-rolled fakes per project policy):

- **CRM** — Postgres-backed local service implementing the connector contract end-to-end (lookup, create, update; tenant-scoped).
- **Company research** — real public APIs (Companies House for UK companies; extensible to others).
- **Email proposal / send** — Mailpit captures all outbound SMTP. Same Mailpit instance handles inbound lead intake (see [ADR 0008](../../adrs/0008-email-intake-via-mailpit.md)).

Connectors are invoked only via the Tool Gateway. They never receive uncredentialed traffic and never write to closed third-party platforms in Phase 1.

Phase 1A workstream **D** (Tool Gateway + local connectors).

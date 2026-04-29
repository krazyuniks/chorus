# Local Connector Service

Contract-faithful CRM, company research, email proposal, and email-send modules backed by **real software** in sandbox/local mode (no mocks, no hand-rolled fakes per project policy):

- **CRM** — Postgres-backed local service implementing the connector contract end-to-end (lookup, create, update; tenant-scoped).
- **Company research** — real public APIs (Companies House for UK companies; extensible to others).
- **Email proposal / send** — Mailpit captures all outbound SMTP. Same Mailpit instance handles inbound lead intake (see [ADR 0008](../../adrs/0008-email-intake-via-mailpit.md)).

Connectors are invoked only via the Tool Gateway. They never receive
uncredentialed traffic and never write to closed third-party platforms in
Phase 1.

Phase 1A Workstream D implements the connector substrate in
`chorus.connectors.local`:

- `MailpitEmailConnector` sends sandbox outbound messages to Mailpit SMTP and
  stamps correlation headers for inspection.
- `LocalCrmConnector` stores lead state in the Postgres `local_crm_leads` table.
- `CompanyResearchConnector` calls Companies House only when
  `CHORUS_COMPANIES_HOUSE_API_KEY` is configured; without the key it fails
  closed rather than returning a fake result.

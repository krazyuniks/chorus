# Local Connector Service

Contract-faithful CRM, company research, email proposal/send, calendar, and ticket modules backed by **real software** in sandbox/local mode (no mocks, no hand-rolled fakes per project policy):

- **CRM** — Postgres-backed local service implementing the connector contract end-to-end (lookup, create, update; tenant-scoped).
- **Company research** — real public APIs (Companies House for UK companies; extensible to others).
- **Email proposal / send** — Mailpit captures all outbound SMTP. Same Mailpit instance handles inbound lead intake (see [ADR 0008](../../adrs/0008-email-intake-via-mailpit.md)).
- **Calendar availability / hold proposal** — Radicale provides a local CalDAV sandbox for Phase 2C calendar connector evidence.
- **Ticket desk** — Postgres stores local Support Desk Triage case refs and proposed case-update refs for Phase 2D ticket connector evidence.

Connectors are invoked only via the Tool Gateway. They never receive
uncredentialed traffic and never write to closed third-party platforms in
Phase 1.

Phase 1A Workstream D and Phase 2C implement the connector substrate in
`chorus.connectors`:

- `MailpitEmailConnector` sends sandbox outbound messages to Mailpit SMTP and
  stamps correlation headers for inspection.
- `LocalCrmConnector` stores lead state in the Postgres `local_crm_leads` table.
- `CompanyResearchConnector` calls Companies House only when
  `CHORUS_COMPANIES_HOUSE_API_KEY` is configured; without the key it fails
  closed rather than returning a fake result.
- `RadicaleCalendarConnector` talks CalDAV/WebDAV to the local Radicale
  sandbox. Availability lookup and hold proposal can execute locally; hold
  creation and cancellation remain approval-required for normal requests and
  can execute only through the Tool Gateway's local approved apply path.
- `LocalTicketDeskConnector` reads local ticket case refs, finds duplicate case
  refs, and persists proposed case-update refs in Postgres. Ticket status
  writes remain approval-required and have no connector execution path in
  2D-02.

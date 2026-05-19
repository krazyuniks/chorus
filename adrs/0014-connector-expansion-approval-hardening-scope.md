---
type: adr
status: accepted
date: 2026-05-17
---

# ADR 0014 - Phase 2C Connector Expansion and Approval-Hardening Scope

## Context

Phase 2C opens connector expansion after Phase 2A provider governance and
Phase 2B identity, authority, approval, policy-change, and observability
boundary work. The risk is expanding straight into production integrations,
credential entry, or connector writes before the Tool Gateway approval,
idempotency, retry, compensation, audit, and eval story is explicit.

Phase 1 already proves Mailpit email capture, a Postgres-backed local CRM, and
an environment-gated Companies House lookup. The next connector should add a
different protocol shape and a risky write path without requiring production
calendar, email, CRM, identity-provider, cloud, or hosted-observability
dependencies.

## Decision

Phase 2C will use a local CalDAV calendar connector, backed by Radicale or an
equivalent local CalDAV sandbox, as the connector expansion candidate.

The connector candidate is local-only and protocol-backed:

- It uses CalDAV/iCalendar semantics against a local sandbox service.
- It does not call Google Calendar, Microsoft Graph, or any production calendar
  provider.
- It does not add OAuth, SSO, credential entry, production identity-provider
  integration, or production calendar credentials.
- It remains unreachable to agents except through the Tool Gateway.
- It is added only after the contract, approval, idempotency, retry,
  compensation, projection, audit, eval, runbook, and evidence-map expectations
  below are satisfied.

The first candidate action is a Lighthouse follow-up calendar hold. Future
contracts may name the concrete tools differently, but the scoped tool family
is:

| Tool family | Mode | Expected behaviour |
|---|---|---|
| Calendar availability lookup | `read` | Query safe local availability slots from the sandbox calendar. |
| Calendar hold proposal | `propose` | Produce a redacted proposed hold summary without creating a CalDAV event. |
| Calendar hold creation | `write` | Create one local sandbox VEVENT after Tool Gateway approval and idempotency checks. |
| Calendar hold cancellation | `write` | Compensate a previously created local sandbox hold by UID after gateway checks. |

Arguments, audit examples, projections, telemetry, eval fixtures, and seeds
must use stable refs and bounded categories, not raw attendee names, email
addresses, free-text meeting bodies, raw lead content, raw prompts, raw model
outputs, raw tool arguments, connector payloads, identity-provider claims, or
PII.

## Tool Gateway Expectations

All calendar actions go through the Tool Gateway. The gateway remains
responsible for:

- argument schema validation before any connector invocation;
- exact grant lookup by tenant, agent, tool, and mode;
- explicit deny handling before downgrade or fallback;
- `approval_required` decisions for calendar write grants before connector
  execution;
- redaction before audit persistence;
- idempotency lookup before connector invocation;
- connector invocation only when the verdict permits it;
- append-only `tool_action_audit` evidence for allow, propose,
  approval-required, denied, transient failure, compensation, and replay paths.

Calendar write grants should start as approval-required. A reviewer decision
must not call the connector directly. Any future approved apply path must
re-enter the Tool Gateway, re-check the approval package, grant, mode, expiry,
idempotency key, tenant, workflow, invocation, and safe authority references,
then call the local connector only if the package is still valid.

## Idempotency

Calendar creation must be idempotent across Temporal activity retries and
operator replay.

Expected evidence:

- Gateway idempotency key is derived from stable non-secret refs such as tenant
  ID, workflow ID, tool name, safe slot ref, and action kind.
- Connector VEVENT UID is derived from, or mapped to, the same stable safe refs.
- Replaying the same idempotency key returns the persisted
  `ToolGatewayResponse` and does not create a second calendar hold.
- A connector-side duplicate UID is classified as idempotent success only when
  tenant, workflow, tool, slot ref, and action kind match the persisted audit
  row.

## Retry And Failure Classification

The connector must classify failures before 2C runtime work is called
delivered:

| Failure class | Handling expectation |
|---|---|
| Transient CalDAV service unavailable, timeout, or retryable protocol error | Raise a typed transient connector error so Temporal activity retry can own retry timing. |
| Contract validation failure | Gateway blocks before connector invocation and writes audit evidence. |
| Grant or approval failure | Gateway blocks or returns `approval_required`; connector is not invoked. |
| Connector duplicate UID with matching idempotency context | Treat as idempotent replay and return the existing safe result. |
| Connector duplicate UID with mismatched context | Block or escalate with audit evidence; do not overwrite the event. |
| Non-retryable CalDAV rejection | Record a blocked connector outcome and branch to escalation or propose-only according to the workflow fixture. |

Errors recorded in telemetry, projections, sidecar exports, audit examples, or
fixtures must use bounded categories, not raw exception text containing
payloads, host data, credentials, or PII.

## Compensation

Calendar hold creation needs an explicit compensation path because it is the
first Phase 2 connector candidate scoped around a risky write.

Expected compensation behaviour:

- A created local calendar hold records a safe calendar event UID and connector
  invocation ID in Tool Gateway audit.
- If a later workflow branch requires rollback, a compensation activity calls
  the Tool Gateway for the cancellation action rather than calling the
  connector directly.
- The cancellation action re-checks tenant, workflow, safe event UID ref,
  grant, idempotency, approval state where required, and authority context refs.
- Successful compensation records an append-only audit event and a workflow
  history event with safe refs only.
- Failed compensation branches to escalation and remains visible in eval and
  runbook inspection.

## Projection, Audit, And Telemetry

Projection and audit surfaces should answer different questions:

- Workflow projections may show safe state such as `calendar_hold_requested`,
  `calendar_hold_created`, `calendar_hold_cancelled`,
  `calendar_hold_compensation_failed`, slot ref, event UID ref, and bounded
  status.
- Tool audit remains the authority record for requested/enforced mode,
  approval state, grant refs, idempotency key ref, verdict, connector
  invocation ID, compensation refs, and safe trace joins.
- Approval audit remains the authority record for reviewer actor refs, reviewer
  role, decision, SLA/expiry, reason category, and approval package state when
  executable approval work is promoted.
- OpenTelemetry span attributes may carry only allowed bounded fields such as
  tool name, requested/enforced mode, gateway verdict, workflow step, retry
  category, compensation category, and correlation IDs.
- Propagated baggage remains limited to the 2B-01 allow-list and must not carry
  approval IDs, policy-change IDs, event UID refs, tool arguments, or authority
  state.

## Eval And Evidence Expectations

Phase 2C runtime work is not delivered until the calendar connector has
focused evidence for:

- approval-required write does not invoke the connector;
- denied write blocks before connector invocation;
- approved local write creates one sandbox event through the gateway;
- idempotent replay returns the persisted gateway response without duplicating
  the VEVENT;
- transient CalDAV failure is retried and audited without caching a failed
  connector response as success;
- compensation cancels a previously created local hold through the gateway;
- failed compensation escalates visibly;
- no raw sensitive content, raw prompts/outputs, raw tool arguments, raw
  connector payloads, raw approval or policy rationale, identity-provider
  claims, or PII appear in contracts, telemetry baggage, projections, sidecar
  examples, audit examples, or seeds.

The smallest relevant gates for future implementation are expected to include
contract drift checks, focused Tool Gateway and connector tests, approval tests
when executable approval packages are promoted, eval fixture coverage for the
calendar happy and failure paths, and replay tests if Temporal workflow logic
changes.

## Runbook And Evidence Map Expectations

Before connector runtime work is called complete, the runbook must document:

- how to start and inspect the local CalDAV sandbox;
- how to prove that no production calendar provider is configured;
- how to inspect calendar grants, approval-required verdicts, and audit rows;
- how to inspect the local calendar event UID refs without exposing raw event
  bodies;
- how to rehearse idempotent replay and compensation;
- which gates to run for contracts, gateway, approval, eval, and replay.

The evidence map must point from the connector-expansion claim to the ADR,
contracts, local sandbox service, Tool Gateway code, approval package evidence
where promoted, eval fixtures, runbook procedures, and BFF/UI read-only
inspection surfaces.

## Non-Goals

This scope decision does not add:

- connector code;
- CalDAV contracts;
- a Radicale service;
- production calendar provider calls;
- production connector writes;
- OAuth, SSO, identity-provider integration, or credential entry;
- credential mutation;
- production cloud deployment or AWS;
- hosted observability dependencies;
- raw prompt/output capture;
- mutating admin UI;
- a second workflow.

## Consequences

The next Phase 2C item can start with contracts and local sandbox scaffolding
instead of debating connector scope. The selected connector is useful because
it exercises a protocol-backed write, approval, idempotency, retry,
compensation, and projection story while staying local and reviewable.

The choice also keeps Lighthouse Phase 1 intact: the existing Mailpit,
Postgres CRM, Companies House, Agent Runtime, Tool Gateway, Temporal, eval, and
observability paths remain the baseline. Production calendar integrations,
credentials, SSO, and cloud deployment stay deferred until a later ADR changes
the boundary.

## Alternatives Considered

### Add a production CRM connector

Rejected for Phase 2C scope. It would force credential handling and production
write questions before approval and compensation evidence is hardened.

### Add Google Calendar or Microsoft Graph directly

Rejected. The business shape is useful, but using a production provider would
pull OAuth, tenant identity, provider credentials, and production write risk
into the local reference implementation too early.

### Add a local ticketing connector first

Deferred. A local ticketing protocol could be useful for a second workflow, but
calendar holds fit the existing Lighthouse follow-up path and exercise
compensation with a small, inspectable protocol surface.

### Extend the existing Mailpit email connector

Rejected as the Phase 2C scope decision. Mailpit already proves local SMTP
capture. A CalDAV sandbox adds a different protocol and a clearer reversible
write surface without production dependencies.

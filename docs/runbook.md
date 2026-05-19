---
type: project-doc
status: phase-0
date: 2026-04-29
---

# Chorus - Local Runbook

This runbook covers the **local sandbox** runtime only. Phase 1 is design-frozen
to local/sandbox operation; production deployment, on-call rotation, and
incident response are explicit Phase 1 deferrals (see
[implementation-plan.md](./implementation-plan.md)). The runbook is the
Workstream F operational artefact; it grows with the slice.

## First-time host setup

```bash
./scripts/first-time-setup.sh
```

Idempotent. Installs `just`, `uv`, Python 3.14, `prek`; verifies Docker and
`gh` are present; runs `uv sync --all-extras`; copies `.env.example` to `.env`
if missing; registers prek-managed git hooks. Re-run any time host tooling
changes.

## Bring the stack up

```bash
just env       # ensure .env exists
just up        # docker compose up -d via scripts/dc
just status    # confirm services healthy
just doctor    # verify scaffold + workstream F + compose validity
```

`scripts/dc` is the canonical wrapper: it sources `.env`, exports `UID`/`GID`
from the host, and execs `docker compose`. Use it in scripts and ad-hoc
operations to keep environment handling consistent.

## Daily commands

| Command | Purpose |
|---|---|
| `just up` / `just down` | Bring the substrate up or down. |
| `just status` | Compose service status. |
| `just logs <service>` | Tail logs for one service. |
| `just doctor` | Scaffold + dev-loop readiness check. |
| `just contracts-check` | Schema/model/sample drift gate. |
| `just db-migrate` | Apply Postgres migrations and demo seed (Workstream A). |
| `just schemas-register` | Register event JSON Schemas with Redpanda Schema Registry. |
| `just relay-once` / `just project-once` | Move workflow events through Redpanda into Postgres projections. |
| `just worker` | Run the Lighthouse Temporal worker. |
| `just intake-once` | Poll Mailpit once and start new Lighthouse workflows. |
| `just test` / `just test-replay` / `just test-persistence` | Python gates. |
| `just test-frontend` / `just test-e2e` | Frontend gates. |
| `just lint` / `just fmt` | Linters and formatters across Python and frontend. |
| `just hooks` | Run every prek hook against the whole tree. |
| `just demo` | Send the fixture lead via Mailpit. |
| `just eval` | Run the happy-path, Phase 1B governance/failure, Phase 2A provider-fallback, and Phase 2D support eval fixtures; inspect live Postgres evidence when a workflow/correlation ID is supplied. |
| `just caldav-propfind` | Probe the local Radicale collection over WebDAV. |
| `just caldav-event-refs` | List local calendar event UID ref filenames without printing event bodies. |

## Local endpoints

| Service | URL / port |
|---|---|
| Postgres | `localhost:${CHORUS_PG_PORT:-5432}` |
| Redpanda Kafka API | `localhost:${REDPANDA_KAFKA_PORT:-9092}` |
| Redpanda Schema Registry | `localhost:${REDPANDA_SCHEMA_REGISTRY_PORT:-8081}` |
| Redpanda Console | `http://localhost:${REDPANDA_CONSOLE_PORT:-8080}` |
| Temporal | `localhost:${TEMPORAL_PORT:-7233}` |
| Temporal UI | `http://localhost:${TEMPORAL_UI_PORT:-8233}` |
| Mailpit SMTP | `localhost:${MAILPIT_SMTP_PORT:-1025}` |
| Mailpit UI / HTTP API | `http://localhost:${MAILPIT_HTTP_PORT:-8025}` |
| Radicale / CalDAV sandbox | `http://localhost:${CALDAV_SANDBOX_PORT:-5232}` |
| Grafana | `http://localhost:${GRAFANA_PORT:-3001}` |
| OTLP gRPC / HTTP | `localhost:${OTEL_GRPC_PORT:-4317}` / `localhost:${OTEL_HTTP_PORT:-4318}` |
| BFF | `localhost:${BFF_PORT:-8000}` |
| Frontend | `http://localhost:${FRONTEND_PORT:-5173}` |

Override any of these in `.env`. Compose interpolates at config time; rerun
`just doctor` after edits to catch typos.

## Workstream A persistence operations

Apply the idempotent migration and seed path:

```bash
just db-migrate
```

When the default Postgres port is occupied, point the migration runner at the
Compose port override:

```bash
CHORUS_DATABASE_URL=postgresql://chorus:chorus@localhost:55432/chorus uv run python -m chorus.persistence.migrate
```

Relay one due outbox batch to Redpanda:

```bash
just relay-once
```

Project one bounded Redpanda batch into Postgres read models:

```bash
just project-once
```

The relay claims rows with `FOR UPDATE SKIP LOCKED`, changes status to
`publishing`, increments `attempts`, and then marks each row `sent` or
`failed`. Failed rows keep `last_error` and retry through `next_attempt_at`.
The projection worker commits Kafka offsets only after the Postgres projection
transaction succeeds; redelivery is safe because projections are idempotent by
source event and workflow sequence.

## Workstream B workflow operations

The normal local stack runs the Lighthouse worker as the
`chorus-intake-poller` Compose service. It uses the same
`chorus.workflows.worker` entry point as the host recipe, but runs under the
service-template `opentelemetry-instrument` entrypoint so Temporal spans, OTel
metrics, and stdout logs join the Grafana stack.

Run the host worker only for focused development:

```bash
just worker
```

Send the fixture email and poll Mailpit once:

```bash
just demo && just intake-once
```

The poller reads `http://localhost:8025/api/v1/messages`, fetches message detail,
parses the generated `lead_intake` contract, deduplicates by `Message-ID`, and
starts one Lighthouse workflow using a stable `lighthouse-<sha256>` workflow ID.
If a workflow with that Message-ID-derived ID already exists, the poll result
records it as a duplicate rather than starting another run.

When repeatedly rehearsing against a persistent Mailpit volume, use a fixture
with a fresh `Message-ID` or reset local Mailpit state before expecting a new
workflow from the same fixture.

The workflow emits `WorkflowEvent` payloads through
`lighthouse.record_workflow_event`; that activity calls
`ProjectionStore.record_workflow_event()`. The activity stamps the active span
with `chorus.tenant_id`, `chorus.correlation_id`, and `chorus.workflow_id`;
the outbox row's `metadata` captures the active OTel trace/span IDs when the
worker is running under instrumentation.

Register event schemas before using Schema Registry evidence:

```bash
just schemas-register
```

To see the BFF/UI read model advance, run the Workstream A relay/projection
commands after workflow activity events have been written:

```bash
just relay-once && just project-once
```

Worker metrics are emitted through the OpenTelemetry SDK to the collector and
scraped from the collector's Prometheus endpoint. There is intentionally no
worker sidecar HTTP `/metrics` endpoint or
`infrastructure/prometheus/targets/intake-poller.yml` file in Phase 1A.

## Phase 1A review path

The 3-minute review path uses the live local stack for evidence surfaces and
the deterministic eval as the final release gate:

```bash
just up && just db-migrate && just schemas-register && just doctor
just demo && just intake-once
just relay-once && just project-once
just eval
```

Capture the workflow's `correlation_id` from the BFF/UI or SQL, then inspect:

- Lighthouse UI/BFF workflow detail, decision trail, tool verdicts, registry,
  grants, and routing views.
- Temporal UI by workflow ID.
- Redpanda Console for `chorus.workflow.events.v1` and registered event schemas.
- Grafana dashboards by pasting the same `correlation_id` into `$correlation`.
- Postgres `decision_trail_entries` and `tool_action_audit` by correlation ID.

To make `just eval` assert persisted live happy-path evidence as well as the
deterministic fixture set, rerun it with the join key:

```bash
CHORUS_EVAL_CORRELATION_ID=<correlation-id> just eval
```

For a live governance/failure run, target the matching fixture explicitly with
`uv run python -m chorus.eval.run --fixture chorus/eval/fixtures/<fixture>.json`.

Set `CHORUS_EVAL_REQUIRE_LIVE=1` when the live substrate is expected to be
available and missing persisted evidence should fail the gate. Full live
inspection requires Postgres migrations/seeds, the Mailpit-triggered workflow,
the Redpanda relay/projection path, decision-trail rows from Agent Runtime, and
Tool Gateway audit rows. Temporal, Redpanda, Grafana, and Mailpit are review
surfaces; the eval harness reads the persisted Postgres evidence.

## Workstream C Agent Runtime operations

`lighthouse.invoke_agent_runtime` resolves runtime policy from Postgres and
writes one `decision_trail_entries` row per invocation. The Phase 1A seed
routes every Lighthouse role to the local `lighthouse-happy-path-v1` structured
model boundary, so the happy path runs without commercial provider credentials.

Phase 2A now runs that invocation through a compiled LangGraph graph inside
Agent Runtime. Temporal still owns the durable Lighthouse workflow, and the
Tool Gateway still owns connector authority. The graph is invoked with
`graph.invoke()` only; there is no LangGraph checkpoint persistence, durable
execution, long-term memory, hosted deployment, LangSmith dependency, or
mutating route UI in the local evidence path.

Inspect the runtime policy for a tenant:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT role, agent_id, version, lifecycle_state, prompt_reference, prompt_hash FROM agent_registry WHERE tenant_id = 'tenant_demo' ORDER BY role;"
```

Inspect the selected model routes:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT agent_role, task_kind, provider, model, budget_cap_usd FROM model_routing_policies WHERE tenant_id = 'tenant_demo' ORDER BY agent_role, task_kind;"
```

Read the decision trail for a workflow correlation ID:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT correlation_id, agent_role, agent_version, prompt_reference, provider, model, task_kind, outcome, cost_amount, duration_ms, started_at FROM decision_trail_entries WHERE correlation_id = '<correlation-id>' ORDER BY started_at;"
```

Inspect graph execution and route-selection metadata for the same run:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT correlation_id, agent_role, outcome, metadata #>> '{agent_execution,engine}' AS engine, metadata #>> '{agent_execution,graph_version}' AS graph_version, metadata #> '{agent_execution,graph_path}' AS graph_path, metadata #>> '{model_route,route_version}' AS route_version, metadata #>> '{model_route,selection_source}' AS selection_source, metadata #>> '{provider_fallback,reason}' AS fallback_reason, started_at FROM decision_trail_entries WHERE correlation_id = '<correlation-id>' ORDER BY started_at;"
```

Inspect the Phase 2A provider catalogue and provider models:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT provider_id, display_name, provider_kind, lifecycle_state, credential_required, secret_ref_names, missing_credentials_behaviour FROM provider_catalogue_providers ORDER BY catalogue_id, provider_id;"
```

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT provider_id, model_id, lifecycle_state, supported_task_kinds, supports_structured_output FROM provider_catalogue_models ORDER BY catalogue_id, provider_id, model_id;"
```

Inspect immutable route versions for the demo tenant:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT agent_role, task_kind, route_version, lifecycle_state, provider_catalogue_id, provider_id, model_id, budget_cap_usd, max_latency_ms, fallback_policy, eval_fixture_refs FROM model_route_versions WHERE tenant_id = 'tenant_demo' ORDER BY agent_role, task_kind, route_version;"
```

The seeded provider catalogue includes `commercial.example` only as a disabled
placeholder. It exists to prove catalogue shape, disabled-provider evidence,
and fallback handling. Setting `CHORUS_COMMERCIAL_LLM_API_KEY` does not enable
a production commercial provider call path in the current implementation; a
real provider adapter and route-promotion policy belong to later Phase 2 work.

To inspect disabled-provider or provider-fallback evidence, run the deterministic
fixture rather than editing seeded routes by hand:

```bash
uv run python -m chorus.eval.run --fixture chorus/eval/fixtures/lighthouse_provider_fallback.json
```

For persisted rows, the relevant decision-trail metadata fields are:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT correlation_id, agent_role, provider, model, outcome, metadata #>> '{provider_boundary,state}' AS boundary_state, metadata #>> '{provider_boundary,reason}' AS boundary_reason, metadata #>> '{provider_failure,reason}' AS provider_failure, metadata #>> '{provider_fallback,applied}' AS fallback_applied, metadata #>> '{provider_fallback,reason}' AS fallback_reason, started_at FROM decision_trail_entries WHERE correlation_id = '<correlation-id>' ORDER BY started_at;"
```

Agents still have no tool authority. Decision rows contain structured agent
reasoning evidence and an empty `tool_call_ids` array until Workstream D records
Tool Gateway calls behind `lighthouse.invoke_tool_gateway`.

## Workstream D Tool Gateway operations

`lighthouse.invoke_tool_gateway` now resolves grants, validates tool contracts,
enforces modes, redacts audit arguments, applies idempotency, and invokes local
connectors only after the gateway has emitted an explicit verdict. The
Lighthouse happy path calls `email.propose_response` in `propose` mode; Mailpit
captures the resulting sandbox outbound message.

Inspect grants for the Lighthouse drafter:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT agent_id, agent_version, tool_name, mode, allowed, approval_required, redaction_policy FROM tool_grants WHERE tenant_id = 'tenant_demo' AND agent_id = 'lighthouse.drafter' ORDER BY tool_name, mode;"
```

Inspect gateway audit for a workflow correlation ID:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT correlation_id, agent_id, tool_name, requested_mode, enforced_mode, verdict, reason, arguments_redacted, metadata, occurred_at FROM tool_action_audit WHERE correlation_id = '<correlation-id>' ORDER BY occurred_at;"
```

Idempotency is enforced by `tenant_id`, `tool_name`, and `idempotency_key`: a
replayed activity returns the original persisted `ToolGatewayResponse` and does
not invoke the connector again. Audit rows store the generated `AuditEvent`
payload in `raw_event`, including the generated `GatewayVerdict`.

The Mailpit connector defaults to `localhost:1025` for host tests. In Compose,
set `CHORUS_MAILPIT_SMTP_HOST=mailpit` and `CHORUS_MAILPIT_SMTP_PORT=1025` for
worker containers. Companies House lookup remains environment-gated by
`CHORUS_COMPANIES_HOUSE_API_KEY`; absence of that key blocks research connector
execution instead of falling back to a fake result.

### Phase 2C local CalDAV connector scope

ADR 0014 selects a local CalDAV calendar connector, backed by Radicale, as the
Phase 2C connector-expansion candidate. The calendar argument schemas and
generated models exist for `calendar.lookup_availability`,
`calendar.propose_hold`, `calendar.create_hold`, and `calendar.cancel_hold`,
with safe representative samples under `contracts/tools/samples/`.

2C-02 adds the local-only Radicale sandbox and connector dispatch behind the
Tool Gateway:

- `compose.yml` runs `radicale` as `chorus-caldav-sandbox` on
  `http://localhost:${CALDAV_SANDBOX_PORT:-5232}`.
- `infrastructure/radicale/config` sets a local unauthenticated sandbox with
  anonymous local rights from `infrastructure/radicale/rights`.
- `chorus.connectors.calendar.RadicaleCalendarConnector` talks CalDAV/WebDAV to
  the configured `CHORUS_CALDAV_BASE_URL`.
- `chorus.tool_gateway.LocalToolConnector` dispatches the four calendar tool
  names only after Tool Gateway validation, grant resolution, mode enforcement,
  idempotency lookup, and verdict handling.
- Seeded calendar write grants for `calendar.create_hold` and
  `calendar.cancel_hold` are `approval_required`, so the connector is not
  invoked for writes in the current runtime.
- 2C-03 promotes a minimal local `approval_packages` table for those calendar
  write verdicts. The gateway creates a `requested` package with safe refs,
  idempotency key hash, SLA/expiry refs, grant/policy refs, redaction summary,
  and trace joins, then still stops before connector execution.
- 2C-04 adds a local approved-apply path inside the Tool Gateway for focused
  evidence. It consumes an already approved calendar package, derives a stable
  apply idempotency key, re-checks package state, expiry, grant, tenant,
  workflow, invocation, original idempotency key hash, and safe calendar refs,
  then invokes the Radicale connector only from the gateway.

There is still no reviewer decision path, reviewer UI, calendar eval fixture,
Lighthouse workflow calendar branch, or UI mutation surface for calendar
actions. 2C-05 adds a read-only BFF calendar status projection derived from
local approval/audit rows; it does not create a mutating calendar UI or
workflow branch.

Start and inspect the sandbox:

```bash
just up
just caldav-propfind
just caldav-event-refs
```

`just caldav-propfind` returns WebDAV collection metadata. `just
caldav-event-refs` lists only safe `evt_*.ics` filenames from the local
Radicale storage volume and does not print raw iCalendar event bodies.

To prove no production calendar provider is configured, inspect only these
local settings:

```bash
rg -n "CALDAV|RADICALE|Google|Microsoft|OAuth|Graph" .env.example compose.yml chorus/connectors docs/runbook.md
```

The implemented connector has no Google Calendar, Microsoft Graph, OAuth,
production calendar credential, or production provider call path. The only
calendar endpoint is `CHORUS_CALDAV_BASE_URL`, defaulting to the local
Radicale sandbox.

Inspect calendar grants:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT agent_id, agent_version, tool_name, mode, allowed, approval_required, redaction_policy FROM tool_grants WHERE tenant_id = 'tenant_demo' AND tool_name LIKE 'calendar.%' ORDER BY tool_name, mode;"
```

Inspect calendar gateway audit for a workflow or focused test correlation ID:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT correlation_id, tool_name, requested_mode, enforced_mode, verdict, reason, connector_invocation_id, arguments_redacted, metadata, occurred_at FROM tool_action_audit WHERE tenant_id = 'tenant_demo' AND tool_name LIKE 'calendar.%' ORDER BY occurred_at DESC LIMIT 20;"
```

Inspect calendar approval packages created by approval-required writes:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT approval_id, approval_state, correlation_id, workflow_id, tool_name, requested_action, requested_mode, enforced_mode, idempotency_key_ref, redaction_summary, sla_policy_ref, expires_at, grant_id, policy_version_refs, trace_join FROM approval_packages WHERE tenant_id = 'tenant_demo' ORDER BY requested_at DESC LIMIT 20;"
```

Approval packages contain only safe refs and bounded categories. They do not
store raw tool arguments, raw connector payloads, attendee names, email
addresses, reviewer identity claims, raw rationale, credentials, or PII.

For current Phase 2C evidence, `calendar.lookup_availability` and
`calendar.propose_hold` may invoke the local connector when grants allow them.
`calendar.create_hold` and `calendar.cancel_hold` should return
`approval_required`, create one requested approval package, and keep
`connector_invocation_id` empty. Focused tests then mark the package approved
inside local Postgres and call `ToolGateway.apply_approved_calendar_write()`;
that method re-enters the gateway, re-checks the package and authority refs,
and writes bounded apply audit before any connector execution.

Inspect approved apply audit rows without printing raw event bodies:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT correlation_id, tool_name, verdict, reason, connector_invocation_id, raw_event->'details'->'approval_apply' AS approval_apply, raw_event->'details'->'connector_failure' AS connector_failure FROM tool_action_audit WHERE tenant_id = 'tenant_demo' AND tool_name IN ('calendar.create_hold', 'calendar.cancel_hold') ORDER BY occurred_at DESC LIMIT 20;"
```

Inspect the BFF's safe calendar status projection:

```bash
curl -s "http://localhost:${BFF_PORT:-8000}/api/calendar/status" | jq
```

```bash
curl -s "http://localhost:${BFF_PORT:-8000}/api/workflows/<workflow-id>/calendar/status" | jq
```

The projection is derived from `approval_packages` and matching
`tool_action_audit` rows where `raw_event.details.approval_apply.approval_id`
matches the package. It exposes bounded statuses such as
`calendar_hold_requested`, `calendar_hold_approved_pending_apply`,
`calendar_hold_created`, `calendar_hold_cancelled`,
`calendar_hold_retry_pending`, `calendar_hold_blocked`, and
`calendar_hold_compensation_failed`, plus safe approval/audit refs,
idempotency key refs, calendar refs, grant/policy refs, retry/compensation
categories, failure categories, and trace joins. It does not include raw event
bodies, raw tool arguments, raw connector payloads, raw approval or policy
rationale, attendee names, email addresses, identity-provider claims,
credentials, API keys, access tokens, or PII.

Idempotent replay evidence is in `tool_action_audit`: the approval request row
uses the original idempotency key and the approved apply row uses a stable
package-bound apply idempotency key ref. Replaying the same approved apply
request returns the persisted `ToolGatewayResponse` and does not invoke the
connector again. Connector-side duplicate VEVENT UIDs are idempotent only when
the stored safe calendar, hold, slot, event UID, meeting, summary, and
participant refs match the requested create context; mismatched duplicate UIDs
are blocked with `caldav_duplicate_uid_context_mismatch`.

Compensation evidence is also gateway-owned. A cancellation compensation uses
`calendar.cancel_hold` through `ToolGateway.apply_approved_calendar_write()`;
successful compensation records `compensation_completed`, while failed
compensation records `compensation_failed` plus the bounded escalation category
`calendar_compensation_failed`. Do not inspect Radicale `.ics` bodies for this
evidence; use the safe event UID refs and gateway audit rows.

Future calendar connector work must remain local-only and gateway-only:

1. Use the Tool Gateway for availability lookup, hold proposal, hold creation,
   and hold cancellation. Workflows, agents, LangGraph, and the BFF must not
   call the connector directly.
2. Start calendar write grants as `approval_required`. A reviewer decision must
   not call the connector; the approved apply path re-enters the Tool Gateway
   and re-checks package state, grant, mode, expiry, idempotency, tenant,
   workflow, invocation, and safe authority refs.
3. Derive idempotency from stable non-secret refs and map the connector VEVENT
   UID to the same safe context so replay cannot create duplicate holds.
4. Classify transient CalDAV failures for Temporal activity retry, distinguish
   idempotent duplicate UIDs from conflicting duplicate UIDs, and use bounded
   failure categories in telemetry, projections, and audit.
5. Compensate created local holds by calling a cancellation action through the
   Tool Gateway, not by calling the connector directly.
6. Project only safe status and refs such as hold requested, created,
   cancelled, compensation failed, slot ref, event UID ref, workflow ID, and
   correlation ID.
7. Keep raw event bodies, attendee names, email addresses, raw lead content,
   raw prompts/outputs, raw tool arguments, raw connector payloads, raw
   approval or policy rationale, identity-provider claims, credentials, API
   keys, access tokens, and PII out of contracts, telemetry baggage,
   projections, sidecar examples, audit examples, and seeds.

For contract inspection, run `just contracts-check` and inspect:

- `contracts/tools/calendar_availability_lookup_args.schema.json`
- `contracts/tools/calendar_hold_proposal_args.schema.json`
- `contracts/tools/calendar_hold_creation_args.schema.json`
- `contracts/tools/calendar_hold_cancellation_args.schema.json`
- `contracts/tools/tool_call.schema.json`
- `chorus/contracts/generated/tools/`

Calendar eval fixtures if promoted and workflow projections remain later work.
Production calendar providers such as Google Calendar or Microsoft Graph,
OAuth, production SSO, credential entry, production connector writes, hosted
observability dependencies, and mutating admin UI remain out of scope.

### Phase 2D Support Desk Triage scope

ADR 0015 selects local Support Desk Triage as the Phase 2D second workflow
proof. 2D-01 adds the contract-only baseline for safe support intake, support
agent IO, local ticket tool arguments, workflow-event values, and eval contract
values. 2D-02 adds a Postgres-backed local ticket desk sandbox behind the Tool
Gateway for read/propose ticket evidence. 2D-03 adds the smallest
code-defined `support_triage` Temporal workflow runtime and replay baseline
using the existing Agent Runtime and Tool Gateway activity boundaries. 2D-04
adds the support eval fixture and persisted evidence baseline for the happy
path. There is still no Support BFF route, UI route, production ticketing
provider, reviewer decision UI, credential entry, ticket status execution, or
workflow DSL.

The selected future workflow type is `support_triage`. It should cover support
request intake, classification and severity triage, account or case context
lookup, resolution planning, response and case-update proposal, validation,
completion, and escalation. It is a code-defined Temporal workflow, not a
workflow DSL, and it reuses the existing Agent Runtime, LangGraph inside Agent
Runtime, and Tool Gateway activity boundaries. Later items still need
Redpanda/projection inspection, BFF/UI read-only projection if promoted, and
OTel/Grafana evidence.

Future support-ticket actions must remain local-only and gateway-only:

1. Use the Tool Gateway for case lookup, duplicate-case lookup, proposed case
   update, and any later local write.
2. Start local ticket writes as `approval_required`; a reviewer decision must
   not call the connector directly.
3. Use stable refs and bounded categories such as `request_ref`, `case_ref`,
   `account_ref`, `product_ref`, `severity_category`,
   `case_status_category`, idempotency key refs, workflow ID, correlation ID,
   and failure categories.
4. Keep raw request content, raw prompts/outputs, raw tool arguments, raw
   connector payloads, raw approval or policy rationale, identity-provider
   claims, personal names, email addresses, credentials, API keys, access
   tokens, and PII out of contracts, telemetry baggage, projections, sidecar
   examples, audit examples, seeds, and fixtures.

2D-02 local ticket desk inspection:

- `chorus.connectors.ticket.LocalTicketDeskConnector` reads safe case refs from
  `local_ticket_cases`, finds duplicate case refs, and writes proposed
  case-update refs to `local_ticket_case_update_proposals`.
- `chorus.tool_gateway.LocalToolConnector` dispatches
  `ticket.lookup_case`, `ticket.lookup_duplicates`, and
  `ticket.propose_case_update` only after Tool Gateway validation, grant
  resolution, mode enforcement, idempotency lookup, and verdict handling.
- Seeded `ticket.update_status` is `approval_required`; normal requests return
  an approval-required verdict and keep `connector_invocation_id` empty. There
  is no ticket approved-apply path in 2D-02.

2D-03 support workflow runtime inspection:

- `chorus.workflows.support.SupportTriageWorkflow` runs on the same worker
  entry point and default local task queue as Lighthouse.
- The worker registers `SupportTriageWorkflow` plus
  `support.record_workflow_event`; the support workflow reuses
  `lighthouse.invoke_agent_runtime` and `lighthouse.invoke_tool_gateway`.
- The local happy path calls support classification, context lookup,
  resolution planning, and validation through Agent Runtime, then calls
  `ticket.lookup_case`, `ticket.lookup_duplicates`, and
  `ticket.propose_case_update` through the Tool Gateway.
- The workflow does not call `ticket.update_status`; status writes remain
  approval-required and there is still no ticket approved-apply path.
- Replay evidence is in
  `tests/workflows/fixtures/support_triage_happy_history.json`, generated by
  `uv run python scripts/generate_support_triage_history.py`.

2D-04 support eval and persisted evidence inspection:

- `chorus/eval/fixtures/support_triage_happy_path.json` asserts the
  `support_triage` happy path, final completion, support Agent Runtime
  decisions, ticket lookup/duplicate/proposal Tool Gateway verdicts, proposed
  `caseupd_support_001`, no `ticket.update_status` call, no case-status
  mutation, and safe tenant/correlation/workflow joins.
- `infrastructure/postgres/migrations/009_support_eval_persisted_evidence_baseline.sql`
  aligns `decision_trail_entries` with the support agent roles so support
  decisions can persist.
- `tests/persistence/test_postgres_foundation.py` includes a focused support
  evidence test that joins workflow events, support decisions, ticket audit
  rows, and the local proposed case-update row by safe refs.

Run focused support runtime/replay checks:

```bash
uv run pytest tests/workflows/test_support_workflow.py tests/workflows/test_activities.py tests/agent_runtime/test_runtime.py -k 'support or Support' -q
```

```bash
just test-replay
```

Run support eval evidence checks:

```bash
uv run python -m chorus.eval.run --fixture chorus/eval/fixtures/support_triage_happy_path.json
just eval
```

To assert a persisted local support run, pass either the workflow ID or
correlation ID and require live evidence:

```bash
CHORUS_EVAL_WORKFLOW_ID=<support-workflow-id> uv run python -m chorus.eval.run --fixture chorus/eval/fixtures/support_triage_happy_path.json --require-live
```

Inspect support workflow outbox rows after a local run by correlation ID:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT workflow_id, event_type, step, payload FROM outbox_events WHERE tenant_id = 'tenant_demo' AND correlation_id = '<correlation-id>' AND payload->>'workflow_type' = 'support_triage' ORDER BY sequence;"
```

Inspect support Agent Runtime decisions for a local run:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT workflow_id, agent_id, agent_role, task_kind, provider, model, outcome, contract_refs, metadata FROM decision_trail_entries WHERE tenant_id = 'tenant_demo' AND correlation_id = '<correlation-id>' AND agent_role LIKE 'support_%' ORDER BY created_at;"
```

Inspect support ticket grants:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT agent_id, agent_version, tool_name, mode, allowed, approval_required, redaction_policy FROM tool_grants WHERE tenant_id = 'tenant_demo' AND tool_name LIKE 'ticket.%' ORDER BY agent_id, tool_name, mode;"
```

Inspect safe local ticket case refs and proposed update refs:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT case_ref, request_ref, account_ref, product_ref, severity_category, status_category, duplicate_group_ref, recent_status_refs FROM local_ticket_cases WHERE tenant_id = 'tenant_demo' ORDER BY case_ref;"
```

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT case_update_ref, request_ref, case_ref, account_ref, product_ref, severity_category, target_status_category, update_reason_category, proposal_status FROM local_ticket_case_update_proposals WHERE tenant_id = 'tenant_demo' ORDER BY updated_at DESC LIMIT 20;"
```

Inspect ticket gateway audit for focused tests or a future workflow
correlation ID:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}" -c "SELECT correlation_id, tool_name, requested_mode, enforced_mode, verdict, reason, connector_invocation_id, arguments_redacted, metadata, occurred_at FROM tool_action_audit WHERE tenant_id = 'tenant_demo' AND tool_name LIKE 'ticket.%' ORDER BY occurred_at DESC LIMIT 20;"
```

These tables and audit rows contain only safe refs and bounded categories. Do
not add or inspect raw request bodies, raw prompts/outputs, raw tool arguments,
raw connector payloads, raw approval or policy rationale, identity-provider
claims, personal names, email addresses, credentials, access tokens, API keys,
or PII for ticket evidence.

The current 2D-01 contract inspection set is:

- `contracts/events/support_request_intake.schema.json`
- `contracts/agents/support_agent_io.schema.json`
- `contracts/tools/ticket_case_lookup_args.schema.json`
- `contracts/tools/ticket_duplicate_case_lookup_args.schema.json`
- `contracts/tools/ticket_case_update_proposal_args.schema.json`
- `contracts/tools/ticket_status_update_args.schema.json`
- `contracts/tools/tool_call.schema.json`
- `contracts/events/workflow_event.schema.json`
- `contracts/events/agent_invocation_record.schema.json`
- `contracts/eval/eval_fixture.schema.json`
- `chorus/contracts/generated/`

Run the support contract drift checks with:

```bash
just contracts-check
uv run pytest tests/test_contracts.py
```

These contracts and samples contain only refs and bounded categories. 2D-04
now adds only the support eval and persisted evidence baseline on top of the
2D-03 support workflow runtime and the 2D-02 ticket connector/Tool Gateway
read/propose dispatch path. It does not imply a Support BFF route, UI route,
production ticketing provider, or ticket write path.

Before any later 2D implementation item is called complete, inspect the
following surfaces:

- contracts and generated models for support intake, support agent IO, support
  ticket tool arguments, workflow events, and eval fixtures;
- Temporal replay histories for the support workflow happy path and any
  support-specific failure branches introduced by code;
- `just eval` output or targeted eval output for support-specific fixtures;
- Postgres workflow projections, decision trail, and `tool_action_audit` rows
  joined by `workflow_id` and `correlation_id`;
- BFF/UI read-only support workflow inspection endpoints or views if promoted;
- Grafana/OTel spans with `chorus.workflow.type=support_triage` and bounded
  `chorus.workflow.step` values.

Lighthouse remains the default review path until Support Desk Triage has its
own complete evidence. Do not rename Lighthouse activity boundaries, delete
Lighthouse eval/replay fixtures, change the existing demo script, or make a
shared helper that weakens Lighthouse replay compatibility without explicit
replay coverage.

For the next support read-only inspection item, expected gates are focused
BFF/UI tests if those surfaces are added, frontend gates if UI changes, `just
contracts-check`, `git diff --check`, and the smallest relevant persistence or
eval gate needed to prove the inspection path. Mutating reviewer decisions and
ticket status execution remain out of scope.

## Workstream E BFF + UI operations

The BFF runs as the `chorus-bff` Compose service under the
`opentelemetry-instrument` entrypoint and exposes:

- `GET /health` — liveness probe used by `just doctor`.
- `GET /api/workflows` and `GET /api/workflows/{workflow_id}` — refresh-safe
  `workflow_read_models` projections.
- `GET /api/workflows/{workflow_id}/events` — append-only history from
  `workflow_history_events`, ordered by `sequence`.
- `GET /api/workflows/{workflow_id}/decision-trail` and
  `GET /api/workflows/{workflow_id}/tool-verdicts` — per-run audit.
- `GET /api/decision-trail` and `GET /api/tool-verdicts` — recent rows
  across the tenant for the index views.
- `GET /api/runtime/registry`, `/api/runtime/grants`, `/api/runtime/routing`
  — read-only governance state.
- `GET /api/runtime/providers`, `/api/runtime/provider-models`,
  `/api/runtime/route-versions` — read-only Phase 2A provider catalogue,
  provider model, and immutable route-version state.
- `GET /api/graph-executions` and
  `/api/workflows/{workflow_id}/graph-executions` — read-only LangGraph
  execution evidence projected from decision-trail metadata.
- `GET /api/calendar/status` and
  `/api/workflows/{workflow_id}/calendar/status` — read-only Phase 2C calendar
  status projection derived from local approval packages and Tool Gateway
  audit rows. It exposes only safe calendar refs, approval/audit refs, bounded
  projection status, retry/compensation/failure categories, grant/policy refs,
  and safe trace joins.
- `GET /api/progress` — Server-Sent Events stream of workflow-history rows.
  Optional `workflow_id` / `correlation_id` query parameters scope the
  stream; `?once=true` makes the stream terminate after one batch (used
  by tests). Frames carry the `event: progress` type and a JSON payload
  matching `WorkflowHistoryEventReadModel`.

The SSE endpoint polls `ProjectionStore.list_recent_workflow_history`
every `CHORUS_BFF_SSE_POLL_INTERVAL_SECONDS` (default `1.0`). It is a
progress channel only — every UI route fetches its projection on mount,
so a refresh or a reconnect rebuilds the full view from Postgres without
relying on retained SSE state. To force a full re-fetch in the browser,
reload the tab; to cut the live stream, navigate away and back.

For focused host development:

```bash
just bff           # uvicorn chorus.bff.app:app --reload on $BFF_PORT
just frontend-dev  # Vite dev server proxying /api to the BFF
```

The frontend uses the `VITE_USE_FIXTURES=true` env to fall back to the
in-memory fixtures (used by Playwright's e2e config); this short-circuits
the SSE EventSource so the offline tests do not require a live BFF.

When SSE looks stuck, check three things in order: the BFF container is
healthy (`just logs bff`), the projection worker is
consuming Redpanda into `workflow_history_events` (run
`just project-once` and confirm
the count increments), and the Vite proxy is reaching the BFF
(`curl -s http://localhost:${BFF_PORT:-8000}/health`).

## Operational procedures

### Stuck Lighthouse workflow

A workflow can hang on a long-poll activity, a wait-for-signal, or a deadlocked external dependency. Decide between **terminate** and **reset** by what state you need preserved.

1. Open the Temporal UI at `http://localhost:${TEMPORAL_UI_PORT:-8233}` and locate the run by workflow ID.
2. Inspect the pending activity, signal, or timer in the event history. The last `WorkflowTaskCompleted` event tells you where the deterministic logic last ran.
3. **Terminate** (`Terminate` button or `temporal workflow terminate -w <id>`) when the run should not be retried — for example, a fixture replay that finished its purpose, or a workflow stuck on a contract that has since been removed. Terminate is final; the workflow will not resume.
4. **Reset** (`Reset` button or `temporal workflow reset -w <id> --event-id <n>`) when you want to rewind to a prior decision and rerun forward — for example, when an activity returned bad data because of a fixed external bug. Pick the `WorkflowTaskCompleted` immediately before the bad branch.
5. After either action, confirm in the Postgres `decision_trail_entries` and `tool_action_audit` tables that the audit trail still makes sense: terminated workflows leave an `escalated` or `terminated` marker; reset workflows append fresh decision rows from the reset point.

Never `down -v` or wipe Postgres to "fix" a stuck workflow. The audit trail is part of the evidence; losing it is worse than the stuck run.

### Reading the Tool Gateway audit for a denied call

Every Tool Gateway call writes a row to `tool_action_audit` regardless of verdict. To investigate a denied or downgraded call:

```bash
./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}"
```

Inside psql:

```sql
SELECT correlation_id, tenant_id, tool_name, requested_mode, enforced_mode, verdict, reason, occurred_at
FROM tool_action_audit
WHERE correlation_id = '<workflow-id>'
ORDER BY occurred_at;
```

`verdict` is one of `allow`, `rewrite`, `propose`, `approval_required`, `block`, or `recorded`. `reason` carries the gateway's decision rationale (grant mismatch, schema rejection, redaction trigger, idempotency replay). Cross-reference with the workflow's `decision_trail_entries` rows by `correlation_id` to see which agent invocation initiated the call.

If the verdict is unexpected, the gateway grant policy or the connector's argument schema is the next place to look — never the agent prompt; agents have no ambient authority by design.

### Regenerating Pydantic models after a contract change

`contracts/` is canonical. When a JSON Schema changes:

1. Edit the schema under `contracts/<category>/<name>.schema.json`.
2. Refresh the representative sample under the matching `samples/` directory if the change is breaking.
3. Regenerate the Pydantic models:

   ```bash
   just contracts-gen
   ```

4. Verify the drift gate is clean:

   ```bash
   just contracts-check
   ```

5. Update any service code that consumed the old model. The compile-time signature is the contract; pyright will fail strict mode if a field disappeared or changed type.
6. If the change is breaking across services, file a contract ADR before merging.

Never hand-edit generated Pydantic files; the gate will fail on the next regeneration.

### Reset the local stack to a clean slate

Use this when fixtures have polluted Postgres beyond the seed's idempotency, when Temporal histories have grown unwieldy, or when a Schema Registry subject collision blocks publishing. **`down -v` destroys local data — there is no recovery.**

```bash
just down                 # stop services, keep volumes
./scripts/dc down -v      # destroy volumes (Postgres, Temporal, Mailpit, Grafana)
just up                   # bring the stack back up with fresh volumes
just db-migrate           # reapply migrations and the demo seed
just doctor               # verify readiness
```

After the reset, replay the fixture lead via `just demo` to repopulate the projection. Schema Registry subjects need to be re-registered when Workstream B publishes the first event after the reset.

## Common failure modes

### Permission denied on bind-mounted files

The `chown-init` service rewrites ownership on `infrastructure/` and `tmp/` at
container startup. If a service writes elsewhere under the workspace and
hits root-owned paths, extend `chown-init` in `compose.yml` rather than
chowning by hand.

### Port already allocated

Another local stack is bound to the default port. Set the relevant
`*_PORT` variable in `.env`; defaults are documented in `.env.example`.

### `just doctor` fails on missing path

Each Workstream lands files in a known layout; the doctor's required-paths
list mirrors that contract. Treat a missing-path failure as a workstream
contract violation, not a doctor bug. Fix the missing artefact or update
`chorus/doctor.py` if the contract has legitimately moved.

### Docker compose fails validation

Run `./scripts/dc config` directly to see the rendered compose file. The
most common cause is an unset variable that lacks a `${VAR:-default}`
fallback; add the default in `compose.yml` and document it in `.env.example`.

### Pre-commit hooks reject a commit

Run `just hooks` to reproduce the failure outside the commit boundary.
Builtins are auto-fix where possible; lint and contracts gates require
addressing the reported issue. Never bypass with `--no-verify` (project
policy).

### Provider or graph evidence looks wrong

The first split is whether the route, provider boundary, or graph metadata is
wrong.

1. Check the read-only UI `Providers` route or `/api/runtime/providers`. The
   local provider should be `approved`; `commercial.example` should be
   `disabled` with `credential_required=true`.
2. Check `/api/runtime/route-versions` or the `model_route_versions` SQL above.
   Route versions are immutable evidence rows; the runnable Phase 2A policy is
   still selected from `model_routing_policies`.
3. Check `/api/graph-executions` or the graph metadata SQL above. Successful
   local invocations should show `langgraph` execution metadata and the graph
   path ending at `final_response`.
4. If the commercial placeholder appears in a normal happy-path run, inspect
   `model_routing_policies` before changing code. The placeholder is not a
   production adapter; it is only valid for disabled-provider or fallback
   fixture evidence.

Do not add real provider credentials, mutate route versions in place, or enable
production provider calls to make the local demo pass. The correct repair is to
restore the local route policy or add a fixture-backed Phase 2 evidence path.

## Observability surfaces

Phase 1A ships OpenTelemetry traces/logs/metrics through the OTel collector
into Grafana. The pipeline shape is committed in
[ADR 0010](../adrs/0010-observability-pipeline.md). Workstream F's exit
criterion is that Temporal, Redpanda, Grafana, the UI, and the audit views
can be correlated from one workflow ID.

Phase 2B keeps the data placement rules in
[`observability-user-journey-model.md`](observability-user-journey-model.md):
OpenTelemetry is for operational diagnosis and correlation; propagated baggage
is limited to safe join keys; Postgres projections and BFF/UI views carry
refresh-safe journey evidence; and audit tables remain the accountability
record. Do not put secrets, credentials, API keys, access tokens, raw sensitive
content, or PII in span attributes, baggage, journey projections, or dashboard
labels.

### Grafana

`just up` launches Grafana at `http://localhost:${GRAFANA_PORT:-3001}` with
provisioned dashboards under the **Chorus** folder, all backed by the
in-network Postgres datasource (`chorus-postgres`):

| Dashboard | What it surfaces | Source table |
|---|---|---|
| Chorus / Workflow timeline | Lighthouse status counts, recent runs, outbox events per step. | `workflow_read_models`, `outbox_events` |
| Chorus / Tool Gateway verdicts | Verdict mix, denied/downgraded calls, per-tool slices. | `tool_action_audit` |
| Chorus / Projection lag | Pending outbox depth, oldest pending age, retry pressure, failing rows. | `outbox_events` |
| Chorus / Agent decisions | Provider/model route mix, outcome mix, per-role cost over time. | `decision_trail_entries` |

Every dashboard exposes a `$tenant` query variable and a `$correlation`
text variable. Pasting a `cor_*` ID narrows every panel uniformly; the
same ID then drops into the SQL audit queries below.

Edit dashboards by changing the JSON under
`infrastructure/grafana/dashboards/`; Grafana reloads within ~30s. The UI
is read-only — do not export-and-overwrite without stripping
`__inputs`/`__requires` and resetting `id` to `null` (see
`infrastructure/grafana/README.md`).

### Cross-surface correlation

Today the trail is **UI/Postgres → Grafana → SQL audit**:

1. From the BFF/UI, capture the `correlation_id` for the workflow under review.
2. Open Grafana → Chorus folder → paste the ID into `$correlation` in any dashboard.
3. Drill into a row in the dashboard's table panel; copy `workflow_id` for the Temporal UI search.
4. Run the runbook's `tool_action_audit` SQL with the same `correlation_id` for the authoritative gateway record.

The Tempo/Loki/Prometheus backends now run alongside Grafana. Once
Workstream B/C/D services emit OTel through the template's
`opentelemetry-instrument` entrypoint, step 3 picks up a "View trace" link
keyed off the `chorus.correlation_id` span attribute, and audit rows record
the active `otel.trace_id` / `otel.span_id` in their `metadata` jsonb so
the join survives a restart. Audit-write code calls
`chorus.observability.current_otel_ids()` at the row-write boundary; the
helper returns an empty dict when no SDK is loaded, so the same code is
safe under tests and in pure-persistence paths.

### Observability stack operations

The OTel pipeline shipped in Phase 1 follows ADR 0010. Operating notes:

- **Reach the backends.** Tempo on `localhost:3200` (HTTP), Loki on
  `localhost:3100`, Prometheus on `localhost:9090`, collector OTLP on
  `localhost:4317`/`4318`, collector Prometheus scrape endpoint on
  `localhost:8889`. `just doctor` probes each one's `/ready` (or
  `/-/ready`) and reports `skip` when the service is not up.
- **Reset noisy telemetry without touching application data.** Each
  backend has its own named volume (`tempo-data`, `loki-data`,
  `prometheus-data`). Tempo and Loki are pinned to 24h retention so a
  long-running stack does not bloat. To drop telemetry only, use
  `scripts/dc rm -fsv tempo loki prometheus` and `just up` again. Do
  **not** run `just down-volumes` — that also wipes Postgres and
  Mailpit.
- **Triage "is anything reaching the collector?"** The collector keeps
  the `debug` exporter on every pipeline, so `scripts/dc logs
  otel-collector` shows a one-line summary per batch forwarded to
  Tempo, Loki, and Prometheus. Use this before opening Grafana when a
  panel looks empty.
- **Datasource provisioning is read-only.** The Tempo datasource carries
  `tracesToLogsV2` (Tempo→Loki by `chorus.tenant_id`/`workflow_id`/
  `correlation_id` span attributes) and `tracesToMetrics`/`serviceMap`
  (→ Prometheus); Loki carries a `derivedFields` rule that turns
  log-line `trace_id=…` into a Tempo link. Edit
  `infrastructure/grafana/provisioning/datasources/chorus.yaml` and
  restart the Grafana container — Grafana itself rejects edits in the
  UI.

### Optional LLM observability sidecar spike

Phase 2B-06 evaluated LangSmith, Langfuse, and similar LLM observability tools
as optional trace/eval sidecars. The full decision lives in
[`llm-observability-sidecar-evaluation.md`](llm-observability-sidecar-evaluation.md).
The local runbook decision is: no sidecar exporter is implemented in the
default stack.

If a later spike exports to one of these tools, keep the spike outside the
default `just up` path and follow these rules:

1. Export through the OTel Collector or a deterministic eval/report export, not
   direct application SDK fan-out from Agent Runtime or Tool Gateway.
2. Keep Grafana/Tempo/Loki/Prometheus, Postgres audit, Temporal replay, and
   `just eval` authoritative. The sidecar is for debugging, annotation, graph
   inspection, and experiment comparison only.
3. Export only safe identifiers and bounded categories: service name,
   deployment environment, workload principal/trust-domain IDs, trace/span IDs,
   tenant/correlation/workflow/invocation IDs, workflow step, agent ID/version,
   task kind, execution engine/graph version, provider/model IDs, route
   ID/version, fallback state/reason, tool name/modes, gateway verdict,
   fixture ID, eval run ID, pass/fail status, bounded failure category,
   aggregate cost, and aggregate latency.
4. Do not export secrets, credentials, API keys, access tokens, raw sensitive
   content, raw prompts/outputs, raw tool arguments, raw connector responses,
   raw approval or policy rationale, identity-provider claims, PII, request
   headers, cookies, IP addresses, hostnames, filesystem paths, or full audit
   records.
5. Join sidecar traces back to local evidence by `correlation_id`,
   `workflow_id`, `invocation_id`, `trace_id`, `span_id`, fixture ID, or eval
   run ID. Approval IDs, policy-change IDs, authority-context IDs, and grant
   refs stay audit-owned unless a future allow-list explicitly promotes them.
6. Make sidecar export non-blocking. Exporter failure must not affect workflow
   progress, Tool Gateway verdicts, audit writes, or `just eval`.
7. Document retention and sampling before enabling export. Tempo/Loki remain
   short-retention local operational stores, Postgres audit remains the local
   accountability store, and sidecar retention is never assumed by release
   gates.

There is intentionally no `just` recipe for sidecar export yet. Add one only
after a future ledger item includes an export allow-list test and a clear
operator reason for the sidecar.

### Onboarding a Phase 1A service

When a Workstream adds an application service to `compose.yml`, three
small steps wire it into the observability plane without restarting
the collector or Prometheus. The full per-service checklist lives in
[`services/_template/README.md` § "Observability onboarding"](../services/_template/README.md);
the operational summary:

1. **Stable container name.** Use `container_name: chorus-<role>` so
   Grafana panels, Loki labels, and the runbook all key off the same
   prefix.
2. **Stdout → Loki.** Add a `logging.driver: fluentd` block on the
   compose entry pointing at
   `localhost:${OTEL_FLUENTD_PORT:-24224}` with
   `fluentd-async: "true"` and `tag: chorus.{{.Name}}`. The collector's
   `fluentforward` receiver is permanently on; logs flow as soon as
   the service's first stdout line is emitted. Auto-instrumented
   Python services keep emitting OTLP logs in parallel — the fluent
   path is the structured-stdout fallback for anything that bypasses
   the SDK (and for non-Python containers).
3. **`/metrics` → Prometheus.** Drop
   `infrastructure/prometheus/targets/<service>.yml` declaring the
   in-network address(es) where the service exposes `/metrics`, with a
   `service: <role>` label. Prometheus picks it up within 30 seconds
   (`http://localhost:9090/targets` confirms). No edit to the central
   `infrastructure/prometheus/config.yaml` required.

Removing a service is symmetric: drop the target file, drop the
compose entry, and Prometheus / fluent reflect the change on the next
refresh tick. Per ADR 0010 §6, alert rules are deferred until at least
two end-to-end runs produce baselines; until then onboarding stops at
the scrape and log-flow steps above.

## CI gates

The `.github/workflows/ci.yml` pipeline runs lint, contracts-check, doctor,
Python tests, and frontend lint/test on every push and PR. `eval.yml` runs the
Phase 1A happy-path fixture as a normal gate; `replay.yml` runs workflow replay
coverage. Treat a red CI as the same severity as a red local `just doctor`;
both signal a project-level contract slipping.

## Deferrals

- Production deployment, secret management, on-call rotation, incident response.
- Real third-party connectors and production provider calls.
- Credential-entry UI or committed provider keys.
- Mutating provider, prompt, route, or grant admin controls before executable
  change-control work explicitly opens them.
- LangGraph checkpoint persistence, durable execution, hosted deployment,
  long-term graph memory, or LangSmith/Langfuse as required dependencies.
- Cloud-hosted observability backends.

These are documented in [implementation-plan.md §Deferred After Phase 1](./implementation-plan.md#deferred-after-phase-1).

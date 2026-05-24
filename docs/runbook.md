---
type: project-doc
status: active
date: 2026-05-24
---

# Chorus - Local Runbook

This runbook covers the local sandbox stack only. Chorus runs entirely
locally: Postgres, Redpanda, Temporal, Mailpit, a local connector substrate,
and an OpenTelemetry and Grafana observability stack. There is no hosted
dependency. Deployment and hosting are out of the Chorus repository; see
[`overview.md`](overview.md).

The runbook has two halves. The **per-port operations reference** is how to
bring up and inspect each of the six named ports; every command in it runs
today. The **UC1 happy-path walk-through** threads the ports into one
end-to-end run and closes with cross-provider replay-eval.

A note on what runs today. R3 (contract and code terminology refactor)
closed 2026-05-24. The runtime code carries the named-port surface, and
the runnable local intake path remains the UC1 enquiry-qualification workflow
on the shared `WorkflowSpine`. UC2 now has a definition-first workflow on the
same spine with focused fake-activity workflow / replay tests, plus
registered deterministic sandbox connector adapters for conflict check, KYC /
beneficial ownership, AML record-store, and engagement-letter-store tools.
UC2 grants now exist for the declared sandbox tools, with
`engagement_letter.send` as the approval-required write. Provider route support,
full eval fixture playback, and a local intake start path remain later R4
work. Read-only BFF/UI inspection can display UC2 workflow rows and
approval-package state when those rows already exist. UC3 lands later in R4
alongside cross-provider replay-eval breadth.

## Bring the stack up

```bash
./scripts/first-time-setup.sh   # idempotent host bootstrap: just, uv, Python, hooks
just env                        # ensure .env exists
just up                         # docker compose up -d via scripts/dc
just db-migrate                 # apply Postgres migrations and the demo seed
just schemas-register           # register event schemas with the Schema Registry
just doctor                     # scaffold and runtime readiness checks
```

`scripts/dc` is the canonical `docker compose` wrapper: it sources `.env`,
exports `UID`/`GID`, and execs `docker compose`. Use it for ad-hoc operations.

### Daily commands

| Command | Purpose |
|---|---|
| `just up` / `just down` | Bring the substrate up or down. |
| `just status` | Compose service status. |
| `just logs <service>` | Tail logs for one service. |
| `just doctor` | Scaffold and runtime readiness checks. |
| `just contracts-check` | Schema, generated-model, and sample drift gate. |
| `just test` / `just test-replay` | Python tests; Temporal replay tests. |
| `just lint` / `just fmt` | Linters and formatters. |
| `just eval` | Run the eval fixtures. |

`just --list` is the discovery command.

### Local endpoints

| Service | URL / port |
|---|---|
| Postgres | `localhost:5432` |
| Redpanda Kafka API | `localhost:9092` |
| Redpanda Schema Registry | `localhost:8081` |
| Redpanda Console | `http://localhost:8080` |
| Temporal | `localhost:7233` |
| Temporal UI | `http://localhost:8233` |
| Mailpit SMTP | `localhost:1025` |
| Mailpit UI / HTTP API | `http://localhost:8025` |
| Grafana | `http://localhost:3001` |
| OTLP gRPC / HTTP | `localhost:4317` / `localhost:4318` |
| BFF | `localhost:8000` |
| Frontend | `http://localhost:5173` |

Ports are parameterised in `.env`; defaults are shown. Rerun `just doctor`
after editing `.env`.

## Per-port operations reference

Each section is how to operate and inspect one named port on the local stack.

### Intake port

The intake port receives inbound business work. On the local stack the channel
adapter is Mailpit: a real email to the intake mailbox starts a workflow.

```bash
just demo          # send the fixture enquiry to Mailpit SMTP
just intake-once   # poll Mailpit once and start a workflow per new message
```

Inspect inbound mail in the Mailpit UI at `http://localhost:8025`. The poller
deduplicates by Message-ID and derives a stable workflow ID, so re-sending the
same fixture records a duplicate rather than starting a second run; use a fresh
Message-ID when rehearsing.

R3 leaves the Mailpit/email UC1 channel runnable and keeps the UC1 web-form,
partner-portal, and synthetic-channel contracts in place. R4 decides which
non-email channel paths must become runnable for local POC readiness.

### LLM provider port

The LLM provider port carries model invocations. On the local stack reasoning
runs through the Agent Runtime; each invocation writes a decision-trail row.

Inspect the model routes resolved for a tenant:

```bash
./scripts/dc exec postgres psql -U chorus -d chorus -c \
  "SELECT agent_role, task_kind, runtime_route_id, provider, model FROM model_routing_policies WHERE tenant_id = 'tenant_demo' ORDER BY agent_role;"
```

The agent execution path uses the OpenAI-SDK adapter, the route catalogue, and
the deterministic recorded-replay route used by offline eval. The verified
R4 live-provider route metadata is DeepSeek `deepseek-v4-flash` with
`DEEPSEEK_API_KEY` for the `dev` route and OpenAI
`gpt-5.4-mini-2026-03-17` with `OPENAI_API_KEY` for the
`demo-eval-canonical` route. These identifiers and credential names were
verified from official provider docs on 2026-05-24; source links are recorded
in [`transformation/r4-design-decisions.md`](transformation/r4-design-decisions.md).
The runtime now loads the approved repo-local `prompt_reference`, verifies the
file bytes against `prompt_hash`, and sends the prompt as the system message
before the user task input for both live routes and recorded-replay-safe runs.
It also attaches the UC1 task response schema to each provider-port call. The
OpenAI route requests `json_schema` structured output; the DeepSeek route
requests JSON-object mode and the adapter validates the returned object
against the same task schema locally. Malformed JSON or an empty
`structured_data` object fails as a non-retryable provider-port error before
any connector action can be proposed. The active local route-governance rows
now align on runtime route `recorded-replay`, provider `local`, and model
`uc1-happy-path-v1` across routing policy, immutable route versions, provider
catalogue rows, BFF inspection, and offline eval route selection. R4 wires
live route activation only after required local credentials and live route
gates are aligned. Replay-run evidence
records now persist the original invocation/transcript refs, alternate route
metadata, comparator status, lineage refs, and token/cost/latency metrics. The
hard-fail comparator tier classifies schema, policy snapshot, conduct hook,
unsafe action, audit/transcript linkage, route-governance, and provider-port
replay defects with safe reason codes and field names. The decision-fail tier
classifies bounded UC1 qualification verdict, routing, regulated-outcome,
approval-decision, and connector-action category divergence under the same
policy snapshot. The review-finding tier records non-terminal
recommended-next-step, confidence, rationale, optional field, and
evidence-selection divergence without storing raw rationale or customer
content. The metrics-only tier records token, latency, retry-count,
provider-cost, and safe provider-metadata deltas with reason codes and field
names only.

### Connector port

The connector port is the external-action authority; the Tool Gateway mediates
every call. On the local stack connectors are real software in sandbox mode.

Inspect the grants for an agent:

```bash
./scripts/dc exec postgres psql -U chorus -d chorus -c \
  "SELECT agent_id, tool_name, mode, allowed, approval_required FROM tool_grants WHERE tenant_id = 'tenant_demo' ORDER BY tool_name;"
```

Inspect the UC1 policy snapshot row emitted by the deterministic qualifier:

```bash
./scripts/dc exec postgres psql -U chorus -d chorus -c \
  "SELECT policy_snapshot_ref, workflow_type, snapshot_version, lifecycle_state, content_hash FROM policy_snapshots WHERE tenant_id = 'tenant_demo' AND policy_snapshot_ref = 'policy_snapshot:uc1:default:v1';"
```

Every gateway call writes an audit row regardless of verdict; see the audit
port section below. The UC1 workflow routes `accept`, `refer`, and `decline`
qualification verdicts through the Tool Gateway to the quoting queue,
referral inbox, and decline ledger adapters, which persist their local
sandbox refs in Postgres. Missing-data verdicts stay on the proposal-mode
outbound-comms path; the write-mode send remains approval-required.
Customer-profile and product-catalogue reads resolve tenant-scoped synthetic
rows from the local Postgres seeds. The emitted
`policy_snapshot:uc1:default:v1` ref resolves to an immutable local
`policy_snapshots` row containing safe refs for agents, routes, grants,
connector policies, target-market checks, and conduct hooks. The offline
eval suite covers the missing-data outbound path plus accepted, referred,
and declined terminal connector routing.

UC2 connector adapters are registered in the default connector registry for
`conflict_check.search`, `kyc_bo.lookup`,
`aml_record_store.record_assessment`, `engagement_letter.draft`,
`engagement_letter.send`, `engagement_letter.record_decline`, and
`engagement_letter.route_manual_review`. They return deterministic synthetic
refs and bounded statuses only; they do not call production legal, AML,
identity, Companies House, sanctions, document-management, matter-management,
email, or e-signature systems. The local Postgres governance seed now
expresses UC2 Tool Gateway grants for those tool names; `engagement_letter.send`
is the approval-required write, while conflict exception and AML EDD approval
remain conduct-gated/manual-review evidence until a later slice adds an exact
connector request shape for those packages. The runbook does not yet claim a
runnable UC2 local intake path.

Inspect approval packages through the read-only BFF:

```bash
curl -s http://localhost:8000/api/approval-packages | jq '.[] | {workflow_id, workflow_type, requested_action, approval_state, latest_verdict, action_refs}'
```

For a known UC2 workflow ID, narrow the same view:

```bash
curl -s http://localhost:8000/api/workflows/<workflow-id>/approval-packages | jq '.[] | select(.workflow_type == "uc2_legal_services_intake_conflict_check")'
```

### Audit / transcript ports

The audit surface answers accountability questions. On the local stack it is a
single Postgres audit store; R3 splits it into the decision-trail port and the
transcript port.

Read the decision trail for a run:

```bash
./scripts/dc exec postgres psql -U chorus -d chorus -c \
  "SELECT agent_role, provider, model, outcome, cost_amount, started_at FROM decision_trail_entries WHERE correlation_id = '<correlation-id>' ORDER BY started_at;"
```

Read the Tool Gateway audit for a run:

```bash
./scripts/dc exec postgres psql -U chorus -d chorus -c \
  "SELECT tool_name, requested_mode, enforced_mode, verdict, reason, occurred_at FROM tool_action_audit WHERE correlation_id = '<correlation-id>' ORDER BY occurred_at;"
```

`verdict` is one of `allow`, `rewrite`, `propose`, `approval_required`,
`block`, or `recorded`. If a verdict is unexpected, the grant policy or the
connector argument schema is the place to look, never the agent prompt: agents
have no ambient authority by design.

Read replay-run evidence for a run:

```bash
./scripts/dc exec postgres psql -U chorus -d chorus -c \
  "SELECT original_invocation_id, original_runtime_route_id, alternate_runtime_route_id, comparator_status, original_cost_amount, alternate_cost_amount, original_latency_ms, alternate_latency_ms FROM replay_run_records WHERE correlation_id = '<correlation-id>' ORDER BY completed_at;"
```

### Projection sink

The projection sink derives read models for inspection. Workflow events move
through Redpanda into Postgres read models, which the read-only BFF serves.

```bash
just relay-once     # publish pending workflow events to Redpanda
just project-once   # project Redpanda events into Postgres read models
```

Inspect the read models through the BFF at `localhost:8000` or the frontend at
`http://localhost:5173`. The read model is the source of truth for the UI; the
progress stream is a convenience, not authoritative.

Filter projected UC2 workflow rows through the BFF:

```bash
curl -s http://localhost:8000/api/workflows | jq '.[] | select(.workflow_type == "uc2_legal_services_intake_conflict_check") | {workflow_id, status, current_step, subject_ref, subject_summary}'
```

### Observability sink

The observability sink carries traces, metrics, and logs. Grafana at
`http://localhost:3001` serves provisioned dashboards backed by the Postgres,
Tempo, Loki, and Prometheus datasources.

Every dashboard exposes a `$correlation` variable. Paste a run's
`correlation_id` to narrow every panel; the same identifier joins the SQL
audit queries above. Do not put secrets, credentials, raw content, or PII into
span attributes, baggage, or dashboard labels.

## UC1 happy-path walk-through

This is the end-to-end happy path threaded through the six ports. The port
sequence is stable; the UC1 enquiry-qualification workflow runs it
end-to-end on the shared `WorkflowSpine`. UC2 and UC3 land alongside in R4
with their own workflow definitions on the same spine; the sequence does
not change.

1. **Bring the stack up (all ports).** Run the bring-up commands above:
   `just up && just db-migrate && just schemas-register && just doctor`.

2. **Inject a synthetic enquiry (intake port).** `just demo && just intake-once`.
   The intake port accepts the inbound work through the UC1 Mailpit/email
   channel and a workflow starts. Capture the `correlation_id` from the
   Mailpit-derived
   workflow or from the BFF.

3. **Classification and qualification (LLM provider port).** The workflow runs
   the UC1 agent path through the LLM provider port. Each invocation writes a
   decision-trail row and a transcript row paired on `invocation_id`.

4. **Qualification verdict (LLM provider port).** The qualifier produces a
   structured verdict carrying `qualification_verdict_category`,
   `policy_snapshot_ref`, the four FCA conduct hooks
   (`best_interests_check`, `demands_and_needs_statement`,
   `target_market_check`, `foreseeable_harm_check`), and an explicit
   rationale.

5. **Routing (connector port).** The workflow routes the qualification verdict
   through the Tool Gateway. `accept` uses `crm.route_to_quoting_queue`,
   `refer` uses `referral_inbox.route`, and `decline` uses
   `decline_ledger.route`, with `verdict_ref` as the idempotency key.
   Missing-data verdicts draft and validate an outbound message, then call
   `outbound_comms.message` in `propose` mode with
   `missing_data_request_ref` as the idempotency key. The write-mode outbound
   send remains approval-required before Mailpit delivery.

6. **Inspect the decision-trail and transcript (audit ports).** Run the
   decision-trail and `tool_action_audit` SQL from the audit port section with
   the captured `correlation_id`. Every LLM invocation and every connector call
   should be covered; that is the audit completeness invariant.

7. **Inspect projections and observability (projection and observability
   sinks).** `just relay-once && just project-once`, then inspect the run in
   the BFF or frontend and in Grafana by `correlation_id`.

8. **Cross-provider replay-eval (closing step).** `just eval` runs the UC1
   invariant fixtures, including missing-data outbound communication and the
   accepted, referred, and declined terminal connector routes. Cross-provider
   replay-eval - re-running a captured transcript against an alternate route
   and comparing the result - is the closing eval step. The replay path now
   builds contract-shaped replay-run records for Postgres/BFF inspection and
   classifies hard-fail defects, bounded UC1 decision-fail divergence, and
   non-terminal review findings; it records metrics-only deltas after those
   semantic tiers agree. Live-provider execution remains credential-gated and
   inactive by default. The target
   shape is in
   [`transformation/eval-reshape-directions.md`](transformation/eval-reshape-directions.md).

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `Port already allocated` | Another local stack holds the default port. | Set the relevant `*_PORT` variable in `.env`; defaults are in `.env.example`. |
| `just doctor` fails on a missing path | A required artefact is absent. | Treat it as a contract violation, not a doctor bug. Restore the artefact. |
| Docker compose fails validation | An unset variable lacks a `${VAR:-default}` fallback. | Run `./scripts/dc config` to see the rendered file; add the default in `compose.yml`. |
| Pre-commit hooks reject a commit | A lint or contracts gate failed. | Run `just hooks` to reproduce outside the commit. Do not bypass with `--no-verify`. |
| A workflow is stuck | A long-poll, a wait, or a deadlocked dependency. | Inspect the run in the Temporal UI at `http://localhost:8233`; terminate or reset from there. Never wipe Postgres to clear a stuck run; the audit trail is evidence. |

### Resetting the local stack

`down -v` destroys local data and there is no recovery. Use it only when
fixtures have polluted Postgres beyond the seed's idempotency.

```bash
just down                 # stop services, keep volumes
./scripts/dc down -v      # destroy volumes
just up && just db-migrate && just schemas-register && just doctor
```

### Regenerating contracts

`contracts/` is canonical. After editing a schema, run `just contracts-gen`
then `just contracts-check`. Never hand-edit generated model files; the drift
gate fails on the next regeneration.

## CI gates

`.github/workflows/ci.yml` runs lint, contracts-check, doctor, Python tests,
and frontend lint and test on every push and pull request. `replay.yml` runs
the Temporal replay coverage; `eval.yml` runs the eval fixtures. Treat a red CI
as the same severity as a red local `just doctor`.

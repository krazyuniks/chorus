---
type: project-doc
status: active
date: 2026-05-30
---

# Chorus - Local Runbook

This runbook covers the local sandbox stack only. Chorus runs entirely
locally: Postgres, Redpanda, Temporal, Mailpit, a local connector substrate,
and an OpenTelemetry and Grafana observability stack. There is no hosted
dependency. Deployment and hosting are out of the Chorus repository; see
[`overview.md`](overview.md).

The runbook starts with the local development bootstrap. The **per-port
operations reference** then shows how to inspect each of the six named ports,
and the **UC1 happy-path walk-through** threads those ports into one
end-to-end run.

Current runnable scope: UC1 runs locally through the Mailpit
enquiry-qualification path on the shared `WorkflowSpine`. UC2 and UC3 have
shared-spine workflow definitions, deterministic sandbox connector adapters,
Tool Gateway grants, approval-package evidence, conduct invariants,
schema-only fixture evidence, and read-only projection/BFF/UI inspection
surfaces. UC2 has a code-level synthetic email-intake fixture adapter for R5
P1 test evidence and recorded-replay model-route policies for the four UC2
workflow agent tasks, but no documented operator command or full eval fixture
playback yet. UC3 does not yet have use-case route activation, full eval
fixture playback, or a local intake start path.

## Local development bootstrap

Run every command from the repository root.

### First-time setup

Use the script directly on a fresh host because it installs `just` when it is
missing:

```bash
./scripts/first-time-setup.sh
```

The script is idempotent. It installs or verifies `just`, `uv`, Python 3.14,
and `prek`; runs `uv sync --all-extras`; copies `.env.example` to `.env` if
`.env` is absent; and registers the prek-managed git hooks. It reports missing
host-managed tools such as Docker, the Docker Compose v2 plugin, `git`, and
`gh`, but it does not install them. After `just` exists, `just setup` runs the
same script.

Re-run the setup script after host tooling changes or after Python dependency
metadata changes. It is non-destructive and does not touch Docker volumes.

### Environment file and drift gate

Create the local environment file and verify it against the committed
template:

```bash
just env
```

```bash
just env-check
```

`.env.example` is the committed local-stack contract. `.env` is the
developer-local copy used by `scripts/dc`, `just` recipes, doctor probes, and
tests. `scripts/dc` sources `.env`, exports `UID` and `GID` from the host, and
then execs `docker compose`; use it for ad-hoc Compose operations instead of
bare `docker compose`.

`just env-check` fails when `.env` or `.env.example` is missing, a key is
duplicated, the two files declare different keys, or a non-secret value differs.
Only these value-only differences are allowed locally:
`CHORUS_PG_PASSWORD`, `TEMPORAL_PG_PASSWORD`,
`GRAFANA_ADMIN_PASSWORD`, `DEEPSEEK_API_KEY`, and `OPENAI_API_KEY`. If a new
runtime variable is added, add it to both files and keep the runbook endpoint
table current. Do not commit real provider keys or private credentials.

The default infrastructure URLs consumed by host-side gates are:

| Variable | Default |
|---|---|
| `CHORUS_DATABASE_URL` | `postgresql://chorus:chorus@localhost:55432/chorus` |
| `CHORUS_TEST_ADMIN_DATABASE_URL` | `postgresql://chorus:chorus@localhost:55432/postgres` |
| `CHORUS_REDPANDA_BOOTSTRAP_SERVERS` | `localhost:19092` |
| `CHORUS_CALDAV_BASE_URL` | `http://localhost:5232` |

### Start and initialise the stack

Start the stack, apply database state, register event schemas, and run the
live readiness gate:

```bash
just up
```

```bash
just status
```

```bash
just db-migrate
```

```bash
just schemas-register
```

```bash
just doctor
```

`just up` runs `./scripts/dc up -d --build`, so local service images are built
from the current checkout before containers start. `just db-migrate` applies
repo-controlled SQL migrations from `infrastructure/postgres/migrations/` and
then runs idempotent seed files from `infrastructure/postgres/seeds/` against
`CHORUS_DATABASE_URL`. `just schemas-register` registers missing
`x-subject` JSON Schema contracts with the Redpanda Schema Registry; it does
not create new versions for subjects that are already present.

`just doctor` is the local prerequisite gate. It validates required paths,
executables, Compose rendering, per-service dependency contracts, running
Compose services, successful one-shot init containers, zero container restarts
since boot, Postgres reachability, applied migration checksums, Redpanda
bootstrap reachability, Schema Registry subjects, Mailpit SMTP and HTTP,
Radicale, and Temporal. The Temporal probe also requires a worker poller on
the configured task queue, which the `intake-poller` service provides in the
Compose stack. BFF, frontend dev server, and observability probes are reported
after required stack prerequisites pass; missing optional development surfaces
are informational, while partially reachable observability services fail the
gate.

### How tests obtain infrastructure URLs

`tests/conftest.py` requires the repository-local `.env` file to exist before
pytest starts. It loads that file with `override=False`, so an explicitly set
process environment variable wins over `.env`.

Infrastructure-backed pytest fixtures fail loudly rather than skipping:

| Fixture | Source variable | Behaviour |
|---|---|---|
| `test_admin_database_url` | `CHORUS_TEST_ADMIN_DATABASE_URL` | Required admin database URL for test database creation. |
| `migrated_database_url` | `CHORUS_TEST_ADMIN_DATABASE_URL` | Creates a module-scoped temporary Postgres database, applies migrations and seeds through `chorus.persistence.apply_migrations`, yields its URL, then drops it. |
| `redpanda_bootstrap` | `CHORUS_REDPANDA_BOOTSTRAP_SERVERS` | Uses a Redpanda `AdminClient` metadata request to prove the Kafka API is reachable. |

Before running `just test`, make sure `just env`, `just up`, and
`just schemas-register` have succeeded. Tests that only need Postgres create
their own migrated database, but they still require the configured admin URL
to point at the running local Postgres service.

### Drift and rebuild recovery

When `just doctor` reports `migration not applied`, run the migrator and then
re-run the doctor gate:

```bash
just db-migrate
```

```bash
just doctor
```

When `just doctor` or `just db-migrate` reports a migration checksum mismatch,
an applied migration file has changed. Do not edit the `schema_migrations`
table and do not wipe volumes as a first response. Restore the applied
migration file or add a new migration that moves the schema forward, then run
`just db-migrate` and `just doctor` again.

When `just doctor` reports missing Schema Registry subjects, register the
declared contracts and re-check:

```bash
just schemas-register
```

```bash
just doctor
```

When a dependency change affects a containerised service, update the owning
`services/<name>/pyproject.toml`, run the import-contract gate, and rebuild the
service image:

```bash
just service-import-contracts
```

```bash
just up
```

For a focused rebuild, use the Compose wrapper with the service name:

```bash
./scripts/dc up -d --build bff
```

```bash
./scripts/dc up -d --build intake-poller
```

No volume reset is required for dependency or application-code image rebuilds.

### Daily commands

| Command | Purpose |
|---|---|
| `just up` / `just down` | Bring the substrate up or down. |
| `just status` | Compose service status. |
| `just logs <service>` | Tail logs for one service. |
| `just doctor` | Scaffold and fail-fast required stack readiness checks. |
| `just service-import-contracts` | Verify service pyprojects declare dependencies used by their service-owned `chorus` entrypoints. |
| `just env-check` | Verify `.env` and `.env.example` declare the same keys and matching non-secret values. |
| `just contracts-check` | Schema, generated-model, and sample drift gate. |
| `just test` / `just test-replay` | Python tests; Temporal replay tests. |
| `just lint` | Environment drift checks, linters, and type-checkers. |
| `just fmt` | Format Python and frontend code. |
| `just eval` | Run the eval fixtures. |

`just --list` is the discovery command.

### Local endpoints

| Service | URL / port |
|---|---|
| Postgres | `localhost:55432` |
| Redpanda Kafka API | `localhost:19092` |
| Redpanda Schema Registry | `localhost:18081` |
| Redpanda Console | `http://localhost:18083` |
| Temporal | `localhost:7233` |
| Temporal UI | `http://localhost:8233` |
| Mailpit SMTP | `localhost:1025` |
| Mailpit UI / HTTP API | `http://localhost:8025` |
| Radicale / CalDAV sandbox | `http://localhost:5232` |
| Grafana | `http://localhost:3001` |
| OTLP gRPC / HTTP | `localhost:14317` / `localhost:14318` |
| BFF | `localhost:18001` |
| Frontend | `http://localhost:5174` |

Ports are parameterised in `.env`; defaults are shown. Rerun `just env-check`
and `just doctor` after editing `.env`. Long-lived local overrides must be
reflected in `.env.example`; only the explicitly listed API-key and password
values may differ between the two files.

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

R4 closes with the Mailpit/email UC1 channel runnable and keeps the UC1
web-form, partner-portal, and synthetic-channel contracts in place. UC2 and
UC3 intake contracts exist. R5 P1 adds a code-level UC2 synthetic email-intake
fixture adapter that validates the documented contract sample and starts the
UC2 workflow; the operator-facing UC2 command remains a later runbook slice.
UC3 still has no local intake adapter.

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
catalogue rows, BFF inspection, and offline eval route selection for UC1, and
across routing policy, immutable route versions, and provider catalogue rows
for the UC2 workflow agent tasks
(`uc2_matter_classification`, `uc2_party_extraction`,
`uc2_conflict_determination`, and `uc2_engagement_decision`). Live route
activation remains deferred until required local credentials and live route
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
runnable UC2 operator intake command.

UC3 has a definition-first workflow for `uc3_ifa_suitability_intake` on the
same `WorkflowSpine`. The workflow routes `attitude_to_risk.profile`,
`capacity_for_loss.assess`, `platform_research.run`,
`suitability_report.draft`, `suitability_report.issue`,
`suitability_report.record_decline`, and
`suitability_report.route_manual_review` through `WorkflowSpine.connector_call`
with safe refs and bounded categories only. The default connector registry now
registers deterministic sandbox adapters for those tool names:
`sandbox-attitude-to-risk-profiler`, `sandbox-capacity-for-loss-tool`,
`sandbox-platform-research`, and `sandbox-suitability-report-store`. They
return synthetic refs and statuses only; they do not call production IFA,
platform, research, advice, client-record, portal, custody, or dealing
systems. The local Postgres governance seed now expresses UC3 Tool Gateway
grants for those tool names; `suitability_report.issue` is the
approval-required write, while risk-profile override and vulnerability
handoff remain workflow/manual-review conduct evidence until a later slice
adds exact connector request shapes for those packages. Read-only projection,
BFF, and UI fixture evidence can show safe UC3 workflow progress and generic
approval-package state for `suitability_report.issue` when rows exist. The
runbook does not yet claim a runnable UC3 local intake path: use-case provider
route activation, full eval playback, and local intake adapters remain absent.

Inspect approval packages through the read-only BFF:

```bash
curl -s http://localhost:18001/api/approval-packages | jq '.[] | {workflow_id, workflow_type, requested_action, approval_state, latest_verdict, action_refs}'
```

For a known UC2 workflow ID, narrow the same view:

```bash
curl -s http://localhost:18001/api/workflows/<workflow-id>/approval-packages | jq '.[] | select(.workflow_type == "uc2_legal_services_intake_conflict_check")'
```

For a known UC3 workflow ID, inspect suitability report issue approvals:

```bash
curl -s http://localhost:18001/api/workflows/<workflow-id>/approval-packages | jq '.[] | select(.requested_action == "suitability_report.issue.write") | {workflow_id, workflow_type, approval_state, latest_verdict, subject_refs, action_refs, grant_ref}'
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

Inspect the read models through the BFF at `localhost:18001` or the frontend at
`http://localhost:5174`. The read model is the source of truth for the UI; the
progress stream is a convenience, not authoritative.

Filter projected UC2 workflow rows through the BFF:

```bash
curl -s http://localhost:18001/api/workflows | jq '.[] | select(.workflow_type == "uc2_legal_services_intake_conflict_check") | {workflow_id, status, current_step, subject_ref, subject_summary}'
```

Filter projected UC3 workflow rows through the BFF:

```bash
curl -s http://localhost:18001/api/workflows | jq '.[] | select(.workflow_type == "uc3_ifa_suitability_intake") | {workflow_id, status, current_step, subject_ref, subject_summary}'
```

### Observability sink

The observability sink carries traces, metrics, and logs. Grafana at
`http://localhost:3001` serves provisioned dashboards backed by the Postgres,
Tempo, Loki, and Prometheus datasources.

Every dashboard exposes a `$correlation` variable. Paste a run's
`correlation_id` to narrow every panel; the same identifier joins the SQL
audit queries above. Do not put secrets, credentials, raw content, or PII into
span attributes, baggage, or dashboard labels.

## Gate matrix

For documentation-only bootstrap changes, run:

```bash
just env-check
just lint
git diff --check
```

For runtime or stack changes, add the relevant live gates:

```bash
just doctor
```

```bash
just contracts-check
```

```bash
just test
```

```bash
just test-replay
```

```bash
just eval
```

Run `just test-frontend` when frontend code or fixture data changes, and run
`just test-e2e` when browser behaviour changes. In R5, missing or unreachable
infrastructure is a gate failure, not a skip. If local Postgres rejects the
configured `chorus` user, fix the stack or stop and record the blocker; do not
claim live DB evidence.

## UC1 happy-path walk-through

This is the end-to-end happy path threaded through the six ports. The port
sequence is stable; the UC1 enquiry-qualification workflow runs it
end-to-end on the shared `WorkflowSpine`. R4 added UC2 and UC3 workflow
definitions on the same spine, but those use cases are inspection and
schema-only evidence paths until documented operator intake commands, UC3
provider route activation, and full fixture playback land in a later phase.
UC2 now has recorded-replay route policies for its workflow agent tasks, but
its documented operator command and full fixture playback remain open.

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
| `tests/conftest.py expected .../.env to exist` | Pytest started before the local environment file was created. | Run `just env`, then `just env-check`. |
| A Postgres or Redpanda pytest fixture raises instead of skipping | Infrastructure-backed tests require live services and required URL variables. | Run `just up`, `just schemas-register`, and `just doctor`; confirm `.env` has `CHORUS_TEST_ADMIN_DATABASE_URL` and `CHORUS_REDPANDA_BOOTSTRAP_SERVERS`. |
| `just doctor` fails on a missing path | A required artefact is absent. | Treat it as a contract violation, not a doctor bug. Restore the artefact. |
| `just doctor` reports an unhealthy or missing Compose service | The local stack is not ready. | Run `just status` and `just logs <service>`, then rebuild with `just up` if an image was stale after a dependency change. |
| `just doctor` reports `RestartCount > 0` | A container restarted since it was created. | Inspect `just logs <service>` and recreate only after preserving the evidence needed for the investigation. |
| `just doctor` reports an unapplied migration or checksum mismatch | Postgres schema state is behind the repo, or an applied migration was edited. | Run `just db-migrate` for unapplied migrations. For checksum drift, create a new migration rather than editing the applied file. |
| `just doctor` reports missing Schema Registry subjects | Declared `x-subject` contracts are not registered. | Run `just schemas-register`; it registers missing declared subjects without creating new versions for subjects already present. |
| `just service-import-contracts` reports a missing dependency | A service-owned `chorus` entrypoint now reaches a third-party runtime import not declared in that service's `services/<name>/pyproject.toml`. | Add the dependency to that service pyproject and rebuild the image with `just up`, or update the explicit service import contract if the Dockerfile entrypoint changed. |
| `just env-check` reports `.env` drift | The local runtime file no longer matches the committed template. | Restore the local value to the committed default, add the key to both files, or extend the explicit secret-value allowlist only for genuine credentials. |
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

`.github/workflows/ci.yml` runs Python ruff, format, service import contracts,
pyright, contracts-check, `just doctor-quick`, pytest, frontend type-check,
and frontend tests on every push and pull request. `just doctor-quick`
validates paths, executables, Compose rendering, and service import contracts;
it does not start or probe the live stack. `replay.yml` runs the Temporal
replay coverage; `eval.yml` runs the eval fixtures. Treat a red CI as the same
severity as a red local `just doctor`.

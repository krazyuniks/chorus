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
| `just worker` | Run the Lighthouse Temporal worker. |
| `just intake-once` | Poll Mailpit once and start new Lighthouse workflows. |
| `just test` / `just test-replay` / `just test-persistence` | Python gates. |
| `just test-frontend` / `just test-e2e` | Frontend gates. |
| `just lint` / `just fmt` | Linters and formatters across Python and frontend. |
| `just hooks` | Run every prek hook against the whole tree. |
| `just demo` | Send the fixture lead via Mailpit (Phase 1A). |

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
CHORUS_DATABASE_URL=postgresql://chorus:chorus@localhost:55432/chorus CHORUS_REDPANDA_BOOTSTRAP_SERVERS=localhost:19092 uv run python -m chorus.persistence.redpanda relay-once
```

Project one bounded Redpanda batch into Postgres read models:

```bash
CHORUS_DATABASE_URL=postgresql://chorus:chorus@localhost:55432/chorus CHORUS_REDPANDA_BOOTSTRAP_SERVERS=localhost:19092 uv run python -m chorus.persistence.redpanda project-once
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
uv run python -m chorus.persistence.redpanda relay-once && uv run python -m chorus.persistence.redpanda project-once
```

Worker metrics are emitted through the OpenTelemetry SDK to the collector and
scraped from the collector's Prometheus endpoint. There is intentionally no
worker sidecar HTTP `/metrics` endpoint or
`infrastructure/prometheus/targets/intake-poller.yml` file in Phase 1A.

## Workstream C Agent Runtime operations

`lighthouse.invoke_agent_runtime` resolves runtime policy from Postgres and
writes one `decision_trail_entries` row per invocation. The Phase 1A seed
routes every Lighthouse role to the local `lighthouse-happy-path-v1` structured
model boundary, so the happy path runs without commercial provider credentials.

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
just psql 2>/dev/null || ./scripts/dc exec postgres psql -U "${CHORUS_PG_USER:-chorus}" -d "${CHORUS_PG_DB:-chorus}"
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

## Observability surfaces

Phase 1A ships OpenTelemetry traces/logs/metrics through the OTel collector
into Grafana. The pipeline shape is committed in
[ADR 0010](../adrs/0010-observability-pipeline.md). Workstream F's exit
criterion is that Temporal, Redpanda, Grafana, the UI, and the audit views
can be correlated from one workflow ID.

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
Python tests, and frontend lint/test on every push and PR. `eval.yml` and
`replay.yml` run their respective gates with `continue-on-error` until the
fixtures land in Phase 1A. Treat a red CI as the same severity as a red
local `just doctor`; both signal a project-level contract slipping.

## Deferrals (Phase 1)

- Production deployment, secret management, on-call rotation, incident response.
- Real third-party connectors and credentials.
- Cloud-hosted observability backends.

These are documented in [implementation-plan.md §Deferred After Phase 1](./implementation-plan.md).

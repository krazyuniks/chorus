---
type: project-doc
status: active
date: 2026-05-20
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

A note on what runs today. The runtime code is the pre-reset implementation.
It exercises all six ports, but the currently runnable workflow is the
pre-reset Lighthouse slice, not the UC1 insurance-broking domain. R3 lands the
named-port refactor and the UC1 adapters; R4 wires UC1, UC2, and UC3. Where a
command runs the pre-reset slice, the runbook says so, and it marks the steps
that R3 and R4 complete.

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
just demo          # send the fixture lead to Mailpit SMTP
just intake-once   # poll Mailpit once and start a workflow per new message
```

Inspect inbound mail in the Mailpit UI at `http://localhost:8025`. The poller
deduplicates by Message-ID and derives a stable workflow ID, so re-sending the
same fixture records a duplicate rather than starting a second run; use a fresh
Message-ID when rehearsing.

R3 lands the UC1 channel adapters (email, web form, partner portal) and the
synthetic-channel fixture loader behind this port.

### LLM provider port

The LLM provider port carries model invocations. On the local stack reasoning
runs through the Agent Runtime; each invocation writes a decision-trail row.

Inspect the model routes resolved for a tenant:

```bash
./scripts/dc exec postgres psql -U chorus -d chorus -c \
  "SELECT agent_role, task_kind, provider, model FROM model_routing_policies WHERE tenant_id = 'tenant_demo' ORDER BY agent_role;"
```

R3 replaces the pre-reset agent execution path with the OpenAI-SDK adapter and
the route catalogue (DeepSeek V4-Flash for the dev route, gpt-5.4-mini for the
demo and eval route).

### Connector port

The connector port is the external-action authority; the Tool Gateway mediates
every call. On the local stack connectors are real software in sandbox mode.

Inspect the grants for an agent:

```bash
./scripts/dc exec postgres psql -U chorus -d chorus -c \
  "SELECT agent_id, tool_name, mode, allowed, approval_required FROM tool_grants WHERE tenant_id = 'tenant_demo' ORDER BY tool_name;"
```

Every gateway call writes an audit row regardless of verdict; see the audit
port section below. R3 replaces the hardcoded dispatch with an adapter registry
and lands the UC1 connector adapters.

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
sequence is stable; it is the UC1 workflow spine. The runnable instance today
is the pre-reset Lighthouse fixture. R3 and R4 swap in the UC1 insurance
enquiry fixtures and the UC1 adapters; the sequence does not change.

1. **Bring the stack up (all ports).** Run the bring-up commands above:
   `just up && just db-migrate && just schemas-register && just doctor`.

2. **Inject a synthetic enquiry (intake port).** `just demo && just intake-once`.
   The intake port accepts the inbound work and a workflow starts. Capture the
   `correlation_id` from the Mailpit-derived workflow or from the BFF.

3. **Classification and context (LLM provider port).** The workflow runs its
   reasoning steps through the LLM provider port. Each invocation writes a
   decision-trail row and, after R3, a transcript row. In the UC1 domain these
   steps are classification and context gathering; in the pre-reset slice they
   are the research and qualification steps.

4. **Qualification verdict (LLM provider port).** The workflow produces a
   structured verdict carrying the policy snapshot reference, the inputs
   considered, and the conduct-hook trace. R3 lands the UC1 verdict shape; the
   pre-reset slice produces the Lighthouse draft-and-validate output.

5. **Routing (connector port).** The verdict is routed through the Tool
   Gateway to a connector adapter. Every call carries a grant check, a mode
   decision, an argument validation, and a verdict. In the pre-reset slice the
   gated outbound action is captured by Mailpit.

6. **Inspect the decision-trail and transcript (audit ports).** Run the
   decision-trail and `tool_action_audit` SQL from the audit port section with
   the captured `correlation_id`. Every LLM invocation and every connector call
   should be covered; that is the audit completeness invariant.

7. **Inspect projections and observability (projection and observability
   sinks).** `just relay-once && just project-once`, then inspect the run in
   the BFF or frontend and in Grafana by `correlation_id`.

8. **Cross-provider replay-eval (closing step).** `just eval` runs the eval
   fixtures. Cross-provider replay-eval - re-running a captured transcript
   against an alternate route and comparing the result - is the closing eval
   step. The replay subcommand and the invariant-based eval suite land in R3
   and R4; the target shape is in
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

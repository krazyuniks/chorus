---
type: adr
status: accepted
date: 2026-04-29
---

# ADR 0010 — Observability pipeline shape

## Status

Accepted — 2026-04-29. Workstreams B and C now emit telemetry through the pipeline this ADR commits: the `chorus-intake-poller` service runs under the service-template `opentelemetry-instrument` ENTRYPOINT, the Temporal worker attaches `temporalio.contrib.opentelemetry.TracingInterceptor`, workflow and activity boundaries stamp `chorus.tenant_id`/`chorus.correlation_id`/`chorus.workflow_id` via `chorus.observability.set_current_span_attributes()`, audit-write paths capture `current_otel_ids()` into `metadata` jsonb, and the four event schemas declare canonical Schema Registry subjects (`x-subject`).

## Context

ADR 0009 fixes the operating model as local-only and states that
"observability terminates at a local Grafana stack. OpenTelemetry collector
exports to a containerised Grafana, Tempo, Loki, and Prometheus." That
sentence is intentionally minimal; it does not say what gets traced, how
trace IDs join audit rows, or what each Workstream owns when it instruments
its services.

The architecture review claim is that for one Lighthouse workflow, a
reviewer can navigate UI → Temporal Console → Grafana panel → SQL audit row
without losing the join. Doing that requires a single, deliberate pipeline
contract, not "every team picks an OTel SDK". This ADR pre-commits the
contract so Workstreams B (workflow + activities), C (agent runtime), D
(tool gateway + connectors), and E (BFF) emit telemetry the same way.

The pipeline must also leave **audit** as the source of truth for
accountability questions (who did what, what did the gateway decide, what
budget did this invocation consume) and use OpenTelemetry only for
**operational** questions (latency, retry rate, dependency health, queue
depth). Mixing those concerns is the failure mode this ADR exists to
prevent.

## Decision

### 1. Stack

Phase 1 ships four services in `compose.yml` for the observability plane:

| Component | Role | Container image |
|---|---|---|
| OpenTelemetry Collector (contrib) | Single OTLP ingress; pipeline of receivers → processors → exporters. | `otel/opentelemetry-collector-contrib` |
| Tempo | Traces backend. | `grafana/tempo` |
| Loki | Logs backend. | `grafana/loki` |
| Prometheus | Metrics backend. | `prom/prometheus` (scrape collector + service `/metrics`) |
| Grafana | Read surface. | `grafana/grafana` (already in `compose.yml`). |

Provisioned datasources live under `infrastructure/grafana/provisioning/datasources/`.
Phase 1A ships the Postgres datasource immediately (read models and audit);
Tempo, Loki, and Prometheus datasources are added in the same file when
their services land.

### 2. Instrumentation

- **Python services** use OpenTelemetry auto-instrumentation for FastAPI,
  httpx, asyncpg, and `psycopg`. Each service starts via
  `opentelemetry-instrument` (or `opentelemetry-bootstrap` baked into the
  image) so adding a new dependency does not need a code change to start
  emitting spans.
- **Temporal** workers use the Temporal Python SDK's OpenTelemetry
  interceptor (`temporalio.contrib.opentelemetry.TracingInterceptor`) so
  workflow and activity executions appear as spans. Workflow code remains
  deterministic — the SDK only records start/end markers, not arbitrary
  span events from inside `@workflow.defn`.
- **Frontend** does not emit OTel directly in Phase 1. The BFF instruments
  the entire request path, which is sufficient for the Lighthouse review
  surface. Browser RUM is deferred.

Resource attributes set on every emitter:

| Attribute | Source |
|---|---|
| `service.name` | `OTEL_SERVICE_NAME` env var, set per-container in `compose.yml` |
| `service.namespace` | `chorus` |
| `deployment.environment` | `local` (per ADR 0009) |
| `service.version` | git SHA at build time, falling back to `dev` |

### 3. Trace context propagation

- W3C `traceparent` and `tracestate` headers carry trace context across the
  BFF, agent runtime, tool gateway, and local connector boundaries. No
  custom header schemes.
- Temporal's interceptor propagates trace context across activity calls so
  that an activity's span is a child of the workflow span.
- The collector deduplicates trace context against `tracestate`. Where an
  upstream caller does not send `traceparent` (e.g. the Mailpit intake
  poller, which polls), the service starts a new trace at the activity
  boundary; the workflow span chain begins there.

### 4. Correlation, tenant, and audit join

The pipeline is non-authoritative. The authoritative join key for
accountability is the **`workflow_id` / `correlation_id` pair already
written into every audit and decision-trail row** by Workstream A. OTel
trace IDs are layered on top and recorded **into** audit rows, not the
other way around.

Concretely:

- Every span carries `chorus.tenant_id`, `chorus.correlation_id`, and
  `chorus.workflow_id` as span attributes. These are stamped at the BFF
  request boundary and at the Temporal workflow boundary, then propagated
  downstream by attribute inheritance from parent span context.
- At each audit-write boundary (Workstream A's
  `ProjectionStore.record_*` methods, Workstream D's gateway audit write),
  the active span's `trace_id` and `span_id` are read from the OTel
  context and persisted into the audit row's `metadata` jsonb under keys
  `otel.trace_id` and `otel.span_id`. Workstream A owns adding those
  fields to the read-model and audit migrations; Workstream F owns the
  documentation and the join queries.
- Grafana panels expose `correlation_id` as a free-text variable so a
  reviewer pasting a `cor_*` ID into one dashboard narrows every panel
  uniformly. Tempo's TraceQL panels then take the same `correlation_id`
  via the `chorus.correlation_id` span attribute.

The result: Postgres audit rows and Tempo traces join on
`correlation_id` for a workflow, on `trace_id` for a single request span
chain.

### 5. Logs

- Python services emit structured JSON logs at INFO+ to stdout. The
  collector's `filelog` receiver reads container stdout; the
  `transform` processor extracts `chorus.correlation_id`,
  `chorus.tenant_id`, `chorus.workflow_id`, `trace_id`, `span_id` from
  the log body or the active OTel context.
- Loki labels: `service`, `tenant_id`, `workflow_id`. `correlation_id`
  and `trace_id` are not labels (high cardinality); they live in the log
  line and are queried with `|=` filters.

### 6. Metrics

- Python services expose `/metrics` for Prometheus scraping where
  framework conventions support it (FastAPI middleware), plus OTel SDK
  metrics for measurements not exposed by frameworks (e.g. agent-runtime
  budget gauges, gateway verdict counters).
- Prometheus scrapes both the collector's `prometheus` exporter and each
  service's `/metrics`. The collector forwards OTel-native metrics to
  Prometheus via the `prometheusremotewrite` exporter.
- Workstream F-owned Prometheus alert rules are deferred until at least
  two end-to-end runs produce baseline numbers.

### 7. Sampling

Phase 1 is **always-on parent-based** sampling. The local volume is one or
two demo runs at a time; sampling adds noise without saving cost.
Production sampling decisions are deferred per ADR 0009.

### 8. Out of scope

- Browser RUM, real user monitoring, frontend-side tracing.
- Cross-tenant aggregation queries (multi-tenant in Phase 1 is the
  fixture seeds, not real workloads).
- SLOs, alerting, paging, on-call runbook entries (ADR 0009 §6).
- Trace-driven prompt replay or model-output capture (decision_trail_entries
  remains the authoritative store for agent reasoning artefacts; OTel does
  not carry prompt or response bodies).

## Alternatives considered

- **Tempo-only stack, no Loki/Prometheus.** Rejected: the runbook already
  references Grafana panels for projection lag, gateway verdicts, and
  agent decisions. Without metrics, those panels collapse to log-tail
  queries that do not aggregate. The added compose surface is small.
- **Embed `trace_id` as a first-class column on every audit table.**
  Rejected: it pollutes the schema with an OTel-specific concept. Storing
  it inside the existing `metadata jsonb` keeps the schema clean and
  allows the OTel pipeline to evolve without migrations.
- **Per-service tracing config.** Rejected: each service picking its own
  exporter, sampler, and resource conventions is exactly the failure mode
  this ADR exists to prevent. The pipeline is one decision, taken once.
- **OpenTelemetry logs as the only log path (no stdout).** Rejected:
  stdout logs are the local-developer-loop surface; routing them through
  the collector preserves both `docker logs <service>` and Loki without
  splitting the pipeline.

## Consequences

### Positive

- One join contract from UI → Temporal → Grafana → audit. The runbook's
  cross-surface correlation procedure has a concrete recipe instead of a
  promise.
- Each workstream gets a single, short instrumentation checklist on
  landing: auto-instrumentation entrypoint, resource attributes, span
  attributes for `correlation_id` / `tenant_id`, and the audit-write
  trace_id capture. No per-service decisions.
- Audit remains authoritative for accountability, which preserves the
  governance posture set by the architecture (agents have no ambient
  authority; the audit row is the artefact).

### Negative

- Three new services in `compose.yml` (Tempo, Loki, Prometheus) raise the
  baseline RAM/disk footprint of `just up` on a developer workstation.
  Mitigated by retention defaults pinned to a few hours and
  `docker compose stop <service>` being available for review-only sessions.
- The trace_id-in-jsonb pattern means trace ↔ audit joins are queried
  with `WHERE metadata->>'otel.trace_id' = ...` rather than via an
  indexed column. For Phase 1 demo volume this is fine; if production
  scales the audit tables, this becomes a candidate column.

### Operational

- `chorus.doctor` already probes the OTel collector's gRPC and HTTP
  endpoints. When Tempo/Loki/Prometheus land, doctor extends with their
  HTTP readiness endpoints in the same layered shape.
- `infrastructure/otel/config.yaml` is the single configuration surface
  for the pipeline. Receivers, processors, and exporter targets all live
  there; no per-service exporter config in service code.
- `docs/runbook.md` cross-surface correlation recipe gains a Tempo step
  when the trace backend lands; the recipe shape (paste `correlation_id`,
  follow links) is committed by this ADR.

## Compliance with existing ADRs

- Consistent with ADR 0001 (evidence-first scope) — the pipeline serves
  the architecture review, not production operations.
- Consistent with ADR 0007 (trace/eval harness) — this ADR governs the
  runtime trace pipeline; ADR 0007 governs the offline replay/eval
  fixtures. They share `correlation_id` as the join key.
- Consistent with ADR 0009 (local-only operating model) — the stack is
  containerised, the data is local, and there is no managed backend.

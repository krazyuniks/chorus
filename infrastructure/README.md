# Infrastructure

Local-first runtime substrate configuration.

- `otel/` — OpenTelemetry Collector pipeline configuration (traces, metrics, logs export to the Grafana stack).
- `grafana/` — Grafana dashboards, datasource provisioning, alert rules (Phase 1A).

The runtime stack itself is defined in [`compose.yml`](../compose.yml) at the repo root. Production deployment is deferred (see [implementation-plan.md](../docs/implementation-plan.md) — Deferred After Phase 1).

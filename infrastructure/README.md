# Infrastructure

Local-first runtime substrate configuration.

- `postgres/` - Postgres migrations and idempotent demo seed data for tenant-scoped policy, audit, projections, and transactional outbox.
- `otel/` - OpenTelemetry Collector pipeline configuration for traces, metrics, and logs export to the Grafana stack.
- `grafana/` - Grafana dashboards, datasource provisioning, and local inspection surfaces.

The runtime stack itself is defined in [`compose.yml`](../compose.yml) at the
repo root. Production deployment is out of scope for the local POC.

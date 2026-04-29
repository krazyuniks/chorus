# Grafana provisioning

Grafana is provisioned at startup from this directory via the bind-mount in
`compose.yml`. Edits made through the Grafana UI are not persisted; change
the JSON or YAML files here instead.

## Layout

```
infrastructure/grafana/
├── provisioning/
│   ├── datasources/chorus.yaml      # Postgres datasource (uid: chorus-postgres)
│   └── dashboards/chorus.yaml       # tells Grafana to load /etc/grafana/dashboards
└── dashboards/
    ├── workflow-timeline.json       # Lighthouse status, recent runs, outbox by step
    ├── gateway-verdicts.json        # tool_action_audit slices by tool / verdict
    ├── projection-lag.json          # outbox depth, oldest pending age, failures
    └── agent-decisions.json         # decision_trail_entries: routes, outcome, cost
```

## Backends

Phase 1A wires only **Postgres** as a datasource. Every panel reads from
the Workstream A tables (`workflow_read_models`, `decision_trail_entries`,
`tool_action_audit`, `outbox_events`). This makes the
"UI -> Grafana panel -> audit row by `correlation_id`" trail demonstrable
before any OTel-driven trace/metric/log backend lands. Empty tables show
empty panels — that is the correct state until B/C/D start producing data.

Tempo, Loki, and Prometheus datasources are intentionally deferred until
the OTel collector pipeline is wired through to running services
(see [ADR 0010](../../adrs/0010-observability-pipeline.md) and
`infrastructure/otel/config.yaml`). When they land, add them to
`provisioning/datasources/chorus.yaml` in the same additive shape.

## Variables

Every dashboard exposes:

- `$tenant` — populated from `SELECT tenant_id FROM tenants`. Defaults to all.
- `$correlation` — free-text filter on `correlation_id`. Defaults to `%`
  (matches all). Pasting a `cor_*` ID narrows every panel to one workflow.

These two filters give an architecture reviewer the cross-surface join
key. The same `correlation_id` then drops into the SQL audit query in the
runbook (`SELECT ... FROM tool_action_audit WHERE correlation_id = ...`)
and, once Temporal traces land, into the Temporal UI search by workflow ID.

## Editing dashboards

1. Edit the JSON file under `dashboards/`.
2. Within 30 seconds Grafana reloads (provisioning poll interval).
3. To pick up larger changes — including new datasources — restart the
   Grafana container: `./scripts/dc restart grafana`.

Do not export dashboards from the Grafana UI to overwrite these files
without removing UI-injected fields (`__inputs`, `__requires`, `id`).
Dashboards here use `"id": null` so Grafana assigns a fresh ID at import.

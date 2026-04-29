# Prometheus service-discovery targets

Phase 1A services declare their `/metrics` endpoints by dropping a YAML
file in this directory. Prometheus's `file_sd_configs` job
(`chorus-services`, see `../config.yaml`) picks the files up on a
30-second refresh — no Prometheus restart, no edit to the central
`config.yaml`.

## File shape

One file per service. Filename matches the service name (e.g.
`bff.yml`, `tool-gateway.yml`). Each file is a single-element list:

```yaml
- targets:
    - chorus-bff:8000
  labels:
    service: bff
```

`targets` lists the in-network address(es) where the service exposes
`/metrics`. The `service` label is promoted to the Prometheus `job`
label by the relabel rule in `config.yaml`, so dashboards keyed off
`job="bff"` work without further configuration.

When the service has multiple replicas, list every replica address;
Prometheus scrapes each one independently and the dashboards aggregate.

## Onboarding workflow

1. Add the service to `compose.yml` with `container_name: chorus-<role>`
   and a port that exposes `/metrics`.
2. Drop the corresponding `<service>.yml` here.
3. Confirm scraping at `http://localhost:9090/targets`.

See `services/_template/README.md` § "Observability onboarding" for the
full per-service checklist (metrics + logs + trace context).

# BFF — Backend-for-Frontend

Read-only FastAPI service that fronts the Lighthouse UI. Owns:

- read endpoints over Workstream A's projections (`workflow_read_models`,
  `workflow_history_events`, `decision_trail_entries`, `tool_action_audit`,
  `agent_registry`, `model_routing_policies`, `tool_grants`);
- a server-sent events stream that polls `workflow_history_events` and emits
  progress frames keyed by tenant/correlation/workflow.

The BFF owns no workflow state and makes no orchestration, model, or
connector calls. SSE is a progress channel — every UI view rehydrates from
a read endpoint on refresh or reconnect (see ADR 0001 §"Phase 1 evidence
posture" and the Workstream E ledger row E-05).

## Run locally

The service is wired into `compose.yml` as `chorus-bff` under the
`opentelemetry-instrument` ENTRYPOINT. Bring it up with the rest of the
stack:

```zsh
just up
```

For focused development on the host:

```zsh
just bff
```

The recipe runs `uvicorn chorus.bff.app:app --reload` against the local
Postgres from `.env`.

## Endpoints

| Method | Path | Returns |
|---|---|---|
| `GET` | `/health` | Liveness probe. |
| `GET` | `/api/workflows` | Workflow run summaries from `workflow_read_models`. |
| `GET` | `/api/workflows/{workflow_id}` | Single workflow run. |
| `GET` | `/api/workflows/{workflow_id}/events` | History events from `workflow_history_events`. |
| `GET` | `/api/workflows/{workflow_id}/decision-trail` | Decision-trail entries scoped to one run. |
| `GET` | `/api/workflows/{workflow_id}/tool-verdicts` | Tool-action audit rows scoped to one run. |
| `GET` | `/api/decision-trail` | Recent decision-trail entries (filterable). |
| `GET` | `/api/tool-verdicts` | Recent tool-action audit rows (filterable). |
| `GET` | `/api/runtime/registry` | Read-only agent registry view. |
| `GET` | `/api/runtime/routing` | Read-only model-routing policy view. |
| `GET` | `/api/runtime/grants` | Read-only tool-grant view. |
| `GET` | `/api/progress` | SSE workflow-history progress stream. |

The service is intentionally tenant-fixed for Phase 1A. `CHORUS_TENANT_ID`
or `CHORUS_BFF_DEFAULT_TENANT` selects the tenant, defaulting to
`tenant_demo`. The SSE stream accepts optional `correlation_id` and
`workflow_id` filters, and `once=true` terminates the stream after one
snapshot batch for tests.

Span attributes (`chorus.tenant_id`, `chorus.correlation_id`,
`chorus.workflow_id`) are stamped on the active request span via
`chorus.observability.set_current_span_attributes()` per ADR 0010 §4.

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `CHORUS_DATABASE_URL` | `postgresql://chorus:chorus@localhost:5432/chorus` | Postgres conninfo for projections. |
| `CHORUS_TENANT_ID` / `CHORUS_BFF_DEFAULT_TENANT` | `tenant_demo` | Tenant projected by the BFF. |
| `CHORUS_BFF_SSE_POLL_INTERVAL_SECONDS` | `1.0` | Poll interval for `/api/progress`. |

Phase 1A workstream **E** (BFF + UI). See
[implementation-plan.md](../../docs/implementation-plan.md).

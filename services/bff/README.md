# BFF - Backend For Frontend

Read-only FastAPI service for Chorus inspection views.

Owns:

- read endpoints over workflow projections, decision trail, tool-action audit,
  runtime policy, provider governance, and grants;
- a server-sent events stream that emits workflow progress frames keyed by
  tenant, correlation, and workflow.

Does not own:

- workflow state;
- orchestration;
- model calls;
- connector calls;
- policy mutation.

## Run Locally

```zsh
just bff
```

## Endpoints

| Method | Path | Returns |
|---|---|---|
| `GET` | `/health` | Liveness probe. |
| `GET` | `/api/workflows` | Workflow run summaries. |
| `GET` | `/api/workflows/{workflow_id}` | Single workflow run. |
| `GET` | `/api/workflows/{workflow_id}/events` | Workflow history events. |
| `GET` | `/api/workflows/{workflow_id}/decision-trail` | Decision-trail entries scoped to one run. |
| `GET` | `/api/workflows/{workflow_id}/tool-verdicts` | Tool-action audit rows scoped to one run. |
| `GET` | `/api/decision-trail` | Recent decision-trail entries. |
| `GET` | `/api/tool-verdicts` | Recent tool-action audit rows. |
| `GET` | `/api/runtime/registry` | Read-only agent registry view. |
| `GET` | `/api/runtime/routing` | Read-only model-routing policy view. |
| `GET` | `/api/runtime/grants` | Read-only tool-grant view. |
| `GET` | `/api/progress` | SSE workflow-history progress stream. |

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `CHORUS_DATABASE_URL` | `postgresql://chorus:chorus@localhost:5432/chorus` | Postgres conninfo for projections. |
| `CHORUS_TENANT_ID` / `CHORUS_BFF_DEFAULT_TENANT` | `tenant_demo` | Tenant projected by the BFF. |
| `CHORUS_BFF_SSE_POLL_INTERVAL_SECONDS` | `1.0` | Poll interval for `/api/progress`. |

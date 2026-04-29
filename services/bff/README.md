# BFF — Backend-for-Frontend

FastAPI service that fronts the Lighthouse UI. Exposes:

- Lead intake endpoint (secondary to the SMTP-receive trigger; used for fixture replay during development).
- Read-model endpoints for workflow timeline, decision trail, tool verdicts, runtime registry, grants, and routing views.
- SSE stream for one-way workflow progress updates.

Owns no workflow state and makes no orchestration or connector calls. Delegates to Postgres projections and Temporal Console links.

Phase 1A persistence exposes the initial read-model interface in [`../../chorus/persistence/projection.py`](../../chorus/persistence/projection.py). BFF endpoints should read workflow summaries and runtime policy snapshots through that adapter or through equivalent SQL that preserves the same tenant-scoped RLS boundary.

Phase 1A workstream **E** (BFF + UI). See [implementation-plan.md](../../docs/implementation-plan.md).

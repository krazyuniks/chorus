# Projection Worker

Consumes schema-governed events from Redpanda and updates Postgres read models:

- Workflow timeline (per workflow run).
- Decision trail (per agent invocation).
- Tool audit (per gateway verdict).
- DLQ / escalation surface.

Survives reconnect. Idempotent on event redelivery. Owns no critical workflow state — Temporal remains source of truth.

Phase 1A workstream **A** has established the storage and adapter foundation:

- SQL schema and RLS policies: [`../../infrastructure/postgres/migrations`](../../infrastructure/postgres/migrations)
- Demo tenant seeds: [`../../infrastructure/postgres/seeds`](../../infrastructure/postgres/seeds)
- Projection adapter: [`../../chorus/persistence/projection.py`](../../chorus/persistence/projection.py)

Later projection-worker implementation should consume `ProjectionStore.apply_workflow_event()` for idempotent read-model updates and preserve Temporal as the workflow state owner. See [implementation-plan.md](../../docs/implementation-plan.md).

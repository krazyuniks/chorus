# Projection Worker

Consumes schema-governed `workflow_event` events from Redpanda and updates Postgres read models:

- Workflow timeline (per workflow run).
- Workflow run status, current step, summary, and completion timestamp.
- Idempotent workflow history for refresh/reconnect semantics.

Survives reconnect. Idempotent on event redelivery. Owns no critical workflow state — Temporal remains source of truth.

Phase 1A workstream **A** has implemented the storage, outbox, relay, and projection foundation:

- SQL schema and RLS policies: [`../../infrastructure/postgres/migrations`](../../infrastructure/postgres/migrations)
- Demo tenant seeds: [`../../infrastructure/postgres/seeds`](../../infrastructure/postgres/seeds)
- Projection adapter: [`../../chorus/persistence/projection.py`](../../chorus/persistence/projection.py)
- Outbox lifecycle: [`../../chorus/persistence/outbox.py`](../../chorus/persistence/outbox.py)
- Redpanda relay/consumer: [`../../chorus/persistence/redpanda.py`](../../chorus/persistence/redpanda.py)

The bounded worker entry point is:

```bash
uv run python -m chorus.persistence.redpanda project-once
```

It consumes Redpanda messages with manual offset commits and calls `ProjectionStore.apply_workflow_event()` inside a Postgres transaction before committing the Kafka offset. Redelivery is safe because `workflow_history_events` dedupes by source event and `workflow_read_models` advances only by newer sequence numbers.

Later Workstream E/BFF code should read `workflow_read_models` and `workflow_history_events`; it should not duplicate tenant-isolation or projection policy.

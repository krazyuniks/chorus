# Postgres Persistence

Phase 1A uses Postgres for policy materialisation, audit evidence, read models, episodic workflow history, and transactional outbox rows.

- `migrations/` contains ordered SQL migrations.
- `seeds/` contains idempotent local demo data. The initial seed creates `tenant_demo` and `tenant_demo_alt` for tenant-isolation evidence.

Run `just db-migrate` after the local Postgres service is running. The migration runner reads `CHORUS_DATABASE_URL` and defaults to `postgresql://chorus:chorus@localhost:5432/chorus`.

RLS policies use `app.tenant_id` as the session tenant context and fail closed when it is unset. Application services should set the tenant context before reading or writing tenant-owned tables.

## Workstream A interfaces

`ProjectionStore.record_workflow_event()` appends canonical `workflow_event` payloads to `outbox_events` and is the interface later Temporal activities should call after their service-owned state changes. The method is idempotent by `event_id` and by `(tenant_id, workflow_id, sequence)`.

`OutboxStore` claims due rows with `FOR UPDATE SKIP LOCKED`, marks them `publishing`, increments `attempts`, and transitions rows to `sent` or `failed`. Failed rows retain `last_error` and retry through `next_attempt_at`; abandoned `publishing` leases can be released back to the retry path. Phase 1B adds terminal `dlq` rows for retry-exhaustion evidence; those rows are retained for inspection and are never reclaimed by the relay claim path.

`ProjectionStore.apply_workflow_event()` is the projection-worker write path. It inserts workflow history once per source event and advances `workflow_read_models` only when the consumed event sequence is newer than the stored sequence.

For local ports that differ from defaults, run the Workstream A tests with:

```bash
CHORUS_TEST_ADMIN_DATABASE_URL=postgresql://chorus:chorus@localhost:55432/postgres CHORUS_REDPANDA_BOOTSTRAP_SERVERS=localhost:19092 uv run pytest tests/persistence
```

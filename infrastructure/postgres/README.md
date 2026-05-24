# Postgres Persistence

Postgres stores policy materialisation, audit evidence, transcript records,
read models, episodic workflow history, transactional outbox rows, provider
catalogue rows, approval package records, local UC1 connector-side routing
records, UC1 connector read-reference data, immutable route-version evidence,
and immutable local policy snapshot rows for governance inspection.

- `migrations/` starts from `001_current_state_baseline.sql`, the current R4
  local POC schema baseline. Earlier experimental migration history lives in
  git history, not in the executable migration directory.
- The projection, outbox, and approval-package workflow-type checks admit the
  declared UC1, UC2, and UC3 workflow families. Calendar-specific approval
  action constraints remain in place until the approval-generalisation slice.
- `seeds/` contains idempotent local demo data. The initial seed creates
  `tenant_demo` and `tenant_demo_alt` for tenant-isolation evidence. The
  provider-governance seed mirrors local route materialisation into
  route-version rows and keeps non-runnable provider placeholders disabled.
  The UC1 connector-reference seed backs the customer-profile and
  product-catalogue read adapters with synthetic local rows. The UC1 policy
  snapshot seed materialises `policy_snapshot:uc1:default:v1` as a safe-ref
  bundle behind the deterministic qualifier output.

Run `just db-migrate` after the local Postgres service is running. The
migration runner reads `CHORUS_DATABASE_URL` and defaults to
`postgresql://chorus:chorus@localhost:5432/chorus`.

The baseline is idempotent enough to be applied once to a local database that
already recorded the previous migration chain; it records the current baseline
without rewriting tenant data. For a schema with no pre-baseline experimental
leftovers, create a fresh local database or reset local volumes before running
`just db-migrate`.

RLS policies use `app.tenant_id` as the session tenant context and fail closed
when it is unset. Application services should set the tenant context before
reading or writing tenant-owned tables.

## Persistence Interfaces

`ProjectionStore.record_workflow_event()` appends canonical `workflow_event` payloads to `outbox_events` and is the interface later Temporal activities should call after their service-owned state changes. The method is idempotent by `event_id` and by `(tenant_id, workflow_id, sequence)`.

`OutboxStore` claims due rows with `FOR UPDATE SKIP LOCKED`, marks them
`publishing`, increments `attempts`, and transitions rows to `sent` or
`failed`. Failed rows retain `last_error` and retry through
`next_attempt_at`; abandoned `publishing` leases can be released back to the
retry path. Terminal `dlq` rows are retained for inspection and are never
reclaimed by the relay claim path.

`ProjectionStore.apply_workflow_event()` is the projection-worker write path. It inserts workflow history once per source event and advances `workflow_read_models` only when the consumed event sequence is newer than the stored sequence.

`ProjectionStore.provider_governance_snapshot()` reads the provider catalogue,
provider models, and tenant-scoped immutable route versions for inspection
surfaces. It does not mutate routes and does not change the Agent Runtime
execution path.

For local ports that differ from defaults, run the Workstream A tests with:

```bash
CHORUS_TEST_ADMIN_DATABASE_URL=postgresql://chorus:chorus@localhost:55432/postgres CHORUS_REDPANDA_BOOTSTRAP_SERVERS=localhost:19092 uv run pytest tests/persistence
```

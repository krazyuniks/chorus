# Postgres Persistence

Phase 1A uses Postgres for policy materialisation, audit evidence, read models, episodic workflow history, and transactional outbox rows.

- `migrations/` contains ordered SQL migrations.
- `seeds/` contains idempotent local demo data. The initial seed creates `tenant_demo` and `tenant_demo_alt` for tenant-isolation evidence.

Run `just db-migrate` after the local Postgres service is running. The migration runner reads `CHORUS_DATABASE_URL` and defaults to `postgresql://chorus:chorus@localhost:5432/chorus`.

RLS policies use `app.tenant_id` as the session tenant context and fail closed when it is unset. Application services should set the tenant context before reading or writing tenant-owned tables.

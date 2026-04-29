# Tests

Repo-level test layout. Most tests live alongside their service (`services/<name>/tests/`). This top-level directory holds:

- `test_scaffold.py` — Phase 0 scaffold checks for docs, service directories, and the fixture email.
- `persistence/` — real Postgres migration, projection, RLS, and fail-closed tenant-isolation tests. Set `CHORUS_TEST_ADMIN_DATABASE_URL` if the Compose Postgres host port is not `5432`.
- `workflows/` — Temporal replay tests and end-to-end workflow tests that span multiple services.
- `e2e/` — Playwright tests for the Lighthouse UI.
- `contracts/` — JSON Schema validation and drift checks for `contracts/`.

Phase 1A items 4, 5, 7, 8, 9, 10 (see [implementation-plan.md](../docs/implementation-plan.md)) declare test coverage as part of their exit criteria.

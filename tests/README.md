# Tests

Repo-level test layout. Most tests live alongside their service (`services/<name>/tests/`). This top-level directory holds:

- `test_scaffold.py` — project scaffold checks for docs, service directories, and the fixture email.
- `persistence/` — real Postgres migration, projection, RLS, and fail-closed tenant-isolation tests. Set `CHORUS_TEST_ADMIN_DATABASE_URL` if the Compose Postgres host port is not `5432`.
- `workflows/` — Temporal replay tests and end-to-end workflow tests that span multiple services.
- `e2e/` — Playwright tests for the Chorus UI.
- `contracts/` — JSON Schema validation and drift checks for `contracts/`.

Reset-phase implementation docs declare the relevant gate for each slice; use
`just --list` for the current command surface.

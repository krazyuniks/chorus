# Tests

Repo-level test layout. Most tests live alongside their service (`services/<name>/tests/`). This top-level directory holds:

- `test_scaffold.py` — project scaffold checks for docs, service directories, and the fixture email.
- `persistence/` — real Postgres migration, projection, RLS, and fail-closed tenant-isolation tests. They target the Compose Postgres on host port `55432` (the value of `CHORUS_PG_PORT` in `.env`). `tests/conftest.py` loads `.env` automatically; override `CHORUS_TEST_ADMIN_DATABASE_URL` explicitly only when running against a non-Compose database.
- `workflows/` — Temporal replay tests and end-to-end workflow tests that span multiple services.
- `e2e/` — Playwright tests for the Chorus UI.
- `contracts/` — JSON Schema validation and drift checks for `contracts/`.

Reset-phase implementation docs declare the relevant gate for each slice; use
`just --list` for the current command surface.

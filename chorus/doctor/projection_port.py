"""Live readiness probes for the projection port substrate.

The projection port is backed by Postgres (`schema_migrations` + the workflow
projection tables) and Redpanda's schema registry (the canonical workflow
event subjects). Both probe modules live here because the projection port
fans out across both stores.
"""

from __future__ import annotations

import json
from typing import Any

import psycopg
from psycopg import Connection

from chorus.doctor._net import env_int, http_get, tcp_reachable
from chorus.doctor._reporting import fail, ok, section, skip
from chorus.doctor.scaffold import ROOT


def _applied_migrations(conn: Connection[Any]) -> set[str]:
    rows = conn.execute("SELECT filename FROM schema_migrations").fetchall()
    return {str(r[0]) for r in rows}


def check_postgres_migrations() -> int:
    section("postgres migrations (projection / audit port substrate)")
    pg_port = env_int("CHORUS_PG_PORT", 5432)
    if not tcp_reachable("localhost", pg_port):
        skip(f"postgres not reachable on localhost:{pg_port} (run 'just up')")
        return 0

    from chorus.persistence.migrate import (
        MIGRATIONS_DIR,
        database_url_from_env,
        sql_files,
    )

    expected = [f.filename for f in sql_files(MIGRATIONS_DIR)]
    if not expected:
        skip("no migration files present yet")
        return 0

    try:
        with psycopg.connect(database_url_from_env(), connect_timeout=2) as conn:
            row = conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone()
            if row is None or row[0] is None:
                fail("schema_migrations table missing - run 'just db-migrate'")
                return 1
            applied = _applied_migrations(conn)
    except psycopg.Error as exc:
        fail(f"postgres reachable but query failed: {exc}")
        return 1

    failures = 0
    for filename in expected:
        if filename in applied:
            ok(f"migration applied: {filename}")
        else:
            fail(f"migration not applied: {filename} - run 'just db-migrate'")
            failures += 1
    return failures


def _expected_event_subjects() -> dict[str, str | None]:
    """Map event-stream contract schemas to their declared registry subject.

    A schema opts into the strict check by setting ``x-subject`` at top level
    (string). Schemas without that declaration are reported informationally
    and never fail the check. After the R3 contract rewrite, event-stream
    contracts live under the relevant ports (intake, projection, audit), so
    we walk ``contracts/**/*.schema.json`` and filter by ``x-subject``.
    """

    expected: dict[str, str | None] = {}
    for path in sorted((ROOT / "contracts").rglob("*.schema.json")):
        try:
            data = json.loads(path.read_text())
        except OSError, json.JSONDecodeError:
            continue
        subject = data.get("x-subject")
        if isinstance(subject, str) and subject:
            expected[path.name] = subject
    return expected


def check_schema_registry() -> int:
    section("redpanda schema registry (projection port subjects)")
    port = env_int("REDPANDA_SCHEMA_REGISTRY_PORT", 8081)
    if not tcp_reachable("localhost", port):
        skip(f"schema registry not reachable on localhost:{port} (run 'just up')")
        return 0
    status, body = http_get(f"http://localhost:{port}/subjects")
    if status != 200:
        fail(f"schema registry on localhost:{port} returned status {status}")
        return 1
    ok(f"schema registry responding on localhost:{port}")

    try:
        registered = set(json.loads(body or "[]"))
    except json.JSONDecodeError:
        fail("schema registry /subjects returned non-JSON body")
        return 1

    expected = _expected_event_subjects()
    if not expected:
        skip("no event-stream contracts declare x-subject under contracts/")
        return 0

    failures = 0
    declared = expected

    if not declared and not registered:
        skip(
            "no x-subject declared on event-stream contracts and no subjects "
            "registered (workstream B has not yet pinned canonical subject names)"
        )
    elif not declared and registered:
        skip(
            f"{len(registered)} subject(s) registered but no contract declares "
            "x-subject - declare on an event-stream schema under contracts/ to "
            "enable the strict drift check"
        )
        for subject in sorted(registered):
            print(f"info  - registry subject: {subject}")
    else:
        for name, subject in declared.items():
            if subject in registered:
                ok(f"{name}: subject '{subject}' registered")
            else:
                fail(f"{name}: subject '{subject}' missing from registry")
                failures += 1

    return failures

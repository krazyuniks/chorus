"""Live readiness probes for the projection port substrate.

The projection port is backed by Postgres (`schema_migrations` + the workflow
projection tables) and Redpanda's schema registry (the canonical workflow
event subjects). Both probe modules live here because the projection port
fans out across both stores.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

import psycopg
from confluent_kafka.admin import AdminClient
from psycopg import Connection

from chorus.doctor._env import redacted_url, required_env
from chorus.doctor._net import env_int, http_get, tcp_reachable, url_host_port
from chorus.doctor._reporting import fail, ok, section, skip
from chorus.doctor.scaffold import ROOT

FindingLevel = Literal["ok", "fail"]


@dataclass(frozen=True)
class MigrationFinding:
    level: FindingLevel
    message: str


def _applied_migrations(conn: Connection[Any]) -> dict[str, str]:
    rows = conn.execute("SELECT filename, checksum_sha256 FROM schema_migrations").fetchall()
    return {str(row[0]): str(row[1]) for row in rows}


def migration_findings(
    expected: Mapping[str, str],
    applied: Mapping[str, str],
) -> list[MigrationFinding]:
    findings: list[MigrationFinding] = []
    for filename, checksum in sorted(expected.items()):
        applied_checksum = applied.get(filename)
        if applied_checksum is None:
            findings.append(
                MigrationFinding(
                    "fail",
                    f"migration not applied: {filename} - run 'just db-migrate'",
                )
            )
        elif applied_checksum != checksum:
            findings.append(
                MigrationFinding(
                    "fail",
                    f"migration checksum mismatch: {filename} - create a new migration",
                )
            )
        else:
            findings.append(MigrationFinding("ok", f"migration applied: {filename}"))
    return findings


def check_postgres_migrations() -> int:
    section("postgres migrations (projection / audit port substrate)")
    database_url = required_env("CHORUS_DATABASE_URL")
    if database_url is None:
        fail("CHORUS_DATABASE_URL is not set in .env or the process environment")
        return 1
    host_port = url_host_port(database_url, default_port=5432)
    if host_port is None:
        fail(f"CHORUS_DATABASE_URL is not a valid Postgres URL: {redacted_url(database_url)}")
        return 1
    pg_host, pg_port = host_port
    if not tcp_reachable(pg_host, pg_port):
        fail(f"postgres not reachable at {pg_host}:{pg_port} from CHORUS_DATABASE_URL")
        return 1

    from chorus.persistence.migrate import (
        MIGRATIONS_DIR,
        sql_files,
    )

    expected_files = sql_files(MIGRATIONS_DIR)
    expected = {file.filename: file.checksum_sha256 for file in expected_files}
    if not expected:
        skip("no migration files present yet")
        return 0

    try:
        with psycopg.connect(database_url, connect_timeout=2) as conn:
            row = conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone()
            if row is None or row[0] is None:
                fail("schema_migrations table missing - run 'just db-migrate'")
                return 1
            applied = _applied_migrations(conn)
    except psycopg.Error as exc:
        fail(f"postgres query failed at {redacted_url(database_url)}: {exc}")
        return 1

    failures = 0
    for finding in migration_findings(expected, applied):
        if finding.level == "ok":
            ok(finding.message)
        else:
            fail(finding.message)
            failures += 1
    return failures


def _bootstrap_list(bootstrap_servers: str) -> Sequence[str]:
    return [server.strip() for server in bootstrap_servers.split(",") if server.strip()]


def check_redpanda_bootstrap() -> int:
    section("redpanda bootstrap (projection event substrate)")
    bootstrap_servers = required_env("CHORUS_REDPANDA_BOOTSTRAP_SERVERS")
    if bootstrap_servers is None:
        fail("CHORUS_REDPANDA_BOOTSTRAP_SERVERS is not set in .env or the process environment")
        return 1
    for server in _bootstrap_list(bootstrap_servers):
        if ":" not in server:
            fail(f"redpanda bootstrap server is missing host:port: {server}")
            return 1
    try:
        metadata = AdminClient({"bootstrap.servers": bootstrap_servers}).list_topics(timeout=2)
    except Exception as exc:
        fail(f"redpanda bootstrap not reachable via {bootstrap_servers}: {exc}")
        return 1
    brokers = cast(object, getattr(metadata, "brokers", {}))
    if isinstance(brokers, Mapping):
        broker_count = len(cast(Mapping[object, object], brokers))
    else:
        broker_count = 0
    ok(f"redpanda bootstrap reachable via {bootstrap_servers} ({broker_count} broker(s))")
    return 0


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

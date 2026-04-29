"""Minimal Postgres migration runner for the Phase 1A persistence foundation."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, LiteralString, cast

import psycopg
from psycopg import Connection, sql

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = ROOT / "infrastructure" / "postgres" / "migrations"
SEEDS_DIR = ROOT / "infrastructure" / "postgres" / "seeds"
DEFAULT_DATABASE_URL = "postgresql://chorus:chorus@localhost:5432/chorus"

MIGRATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename text PRIMARY KEY,
    checksum_sha256 text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);
"""


@dataclass(frozen=True)
class SqlFile:
    path: Path
    checksum_sha256: str
    body: str

    @property
    def filename(self) -> str:
        return self.path.name


def sql_files(directory: Path) -> list[SqlFile]:
    files: list[SqlFile] = []
    for path in sorted(directory.glob("*.sql")):
        body = path.read_text(encoding="utf-8")
        files.append(
            SqlFile(
                path=path,
                checksum_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
                body=body,
            )
        )
    return files


def database_url_from_env() -> str:
    return os.environ.get("CHORUS_DATABASE_URL", DEFAULT_DATABASE_URL)


def _trusted_sql(body: str) -> sql.SQL:
    # Migration files are repo-controlled SQL, not user-supplied query text.
    return sql.SQL(cast(LiteralString, body))


def _applied_checksum(conn: Connection[Any], filename: str) -> str | None:
    row = conn.execute(
        "SELECT checksum_sha256 FROM schema_migrations WHERE filename = %s",
        (filename,),
    ).fetchone()
    if row is None:
        return None
    checksum = row[0]
    if not isinstance(checksum, str):
        raise TypeError(f"Unexpected checksum type for {filename}: {type(checksum).__name__}")
    return checksum


def _record_migration(conn: Connection[Any], sql_file: SqlFile) -> None:
    conn.execute(
        """
        INSERT INTO schema_migrations (filename, checksum_sha256)
        VALUES (%s, %s)
        ON CONFLICT (filename) DO UPDATE
        SET checksum_sha256 = EXCLUDED.checksum_sha256,
            applied_at = now()
        """,
        (sql_file.filename, sql_file.checksum_sha256),
    )


def apply_migrations(
    database_url: str | None = None,
    *,
    include_seeds: bool = True,
) -> list[str]:
    """Apply SQL migrations and optional idempotent seeds.

    Migrations are checksum-protected and only run once. Seed files are designed
    to be idempotent and run after migrations whenever requested.
    """

    applied: list[str] = []
    conninfo = database_url or database_url_from_env()

    with psycopg.connect(conninfo) as conn:
        conn.execute(MIGRATION_TABLE_SQL)

        for sql_file in sql_files(MIGRATIONS_DIR):
            checksum = _applied_checksum(conn, sql_file.filename)
            if checksum == sql_file.checksum_sha256:
                continue
            if checksum is not None and checksum != sql_file.checksum_sha256:
                raise RuntimeError(
                    f"Migration checksum changed for {sql_file.filename}; "
                    "create a new migration instead of editing an applied one."
                )

            conn.execute(_trusted_sql(sql_file.body))
            _record_migration(conn, sql_file)
            applied.append(sql_file.filename)

        if include_seeds:
            for sql_file in sql_files(SEEDS_DIR):
                conn.execute(_trusted_sql(sql_file.body))
                applied.append(sql_file.filename)

    return applied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply Chorus Postgres migrations.")
    parser.add_argument(
        "--database-url",
        default=None,
        help="Postgres connection URL. Defaults to CHORUS_DATABASE_URL or the local Compose URL.",
    )
    parser.add_argument(
        "--no-seeds",
        action="store_true",
        help="Apply migrations only; skip idempotent demo seed data.",
    )
    args = parser.parse_args(argv)

    applied = apply_migrations(args.database_url, include_seeds=not args.no_seeds)
    if applied:
        print("Applied:")
        for filename in applied:
            print(f"- {filename}")
    else:
        print("Postgres schema is current.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

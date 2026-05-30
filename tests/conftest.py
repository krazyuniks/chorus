"""Test bootstrap.

Loads `chorus/.env` so test runs use the same host-mapped service ports
(Postgres on 55432, Redpanda on 19092, etc.) as the Compose stack. The
authoritative configuration is `.env`; infrastructure-backed fixtures fail
loudly when required URLs are unset or unreachable.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from confluent_kafka.admin import AdminClient
from dotenv import load_dotenv
from psycopg import sql

from chorus.persistence import apply_migrations

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / ".env"

if not ENV_FILE.is_file():
    raise RuntimeError(
        f"tests/conftest.py expected {ENV_FILE} to exist. "
        "Copy .env.example to .env or set the required environment variables "
        "before running the test suite."
    )

load_dotenv(ENV_FILE, override=False)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live-openai",
        action="store_true",
        default=False,
        help="Run credential-gated live OpenAI provider integration tests.",
    )
    parser.addoption(
        "--live-deepseek",
        action="store_true",
        default=False,
        help="Run credential-gated live DeepSeek provider integration tests.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live_openai: credential-gated live OpenAI provider integration test",
    )
    config.addinivalue_line(
        "markers",
        "live_deepseek: credential-gated live DeepSeek provider integration test",
    )
    if bool(config.getoption("--live-openai")) and not os.environ.get("OPENAI_API_KEY", "").strip():
        raise pytest.UsageError(
            "Live OpenAI integration tests require OPENAI_API_KEY to be set and non-empty."
        )
    if (
        bool(config.getoption("--live-deepseek"))
        and not os.environ.get("DEEPSEEK_API_KEY", "").strip()
    ):
        raise pytest.UsageError(
            "Live DeepSeek integration tests require DEEPSEEK_API_KEY to be set and non-empty."
        )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    live_openai_requested = bool(config.getoption("--live-openai"))
    live_deepseek_requested = bool(config.getoption("--live-deepseek"))

    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        unrequested_live_test = ("live_openai" in item.keywords and not live_openai_requested) or (
            "live_deepseek" in item.keywords and not live_deepseek_requested
        )
        if unrequested_live_test:
            deselected.append(item)
        else:
            selected.append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        raise RuntimeError(
            f"{name} must be set in {ENV_FILE} or the process environment before "
            "running infrastructure-backed tests."
        )
    return value


def _redacted_url(url: str) -> str:
    parts = urlsplit(url)
    netloc = parts.netloc
    if parts.password is not None and "@" in netloc:
        auth, host = netloc.rsplit("@", 1)
        username = auth.split(":", 1)[0]
        netloc = f"{username}:***@{host}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _database_url(admin_database_url: str, dbname: str) -> str:
    parts = urlsplit(admin_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{dbname}", parts.query, parts.fragment))


@pytest.fixture(scope="session")
def test_admin_database_url() -> str:
    return _required_env("CHORUS_TEST_ADMIN_DATABASE_URL")


@pytest.fixture(scope="module")
def migrated_database_url(
    request: pytest.FixtureRequest,
    test_admin_database_url: str,
) -> Iterator[str]:
    module = cast(ModuleType, cast(Any, request).module)
    prefix = cast(str, getattr(module, "TEST_DATABASE_PREFIX", "chorus_test"))
    dbname = f"{prefix}_{uuid4().hex}"
    if len(dbname) > 63:
        dbname = f"{prefix[:30].rstrip('_')}_{uuid4().hex}"

    try:
        with psycopg.connect(
            test_admin_database_url,
            autocommit=True,
            connect_timeout=2,
        ) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    except psycopg.OperationalError as exc:
        raise RuntimeError(
            "Postgres is required for infrastructure-backed tests but could not be "
            "reached via "
            f"CHORUS_TEST_ADMIN_DATABASE_URL={_redacted_url(test_admin_database_url)!r}."
        ) from exc

    database_url = _database_url(test_admin_database_url, dbname)
    try:
        apply_migrations(database_url)
        yield database_url
    finally:
        with psycopg.connect(
            test_admin_database_url,
            autocommit=True,
            connect_timeout=2,
        ) as admin:
            admin.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (dbname,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname)))


@pytest.fixture(scope="module")
def redpanda_bootstrap() -> str:
    bootstrap_servers = _required_env("CHORUS_REDPANDA_BOOTSTRAP_SERVERS")
    admin = AdminClient({"bootstrap.servers": bootstrap_servers})
    try:
        admin.list_topics(timeout=2)
    except Exception as exc:
        raise RuntimeError(
            "Redpanda is required for projection tests but could not be reached "
            f"via CHORUS_REDPANDA_BOOTSTRAP_SERVERS={bootstrap_servers!r}."
        ) from exc
    return bootstrap_servers

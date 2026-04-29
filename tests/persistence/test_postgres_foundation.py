from __future__ import annotations

import os
from collections.abc import Iterator
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from chorus.contracts.generated.events.workflow_event import WorkflowEvent
from chorus.persistence import ProjectionStore, apply_migrations

ADMIN_DATABASE_URL = os.environ.get(
    "CHORUS_TEST_ADMIN_DATABASE_URL",
    "postgresql://chorus:chorus@localhost:5432/postgres",
)


def _database_url(dbname: str) -> str:
    parts = urlsplit(ADMIN_DATABASE_URL)
    return urlunsplit((parts.scheme, parts.netloc, f"/{dbname}", parts.query, parts.fragment))


@pytest.fixture(scope="module")
def migrated_database_url() -> Iterator[str]:
    dbname = f"chorus_test_{uuid4().hex}"

    try:
        with psycopg.connect(ADMIN_DATABASE_URL, autocommit=True, connect_timeout=2) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres is not available for persistence tests: {exc}")

    database_url = _database_url(dbname)
    try:
        apply_migrations(database_url)
        yield database_url
    finally:
        with psycopg.connect(ADMIN_DATABASE_URL, autocommit=True, connect_timeout=2) as admin:
            admin.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (dbname,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname)))


def _set_app_role(conn: psycopg.Connection[object], tenant_id: str | None = None) -> None:
    conn.execute("SET ROLE chorus_app")
    if tenant_id is not None:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (tenant_id,))


def _workflow_event(
    *,
    tenant_id: str,
    workflow_id: str,
    sequence: int,
    event_type: str = "workflow.started",
    step: str | None = "intake",
) -> WorkflowEvent:
    return WorkflowEvent.model_validate(
        {
            "schema_version": "1.0.0",
            "event_id": str(uuid4()),
            "event_type": event_type,
            "occurred_at": "2026-04-29T12:00:00Z",
            "tenant_id": tenant_id,
            "correlation_id": f"cor_{workflow_id.replace('-', '_')}",
            "workflow_id": workflow_id,
            "lead_id": str(uuid4()),
            "sequence": sequence,
            "step": step,
            "payload": {
                "lead_summary": f"Lead for {tenant_id}",
                "status": "started",
            },
        }
    )


def test_migration_applies_schema_and_demo_seed_data(migrated_database_url: str) -> None:
    with psycopg.connect(migrated_database_url) as conn:
        tenants = conn.execute("SELECT tenant_id FROM tenants ORDER BY tenant_id").fetchall()
        tables = conn.execute(
            """
            SELECT relname
            FROM pg_class
            WHERE relkind = 'r' AND relnamespace = 'public'::regnamespace
            ORDER BY relname
            """
        ).fetchall()
        rls_enabled = conn.execute(
            """
            SELECT relname
            FROM pg_class
            WHERE relrowsecurity
              AND relname IN (
                'tenants',
                'agent_registry',
                'model_routing_policies',
                'tool_grants',
                'workflow_read_models',
                'decision_trail_entries',
                'tool_action_audit',
                'workflow_history_events',
                'outbox_events'
              )
            ORDER BY relname
            """
        ).fetchall()

    assert tenants == [("tenant_demo",), ("tenant_demo_alt",)]
    assert ("outbox_events",) in tables
    assert ("workflow_read_models",) in tables
    assert len(rls_enabled) == 9


def test_rls_fails_closed_without_tenant_context(migrated_database_url: str) -> None:
    with psycopg.connect(migrated_database_url, autocommit=True) as conn:
        _set_app_role(conn)

        visible_tenants = conn.execute("SELECT tenant_id FROM tenants").fetchall()
        assert visible_tenants == []

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                """
                INSERT INTO workflow_read_models (
                    tenant_id,
                    workflow_id,
                    correlation_id,
                    lead_id,
                    status
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    "tenant_demo",
                    "lighthouse-fail-closed",
                    "cor_fail_closed",
                    uuid4(),
                    "running",
                ),
            )


def test_rls_limits_reads_to_current_tenant(migrated_database_url: str) -> None:
    with psycopg.connect(migrated_database_url) as conn:
        store = ProjectionStore(conn)
        store.record_workflow_event(
            _workflow_event(
                tenant_id="tenant_demo",
                workflow_id="lighthouse-tenant-demo",
                sequence=1,
            )
        )
        store.record_workflow_event(
            _workflow_event(
                tenant_id="tenant_demo_alt",
                workflow_id="lighthouse-tenant-demo-alt",
                sequence=1,
            )
        )

    with psycopg.connect(migrated_database_url, autocommit=True) as conn:
        _set_app_role(conn, "tenant_demo")
        visible = conn.execute(
            "SELECT tenant_id, workflow_id FROM workflow_read_models ORDER BY workflow_id"
        ).fetchall()

    assert visible == [("tenant_demo", "lighthouse-tenant-demo")]


def test_projection_store_records_read_model_history_and_outbox(
    migrated_database_url: str,
) -> None:
    event = _workflow_event(
        tenant_id="tenant_demo",
        workflow_id="lighthouse-projection",
        sequence=1,
    )

    with psycopg.connect(migrated_database_url) as conn:
        store = ProjectionStore(conn)
        store.record_workflow_event(event)
        store.record_workflow_event(event)

        read_model = store.get_workflow("tenant_demo", "lighthouse-projection")
        outbox_count = conn.execute(
            "SELECT count(*) FROM outbox_events WHERE event_id = %s",
            (event.event_id,),
        ).fetchone()
        history_count = conn.execute(
            "SELECT count(*) FROM workflow_history_events WHERE source_event_id = %s",
            (event.event_id,),
        ).fetchone()

    assert read_model is not None
    assert read_model.status == "running"
    assert read_model.current_step == "intake"
    assert read_model.last_event_sequence == 1
    assert outbox_count == (1,)
    assert history_count == (1,)


def test_runtime_policy_snapshot_is_tenant_scoped(migrated_database_url: str) -> None:
    with psycopg.connect(migrated_database_url, autocommit=True) as conn:
        _set_app_role(conn, "tenant_demo")
        store = ProjectionStore(conn)
        demo_snapshot = store.runtime_policy_snapshot("tenant_demo")

        store.set_tenant_context("tenant_demo_alt")
        alt_snapshot = store.runtime_policy_snapshot("tenant_demo_alt")

    assert [agent.tenant_id for agent in demo_snapshot.agents] == ["tenant_demo"]
    assert [route.tenant_id for route in demo_snapshot.model_routes] == ["tenant_demo"]
    assert [grant.tenant_id for grant in demo_snapshot.tool_grants] == ["tenant_demo"]
    assert [agent.tenant_id for agent in alt_snapshot.agents] == ["tenant_demo_alt"]

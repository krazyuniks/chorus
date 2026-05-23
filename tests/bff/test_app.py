from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from chorus.bff import BffSettings, create_app
from chorus.contracts.generated.projection.workflow_event import WorkflowEvent
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
    dbname = f"chorus_bff_test_{uuid4().hex}"

    try:
        with psycopg.connect(ADMIN_DATABASE_URL, autocommit=True, connect_timeout=2) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres is not available for BFF tests: {exc}")

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


@pytest.fixture
def seeded_bff(migrated_database_url: str) -> TestClient:
    workflow_id = f"uc1-enq-bff-{uuid4().hex}"
    correlation_id = f"cor_bff_{uuid4().hex}"
    subject_id = uuid4()
    subject_ref = f"enq_bff_{uuid4().hex[:12]}"
    now = datetime(2026, 4, 29, 12, 0, tzinfo=UTC)

    with psycopg.connect(migrated_database_url) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", ("tenant_demo",))
        store = ProjectionStore(conn)
        store.set_tenant_context("tenant_demo")

        event = WorkflowEvent.model_validate(
            {
                "schema_version": "1.0.0",
                "event_id": str(uuid4()),
                "event_type": "enquiry.received",
                "occurred_at": now.isoformat(),
                "tenant_id": "tenant_demo",
                "correlation_id": correlation_id,
                "workflow_id": workflow_id,
                "workflow_type": "uc1_enquiry_qualification",
                "subject_id": str(subject_id),
                "subject_ref": subject_ref,
                "sequence": 1,
                "step": "intake",
                "payload": {
                    "enquiry_summary": "BFF projection enquiry",
                    "sender": "enquiry@example.com",
                },
            }
        )
        store.record_workflow_event(event)
        store.apply_workflow_event(event)
        conn.commit()

    settings = BffSettings(database_url=migrated_database_url, tenant_id="tenant_demo")
    app = create_app(settings)
    client = TestClient(app)
    client.headers.update({"x-test-workflow-id": workflow_id})
    client.headers.update({"x-test-correlation-id": correlation_id})
    client.headers.update({"x-test-subject-ref": subject_ref})
    return client


def _workflow_id(client: TestClient) -> str:
    return client.headers["x-test-workflow-id"]


def test_bff_serves_projection_backed_workflow_detail(seeded_bff: TestClient) -> None:
    workflow_id = _workflow_id(seeded_bff)

    workflows = seeded_bff.get("/api/workflows").json()
    detail = seeded_bff.get(f"/api/workflows/{workflow_id}").json()

    assert any(row["workflow_id"] == workflow_id for row in workflows)
    assert detail["workflow_type"] == "uc1_enquiry_qualification"
    assert detail["subject_summary"] == "BFF projection enquiry"


def test_bff_serves_history_events(seeded_bff: TestClient) -> None:
    workflow_id = _workflow_id(seeded_bff)
    events = seeded_bff.get(f"/api/workflows/{workflow_id}/events").json()
    assert events
    assert events[0]["event_type"] == "enquiry.received"
    assert events[0]["step"] == "intake"

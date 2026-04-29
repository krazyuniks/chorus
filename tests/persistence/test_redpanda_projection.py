from __future__ import annotations

import os
from collections.abc import Iterator
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from confluent_kafka.admin import AdminClient
from psycopg import sql

from chorus.contracts.generated.events.workflow_event import WorkflowEvent
from chorus.persistence import OutboxStore, ProjectionStore, apply_migrations
from chorus.persistence.redpanda import (
    RedpandaWorkflowEventConsumer,
    RedpandaWorkflowEventPublisher,
)

ADMIN_DATABASE_URL = os.environ.get(
    "CHORUS_TEST_ADMIN_DATABASE_URL",
    "postgresql://chorus:chorus@localhost:5432/postgres",
)
BOOTSTRAP_SERVERS = os.environ.get("CHORUS_REDPANDA_BOOTSTRAP_SERVERS", "localhost:9092")


def _database_url(dbname: str) -> str:
    parts = urlsplit(ADMIN_DATABASE_URL)
    return urlunsplit((parts.scheme, parts.netloc, f"/{dbname}", parts.query, parts.fragment))


@pytest.fixture(scope="module")
def migrated_database_url() -> Iterator[str]:
    dbname = f"chorus_redpanda_test_{uuid4().hex}"

    try:
        with psycopg.connect(ADMIN_DATABASE_URL, autocommit=True, connect_timeout=2) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres is not available for Redpanda projection tests: {exc}")

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


@pytest.fixture(scope="module")
def redpanda_bootstrap() -> str:
    admin = AdminClient({"bootstrap.servers": BOOTSTRAP_SERVERS})
    try:
        admin.list_topics(timeout=2)
    except Exception as exc:
        pytest.skip(f"Redpanda is not available for projection tests: {exc}")
    return BOOTSTRAP_SERVERS


def _workflow_event(*, topic_token: str) -> WorkflowEvent:
    return WorkflowEvent.model_validate(
        {
            "schema_version": "1.0.0",
            "event_id": str(uuid4()),
            "event_type": "workflow.started",
            "occurred_at": "2026-04-29T12:00:00Z",
            "tenant_id": "tenant_demo",
            "correlation_id": f"cor_{topic_token}",
            "workflow_id": f"lighthouse-{topic_token}",
            "lead_id": str(uuid4()),
            "sequence": 1,
            "step": "intake",
            "payload": {
                "lead_summary": "Redpanda projection fixture",
                "status": "started",
            },
        }
    )


def test_outbox_event_relays_through_redpanda_and_projects_idempotently(
    migrated_database_url: str,
    redpanda_bootstrap: str,
) -> None:
    topic_token = uuid4().hex
    topic = f"chorus.workflow.events.test.{topic_token}"
    event = _workflow_event(topic_token=topic_token)

    with psycopg.connect(migrated_database_url) as conn:
        store = ProjectionStore(conn)
        store.record_workflow_event(event)
        conn.execute(
            "UPDATE outbox_events SET topic = %s WHERE event_id = %s",
            (topic, event.event_id),
        )
        outbox = OutboxStore(conn)
        claimed = outbox.claim_pending(limit=1)

        publisher = RedpandaWorkflowEventPublisher(bootstrap_servers=redpanda_bootstrap)
        publisher.publish(claimed[0])
        outbox.mark_sent(claimed[0].outbox_id)

    consumer = RedpandaWorkflowEventConsumer(
        bootstrap_servers=redpanda_bootstrap,
        group_id=f"chorus-projection-test-{topic_token}",
        topics=(topic,),
    )
    try:
        consumed = None
        for _ in range(10):
            consumed = consumer.poll(timeout=1)
            if consumed is not None:
                break
        assert consumed is not None
        assert consumed.event == event

        with psycopg.connect(migrated_database_url) as conn:
            store = ProjectionStore(conn)
            store.apply_workflow_event(consumed.event)
            store.apply_workflow_event(consumed.event)
            consumer.commit()

            read_model = store.get_workflow("tenant_demo", event.workflow_id)
            status = conn.execute(
                """
                SELECT status, attempts, sent_at IS NOT NULL
                FROM outbox_events
                WHERE event_id = %s
                """,
                (event.event_id,),
            ).fetchone()
            history_count = conn.execute(
                "SELECT count(*) FROM workflow_history_events WHERE source_event_id = %s",
                (event.event_id,),
            ).fetchone()
    finally:
        consumer.close()

    assert read_model is not None
    assert read_model.status == "running"
    assert read_model.current_step == "intake"
    assert read_model.lead_summary == "Redpanda projection fixture"
    assert status == ("sent", 1, True)
    assert history_count == (1,)

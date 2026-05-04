from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from chorus.contracts.generated.events.workflow_event import WorkflowEvent
from chorus.persistence import OutboxStore, ProjectionStore, apply_migrations
from chorus.workflows.activities import record_retry_exhaustion_dlq
from chorus.workflows.types import RetryExhaustionDlqCommand

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
                'outbox_events',
                'model_route_versions'
              )
            ORDER BY relname
            """
        ).fetchall()

    assert tenants == [("tenant_demo",), ("tenant_demo_alt",)]
    assert ("outbox_events",) in tables
    assert ("provider_catalogues",) in tables
    assert ("provider_catalogue_providers",) in tables
    assert ("provider_catalogue_models",) in tables
    assert ("model_route_versions",) in tables
    assert ("workflow_read_models",) in tables
    assert len(rls_enabled) == 10


def test_migrations_and_seeds_are_idempotent(migrated_database_url: str) -> None:
    first = apply_migrations(migrated_database_url)
    second = apply_migrations(migrated_database_url)

    with psycopg.connect(migrated_database_url) as conn:
        tenant_count = conn.execute("SELECT count(*) FROM tenants").fetchone()
        seed_agents = conn.execute(
            "SELECT count(*) FROM agent_registry WHERE metadata ->> 'seed' = 'true'"
        ).fetchone()

    assert first == ["001_demo_tenants.sql", "002_provider_governance.sql"]
    assert second == ["001_demo_tenants.sql", "002_provider_governance.sql"]
    assert tenant_count == (2,)
    assert seed_agents == (8,)


def test_provider_governance_seed_preserves_phase_1_routes(
    migrated_database_url: str,
) -> None:
    with psycopg.connect(migrated_database_url) as conn:
        providers = conn.execute(
            """
            SELECT provider_id, lifecycle_state, credential_required
            FROM provider_catalogue_providers
            ORDER BY provider_id
            """
        ).fetchall()
        models = conn.execute(
            """
            SELECT provider_id, model_id, lifecycle_state
            FROM provider_catalogue_models
            ORDER BY provider_id, model_id
            """
        ).fetchall()
        route_alignment = conn.execute(
            """
            SELECT
                policy.tenant_id,
                policy.agent_role,
                policy.task_kind,
                policy.provider,
                policy.model,
                version.route_version,
                version.provider_catalogue_id,
                version.max_latency_ms
            FROM model_routing_policies AS policy
            JOIN model_route_versions AS version
              ON version.route_id = policy.policy_id
             AND version.tenant_id = policy.tenant_id
             AND version.agent_role = policy.agent_role
             AND version.task_kind = policy.task_kind
             AND version.tenant_tier = policy.tenant_tier
            ORDER BY policy.tenant_id, policy.agent_role, policy.task_kind
            """
        ).fetchall()
        runtime_route_models = conn.execute(
            """
            SELECT DISTINCT provider, model
            FROM model_routing_policies
            ORDER BY provider, model
            """
        ).fetchall()
        commercial_route_count = conn.execute(
            """
            SELECT count(*)
            FROM model_route_versions
            WHERE provider_id = 'commercial.example'
            """
        ).fetchone()

    assert providers == [
        ("commercial.example", "disabled", True),
        ("local", "approved", False),
    ]
    assert models == [
        ("commercial.example", "commercial-reasoner-v1", "disabled"),
        ("local", "lighthouse-happy-path-v1", "approved"),
    ]
    assert len(route_alignment) == 8
    assert {row[3:5] for row in route_alignment} == {("local", "lighthouse-happy-path-v1")}
    assert {row[5] for row in route_alignment} == {1}
    assert {row[6] for row in route_alignment} == {"provider-catalogue.phase2a.seed"}
    assert {row[7] for row in route_alignment} == {5000}
    assert runtime_route_models == [("local", "lighthouse-happy-path-v1")]
    assert commercial_route_count == (0,)


def test_model_route_versions_are_immutable(migrated_database_url: str) -> None:
    with psycopg.connect(migrated_database_url, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute(
                """
                UPDATE model_route_versions
                SET max_latency_ms = 6000
                WHERE route_id = '11000000-0000-4000-8000-000000000004'
                  AND route_version = 1
                """
            )

        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute(
                """
                DELETE FROM model_route_versions
                WHERE route_id = '11000000-0000-4000-8000-000000000004'
                  AND route_version = 1
                """
            )


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
        store.apply_workflow_event(
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
        store.apply_workflow_event(
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
        store.apply_workflow_event(event)
        store.apply_workflow_event(event)

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


def test_projection_replay_is_idempotent_and_sequence_ordered(
    migrated_database_url: str,
) -> None:
    workflow_id = "lighthouse-reconnect"
    started = _workflow_event(
        tenant_id="tenant_demo",
        workflow_id=workflow_id,
        sequence=1,
        event_type="workflow.started",
        step="intake",
    )
    completed = _workflow_event(
        tenant_id="tenant_demo",
        workflow_id=workflow_id,
        sequence=2,
        event_type="workflow.completed",
        step="complete",
    )

    with psycopg.connect(migrated_database_url) as conn:
        store = ProjectionStore(conn)
        store.apply_workflow_event(completed)
        store.apply_workflow_event(started)
        store.apply_workflow_event(completed)

    with psycopg.connect(migrated_database_url) as conn:
        store = ProjectionStore(conn)
        read_model = store.get_workflow("tenant_demo", workflow_id)
        history_count = conn.execute(
            "SELECT count(*) FROM workflow_history_events WHERE workflow_id = %s",
            (workflow_id,),
        ).fetchone()

    assert read_model is not None
    assert read_model.status == "completed"
    assert read_model.current_step == "complete"
    assert read_model.last_event_sequence == 2
    assert history_count == (2,)


def test_outbox_claim_sent_failed_and_retry_transitions(
    migrated_database_url: str,
) -> None:
    event = _workflow_event(
        tenant_id="tenant_demo",
        workflow_id="lighthouse-outbox",
        sequence=1,
    )

    with psycopg.connect(migrated_database_url) as conn:
        conn.execute("UPDATE outbox_events SET status = 'sent', sent_at = now()")
        store = ProjectionStore(conn)
        store.record_workflow_event(event)
        outbox = OutboxStore(conn)

        claimed = outbox.claim_pending(limit=10)
        assert [row.event.event_id for row in claimed] == [event.event_id]
        assert claimed[0].attempts == 1
        assert claimed[0].event == event

        assert outbox.claim_pending(limit=10) == []

        outbox.mark_failed(
            claimed[0].outbox_id,
            error="temporary redpanda failure",
            retry_delay=timedelta(minutes=5),
        )
        retry_not_due = outbox.claim_pending(limit=10)
        assert retry_not_due == []

        conn.execute(
            "UPDATE outbox_events SET next_attempt_at = now() WHERE outbox_id = %s",
            (claimed[0].outbox_id,),
        )
        retry_claim = outbox.claim_pending(limit=10)
        assert [row.event.event_id for row in retry_claim] == [event.event_id]
        assert retry_claim[0].attempts == 2

        outbox.mark_sent(retry_claim[0].outbox_id)
        status = conn.execute(
            """
            SELECT status, attempts, sent_at IS NOT NULL, last_error
            FROM outbox_events
            WHERE event_id = %s
            """,
            (event.event_id,),
        ).fetchone()

    assert status == ("sent", 2, True, None)


def test_outbox_stale_publishing_rows_return_to_retry_path(
    migrated_database_url: str,
) -> None:
    event = _workflow_event(
        tenant_id="tenant_demo",
        workflow_id="lighthouse-stale-outbox",
        sequence=1,
    )

    with psycopg.connect(migrated_database_url) as conn:
        conn.execute("UPDATE outbox_events SET status = 'sent', sent_at = now()")
        store = ProjectionStore(conn)
        store.record_workflow_event(event)
        outbox = OutboxStore(conn)
        claimed = outbox.claim_pending(limit=1)

        conn.execute(
            """
            UPDATE outbox_events
            SET updated_at = now() - interval '10 minutes'
            WHERE outbox_id = %s
            """,
            (claimed[0].outbox_id,),
        )
        released = outbox.release_stale_publishing(older_than=timedelta(minutes=5))
        retry_claim = outbox.claim_pending(limit=1)

    assert released == 1
    assert retry_claim[0].event.event_id == event.event_id
    assert retry_claim[0].attempts == 2


def test_outbox_dlq_rows_are_terminal_and_not_reclaimed(
    migrated_database_url: str,
) -> None:
    event = _workflow_event(
        tenant_id="tenant_demo",
        workflow_id="lighthouse-dlq-outbox",
        sequence=1,
        event_type="workflow.failed",
        step="escalate",
    )

    with psycopg.connect(migrated_database_url) as conn:
        conn.execute("UPDATE outbox_events SET status = 'sent', sent_at = now()")
        store = ProjectionStore(conn)
        store.record_workflow_event(event)
        outbox = OutboxStore(conn)

        outbox_id = outbox.mark_dlq_by_event_id(
            event.event_id,
            error="retry policy exhausted",
        )
        outbox.mark_dlq(outbox_id, error="retry policy exhausted")

        assert outbox.claim_pending(limit=10) == []
        released = outbox.release_stale_publishing(older_than=timedelta(seconds=0))
        row = conn.execute(
            """
            SELECT status, last_error, next_attempt_at = 'infinity'::timestamptz
            FROM outbox_events
            WHERE event_id = %s
            """,
            (event.event_id,),
        ).fetchone()

    assert released == 0
    assert row == ("dlq", "retry policy exhausted", True)


def test_retry_exhaustion_activity_writes_dlq_outbox_and_audit(
    migrated_database_url: str,
) -> None:
    lead_id = uuid4()

    with psycopg.connect(migrated_database_url) as conn:
        conn.execute("UPDATE outbox_events SET status = 'sent', sent_at = now()")
        result = record_retry_exhaustion_dlq(
            conn,
            RetryExhaustionDlqCommand(
                tenant_id="tenant_demo",
                correlation_id="cor_retry_exhaustion_dlq",
                workflow_id="lighthouse-retry-exhaustion-dlq",
                lead_id=str(lead_id),
                sequence=5,
                failed_step="research_qualification",
                failed_activity="lighthouse.invoke_agent_runtime",
                failure_reason="fixture persistent agent runtime failure",
                attempts=3,
            ),
        )
        outbox = OutboxStore(conn)
        assert outbox.claim_pending(limit=10) == []
        row = conn.execute(
            """
            SELECT
                outbox.status,
                outbox.event_type,
                outbox.payload ->> 'failure_classification',
                audit.action,
                audit.raw_event -> 'details' -> 'dlq' ->> 'status'
            FROM outbox_events AS outbox
            JOIN tool_action_audit AS audit
              ON audit.tenant_id = outbox.tenant_id
             AND audit.workflow_id = outbox.workflow_id
            WHERE outbox.event_id = %s
            """,
            (result.event_id,),
        ).fetchone()

    assert result.outbox_status == "dlq"
    assert result.action == "workflow.retry_exhausted.dlq_recorded"
    assert row == (
        "dlq",
        "workflow.failed",
        "retry_exhausted",
        "workflow.retry_exhausted.dlq_recorded",
        "dlq",
    )


def test_runtime_policy_snapshot_is_tenant_scoped(migrated_database_url: str) -> None:
    with psycopg.connect(migrated_database_url, autocommit=True) as conn:
        _set_app_role(conn, "tenant_demo")
        store = ProjectionStore(conn)
        demo_snapshot = store.runtime_policy_snapshot("tenant_demo")

        store.set_tenant_context("tenant_demo_alt")
        alt_snapshot = store.runtime_policy_snapshot("tenant_demo_alt")

    assert {agent.tenant_id for agent in demo_snapshot.agents} == {"tenant_demo"}
    assert {route.tenant_id for route in demo_snapshot.model_routes} == {"tenant_demo"}
    assert {grant.tenant_id for grant in demo_snapshot.tool_grants} == {"tenant_demo"}
    assert {grant.tool_name for grant in demo_snapshot.tool_grants} >= {
        "company_research.lookup",
        "email.propose_response",
    }
    assert {agent.tenant_id for agent in alt_snapshot.agents} == {"tenant_demo_alt"}


def test_provider_governance_snapshot_keeps_route_versions_tenant_scoped(
    migrated_database_url: str,
) -> None:
    with psycopg.connect(migrated_database_url, autocommit=True) as conn:
        _set_app_role(conn, "tenant_demo")
        store = ProjectionStore(conn)
        demo_snapshot = store.provider_governance_snapshot("tenant_demo")

        store.set_tenant_context("tenant_demo_alt")
        alt_snapshot = store.provider_governance_snapshot("tenant_demo_alt")

    assert {provider.provider_id for provider in demo_snapshot.providers} == {
        "local",
        "commercial.example",
    }
    assert {model.model_id for model in demo_snapshot.provider_models} == {
        "lighthouse-happy-path-v1",
        "commercial-reasoner-v1",
    }
    assert {route.tenant_id for route in demo_snapshot.route_versions} == {"tenant_demo"}
    assert {route.tenant_id for route in alt_snapshot.route_versions} == {"tenant_demo_alt"}
    assert {route.model_id for route in demo_snapshot.route_versions} == {
        "lighthouse-happy-path-v1"
    }
    assert {route.provider_id for route in demo_snapshot.route_versions} == {"local"}

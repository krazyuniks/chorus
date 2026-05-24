from __future__ import annotations

import os
from collections.abc import Iterator
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from chorus.contracts.generated.projection.workflow_event import WorkflowEvent
from chorus.persistence import (
    OutboxStore,
    ProjectionStore,
    apply_migrations,
)
from chorus.persistence.projection import metadata_for_event, subject_summary_for_event
from chorus.persistence.runtime_policy import PolicySnapshotStore
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
    dbname = f"chorus_persistence_test_{uuid4().hex}"

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


def _workflow_event(
    *,
    tenant_id: str,
    workflow_id: str,
    sequence: int,
    workflow_type: str = "uc1_enquiry_qualification",
    event_type: str = "workflow.started",
    step: str | None = "intake",
    subject_ref: str = "enq_test_001",
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
            "workflow_type": workflow_type,
            "subject_id": str(uuid4()),
            "subject_ref": subject_ref,
            "sequence": sequence,
            "step": step,
            "payload": {
                "subject_summary": f"Enquiry for {tenant_id}",
                "status": "started",
            },
        }
    )


def test_projection_payload_helpers_prefer_generic_subject_vocabulary() -> None:
    event = _workflow_event(
        tenant_id="tenant_demo",
        workflow_id="uc1-enq-subject-vocabulary",
        sequence=1,
    )
    assert subject_summary_for_event(event) == "Enquiry for tenant_demo"

    legacy_event = event.model_copy(
        update={
            "payload": {
                "enquiry_summary": "Legacy UC1 enquiry summary",
                "sender": "enquiry@example.com",
                "message_id": "<legacy@example.test>",
            }
        }
    )
    assert subject_summary_for_event(legacy_event) == "Legacy UC1 enquiry summary"
    assert metadata_for_event(legacy_event)["subject_from"] == "enquiry@example.com"
    assert metadata_for_event(legacy_event)["source_message_id"] == "<legacy@example.test>"


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
        local_ticket_present = conn.execute(
            """
            SELECT relname
            FROM pg_class
            WHERE relname IN ('local_ticket_cases', 'local_ticket_case_update_proposals')
            """
        ).fetchall()

    assert tenants == [("tenant_demo",), ("tenant_demo_alt",)]
    assert ("outbox_events",) in tables
    assert ("provider_catalogues",) in tables
    assert ("model_route_versions",) in tables
    assert ("policy_snapshots",) in tables
    assert ("approval_packages",) in tables
    assert ("local_customer_profiles",) in tables
    assert ("local_product_catalogue_entries",) in tables
    assert ("local_quoting_queue_routes",) in tables
    assert ("local_referral_inbox_routes",) in tables
    assert ("local_decline_ledger_routes",) in tables
    assert ("workflow_read_models",) in tables
    assert local_ticket_present == []


def test_migrations_and_seeds_are_idempotent(migrated_database_url: str) -> None:
    first = apply_migrations(migrated_database_url)
    second = apply_migrations(migrated_database_url)

    with psycopg.connect(migrated_database_url) as conn:
        tenant_count = conn.execute("SELECT count(*) FROM tenants").fetchone()
        seed_agents = conn.execute(
            "SELECT count(*) FROM agent_registry WHERE metadata ->> 'seed' = 'true'"
        ).fetchone()

    assert first == [
        "001_demo_tenants.sql",
        "002_provider_governance.sql",
        "003_uc1_connector_reference_data.sql",
        "004_uc1_policy_snapshots.sql",
    ]
    assert second == [
        "001_demo_tenants.sql",
        "002_provider_governance.sql",
        "003_uc1_connector_reference_data.sql",
        "004_uc1_policy_snapshots.sql",
    ]
    assert tenant_count == (2,)
    assert seed_agents == (10,)


def test_uc1_connector_reference_data_is_seeded(migrated_database_url: str) -> None:
    with psycopg.connect(migrated_database_url) as conn:
        profile = conn.execute(
            """
            SELECT
                display_name_category,
                vulnerability_markers,
                consent_state_category,
                profile_status
            FROM local_customer_profiles
            WHERE tenant_id = 'tenant_demo'
              AND customer_ref = 'cust_demo_002'
            """
        ).fetchone()
        product = conn.execute(
            """
            SELECT
                target_market_summary_category,
                construction_categories,
                excluded_postcode_categories,
                fair_value_assessment_ref,
                catalogue_status
            FROM local_product_catalogue_entries
            WHERE tenant_id = 'tenant_demo'
              AND product_family_category = 'home_buildings'
            """
        ).fetchone()

    assert profile == (
        "individual_personal_lines",
        ["bereavement_declared"],
        "marketing_opt_out",
        "active",
    )
    assert product == (
        "uk_resident_homeowner_buildings",
        ["standard_brick", "standard_stone"],
        ["flood_zone_3"],
        "fva_home_buildings_2026_q1",
        "active",
    )


def test_uc1_agent_registry_roles_are_constrained(migrated_database_url: str) -> None:
    with psycopg.connect(migrated_database_url) as conn:
        roles = conn.execute("SELECT DISTINCT role FROM agent_registry ORDER BY role").fetchall()
    assert roles == [
        ("classifier",),
        ("context_gatherer",),
        ("qualifier",),
        ("request_drafter",),
        ("validator",),
    ]


def test_uc1_tool_grants_are_seeded(migrated_database_url: str) -> None:
    with psycopg.connect(migrated_database_url) as conn:
        tools = conn.execute(
            "SELECT DISTINCT tool_name FROM tool_grants ORDER BY tool_name"
        ).fetchall()
    assert ("customer_profile.lookup",) in tools
    assert ("outbound_comms.message",) in tools
    assert ("crm.route_to_quoting_queue",) in tools


def test_projection_store_records_read_model_history_and_outbox(
    migrated_database_url: str,
) -> None:
    with psycopg.connect(migrated_database_url) as conn:
        conn.execute("SELECT set_config('app.tenant_id', 'tenant_demo', false)")
        store = ProjectionStore(conn)
        event = _workflow_event(
            tenant_id="tenant_demo",
            workflow_id="uc1-enq-projection",
            sequence=1,
            event_type="enquiry.received",
        )
        store.record_workflow_event(event)
        store.apply_workflow_event(event)
        conn.commit()

        read_model = store.get_workflow("tenant_demo", "uc1-enq-projection")

    assert read_model is not None
    assert read_model.workflow_type == "uc1_enquiry_qualification"
    assert read_model.subject_ref == "enq_test_001"
    assert read_model.subject_summary == "Enquiry for tenant_demo"


@pytest.mark.parametrize(
    ("workflow_type", "subject_ref"),
    [
        ("uc1_enquiry_qualification", "enq_projection_001"),
        (
            "uc2_legal_services_intake_conflict_check",
            "legal_intake_projection_001",
        ),
        ("uc3_ifa_suitability_intake", "advice_enquiry_projection_001"),
    ],
)
def test_projection_constraints_accept_r4_use_case_identifiers(
    migrated_database_url: str,
    workflow_type: str,
    subject_ref: str,
) -> None:
    workflow_id = f"{workflow_type.replace('_', '-')}-{uuid4().hex[:8]}"
    with psycopg.connect(migrated_database_url) as conn:
        conn.execute("SELECT set_config('app.tenant_id', 'tenant_demo', false)")
        store = ProjectionStore(conn)
        event = _workflow_event(
            tenant_id="tenant_demo",
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            sequence=1,
            event_type="workflow.started",
            subject_ref=subject_ref,
        )
        store.record_workflow_event(event)
        store.apply_workflow_event(event)
        conn.commit()

        read_model = store.get_workflow("tenant_demo", workflow_id)

    assert read_model is not None
    assert read_model.workflow_type == workflow_type
    assert read_model.subject_ref == subject_ref


def test_approval_package_constraints_are_generic_for_connector_writes(
    migrated_database_url: str,
) -> None:
    with psycopg.connect(migrated_database_url) as conn:
        constraints = dict(
            conn.execute(
                """
                SELECT conname, pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid = 'approval_packages'::regclass
                  AND conname IN (
                    'approval_packages_tool_name_check',
                    'approval_packages_requested_action_check'
                  )
                """
            ).fetchall()
        )

    assert "calendar.create_hold" not in constraints["approval_packages_tool_name_check"]
    assert (
        "outbound_comms.message.write"
        not in constraints["approval_packages_requested_action_check"]
    )
    assert (
        "requested_action = ((tool_name || '.'::text) || requested_mode)"
        in constraints["approval_packages_requested_action_check"]
    )


def test_outbox_claim_sent_and_failed_transitions(migrated_database_url: str) -> None:
    workflow_id = "uc1-enq-outbox"
    with psycopg.connect(migrated_database_url) as conn:
        conn.execute("SELECT set_config('app.tenant_id', 'tenant_demo', false)")
        store = ProjectionStore(conn)
        outbox = OutboxStore(conn)
        event = _workflow_event(
            tenant_id="tenant_demo",
            workflow_id=workflow_id,
            sequence=1,
            event_type="workflow.started",
        )
        store.append_outbox_event(event)
        conn.commit()

        claimed = outbox.claim_pending(limit=10)
        target = next(
            (entry for entry in claimed if entry.event.workflow_id == workflow_id),
            None,
        )
        assert target is not None
        for entry in claimed:
            outbox.mark_sent(entry.outbox_id)
        conn.commit()

        again = outbox.claim_pending(limit=10)
        assert all(entry.event.workflow_id != workflow_id for entry in again)


def test_retry_exhaustion_activity_writes_dlq_outbox_and_audit(
    migrated_database_url: str,
) -> None:
    subject_id = uuid4()
    subject_ref = "enq_retry_exhaustion_001"
    workflow_id = "uc1-enq-retry-exhaustion-dlq"
    with psycopg.connect(migrated_database_url) as conn:
        result = record_retry_exhaustion_dlq(
            conn,
            RetryExhaustionDlqCommand(
                tenant_id="tenant_demo",
                correlation_id=f"cor_{workflow_id.replace('-', '_')}",
                workflow_id=workflow_id,
                workflow_type="uc1_enquiry_qualification",
                workflow_actor_id="uc1.workflow",
                subject_id=str(subject_id),
                subject_ref=subject_ref,
                sequence=4,
                failed_step="classification",
                failed_activity="chorus.invoke_agent_runtime",
                failure_reason="forced classifier failure",
                attempts=3,
                subject_summary="Retry exhaustion subject",
            ),
        )
        conn.commit()
        dlq_row = conn.execute(
            """
            SELECT status, workflow_type, subject_ref, payload
            FROM outbox_events
            WHERE event_id = %s
            """,
            (result.event_id,),
        ).fetchone()
        audit_row = conn.execute(
            """
            SELECT action, actor_id, raw_event
            FROM tool_action_audit
            WHERE audit_event_id = %s
            """,
            (result.audit_event_id,),
        ).fetchone()

    assert dlq_row is not None
    assert dlq_row[:3] == ("dlq", "uc1_enquiry_qualification", subject_ref)
    assert dlq_row[3]["subject_summary"] == "Retry exhaustion subject"
    assert dlq_row[3]["dlq_summary"] == "retry exhaustion DLQ marker"
    assert audit_row is not None
    assert audit_row[:2] == ("workflow.retry_exhausted.dlq_recorded", "uc1.workflow")
    assert audit_row[2]["details"]["subject"]["subject_summary"] == "Retry exhaustion subject"


def test_rls_limits_reads_to_current_tenant(migrated_database_url: str) -> None:
    with psycopg.connect(migrated_database_url) as conn:
        conn.execute("SELECT set_config('app.tenant_id', 'tenant_demo', false)")
        store = ProjectionStore(conn)
        store.apply_workflow_event(
            _workflow_event(
                tenant_id="tenant_demo",
                workflow_id="uc1-enq-tenant-demo",
                sequence=1,
            )
        )
        store.apply_workflow_event(
            _workflow_event(
                tenant_id="tenant_demo",
                workflow_id="uc1-enq-tenant-demo",
                sequence=2,
                event_type="workflow.step.completed",
                step="intake",
            )
        )
        conn.commit()

        conn.execute("SELECT set_config('app.tenant_id', 'tenant_demo', false)")
        tenants = conn.execute("SELECT DISTINCT tenant_id FROM workflow_read_models").fetchall()
        target = conn.execute(
            "SELECT workflow_id FROM workflow_read_models WHERE workflow_id = %s",
            ("uc1-enq-tenant-demo",),
        ).fetchone()

    assert tenants == [("tenant_demo",)]
    assert target == ("uc1-enq-tenant-demo",)


def test_provider_catalogue_seed_uc1_model(migrated_database_url: str) -> None:
    with psycopg.connect(migrated_database_url) as conn:
        models = conn.execute(
            "SELECT provider_id, model_id, lifecycle_state FROM provider_catalogue_models "
            "ORDER BY provider_id, model_id"
        ).fetchall()

    assert ("local", "uc1-happy-path-v1", "approved") in models


def test_runtime_policy_snapshot_is_tenant_scoped(migrated_database_url: str) -> None:
    with psycopg.connect(migrated_database_url) as conn:
        conn.execute("SELECT set_config('app.tenant_id', 'tenant_demo', false)")
        snapshot = PolicySnapshotStore(conn).snapshot("tenant_demo")
    assert all(agent.tenant_id == "tenant_demo" for agent in snapshot.agents)
    assert any(grant.tool_name == "outbound_comms.message" for grant in snapshot.tool_grants)
    assert all(
        policy_snapshot.tenant_id == "tenant_demo" for policy_snapshot in snapshot.policy_snapshots
    )


def test_uc1_policy_snapshot_ref_is_materialised(migrated_database_url: str) -> None:
    with psycopg.connect(migrated_database_url) as conn:
        conn.execute("SELECT set_config('app.tenant_id', 'tenant_demo', false)")
        snapshot = PolicySnapshotStore(conn).get_policy_snapshot(
            "tenant_demo",
            "policy_snapshot:uc1:default:v1",
        )

    assert snapshot is not None
    assert snapshot.workflow_type == "uc1_enquiry_qualification"
    assert snapshot.snapshot_version == "v1"
    assert snapshot.lifecycle_state == "active"
    assert snapshot.content_hash.startswith("sha256:")
    assert snapshot.policy_bundle["policy_snapshot_ref"] == "policy_snapshot:uc1:default:v1"
    assert snapshot.policy_bundle["connector_policy_refs"]["routing_policy_ref"] == (
        "policy_uc1_routing_v1"
    )
    assert any(
        route["agent_role"] == "qualifier" and route["task_kind"] == "enquiry_qualification"
        for route in snapshot.policy_bundle["model_routes"]
    )
    assert any(
        grant["tool_name"] == "outbound_comms.message"
        and grant["mode"] == "write"
        and grant["approval_required"] is True
        for grant in snapshot.policy_bundle["tool_grants"]
    )

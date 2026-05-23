from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from chorus.agent_runtime import (
    SUPPORT_AGENT_CONTRACT_REF,
    AgentRuntime,
    AgentRuntimeStore,
    default_model_adapter_registry,
)
from chorus.contracts.generated.projection.workflow_event import WorkflowEvent
from chorus.persistence import OutboxStore, ProjectionStore, apply_migrations
from chorus.tool_gateway.gateway import LocalToolConnector, ToolGateway, ToolGatewayStore
from chorus.workflows.activities import record_retry_exhaustion_dlq
from chorus.workflows.types import (
    AgentInvocationRequest,
    RetryExhaustionDlqCommand,
    ToolGatewayRequest,
)

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


def _support_workflow_event(
    *,
    tenant_id: str,
    workflow_id: str,
    correlation_id: str,
    subject_id: str,
    sequence: int,
    event_type: str,
    step: str | None,
    payload: dict[str, object] | None = None,
) -> WorkflowEvent:
    return WorkflowEvent.model_validate(
        {
            "schema_version": "1.0.0",
            "event_id": str(uuid4()),
            "event_type": event_type,
            "occurred_at": "2026-05-19T12:00:00Z",
            "tenant_id": tenant_id,
            "correlation_id": correlation_id,
            "workflow_id": workflow_id,
            "workflow_type": "support_triage",
            "lead_id": subject_id,
            "subject_ref": "req_support_001",
            "sequence": sequence,
            "step": step,
            "payload": {
                "workflow_type": "support_triage",
                "request_ref": "req_support_001",
                "case_ref": "case_existing_001",
                **(payload or {}),
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
                'model_route_versions',
                'approval_packages',
                'local_ticket_cases',
                'local_ticket_case_update_proposals'
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
    assert ("approval_packages",) in tables
    assert ("local_ticket_cases",) in tables
    assert ("local_ticket_case_update_proposals",) in tables
    assert ("workflow_read_models",) in tables
    assert len(rls_enabled) == 13


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
    assert seed_agents == (12,)


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
        support_routes = conn.execute(
            """
            SELECT agent_role, task_kind, provider, model
            FROM model_routing_policies
            WHERE agent_role LIKE 'support_%'
            ORDER BY agent_role, task_kind
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
    assert support_routes == [
        (
            "support_classifier",
            "support_classification",
            "local",
            "lighthouse-happy-path-v1",
        ),
        (
            "support_context_researcher",
            "support_context_lookup",
            "local",
            "lighthouse-happy-path-v1",
        ),
        (
            "support_resolution_planner",
            "support_resolution_plan",
            "local",
            "lighthouse-happy-path-v1",
        ),
        (
            "support_validator",
            "support_validation",
            "local",
            "lighthouse-happy-path-v1",
        ),
    ]
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
        "ticket.lookup_case",
        "ticket.propose_case_update",
        "ticket.update_status",
    }
    assert {agent.tenant_id for agent in alt_snapshot.agents} == {"tenant_demo_alt"}


def test_local_ticket_desk_seed_is_tenant_scoped(migrated_database_url: str) -> None:
    with psycopg.connect(migrated_database_url, autocommit=True) as conn:
        _set_app_role(conn, "tenant_demo")
        demo_cases = conn.execute(
            """
            SELECT case_ref, account_ref, product_ref, severity_category, status_category
            FROM local_ticket_cases
            ORDER BY case_ref
            """
        ).fetchall()

        conn.execute("RESET ROLE")
        _set_app_role(conn, "tenant_demo_alt")
        alt_cases = conn.execute(
            """
            SELECT case_ref
            FROM local_ticket_cases
            ORDER BY case_ref
            """
        ).fetchall()

    assert demo_cases == [
        (
            "case_duplicate_001",
            "acct_demo_001",
            "prod_core_platform",
            "sev_high",
            "pending_internal",
        ),
        ("case_existing_001", "acct_demo_001", "prod_core_platform", "sev_high", "open"),
    ]
    assert alt_cases == []


def test_support_eval_persisted_evidence_joins_safe_refs(
    migrated_database_url: str,
) -> None:
    tenant_id = "tenant_demo"
    workflow_id = "support-eval-persisted-evidence"
    correlation_id = "cor_support_eval_persisted_evidence"
    subject_id = str(uuid4())
    request_ref = "req_support_001"
    case_ref = "case_existing_001"
    account_ref = "acct_demo_001"
    product_ref = "prod_core_platform"
    policy_ref = "policy_support_triage_local_v1"

    input_refs = {
        "request_ref": request_ref,
        "account_ref": account_ref,
        "product_ref": product_ref,
        "case_ref": case_ref,
        "redacted_summary_ref": "summary_support_001",
    }

    def agent_request(agent_role: str, task_kind: str) -> AgentInvocationRequest:
        return AgentInvocationRequest(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            lead_id=request_ref,
            agent_role=agent_role,
            task_kind=task_kind,
            input={
                "workflow_type": "support_triage",
                "input_refs": input_refs,
                "severity_hint_category": "sev_high",
                "request_status_category": "open",
                "routing_policy_ref": policy_ref,
            },
            expected_output_contract=SUPPORT_AGENT_CONTRACT_REF,
        )

    with psycopg.connect(migrated_database_url) as conn:
        projection = ProjectionStore(conn)
        events = [
            _support_workflow_event(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                subject_id=subject_id,
                sequence=1,
                event_type="workflow.started",
                step="support_intake",
                payload={"account_ref": account_ref, "product_ref": product_ref},
            ),
            _support_workflow_event(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                subject_id=subject_id,
                sequence=2,
                event_type="workflow.step.completed",
                step="support_context_lookup",
                payload={
                    "lookup_verdict": "allow",
                    "duplicate_lookup_verdict": "allow",
                    "duplicate_status": "duplicates_found",
                },
            ),
            _support_workflow_event(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                subject_id=subject_id,
                sequence=3,
                event_type="workflow.step.completed",
                step="support_resolution_plan",
                payload={
                    "resolution_plan_ref": "plan_support_001",
                    "response_draft_ref": "response_support_001",
                    "case_update_ref": "caseupd_support_001",
                    "verdict_category": "propose_case_update",
                },
            ),
            _support_workflow_event(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                subject_id=subject_id,
                sequence=4,
                event_type="workflow.step.completed",
                step="support_propose",
                payload={
                    "gateway_verdict": "propose",
                    "enforced_mode": "propose",
                    "case_update_ref": "caseupd_support_001",
                    "case_status_mutated": False,
                },
            ),
            _support_workflow_event(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                subject_id=subject_id,
                sequence=5,
                event_type="workflow.completed",
                step="support_complete",
                payload={"outcome": "completed"},
            ),
        ]
        for event in events:
            projection.record_workflow_event(event)
            projection.apply_workflow_event(event)

        runtime = AgentRuntime(AgentRuntimeStore(conn), default_model_adapter_registry())
        responses = {
            task_kind: runtime.invoke(agent_request(agent_role, task_kind))
            for agent_role, task_kind in [
                ("support_classifier", "support_classification"),
                ("support_context_researcher", "support_context_lookup"),
                ("support_resolution_planner", "support_resolution_plan"),
                ("support_validator", "support_validation"),
            ]
        }

        plan_refs = responses["support_resolution_plan"].structured_data["output_refs"]
        gateway = ToolGateway(ToolGatewayStore(conn), LocalToolConnector(conn))
        lookup = gateway.invoke(
            ToolGatewayRequest(
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                workflow_id=workflow_id,
                invocation_id=responses["support_context_lookup"].invocation_id,
                agent_id="support.context_researcher",
                tool_name="ticket.lookup_case",
                mode="read",
                idempotency_key=f"{workflow_id}:ticket.lookup_case:{case_ref}",
                arguments={
                    "case_ref": case_ref,
                    "request_ref": request_ref,
                    "account_ref": account_ref,
                    "product_ref": product_ref,
                    "lookup_policy_ref": policy_ref,
                    "include_history_category": "bounded_recent_status_refs",
                },
            )
        )
        duplicates = gateway.invoke(
            ToolGatewayRequest(
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                workflow_id=workflow_id,
                invocation_id=responses["support_context_lookup"].invocation_id,
                agent_id="support.context_researcher",
                tool_name="ticket.lookup_duplicates",
                mode="read",
                idempotency_key=f"{workflow_id}:ticket.lookup_duplicates:{request_ref}",
                arguments={
                    "request_ref": request_ref,
                    "case_ref": case_ref,
                    "account_ref": account_ref,
                    "product_ref": product_ref,
                    "severity_category": "sev_high",
                    "status_categories": ["new", "open", "pending_customer", "pending_internal"],
                    "duplicate_scope_category": "same_account_product_open",
                    "lookup_policy_ref": policy_ref,
                },
            )
        )
        proposal = gateway.invoke(
            ToolGatewayRequest(
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                workflow_id=workflow_id,
                invocation_id=responses["support_resolution_plan"].invocation_id,
                agent_id="support.resolution_planner",
                tool_name="ticket.propose_case_update",
                mode="propose",
                idempotency_key=f"{workflow_id}:ticket.propose_case_update:{request_ref}",
                arguments={
                    "request_ref": request_ref,
                    "case_ref": case_ref,
                    "account_ref": account_ref,
                    "product_ref": product_ref,
                    "severity_category": "sev_high",
                    "target_status_category": "pending_customer",
                    "resolution_plan_ref": plan_refs["resolution_plan_ref"],
                    "response_draft_ref": plan_refs["response_draft_ref"],
                    "case_update_ref": plan_refs["case_update_ref"],
                    "update_reason_category": "resolution_plan_ready",
                    "policy_ref": policy_ref,
                },
            )
        )

        outbox_rows = conn.execute(
            """
            SELECT
                tenant_id,
                correlation_id,
                workflow_id,
                event_type,
                step,
                payload ->> 'workflow_type'
            FROM outbox_events
            WHERE tenant_id = %s AND correlation_id = %s AND workflow_id = %s
            ORDER BY sequence
            """,
            (tenant_id, correlation_id, workflow_id),
        ).fetchall()
        decision_rows = conn.execute(
            """
            SELECT agent_role, provider, model, task_kind, contract_refs
            FROM decision_trail_entries
            WHERE tenant_id = %s AND correlation_id = %s AND workflow_id = %s
            ORDER BY started_at
            """,
            (tenant_id, correlation_id, workflow_id),
        ).fetchall()
        tool_rows = conn.execute(
            """
            SELECT
                tool_name,
                requested_mode,
                enforced_mode,
                verdict,
                raw_event -> 'details' -> 'gateway_response' -> 'output' ->> 'case_update_ref'
            FROM tool_action_audit
            WHERE tenant_id = %s AND correlation_id = %s AND workflow_id = %s
            ORDER BY tool_name
            """,
            (tenant_id, correlation_id, workflow_id),
        ).fetchall()
        proposal_row = conn.execute(
            """
            SELECT
                proposal_status,
                target_status_category,
                metadata ->> 'case_status_mutated'
            FROM local_ticket_case_update_proposals
            WHERE tenant_id = %s AND case_update_ref = %s
            """,
            (tenant_id, "caseupd_support_001"),
        ).fetchone()
        case_status = conn.execute(
            """
            SELECT status_category
            FROM local_ticket_cases
            WHERE tenant_id = %s AND case_ref = %s
            """,
            (tenant_id, case_ref),
        ).fetchone()
        status_write_grant = conn.execute(
            """
            SELECT approval_required
            FROM tool_grants
            WHERE tenant_id = %s
              AND agent_id = 'support.resolution_planner'
              AND tool_name = 'ticket.update_status'
              AND mode = 'write'
            """,
            (tenant_id,),
        ).fetchone()
        inspection_rows = projection.list_support_inspections(
            tenant_id,
            workflow_id=workflow_id,
        )

    assert lookup.verdict == "allow"
    assert duplicates.verdict == "allow"
    assert proposal.verdict == "propose"
    assert proposal.output["case_update_ref"] == "caseupd_support_001"
    assert proposal.output["case_status_mutated"] is False

    assert {row[:3] for row in outbox_rows} == {(tenant_id, correlation_id, workflow_id)}
    assert {row[5] for row in outbox_rows} == {"support_triage"}
    assert {row[0] for row in decision_rows} == {
        "support_classifier",
        "support_context_researcher",
        "support_resolution_planner",
        "support_validator",
    }
    assert {row[1:3] for row in decision_rows} == {("local", "lighthouse-happy-path-v1")}
    assert all(SUPPORT_AGENT_CONTRACT_REF in row[4] for row in decision_rows)
    assert tool_rows == [
        ("ticket.lookup_case", "read", "read", "allow", None),
        ("ticket.lookup_duplicates", "read", "read", "allow", None),
        (
            "ticket.propose_case_update",
            "propose",
            "propose",
            "propose",
            "caseupd_support_001",
        ),
    ]
    assert proposal_row == ("proposed", "pending_customer", "false")
    assert case_status == ("open",)
    assert status_write_grant == (True,)
    assert len(inspection_rows) == 1
    inspection = inspection_rows[0]
    assert inspection.tenant_id == tenant_id
    assert inspection.workflow_id == workflow_id
    assert inspection.correlation_id == correlation_id
    assert inspection.workflow_type == "support_triage"
    assert inspection.request_refs == [request_ref]
    assert inspection.case_refs == [case_ref]
    assert inspection.account_refs == [account_ref]
    assert inspection.product_refs == [product_ref]
    assert inspection.proposed_case_update_refs == ["caseupd_support_001"]
    assert [event.step for event in inspection.workflow_events] == [
        "support_intake",
        "support_context_lookup",
        "support_resolution_plan",
        "support_propose",
        "support_complete",
    ]
    assert {decision.agent_role for decision in inspection.agent_decisions} == {
        "support_classifier",
        "support_context_researcher",
        "support_resolution_planner",
        "support_validator",
    }
    assert {
        (verdict.tool_name, verdict.requested_mode, verdict.enforced_mode, verdict.verdict)
        for verdict in inspection.ticket_verdicts
    } == {
        ("ticket.lookup_case", "read", "read", "allow"),
        ("ticket.lookup_duplicates", "read", "read", "allow"),
        ("ticket.propose_case_update", "propose", "propose", "propose"),
    }
    assert {proposal.case_update_ref for proposal in inspection.proposed_case_updates} == {
        "caseupd_support_001"
    }
    assert all(
        proposal.case_status_mutated is False for proposal in inspection.proposed_case_updates
    )
    assert [
        (boundary.tool_name, boundary.mode, boundary.approval_required)
        for boundary in inspection.status_write_boundary
    ] == [("ticket.update_status", "write", True)]


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

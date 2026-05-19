from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.types.json import Jsonb

from chorus.bff import BffSettings, create_app
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
    workflow_id = f"lighthouse-bff-{uuid4().hex}"
    correlation_id = f"cor_bff_{uuid4().hex}"
    lead_id = uuid4()
    invocation_id = uuid4()
    audit_event_id = uuid4()
    tool_call_id = uuid4()
    verdict_id = uuid4()
    calendar_source_audit_event_id = uuid4()
    calendar_apply_audit_event_id = uuid4()
    calendar_tool_call_id = uuid4()
    calendar_verdict_id = uuid4()
    calendar_apply_tool_call_id = uuid4()
    calendar_apply_verdict_id = uuid4()
    approval_id = uuid4()
    connector_invocation_id = uuid4()
    idempotency_key_ref = f"sha256:{uuid4().hex}{uuid4().hex}"
    apply_idempotency_key_ref = f"sha256:{uuid4().hex}{uuid4().hex}"

    event = WorkflowEvent.model_validate(
        {
            "schema_version": "1.0.0",
            "event_id": str(uuid4()),
            "event_type": "lead.received",
            "occurred_at": "2026-04-29T12:00:00Z",
            "tenant_id": "tenant_demo",
            "correlation_id": correlation_id,
            "workflow_id": workflow_id,
            "lead_id": str(lead_id),
            "sequence": 1,
            "step": "intake",
            "payload": {
                "lead_summary": "BFF projection lead",
                "sender": "buyer@example.com",
                "message_id": "<bff@example.com>",
                "source": "mailpit",
            },
        }
    )

    with psycopg.connect(migrated_database_url) as conn:
        store = ProjectionStore(conn)
        store.apply_workflow_event(event)
        conn.execute(
            """
            INSERT INTO decision_trail_entries (
                tenant_id,
                invocation_id,
                correlation_id,
                workflow_id,
                agent_id,
                agent_role,
                agent_version,
                lifecycle_state,
                prompt_reference,
                prompt_hash,
                provider,
                model,
                task_kind,
                budget_cap_usd,
                input_summary,
                output_summary,
                justification,
                outcome,
                tool_call_ids,
                cost_amount,
                cost_currency,
                duration_ms,
                started_at,
                completed_at,
                contract_refs,
                raw_record,
                metadata
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                "tenant_demo",
                invocation_id,
                correlation_id,
                workflow_id,
                "lighthouse.drafter",
                "drafter",
                "v1",
                "approved",
                "prompts/lighthouse/drafter/v1.md",
                "sha256:" + "d" * 64,
                "local",
                "lighthouse-happy-path-v1",
                "response_draft",
                "0.0100",
                "BFF input",
                "BFF output",
                "BFF test justification",
                "succeeded",
                [],
                "0.000100",
                "USD",
                12,
                datetime(2026, 4, 29, 12, 0, 1, tzinfo=UTC),
                datetime(2026, 4, 29, 12, 0, 2, tzinfo=UTC),
                ["contracts/agents/lighthouse_agent_io.schema.json"],
                Jsonb({"metadata": {"test": True}}),
                Jsonb(
                    {
                        "agent_execution.engine": "langgraph",
                        "agent_execution.graph_version": "lighthouse-agent-runtime-graph-v1",
                        "agent_execution.graph_path": [
                            "prepare_context",
                            "invoke_model_adapter",
                            "normalise_result",
                            "validate_contract",
                            "final_response",
                        ],
                        "agent_execution.graph_path_summary": (
                            "prepare_context -> invoke_model_adapter -> normalise_result -> "
                            "validate_contract -> final_response"
                        ),
                        "model_route.route_id": str(invocation_id),
                        "model_route.route_version": 1,
                        "model_route.fallback_reason": None,
                        "provider_fallback.applied": False,
                    }
                ),
            ),
        )
        conn.execute(
            """
            INSERT INTO tool_action_audit (
                tenant_id,
                audit_event_id,
                correlation_id,
                workflow_id,
                invocation_id,
                tool_call_id,
                verdict_id,
                actor_type,
                actor_id,
                category,
                action,
                tool_name,
                requested_mode,
                enforced_mode,
                verdict,
                idempotency_key,
                arguments_redacted,
                reason,
                occurred_at,
                raw_event
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            """,
            (
                "tenant_demo",
                audit_event_id,
                correlation_id,
                workflow_id,
                invocation_id,
                tool_call_id,
                verdict_id,
                "agent",
                "lighthouse.drafter",
                "tool_gateway",
                "email.propose_response",
                "email.propose_response",
                "propose",
                "propose",
                "propose",
                f"{workflow_id}:email.propose_response",
                Jsonb({"body_text": "[redacted]", "subject": "Re: BFF projection lead"}),
                "Proposal captured by Mailpit",
                datetime(2026, 4, 29, 12, 0, 3, tzinfo=UTC),
                Jsonb({"details": {"gateway_verdict": {"verdict": "propose"}}}),
            ),
        )
        grant_row = conn.execute(
            """
            SELECT grant_id
            FROM tool_grants
            WHERE tenant_id = 'tenant_demo'
              AND agent_id = 'lighthouse.drafter'
              AND tool_name = 'calendar.create_hold'
              AND mode = 'write'
                """
        ).fetchone()
        assert grant_row is not None
        grant_value = grant_row[0]
        assert isinstance(grant_value, UUID)
        grant_id = grant_value
        conn.execute(
            """
            INSERT INTO tool_action_audit (
                tenant_id,
                audit_event_id,
                correlation_id,
                workflow_id,
                invocation_id,
                tool_call_id,
                verdict_id,
                actor_type,
                actor_id,
                category,
                action,
                tool_name,
                requested_mode,
                enforced_mode,
                verdict,
                idempotency_key,
                arguments_redacted,
                reason,
                occurred_at,
                raw_event
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            """,
            (
                "tenant_demo",
                calendar_source_audit_event_id,
                correlation_id,
                workflow_id,
                invocation_id,
                calendar_tool_call_id,
                calendar_verdict_id,
                "agent",
                "lighthouse.drafter",
                "tool_gateway",
                "tool_call.decided",
                "calendar.create_hold",
                "write",
                "write",
                "approval_required",
                f"{workflow_id}:calendar.create_hold:write",
                Jsonb(
                    {
                        "calendar_ref": "cal_lighthouse_local_followup",
                        "hold_ref": "hold_lighthouse_followup_001",
                        "slot_ref": "slot_lighthouse_followup_001",
                        "event_uid_ref": "evt_lighthouse_followup_001",
                        "participant_refs": "[redacted]",
                    }
                ),
                "Grant exists but requires approval before connector execution.",
                datetime(2026, 4, 29, 12, 0, 4, tzinfo=UTC),
                Jsonb(
                    {
                        "details": {
                            "approval_package": {
                                "approval_id": str(approval_id),
                                "approval_state": "requested",
                                "requested_action": "calendar.create_hold.write",
                            }
                        }
                    }
                ),
            ),
        )
        conn.execute(
            """
            INSERT INTO approval_packages (
                tenant_id,
                approval_id,
                approval_package_version,
                approval_state,
                decision,
                reason_category,
                correlation_id,
                workflow_id,
                workflow_type,
                invocation_id,
                tool_call_id,
                verdict_id,
                source_audit_event_id,
                agent_id,
                agent_version,
                requested_action,
                tool_name,
                requested_mode,
                enforced_mode,
                idempotency_key_ref,
                redaction_policy_ref,
                redaction_summary,
                requested_at,
                decision_due_at,
                expires_at,
                sla_policy_ref,
                reviewer_trust_domain,
                decision_at,
                trust_domain,
                grant_id,
                policy_version_refs,
                trace_join,
                metadata
            )
            VALUES (
                %s, %s, 1, 'approved', 'approved', 'tool_write_risk',
                %s, %s, 'lighthouse', %s, %s, %s, %s, 'lighthouse.drafter',
                'v1', 'calendar.create_hold.write', 'calendar.create_hold',
                'write', 'write', %s, %s, %s, %s, %s, %s, %s,
                'local.chorus', %s, 'local.chorus', %s, %s, %s, %s
            )
            """,
            (
                "tenant_demo",
                approval_id,
                correlation_id,
                workflow_id,
                invocation_id,
                calendar_tool_call_id,
                calendar_verdict_id,
                calendar_source_audit_event_id,
                idempotency_key_ref,
                f"tool_grant:{grant_id}:redaction_policy",
                Jsonb({"redacted_field_count": 1, "redacted_field_refs": ["participant_refs"]}),
                datetime(2026, 4, 29, 12, 0, 4, tzinfo=UTC),
                datetime(2026, 4, 29, 16, 0, 4, tzinfo=UTC),
                datetime(2026, 4, 30, 12, 0, 4, tzinfo=UTC),
                "approval_sla.calendar_write.local.v1",
                datetime(2026, 4, 29, 12, 0, 5, tzinfo=UTC),
                grant_id,
                Jsonb(
                    {
                        "tool_grant_ref": f"tool_grant:{grant_id}",
                        "approval_policy_ref": "approval_policy.calendar_write.local.v1",
                    }
                ),
                Jsonb({}),
                Jsonb(
                    {
                        "source": "tool_gateway.approval_required",
                        "scope": "phase_2c_calendar_write",
                        "calendar_refs": {
                            "calendar_ref": "cal_lighthouse_local_followup",
                            "hold_ref": "hold_lighthouse_followup_001",
                            "slot_ref": "slot_lighthouse_followup_001",
                            "event_uid_ref": "evt_lighthouse_followup_001",
                        },
                    }
                ),
            ),
        )
        conn.execute(
            """
            INSERT INTO tool_action_audit (
                tenant_id,
                audit_event_id,
                correlation_id,
                workflow_id,
                invocation_id,
                tool_call_id,
                verdict_id,
                actor_type,
                actor_id,
                category,
                action,
                tool_name,
                requested_mode,
                enforced_mode,
                verdict,
                idempotency_key,
                arguments_redacted,
                reason,
                connector_invocation_id,
                occurred_at,
                raw_event
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                "tenant_demo",
                calendar_apply_audit_event_id,
                correlation_id,
                workflow_id,
                invocation_id,
                calendar_apply_tool_call_id,
                calendar_apply_verdict_id,
                "agent",
                "lighthouse.drafter",
                "tool_gateway",
                "tool_call.decided",
                "calendar.create_hold",
                "write",
                "write",
                "allow",
                f"{workflow_id}:calendar.create_hold:write:approval_apply:{approval_id}",
                Jsonb(
                    {
                        "calendar_ref": "cal_lighthouse_local_followup",
                        "hold_ref": "hold_lighthouse_followup_001",
                        "slot_ref": "slot_lighthouse_followup_001",
                        "event_uid_ref": "evt_lighthouse_followup_001",
                        "participant_refs": "[redacted]",
                    }
                ),
                "Approved local calendar package re-entered the Tool Gateway.",
                connector_invocation_id,
                datetime(2026, 4, 29, 12, 0, 6, tzinfo=UTC),
                Jsonb(
                    {
                        "details": {
                            "approval_apply": {
                                "approval_id": str(approval_id),
                                "approval_state": "approved",
                                "tool_name": "calendar.create_hold",
                                "requested_mode": "write",
                                "enforced_mode": "write",
                                "idempotency_key_ref": idempotency_key_ref,
                                "apply_idempotency_key_ref": apply_idempotency_key_ref,
                                "calendar_refs": {
                                    "calendar_ref": "cal_lighthouse_local_followup",
                                    "hold_ref": "hold_lighthouse_followup_001",
                                    "slot_ref": "slot_lighthouse_followup_001",
                                    "event_uid_ref": "evt_lighthouse_followup_001",
                                },
                            },
                            "gateway_response": {
                                "output": {
                                    "approval_id": str(approval_id),
                                    "calendar_apply_status": "applied",
                                    "calendar_ref": "cal_lighthouse_local_followup",
                                    "hold_ref": "hold_lighthouse_followup_001",
                                    "slot_ref": "slot_lighthouse_followup_001",
                                    "event_uid_ref": "evt_lighthouse_followup_001",
                                    "event_status": "created",
                                }
                            },
                        }
                    }
                ),
            ),
        )

    app = create_app(
        BffSettings(
            database_url=migrated_database_url,
            tenant_id="tenant_demo",
            sse_poll_interval_seconds=0.01,
        )
    )
    client = TestClient(app)
    client.headers.update({"x-test-workflow-id": workflow_id})
    return client


def _workflow_id(client: TestClient) -> str:
    value = client.headers["x-test-workflow-id"]
    assert isinstance(value, str)
    return value


def test_bff_serves_projection_backed_workflow_detail(seeded_bff: TestClient) -> None:
    workflow_id = _workflow_id(seeded_bff)

    response = seeded_bff.get(f"/api/workflows/{workflow_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_id"] == workflow_id
    assert body["lead_subject"] == "BFF projection lead"
    assert body["lead_from"] == "buyer@example.com"


def test_bff_serves_timeline_decisions_tool_verdicts_and_runtime_policy(
    seeded_bff: TestClient,
) -> None:
    workflow_id = _workflow_id(seeded_bff)

    events = seeded_bff.get(f"/api/workflows/{workflow_id}/events").json()
    decisions = seeded_bff.get(f"/api/workflows/{workflow_id}/decision-trail").json()
    verdicts = seeded_bff.get(f"/api/workflows/{workflow_id}/tool-verdicts").json()
    registry = seeded_bff.get("/api/runtime/registry").json()
    grants = seeded_bff.get("/api/runtime/grants").json()
    routing = seeded_bff.get("/api/runtime/routing").json()
    providers = seeded_bff.get("/api/runtime/providers").json()
    provider_models = seeded_bff.get("/api/runtime/provider-models").json()
    route_versions = seeded_bff.get("/api/runtime/route-versions").json()
    graph = seeded_bff.get(f"/api/workflows/{workflow_id}/graph-executions").json()
    calendar_status = seeded_bff.get(f"/api/workflows/{workflow_id}/calendar/status").json()

    assert events[0]["event_type"] == "lead.received"
    assert decisions[0]["prompt_ref"] == "prompts/lighthouse/drafter/v1.md"
    assert decisions[0]["provider"] == "local"
    assert decisions[0]["route_version"] == 1
    assert decisions[0]["fallback_applied"] is False
    assert verdicts[0]["redactions"] == ["body_text"]
    assert {row["agent_id"] for row in registry} >= {"lighthouse.drafter"}
    assert {row["tool_name"] for row in grants} >= {"email.propose_response"}
    assert {row["model"] for row in routing} == {"lighthouse-happy-path-v1"}
    assert {row["provider_id"] for row in providers} == {"commercial.example", "local"}
    assert {row["model_id"] for row in provider_models} == {
        "commercial-reasoner-v1",
        "lighthouse-happy-path-v1",
    }
    assert {row["route_version"] for row in route_versions} == {1}
    assert graph[0]["execution_engine"] == "langgraph"
    assert graph[0]["graph_path_summary"].endswith("final_response")
    assert calendar_status[0]["projection_status"] == "calendar_hold_created"
    assert calendar_status[0]["tool_name"] == "calendar.create_hold"
    assert calendar_status[0]["latest_verdict"] == "allow"
    assert calendar_status[0]["calendar_refs"] == {
        "calendar_ref": "cal_lighthouse_local_followup",
        "hold_ref": "hold_lighthouse_followup_001",
        "slot_ref": "slot_lighthouse_followup_001",
        "event_uid_ref": "evt_lighthouse_followup_001",
    }


def test_bff_progress_sse_streams_projection_events_once(seeded_bff: TestClient) -> None:
    response = seeded_bff.get("/api/progress?once=true")

    assert response.status_code == 200
    assert "event: progress" in response.text
    assert "lead.received" in response.text

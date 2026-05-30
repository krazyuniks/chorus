from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep
from typing import Any, cast
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from chorus.bff import BffSettings, create_app
from chorus.contracts.generated.projection.workflow_event import WorkflowEvent
from chorus.eval import run
from chorus.eval.uc2_workflow_playback import play_uc2_workflow_fixture_async
from chorus.eval.uc3_workflow_playback import play_uc3_workflow_fixture_async
from chorus.persistence import ProjectionStore

TEST_DATABASE_PREFIX = "chorus_bff_test"
ROOT = Path(__file__).resolve().parents[2]
UC2_FIXTURE_DIR = ROOT / "chorus" / "eval" / "fixtures" / "uc2"
UC3_FIXTURE_DIR = ROOT / "chorus" / "eval" / "fixtures" / "uc3"


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
                    "subject_summary": "BFF projection enquiry",
                    "subject_from": "enquiry@example.com",
                    "source_message_id": "<bff-projection@example.test>",
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


@pytest.mark.asyncio
async def test_bff_serves_projected_uc2_workflow_evidence(
    migrated_database_url: str,
) -> None:
    fixture = run.load_fixture(UC2_FIXTURE_DIR / "uc2_synthetic_acceptance_conduct.json")
    playback = await play_uc2_workflow_fixture_async(
        fixture,
        database_url=migrated_database_url,
        playback_ref=f"bff_{uuid4().hex[:8]}",
    )
    workflow_id = playback.workflow_result.workflow_id

    projected_count = _project_outbox_for_workflow_within(
        migrated_database_url,
        tenant_id="tenant_demo",
        workflow_id=workflow_id,
        timeout_seconds=2.0,
    )

    client = TestClient(
        create_app(BffSettings(database_url=migrated_database_url, tenant_id="tenant_demo"))
    )
    workflows = client.get("/api/workflows").json()
    detail = client.get(f"/api/workflows/{workflow_id}").json()
    events = client.get(f"/api/workflows/{workflow_id}/events").json()
    decisions = client.get(f"/api/workflows/{workflow_id}/decision-trail").json()
    verdicts = client.get(f"/api/workflows/{workflow_id}/tool-verdicts").json()
    approval_packages = client.get(f"/api/workflows/{workflow_id}/approval-packages").json()

    assert projected_count >= 1
    assert any(row["workflow_id"] == workflow_id for row in workflows)
    assert detail["workflow_type"] == "uc2_legal_services_intake_conflict_check"
    assert detail["status"] == "completed"
    assert detail["current_step"] == "close"
    assert detail["subject_ref"].startswith("legal_intake_")
    assert detail["subject_summary"] == "Commercial contract review enquiry"

    completed_steps = {
        event["step"] for event in events if event["event_type"] == "workflow.step.completed"
    }
    assert {
        "intake",
        "matter_classification",
        "party_extraction",
        "conflict_check",
        "conflict_determination",
        "kyc_beneficial_ownership",
        "aml_assessment",
        "engagement_decision",
        "engagement_letter_draft",
        "engagement_letter_send",
        "close",
    }.issubset(completed_steps)

    assert [row["task_kind"] for row in decisions] == [
        "uc2_matter_classification",
        "uc2_party_extraction",
        "uc2_conflict_determination",
        "uc2_engagement_decision",
    ]
    assert all(row["provider"] == "local" for row in decisions)
    assert all(row["outcome"] == "succeeded" for row in decisions)

    verdict_by_tool = {row["tool_name"]: row for row in verdicts}
    assert verdict_by_tool["conflict_check.search"]["verdict"] == "allow"
    assert verdict_by_tool["kyc_bo.lookup"]["verdict"] == "allow"
    assert verdict_by_tool["aml_record_store.record_assessment"]["verdict"] == "allow"
    assert verdict_by_tool["engagement_letter.draft"]["verdict"] == "allow"
    assert verdict_by_tool["engagement_letter.send"]["verdict"] == "approval_required"

    assert len(approval_packages) == 1
    package = approval_packages[0]
    assert package["workflow_type"] == "uc2_legal_services_intake_conflict_check"
    assert package["requested_action"] == "engagement_letter.send.write"
    assert package["tool_name"] == "engagement_letter.send"
    assert package["approval_state"] == "requested"
    assert package["latest_verdict"] == "approval_required"
    assert package["subject_refs"]["subject_ref"].startswith("legal_intake_")
    assert package["action_refs"]["engagement_letter_ref"].startswith("engagement_letter_")
    assert package["action_refs"]["conduct_hook_refs"] == [
        "conduct_sra_identify_client_8_1",
        "conduct_mlr_cdd_reg_27_28",
        "conduct_sra_accountability_7_1_7_2",
    ]
    assert "engagement_letter_text" not in package["action_refs"]


@pytest.mark.asyncio
async def test_bff_serves_projected_uc3_workflow_evidence(
    migrated_database_url: str,
) -> None:
    fixture = run.load_fixture(UC3_FIXTURE_DIR / "uc3_synthetic_suitability_conduct.json")
    playback = await play_uc3_workflow_fixture_async(
        fixture,
        database_url=migrated_database_url,
        playback_ref=f"bff_{uuid4().hex[:8]}",
    )
    workflow_id = playback.workflow_result.workflow_id

    projected_count = _project_outbox_for_workflow_within(
        migrated_database_url,
        tenant_id="tenant_demo",
        workflow_id=workflow_id,
        timeout_seconds=2.0,
    )

    client = TestClient(
        create_app(BffSettings(database_url=migrated_database_url, tenant_id="tenant_demo"))
    )
    workflows = client.get("/api/workflows").json()
    detail = client.get(f"/api/workflows/{workflow_id}").json()
    events = client.get(f"/api/workflows/{workflow_id}/events").json()
    decisions = client.get(f"/api/workflows/{workflow_id}/decision-trail").json()
    verdicts = client.get(f"/api/workflows/{workflow_id}/tool-verdicts").json()
    approval_packages = client.get(f"/api/workflows/{workflow_id}/approval-packages").json()

    assert projected_count >= 1
    assert any(row["workflow_id"] == workflow_id for row in workflows)
    assert detail["workflow_type"] == "uc3_ifa_suitability_intake"
    assert detail["status"] == "completed"
    assert detail["current_step"] == "close"
    assert detail["subject_ref"].startswith("advice_enquiry_")
    assert detail["subject_summary"] == "Synthetic pension consolidation enquiry"

    completed_steps = {
        event["step"] for event in events if event["event_type"] == "workflow.step.completed"
    }
    assert {
        "intake",
        "advice_scope_classification",
        "fact_find_summary",
        "attitude_to_risk_profile",
        "risk_profile_assessment",
        "capacity_for_loss_assessment",
        "consumer_duty_support_assessment",
        "platform_research",
        "suitability_conclusion",
        "suitability_report_draft",
        "suitability_report_approval",
        "suitability_report_issue",
        "close",
    }.issubset(completed_steps)

    assert [row["task_kind"] for row in decisions] == [
        "uc3_advice_scope_classification",
        "uc3_fact_find_summary",
        "uc3_risk_profile_assessment",
        "uc3_consumer_duty_support_assessment",
        "uc3_suitability_conclusion",
    ]
    assert all(row["provider"] == "local" for row in decisions)
    assert all(row["outcome"] == "succeeded" for row in decisions)

    verdict_by_tool = {row["tool_name"]: row for row in verdicts}
    assert verdict_by_tool["attitude_to_risk.profile"]["verdict"] == "allow"
    assert verdict_by_tool["capacity_for_loss.assess"]["verdict"] == "allow"
    assert verdict_by_tool["platform_research.run"]["verdict"] == "allow"
    assert verdict_by_tool["suitability_report.draft"]["verdict"] == "allow"
    assert verdict_by_tool["suitability_report.issue"]["verdict"] == "approval_required"

    assert len(approval_packages) == 1
    package = approval_packages[0]
    assert package["workflow_type"] == "uc3_ifa_suitability_intake"
    assert package["requested_action"] == "suitability_report.issue.write"
    assert package["tool_name"] == "suitability_report.issue"
    assert package["approval_state"] == "requested"
    assert package["latest_verdict"] == "approval_required"
    assert package["subject_refs"]["subject_ref"].startswith("advice_enquiry_")
    assert package["action_refs"]["suitability_report_ref"].startswith("suitability_report_")
    assert package["action_refs"]["suitability_conclusion_ref"].startswith(
        "suitability_conclusion_"
    )
    assert package["action_refs"]["conduct_hook_refs"] == [
        "conduct_fca_cobs_9_report",
        "conduct_fca_prin_2a_consumer_understanding",
        "conduct_fca_cobs_9_recordkeeping",
    ]
    assert "raw_suitability_report_text" not in package["action_refs"]
    assert "client_name" not in package["action_refs"]


def _project_outbox_for_workflow_within(
    database_url: str,
    *,
    tenant_id: str,
    workflow_id: str,
    timeout_seconds: float,
) -> int:
    deadline = monotonic() + timeout_seconds
    last_count = 0
    while monotonic() <= deadline:
        last_count = _project_outbox_for_workflow(
            database_url,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
        )
        if _workflow_projection_is_terminal(
            database_url,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
        ):
            return last_count
        sleep(0.05)
    raise AssertionError(
        f"workflow {workflow_id!r} did not project to a terminal BFF read model "
        f"within {timeout_seconds:.1f}s; projected_events={last_count}"
    )


def _project_outbox_for_workflow(
    database_url: str,
    *,
    tenant_id: str,
    workflow_id: str,
) -> int:
    with cast(
        psycopg.Connection[dict[str, Any]],
        psycopg.connect(database_url, row_factory=cast(Any, dict_row)),
    ) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (tenant_id,))
        rows = conn.execute(
            """
            SELECT
                schema_version,
                event_id,
                event_type,
                occurred_at,
                tenant_id,
                correlation_id,
                workflow_id,
                workflow_type,
                subject_id,
                subject_ref,
                sequence,
                step,
                payload
            FROM outbox_events
            WHERE tenant_id = %s
              AND workflow_id = %s
            ORDER BY sequence ASC, occurred_at ASC
            """,
            (tenant_id, workflow_id),
        ).fetchall()
        store = ProjectionStore(conn)
        with conn.transaction():
            for row in rows:
                store.apply_workflow_event(WorkflowEvent.model_validate(row))
    return len(rows)


def _workflow_projection_is_terminal(
    database_url: str,
    *,
    tenant_id: str,
    workflow_id: str,
) -> bool:
    with psycopg.connect(database_url) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (tenant_id,))
        row = ProjectionStore(conn).get_workflow(tenant_id, workflow_id)
    return row is not None and row.status in {"completed", "escalated", "failed"}

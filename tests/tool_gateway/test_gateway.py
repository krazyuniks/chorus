from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg import sql

from chorus.connectors.calendar import CalendarConnectorSettings, RadicaleCalendarConnector
from chorus.connectors.local import ConnectorError, ConnectorResult, ConnectorTransientError
from chorus.contracts.generated.events.audit_event import AuditEvent
from chorus.contracts.generated.tools.calendar_availability_lookup_args import (
    CalendarAvailabilityLookupArgs,
)
from chorus.contracts.generated.tools.calendar_hold_cancellation_args import (
    CalendarHoldCancellationArgs,
)
from chorus.contracts.generated.tools.calendar_hold_creation_args import CalendarHoldCreationArgs
from chorus.contracts.generated.tools.calendar_hold_proposal_args import CalendarHoldProposalArgs
from chorus.contracts.generated.tools.gateway_verdict import GatewayVerdict
from chorus.persistence import apply_migrations
from chorus.tool_gateway import ToolGateway, ToolGatewayStore
from chorus.tool_gateway.gateway import LocalToolConnector
from chorus.workflows.types import ToolGatewayRequest

ADMIN_DATABASE_URL = os.environ.get(
    "CHORUS_TEST_ADMIN_DATABASE_URL",
    "postgresql://chorus:chorus@localhost:5432/postgres",
)


def _database_url(dbname: str) -> str:
    parts = urlsplit(ADMIN_DATABASE_URL)
    return urlunsplit((parts.scheme, parts.netloc, f"/{dbname}", parts.query, parts.fragment))


@pytest.fixture(scope="module")
def migrated_database_url() -> Iterator[str]:
    dbname = f"chorus_tool_gateway_test_{uuid4().hex}"

    try:
        with psycopg.connect(ADMIN_DATABASE_URL, autocommit=True, connect_timeout=2) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres is not available for tool gateway tests: {exc}")

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


class RecordingConnector:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        tenant_id: str,
        correlation_id: str,
        workflow_id: str,
        arguments: dict[str, object],
    ) -> ConnectorResult:
        self.calls.append(
            {
                "tool_name": tool_name,
                "mode": mode,
                "tenant_id": tenant_id,
                "correlation_id": correlation_id,
                "workflow_id": workflow_id,
                "arguments": arguments,
            }
        )
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={"connector": "recording", "tool_name": tool_name, "mode": mode},
        )


class TransientFailingConnector:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        tenant_id: str,
        correlation_id: str,
        workflow_id: str,
        arguments: dict[str, object],
    ) -> ConnectorResult:
        self.calls += 1
        raise ConnectorTransientError("fixture transient connector failure")


class CountingConnector:
    def __init__(self, delegate: LocalToolConnector) -> None:
        self._delegate = delegate
        self.calls: list[dict[str, object]] = []

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        tenant_id: str,
        correlation_id: str,
        workflow_id: str,
        arguments: dict[str, object],
    ) -> ConnectorResult:
        self.calls.append(
            {
                "tool_name": tool_name,
                "mode": mode,
                "tenant_id": tenant_id,
                "correlation_id": correlation_id,
                "workflow_id": workflow_id,
                "arguments": arguments,
            }
        )
        return self._delegate.invoke(
            tool_name=tool_name,
            mode=mode,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            arguments=arguments,
        )


class RejectingCalendarConnector:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        tenant_id: str,
        correlation_id: str,
        workflow_id: str,
        arguments: dict[str, object],
    ) -> ConnectorResult:
        self.calls += 1
        if tool_name == "calendar.cancel_hold":
            raise ConnectorError("caldav_rejected")
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={"connector": "rejecting-calendar", "tool_name": tool_name, "mode": mode},
        )


def _request(
    *,
    tenant_id: str = "tenant_demo",
    agent_id: str = "lighthouse.drafter",
    tool_name: str = "email.propose_response",
    mode: str = "propose",
    idempotency_key: str | None = None,
) -> ToolGatewayRequest:
    workflow_id = f"lighthouse-gateway-{uuid4().hex}"
    return ToolGatewayRequest(
        tenant_id=tenant_id,
        correlation_id=f"cor_tool_gateway_{uuid4().hex}",
        workflow_id=workflow_id,
        invocation_id=str(uuid4()),
        agent_id=agent_id,
        tool_name=tool_name,
        mode=mode,
        idempotency_key=idempotency_key or f"{workflow_id}:{tool_name}:{mode}",
        arguments={
            "to": "lead@example.com",
            "subject": "Re: Need help",
            "body_text": "A governed Lighthouse proposal draft.",
        },
    )


def _crm_create_request(*, mode: str) -> ToolGatewayRequest:
    workflow_id = f"lighthouse-gateway-{uuid4().hex}"
    return ToolGatewayRequest(
        tenant_id="tenant_demo",
        correlation_id=f"cor_tool_gateway_{uuid4().hex}",
        workflow_id=workflow_id,
        invocation_id=str(uuid4()),
        agent_id="lighthouse.drafter",
        tool_name="crm.create_lead",
        mode=mode,
        idempotency_key=f"{workflow_id}:crm.create_lead:{mode}",
        arguments={
            "company_name": "Acme Field Services",
            "contact_email": "lead@example.com",
            "lead_summary": "Qualified lead ready for CRM proposal.",
        },
    )


def _calendar_availability_request() -> ToolGatewayRequest:
    workflow_id = f"lighthouse-gateway-{uuid4().hex}"
    return ToolGatewayRequest(
        tenant_id="tenant_demo",
        correlation_id=f"cor_tool_gateway_{uuid4().hex}",
        workflow_id=workflow_id,
        invocation_id=str(uuid4()),
        agent_id="lighthouse.drafter",
        tool_name="calendar.lookup_availability",
        mode="read",
        idempotency_key=f"{workflow_id}:calendar.lookup_availability:read",
        arguments={
            "calendar_ref": "cal_lighthouse_local_followup",
            "window_start": "2026-05-18T10:00:00Z",
            "window_end": "2026-05-18T12:00:00Z",
            "duration_minutes": 30,
            "timezone": "UTC",
            "availability_policy_ref": "policy_lighthouse_followup_default",
            "required_slot_count": 2,
        },
    )


def _calendar_proposal_request() -> ToolGatewayRequest:
    workflow_id = f"lighthouse-gateway-{uuid4().hex}"
    return ToolGatewayRequest(
        tenant_id="tenant_demo",
        correlation_id=f"cor_tool_gateway_{uuid4().hex}",
        workflow_id=workflow_id,
        invocation_id=str(uuid4()),
        agent_id="lighthouse.drafter",
        tool_name="calendar.propose_hold",
        mode="propose",
        idempotency_key=f"{workflow_id}:calendar.propose_hold:propose",
        arguments={
            "calendar_ref": "cal_lighthouse_local_followup",
            "hold_ref": "hold_lighthouse_followup_001",
            "slot_ref": "slot_lighthouse_followup_001",
            "meeting_type": "lighthouse_follow_up",
            "participant_refs": ["participant_lighthouse_requester"],
            "summary_category": "lead_follow_up",
            "proposal_note_ref": "note_lighthouse_followup_default",
        },
    )


def _calendar_create_request() -> ToolGatewayRequest:
    workflow_id = f"lighthouse-gateway-{uuid4().hex}"
    return ToolGatewayRequest(
        tenant_id="tenant_demo",
        correlation_id=f"cor_tool_gateway_{uuid4().hex}",
        workflow_id=workflow_id,
        invocation_id=str(uuid4()),
        agent_id="lighthouse.drafter",
        tool_name="calendar.create_hold",
        mode="write",
        idempotency_key=f"{workflow_id}:calendar.create_hold:write",
        arguments={
            "calendar_ref": "cal_lighthouse_local_followup",
            "hold_ref": "hold_lighthouse_followup_001",
            "slot_ref": "slot_lighthouse_followup_001",
            "event_uid_ref": "evt_lighthouse_followup_001",
            "starts_at": "2026-05-18T10:00:00Z",
            "ends_at": "2026-05-18T10:30:00Z",
            "meeting_type": "lighthouse_follow_up",
            "participant_refs": ["participant_lighthouse_requester"],
            "summary_category": "lead_follow_up",
            "busy_status": "tentative",
            "visibility": "busy_only",
        },
    )


def _calendar_cancel_request() -> ToolGatewayRequest:
    workflow_id = f"lighthouse-gateway-{uuid4().hex}"
    return ToolGatewayRequest(
        tenant_id="tenant_demo",
        correlation_id=f"cor_tool_gateway_{uuid4().hex}",
        workflow_id=workflow_id,
        invocation_id=str(uuid4()),
        agent_id="lighthouse.drafter",
        tool_name="calendar.cancel_hold",
        mode="write",
        idempotency_key=f"{workflow_id}:calendar.cancel_hold:write",
        arguments={
            "calendar_ref": "cal_lighthouse_local_followup",
            "hold_ref": "hold_lighthouse_followup_001",
            "event_uid_ref": "evt_lighthouse_followup_001",
            "cancellation_reason_category": "workflow_compensation",
            "compensation_ref": "comp_lighthouse_followup_001",
        },
    )


def _ticket_case_lookup_request() -> ToolGatewayRequest:
    workflow_id = f"support-triage-gateway-{uuid4().hex}"
    return ToolGatewayRequest(
        tenant_id="tenant_demo",
        correlation_id=f"cor_tool_gateway_{uuid4().hex}",
        workflow_id=workflow_id,
        invocation_id=str(uuid4()),
        agent_id="support.context_researcher",
        tool_name="ticket.lookup_case",
        mode="read",
        idempotency_key=f"{workflow_id}:ticket.lookup_case:read",
        arguments={
            "case_ref": "case_existing_001",
            "request_ref": "req_support_001",
            "account_ref": "acct_demo_001",
            "product_ref": "prod_core_platform",
            "lookup_policy_ref": "policy_ticket_lookup_read",
            "include_history_category": "bounded_recent_status_refs",
        },
    )


def _ticket_duplicate_lookup_request() -> ToolGatewayRequest:
    workflow_id = f"support-triage-gateway-{uuid4().hex}"
    return ToolGatewayRequest(
        tenant_id="tenant_demo",
        correlation_id=f"cor_tool_gateway_{uuid4().hex}",
        workflow_id=workflow_id,
        invocation_id=str(uuid4()),
        agent_id="support.context_researcher",
        tool_name="ticket.lookup_duplicates",
        mode="read",
        idempotency_key=f"{workflow_id}:ticket.lookup_duplicates:read",
        arguments={
            "request_ref": "req_support_001",
            "account_ref": "acct_demo_001",
            "product_ref": "prod_core_platform",
            "case_ref": "case_existing_001",
            "severity_category": "sev_high",
            "status_categories": ["new", "open", "pending_internal"],
            "duplicate_scope_category": "same_account_product_open",
            "lookup_policy_ref": "policy_ticket_duplicate_read",
        },
    )


def _ticket_case_update_proposal_request() -> ToolGatewayRequest:
    workflow_id = f"support-triage-gateway-{uuid4().hex}"
    return ToolGatewayRequest(
        tenant_id="tenant_demo",
        correlation_id=f"cor_tool_gateway_{uuid4().hex}",
        workflow_id=workflow_id,
        invocation_id=str(uuid4()),
        agent_id="support.resolution_planner",
        tool_name="ticket.propose_case_update",
        mode="propose",
        idempotency_key=f"{workflow_id}:ticket.propose_case_update:propose",
        arguments={
            "request_ref": "req_support_001",
            "case_ref": "case_existing_001",
            "account_ref": "acct_demo_001",
            "product_ref": "prod_core_platform",
            "severity_category": "sev_high",
            "target_status_category": "pending_internal",
            "resolution_plan_ref": "plan_support_001",
            "response_draft_ref": "response_support_001",
            "case_update_ref": "caseupd_support_001",
            "update_reason_category": "resolution_plan_ready",
            "policy_ref": "policy_ticket_update_propose",
        },
    )


def _ticket_status_update_request() -> ToolGatewayRequest:
    workflow_id = f"support-triage-gateway-{uuid4().hex}"
    return ToolGatewayRequest(
        tenant_id="tenant_demo",
        correlation_id=f"cor_tool_gateway_{uuid4().hex}",
        workflow_id=workflow_id,
        invocation_id=str(uuid4()),
        agent_id="support.resolution_planner",
        tool_name="ticket.update_status",
        mode="write",
        idempotency_key=f"{workflow_id}:ticket.update_status:write",
        arguments={
            "request_ref": "req_support_001",
            "case_ref": "case_existing_001",
            "account_ref": "acct_demo_001",
            "product_ref": "prod_core_platform",
            "prior_status_category": "open",
            "target_status_category": "pending_internal",
            "case_update_ref": "caseupd_support_001",
            "idempotency_ref": "idem_ticket_status_001",
            "approval_policy_ref": "policy_ticket_write_approval",
            "update_reason_category": "resolution_plan_ready",
        },
    )


def _approve_package(
    conn: psycopg.Connection[object],
    *,
    tenant_id: str,
    approval_id: str,
    expired: bool = False,
) -> None:
    if expired:
        conn.execute(
            """
            UPDATE approval_packages
            SET approval_state = 'approved',
                decision = 'approved',
                decision_due_at = now() - interval '2 minutes',
                expires_at = now() - interval '1 minute',
                decision_at = now() - interval '2 minutes',
                updated_at = now()
            WHERE tenant_id = %s AND approval_id = %s
            """,
            (tenant_id, approval_id),
        )
        return

    conn.execute(
        """
        UPDATE approval_packages
        SET approval_state = 'approved',
            decision = 'approved',
            decision_at = now(),
            updated_at = now()
        WHERE tenant_id = %s AND approval_id = %s
        """,
        (tenant_id, approval_id),
    )


@pytest.fixture()
def radicale_base_url(tmp_path: Path) -> Iterator[str]:
    pytest.importorskip("radicale")
    port = _free_port()
    storage_path = tmp_path / "collections"
    rights_path = tmp_path / "rights"
    rights_path.write_text(
        "[anonymous-local-sandbox]\nuser: ^$\ncollection: .*\npermissions: RrWw\n"
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "radicale",
            "--server-hosts",
            f"127.0.0.1:{port}",
            "--auth-type",
            "none",
            "--rights-type",
            "from_file",
            "--rights-file",
            str(rights_path),
            "--storage-filesystem-folder",
            str(storage_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_radicale(base_url, process)
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_proposal_grant_invokes_connector_and_persists_redacted_audit(
    migrated_database_url: str,
) -> None:
    connector = RecordingConnector()
    request = _request()

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), connector).invoke(request)

        row = conn.execute(
            """
            SELECT verdict, enforced_mode, arguments_redacted, raw_event
            FROM tool_action_audit
            WHERE tenant_id = %s AND audit_event_id = %s
            """,
            (request.tenant_id, response.audit_event_id),
        ).fetchone()

    assert response.verdict == "propose"
    assert response.enforced_mode == "propose"
    assert response.output == {
        "connector": "recording",
        "tool_name": "email.propose_response",
        "mode": "propose",
    }
    assert len(connector.calls) == 1
    assert row is not None
    assert row[0:2] == ("propose", "propose")
    assert row[2]["body_text"] == "[redacted]"

    audit_event = AuditEvent.model_validate(row[3])
    verdict = GatewayVerdict.model_validate(audit_event.details["gateway_verdict"])
    assert audit_event.actor.id == "lighthouse.drafter"
    assert verdict.verdict.value == "propose"


def test_transient_connector_failure_is_audited_without_idempotent_response(
    migrated_database_url: str,
) -> None:
    connector = TransientFailingConnector()
    request = _request(idempotency_key=f"transient-failure-{uuid4().hex}")

    with psycopg.connect(migrated_database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), connector)

        with pytest.raises(ConnectorTransientError):
            gateway.invoke(request)

        row = conn.execute(
            """
            SELECT verdict, reason, arguments_redacted, raw_event
            FROM tool_action_audit
            WHERE tenant_id = %s AND idempotency_key = %s
            """,
            (request.tenant_id, request.idempotency_key),
        ).fetchone()

        with pytest.raises(ConnectorTransientError):
            gateway.invoke(request)

    assert connector.calls == 2
    assert row is not None
    assert row[0] == "block"
    assert "transient" in row[1]
    assert row[2]["body_text"] == "[redacted]"

    audit_event = AuditEvent.model_validate(row[3])
    verdict = GatewayVerdict.model_validate(audit_event.details["gateway_verdict"])
    assert audit_event.category.value == "connector"
    assert audit_event.details["connector_failure"]["classification"] == "transient"
    assert "gateway_response" not in audit_event.details
    assert verdict.verdict.value == "block"


def test_idempotency_returns_persisted_response_without_second_connector_call(
    migrated_database_url: str,
) -> None:
    connector = RecordingConnector()
    request = _request(idempotency_key=f"idempotency-{uuid4().hex}")

    with psycopg.connect(migrated_database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), connector)
        first = gateway.invoke(request)
        second = gateway.invoke(request)

    assert first == second
    assert len(connector.calls) == 1


def test_write_request_downgrades_to_proposal_when_only_propose_grant_exists(
    migrated_database_url: str,
) -> None:
    connector = RecordingConnector()
    request = _request(tool_name="email.send_response", mode="write")

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), connector).invoke(request)

    assert response.verdict == "propose"
    assert response.enforced_mode == "propose"
    assert "downgraded" in response.reason
    assert connector.calls[0]["mode"] == "propose"


def test_missing_grant_blocks_without_connector_call(migrated_database_url: str) -> None:
    connector = RecordingConnector()
    request = _request(agent_id="lighthouse.validator")

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), connector).invoke(request)

        row = conn.execute(
            """
            SELECT verdict, reason
            FROM tool_action_audit
            WHERE tenant_id = %s AND audit_event_id = %s
            """,
            (request.tenant_id, response.audit_event_id),
        ).fetchone()

    assert response.verdict == "block"
    assert response.connector_invocation_id is None
    assert connector.calls == []
    assert row is not None
    assert row[0] == "block"
    assert "No allowed Tool Gateway grant" in row[1]


def test_seeded_denied_write_grant_blocks_before_downgrade(
    migrated_database_url: str,
) -> None:
    connector = RecordingConnector()
    request = _request(
        tenant_id="tenant_demo_alt",
        tool_name="email.send_response",
        mode="write",
    )

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), connector).invoke(request)

        row = conn.execute(
            """
            SELECT verdict, enforced_mode, reason, arguments_redacted, raw_event
            FROM tool_action_audit
            WHERE tenant_id = %s AND audit_event_id = %s
            """,
            (request.tenant_id, response.audit_event_id),
        ).fetchone()

    assert response.verdict == "block"
    assert response.enforced_mode == "write"
    assert response.connector_invocation_id is None
    assert connector.calls == []
    assert row is not None
    assert row[0:2] == ("block", "write")
    assert "explicit" in row[2].lower()
    assert row[3]["body_text"] == "[redacted]"

    audit_event = AuditEvent.model_validate(row[4])
    verdict = GatewayVerdict.model_validate(audit_event.details["gateway_verdict"])
    assert audit_event.actor.id == "lighthouse.drafter"
    assert verdict.verdict.value == "block"
    assert verdict.enforced_mode.value == "write"


def test_approval_required_grant_does_not_invoke_connector(migrated_database_url: str) -> None:
    connector = RecordingConnector()
    request = _crm_create_request(mode="write")

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), connector).invoke(request)
        approval_count = conn.execute("SELECT count(*) FROM approval_packages").fetchone()

    assert response.verdict == "approval_required"
    assert response.enforced_mode == "write"
    assert response.connector_invocation_id is None
    assert connector.calls == []
    assert approval_count == (0,)


def test_calendar_availability_dispatches_to_local_caldav_connector(
    migrated_database_url: str,
    radicale_base_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHORUS_CALDAV_BASE_URL", radicale_base_url)
    request = _calendar_availability_request()

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), LocalToolConnector(conn)).invoke(request)

    assert response.verdict == "allow"
    assert response.enforced_mode == "read"
    assert response.output["connector"] == "radicale.caldav.local"
    assert response.output["calendar_ref"] == "cal_lighthouse_local_followup"
    assert response.output["availability_status"] == "slots_available"
    assert response.output["slot_count"] == 2


def test_calendar_hold_proposal_dispatches_without_creating_event(
    migrated_database_url: str,
    radicale_base_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHORUS_CALDAV_BASE_URL", radicale_base_url)
    request = _calendar_proposal_request()

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), LocalToolConnector(conn)).invoke(request)

    assert response.verdict == "propose"
    assert response.enforced_mode == "propose"
    assert response.output == {
        "connector": "radicale.caldav.local",
        "calendar_ref": "cal_lighthouse_local_followup",
        "hold_ref": "hold_lighthouse_followup_001",
        "slot_ref": "slot_lighthouse_followup_001",
        "proposal_status": "proposed",
        "event_created": False,
        "meeting_type": "lighthouse_follow_up",
        "summary_category": "lead_follow_up",
        "participant_ref_count": 1,
    }


def test_ticket_case_lookup_dispatches_to_local_ticket_connector(
    migrated_database_url: str,
) -> None:
    request = _ticket_case_lookup_request()

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), LocalToolConnector(conn)).invoke(request)

    assert response.verdict == "allow"
    assert response.enforced_mode == "read"
    assert response.output["connector"] == "local_ticket_desk.postgres"
    assert response.output["lookup_status"] == "case_found"
    assert response.output["case"]["case_ref"] == "case_existing_001"
    assert response.output["case"]["account_ref"] == "acct_demo_001"
    assert response.output["case"]["product_ref"] == "prod_core_platform"
    assert response.output["case"]["severity_category"] == "sev_high"
    assert response.output["case"]["status_category"] == "open"
    assert response.output["case"]["recent_status_refs"] == [
        "status_open_001",
        "status_triaged_001",
    ]


def test_ticket_duplicate_lookup_dispatches_with_safe_refs_only(
    migrated_database_url: str,
) -> None:
    request = _ticket_duplicate_lookup_request()

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), LocalToolConnector(conn)).invoke(request)

    assert response.verdict == "allow"
    assert response.enforced_mode == "read"
    assert response.output["connector"] == "local_ticket_desk.postgres"
    assert response.output["duplicate_status"] == "duplicates_found"
    assert response.output["duplicate_case_refs"] == ["case_duplicate_001"]
    assert response.output["duplicate_count"] == 1


def test_ticket_case_update_proposal_persists_without_mutating_case_status(
    migrated_database_url: str,
) -> None:
    request = _ticket_case_update_proposal_request()

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), LocalToolConnector(conn)).invoke(request)
        case_status = conn.execute(
            """
            SELECT status_category
            FROM local_ticket_cases
            WHERE tenant_id = %s AND case_ref = %s
            """,
            (request.tenant_id, request.arguments["case_ref"]),
        ).fetchone()
        proposal = conn.execute(
            """
            SELECT case_update_ref, proposal_status, target_status_category, metadata
            FROM local_ticket_case_update_proposals
            WHERE tenant_id = %s AND case_update_ref = %s
            """,
            (request.tenant_id, request.arguments["case_update_ref"]),
        ).fetchone()

    assert response.verdict == "propose"
    assert response.enforced_mode == "propose"
    assert response.output["connector"] == "local_ticket_desk.postgres"
    assert response.output["proposal_status"] == "proposed"
    assert response.output["case_status_mutated"] is False
    assert response.output["case_update_ref"] == "caseupd_support_001"
    assert response.output["target_status_category"] == "pending_internal"
    assert case_status == ("open",)
    assert proposal is not None
    assert proposal[0:3] == ("caseupd_support_001", "proposed", "pending_internal")
    assert proposal[3]["case_status_mutated"] is False


def test_ticket_status_update_requires_approval_before_connector_execution(
    migrated_database_url: str,
) -> None:
    connector = RecordingConnector()
    request = _ticket_status_update_request()

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), connector).invoke(request)

    assert response.verdict == "approval_required"
    assert response.enforced_mode == "write"
    assert response.connector_invocation_id is None
    assert response.output == {}
    assert connector.calls == []


def test_ticket_argument_validation_blocks_before_connector_execution(
    migrated_database_url: str,
) -> None:
    connector = RecordingConnector()
    request = replace(
        _ticket_case_lookup_request(),
        arguments={
            "request_ref": "req_support_001",
            "account_ref": "acct_demo_001",
            "lookup_policy_ref": "policy_ticket_lookup_read",
        },
    )

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), connector).invoke(request)

    assert response.verdict == "block"
    assert response.connector_invocation_id is None
    assert "schema validation failed" in response.reason
    assert connector.calls == []


def test_calendar_write_grant_requires_approval_before_connector_execution(
    migrated_database_url: str,
) -> None:
    connector = RecordingConnector()
    request = _calendar_create_request()

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), connector).invoke(request)
        package = conn.execute(
            """
            SELECT
                approval_id,
                approval_state,
                decision,
                reason_category,
                correlation_id,
                workflow_id,
                invocation_id::text,
                tool_call_id::text,
                verdict_id::text,
                source_audit_event_id::text,
                agent_id,
                agent_version,
                requested_action,
                tool_name,
                requested_mode,
                enforced_mode,
                idempotency_key_ref,
                redaction_summary,
                sla_policy_ref,
                reviewer_actor_subject_ref,
                reviewer_role,
                grant_id::text,
                policy_version_refs,
                trace_join,
                metadata
            FROM approval_packages
            WHERE tenant_id = %s AND workflow_id = %s
            """,
            (request.tenant_id, request.workflow_id),
        ).fetchone()
        audit = conn.execute(
            """
            SELECT raw_event->'details'->'approval_package'
            FROM tool_action_audit
            WHERE tenant_id = %s AND audit_event_id = %s
            """,
            (request.tenant_id, response.audit_event_id),
        ).fetchone()

    assert response.verdict == "approval_required"
    assert response.enforced_mode == "write"
    assert response.connector_invocation_id is None
    assert response.output["approval_state"] == "requested"
    assert response.output["requested_action"] == "calendar.create_hold.write"
    assert connector.calls == []
    assert package is not None
    assert str(package[0]) == response.output["approval_id"]
    assert package[1:16] == (
        "requested",
        None,
        "tool_write_risk",
        request.correlation_id,
        request.workflow_id,
        request.invocation_id,
        response.tool_call_id,
        response.verdict_id,
        response.audit_event_id,
        "lighthouse.drafter",
        "v1",
        "calendar.create_hold.write",
        "calendar.create_hold",
        "write",
        "write",
    )
    assert package[16].startswith("sha256:")
    assert package[17] == {
        "redaction_policy_ref": f"tool_grant:{package[21]}:redaction_policy",
        "redacted_field_count": 1,
        "redacted_field_refs": ["participant_refs"],
    }
    assert package[18] == "approval_sla.calendar_write.local.v1"
    assert package[19:21] == (None, None)
    assert package[22]["tool_grant_ref"] == f"tool_grant:{package[21]}"
    assert package[22]["approval_policy_ref"] == "approval_policy.calendar_write.local.v1"
    assert package[23] == {}
    assert package[24] == {
        "source": "tool_gateway.approval_required",
        "scope": "phase_2c_calendar_write",
        "calendar_refs": {
            "calendar_ref": "cal_lighthouse_local_followup",
            "hold_ref": "hold_lighthouse_followup_001",
            "slot_ref": "slot_lighthouse_followup_001",
            "event_uid_ref": "evt_lighthouse_followup_001",
        },
    }
    assert audit is not None
    assert audit[0]["approval_id"] == response.output["approval_id"]
    assert audit[0]["idempotency_key_ref"] == package[16]


def test_calendar_approval_package_is_idempotent_for_replayed_request(
    migrated_database_url: str,
) -> None:
    connector = RecordingConnector()
    request = _calendar_create_request()

    with psycopg.connect(migrated_database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), connector)
        first = gateway.invoke(request)
        second = gateway.invoke(request)
        package_count = conn.execute(
            """
            SELECT count(*)
            FROM approval_packages
            WHERE tenant_id = %s AND workflow_id = %s
            """,
            (request.tenant_id, request.workflow_id),
        ).fetchone()

    assert first == second
    assert first.verdict == "approval_required"
    assert first.output["approval_id"] == second.output["approval_id"]
    assert package_count == (1,)
    assert connector.calls == []


def test_calendar_cancel_write_creates_requested_approval_package(
    migrated_database_url: str,
) -> None:
    connector = RecordingConnector()
    request = _calendar_cancel_request()

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), connector).invoke(request)
        package = conn.execute(
            """
            SELECT requested_action, tool_name, approval_state, redaction_summary
            FROM approval_packages
            WHERE tenant_id = %s AND workflow_id = %s
            """,
            (request.tenant_id, request.workflow_id),
        ).fetchone()

    assert response.verdict == "approval_required"
    assert response.enforced_mode == "write"
    assert response.connector_invocation_id is None
    assert response.output["requested_action"] == "calendar.cancel_hold.write"
    assert connector.calls == []
    redaction_policy_ref = "tool_grant:12000000-0000-4000-8000-000000000012:redaction_policy"
    assert package == (
        "calendar.cancel_hold.write",
        "calendar.cancel_hold",
        "requested",
        {
            "redaction_policy_ref": redaction_policy_ref,
            "redacted_field_count": 0,
            "redacted_field_refs": [],
        },
    )


def test_approved_calendar_create_apply_creates_one_event_through_gateway(
    migrated_database_url: str,
    radicale_base_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHORUS_CALDAV_BASE_URL", radicale_base_url)
    request = _calendar_create_request()

    with psycopg.connect(migrated_database_url) as conn:
        approval_response = ToolGateway(ToolGatewayStore(conn), RecordingConnector()).invoke(
            request
        )
        _approve_package(
            conn,
            tenant_id=request.tenant_id,
            approval_id=approval_response.output["approval_id"],
        )
        connector = CountingConnector(LocalToolConnector(conn))
        gateway = ToolGateway(ToolGatewayStore(conn), connector)

        first = gateway.apply_approved_calendar_write(
            request,
            approval_id=approval_response.output["approval_id"],
        )
        second = gateway.apply_approved_calendar_write(
            request,
            approval_id=approval_response.output["approval_id"],
        )
        audit = conn.execute(
            """
            SELECT raw_event->'details'->'approval_apply'
            FROM tool_action_audit
            WHERE tenant_id = %s
              AND audit_event_id = %s
            """,
            (request.tenant_id, first.audit_event_id),
        ).fetchone()

    availability = RadicaleCalendarConnector(
        CalendarConnectorSettings(base_url=radicale_base_url, timeout_seconds=5)
    ).lookup_availability(
        CalendarAvailabilityLookupArgs.model_validate(
            {
                "calendar_ref": "cal_lighthouse_local_followup",
                "window_start": "2026-05-18T10:00:00Z",
                "window_end": "2026-05-18T11:00:00Z",
                "duration_minutes": 30,
                "timezone": "UTC",
                "availability_policy_ref": "policy_lighthouse_followup_default",
                "required_slot_count": 1,
            }
        )
    )

    assert first == second
    assert first.verdict == "allow"
    assert first.connector_invocation_id is not None
    assert first.output["event_status"] == "created"
    assert first.output["calendar_apply_status"] == "applied"
    assert first.output["approval_id"] == approval_response.output["approval_id"]
    assert len(connector.calls) == 1
    assert connector.calls[0]["tool_name"] == "calendar.create_hold"
    assert availability.output["slots"][0]["starts_at"] == "2026-05-18T10:30:00+00:00"
    assert audit is not None
    assert audit[0]["approval_id"] == approval_response.output["approval_id"]
    assert audit[0]["calendar_refs"] == {
        "calendar_ref": "cal_lighthouse_local_followup",
        "hold_ref": "hold_lighthouse_followup_001",
        "slot_ref": "slot_lighthouse_followup_001",
        "event_uid_ref": "evt_lighthouse_followup_001",
    }


def test_approved_calendar_apply_rechecks_expiry_before_connector_execution(
    migrated_database_url: str,
) -> None:
    connector = RecordingConnector()
    request = _calendar_create_request()

    with psycopg.connect(migrated_database_url) as conn:
        approval_response = ToolGateway(ToolGatewayStore(conn), connector).invoke(request)
        _approve_package(
            conn,
            tenant_id=request.tenant_id,
            approval_id=approval_response.output["approval_id"],
            expired=True,
        )
        response = ToolGateway(ToolGatewayStore(conn), connector).apply_approved_calendar_write(
            request,
            approval_id=approval_response.output["approval_id"],
        )

    assert response.verdict == "block"
    assert response.connector_invocation_id is None
    assert response.output["failure_category"] == "approval_expired"
    assert connector.calls == []


def test_approved_calendar_apply_transient_failure_is_retry_classified(
    migrated_database_url: str,
) -> None:
    connector = TransientFailingConnector()
    request = _calendar_create_request()

    with psycopg.connect(migrated_database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), connector)
        approval_response = gateway.invoke(request)
        _approve_package(
            conn,
            tenant_id=request.tenant_id,
            approval_id=approval_response.output["approval_id"],
        )

        with pytest.raises(ConnectorTransientError):
            gateway.apply_approved_calendar_write(
                request,
                approval_id=approval_response.output["approval_id"],
            )
        with pytest.raises(ConnectorTransientError):
            gateway.apply_approved_calendar_write(
                request,
                approval_id=approval_response.output["approval_id"],
            )
        failures = conn.execute(
            """
            SELECT raw_event
            FROM tool_action_audit
            WHERE tenant_id = %s
              AND tool_name = 'calendar.create_hold'
              AND category = 'connector'
            ORDER BY occurred_at
            """,
            (request.tenant_id,),
        ).fetchall()

    assert connector.calls == 2
    assert len(failures) == 2
    first_failure = AuditEvent.model_validate(failures[0][0])
    assert "gateway_response" not in first_failure.details
    assert first_failure.details["connector_failure"] == {
        "classification": "transient",
        "failure_category": "transient_connector_error",
        "retryable_by": "temporal_activity_retry_policy",
    }
    assert first_failure.details["approval_apply"]["approval_state"] == "approved"


def test_approved_calendar_cancel_compensates_through_gateway(
    migrated_database_url: str,
    radicale_base_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHORUS_CALDAV_BASE_URL", radicale_base_url)
    create_request = _calendar_create_request()
    cancel_request = replace(
        _calendar_cancel_request(),
        correlation_id=create_request.correlation_id,
        workflow_id=create_request.workflow_id,
        invocation_id=create_request.invocation_id,
    )

    with psycopg.connect(migrated_database_url) as conn:
        connector = CountingConnector(LocalToolConnector(conn))
        gateway = ToolGateway(ToolGatewayStore(conn), connector)
        create_approval = gateway.invoke(create_request)
        _approve_package(
            conn,
            tenant_id=create_request.tenant_id,
            approval_id=create_approval.output["approval_id"],
        )
        gateway.apply_approved_calendar_write(
            create_request,
            approval_id=create_approval.output["approval_id"],
        )

        cancel_approval = gateway.invoke(cancel_request)
        _approve_package(
            conn,
            tenant_id=cancel_request.tenant_id,
            approval_id=cancel_approval.output["approval_id"],
        )
        cancelled = gateway.apply_approved_calendar_write(
            cancel_request,
            approval_id=cancel_approval.output["approval_id"],
        )

    assert cancelled.verdict == "allow"
    assert cancelled.output["cancellation_status"] == "cancelled"
    assert cancelled.output["compensation_category"] == "compensation_completed"
    assert [call["tool_name"] for call in connector.calls] == [
        "calendar.create_hold",
        "calendar.cancel_hold",
    ]


def test_calendar_compensation_failure_blocks_with_escalation_category(
    migrated_database_url: str,
) -> None:
    connector = RejectingCalendarConnector()
    request = _calendar_cancel_request()

    with psycopg.connect(migrated_database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), connector)
        approval_response = gateway.invoke(request)
        _approve_package(
            conn,
            tenant_id=request.tenant_id,
            approval_id=approval_response.output["approval_id"],
        )
        response = gateway.apply_approved_calendar_write(
            request,
            approval_id=approval_response.output["approval_id"],
        )
        audit = conn.execute(
            """
            SELECT raw_event->'details'
            FROM tool_action_audit
            WHERE tenant_id = %s
              AND audit_event_id = %s
            """,
            (request.tenant_id, response.audit_event_id),
        ).fetchone()

    assert response.verdict == "block"
    assert response.output["compensation_category"] == "compensation_failed"
    assert response.output["escalation_category"] == "calendar_compensation_failed"
    assert connector.calls == 1
    assert audit is not None
    assert audit[0]["connector_failure"]["classification"] == "non_retryable"
    assert audit[0]["connector_failure"]["failure_category"] == "caldav_rejected"
    assert audit[0]["connector_failure"]["compensation_category"] == "compensation_failed"
    assert audit[0]["connector_failure"]["escalation_category"] == "calendar_compensation_failed"


def test_radicale_calendar_connector_round_trips_safe_event_refs(
    radicale_base_url: str,
) -> None:
    connector = RadicaleCalendarConnector(
        CalendarConnectorSettings(base_url=radicale_base_url, timeout_seconds=5)
    )

    created = connector.create_hold(
        CalendarHoldCreationArgs.model_validate(
            {
                "calendar_ref": "cal_lighthouse_local_followup",
                "hold_ref": "hold_lighthouse_followup_001",
                "slot_ref": "slot_lighthouse_followup_001",
                "event_uid_ref": "evt_lighthouse_followup_001",
                "starts_at": "2026-05-18T10:00:00Z",
                "ends_at": "2026-05-18T10:30:00Z",
                "meeting_type": "lighthouse_follow_up",
                "participant_refs": ["participant_lighthouse_requester"],
                "summary_category": "lead_follow_up",
                "busy_status": "tentative",
                "visibility": "busy_only",
            }
        )
    )
    availability = connector.lookup_availability(
        CalendarAvailabilityLookupArgs.model_validate(
            {
                "calendar_ref": "cal_lighthouse_local_followup",
                "window_start": "2026-05-18T10:00:00Z",
                "window_end": "2026-05-18T11:00:00Z",
                "duration_minutes": 30,
                "timezone": "UTC",
                "availability_policy_ref": "policy_lighthouse_followup_default",
                "required_slot_count": 1,
            }
        )
    )
    proposed = connector.propose_hold(
        CalendarHoldProposalArgs.model_validate(
            {
                "calendar_ref": "cal_lighthouse_local_followup",
                "hold_ref": "hold_lighthouse_followup_002",
                "slot_ref": availability.output["slots"][0]["slot_ref"],
                "meeting_type": "lighthouse_follow_up",
                "participant_refs": ["participant_lighthouse_requester"],
                "summary_category": "lead_follow_up",
            }
        )
    )
    cancelled = connector.cancel_hold(
        CalendarHoldCancellationArgs.model_validate(
            {
                "calendar_ref": "cal_lighthouse_local_followup",
                "hold_ref": "hold_lighthouse_followup_001",
                "event_uid_ref": "evt_lighthouse_followup_001",
                "cancellation_reason_category": "workflow_compensation",
                "compensation_ref": "comp_lighthouse_followup_001",
            }
        )
    )

    assert created.output["event_status"] == "created"
    assert availability.output["slots"][0]["starts_at"] == "2026-05-18T10:30:00+00:00"
    assert proposed.output["event_created"] is False
    assert cancelled.output["cancellation_status"] == "cancelled"


def test_radicale_calendar_connector_duplicate_uid_requires_matching_context(
    radicale_base_url: str,
) -> None:
    connector = RadicaleCalendarConnector(
        CalendarConnectorSettings(base_url=radicale_base_url, timeout_seconds=5)
    )
    arguments = {
        "calendar_ref": "cal_lighthouse_local_followup",
        "hold_ref": "hold_lighthouse_followup_001",
        "slot_ref": "slot_lighthouse_followup_001",
        "event_uid_ref": "evt_lighthouse_followup_001",
        "starts_at": "2026-05-18T10:00:00Z",
        "ends_at": "2026-05-18T10:30:00Z",
        "meeting_type": "lighthouse_follow_up",
        "participant_refs": ["participant_lighthouse_requester"],
        "summary_category": "lead_follow_up",
        "busy_status": "tentative",
        "visibility": "busy_only",
    }

    created = connector.create_hold(CalendarHoldCreationArgs.model_validate(arguments))
    duplicate = connector.create_hold(CalendarHoldCreationArgs.model_validate(arguments))
    mismatch = {**arguments, "slot_ref": "slot_lighthouse_followup_999"}

    assert created.output["event_status"] == "created"
    assert duplicate.output["event_status"] == "already_exists"
    assert duplicate.output["idempotency_category"] == ("duplicate_event_uid_ref_matching_context")
    with pytest.raises(ConnectorError, match="caldav_duplicate_uid_context_mismatch"):
        connector.create_hold(CalendarHoldCreationArgs.model_validate(mismatch))


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_radicale(base_url: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 10
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.skip("Radicale subprocess exited before accepting connections")
        try:
            response = httpx.get(base_url, timeout=1)
            if response.status_code < 500:
                return
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(0.1)
    pytest.skip(f"Radicale did not become ready for connector tests: {last_error}")

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator, Sequence
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg import sql
from pydantic import BaseModel

from chorus.connectors import (
    ConnectorAdapter,
    ConnectorContext,
    ConnectorError,
    ConnectorRegistry,
    ConnectorResult,
    ConnectorTransientError,
    ToolSpec,
    default_registry,
)
from chorus.connectors.calendar import CalendarConnectorSettings, RadicaleCalendarConnector
from chorus.connectors.local import (
    CrmCreateLeadArguments,
)
from chorus.contracts.generated.audit.audit_event import AuditEvent
from chorus.contracts.generated.connector.calendar_availability_lookup_args import (
    CalendarAvailabilityLookupArgs,
)
from chorus.contracts.generated.connector.calendar_hold_cancellation_args import (
    CalendarHoldCancellationArgs,
)
from chorus.contracts.generated.connector.calendar_hold_creation_args import (
    CalendarHoldCreationArgs,
)
from chorus.contracts.generated.connector.calendar_hold_proposal_args import (
    CalendarHoldProposalArgs,
)
from chorus.contracts.generated.connector.email_message_args import EmailMessageArgs
from chorus.contracts.generated.connector.gateway_verdict import GatewayVerdict
from chorus.persistence import apply_migrations
from chorus.tool_gateway import ToolGateway, ToolGatewayStore
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


class _RecordingAdapter:
    """Connector adapter that records calls and returns a canned output."""

    adapter_id = "test_recording"

    def __init__(self, specs: Sequence[ToolSpec]) -> None:
        self._specs = tuple(specs)
        self.calls: list[dict[str, object]] = []

    def tool_specs(self) -> Sequence[ToolSpec]:
        return self._specs

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        context: ConnectorContext,
        arguments: BaseModel,
    ) -> ConnectorResult:
        self.calls.append(
            {
                "tool_name": tool_name,
                "mode": mode,
                "tenant_id": context.tenant_id,
                "correlation_id": context.correlation_id,
                "workflow_id": context.workflow_id,
                "arguments": arguments.model_dump(mode="json"),
            }
        )
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={"connector": "recording", "tool_name": tool_name, "mode": mode},
        )


class _TransientFailingAdapter:
    """Adapter that always raises a transient failure for the registered tools."""

    adapter_id = "test_transient_failing"

    def __init__(self, specs: Sequence[ToolSpec]) -> None:
        self._specs = tuple(specs)
        self.calls = 0

    def tool_specs(self) -> Sequence[ToolSpec]:
        return self._specs

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        context: ConnectorContext,
        arguments: BaseModel,
    ) -> ConnectorResult:
        del tool_name, mode, context, arguments
        self.calls += 1
        raise ConnectorTransientError("fixture transient connector failure")


class _RejectingCalendarAdapter:
    """Calendar adapter that rejects only `calendar.cancel_hold`."""

    adapter_id = "test_rejecting_calendar"

    def __init__(self) -> None:
        self.calls = 0

    def tool_specs(self) -> Sequence[ToolSpec]:
        return (
            ToolSpec(
                tool_name="calendar.create_hold",
                argument_contract=CalendarHoldCreationArgs,
                return_contract_ref="test.calendar.create_hold",
            ),
            ToolSpec(
                tool_name="calendar.cancel_hold",
                argument_contract=CalendarHoldCancellationArgs,
                return_contract_ref="test.calendar.cancel_hold",
            ),
        )

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        context: ConnectorContext,
        arguments: BaseModel,
    ) -> ConnectorResult:
        del context, arguments
        self.calls += 1
        if tool_name == "calendar.cancel_hold":
            raise ConnectorError("caldav_rejected")
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={"connector": "rejecting-calendar", "tool_name": tool_name, "mode": mode},
        )


class _CountingRegistry(ConnectorRegistry):
    """Test registry that counts every adapter.invoke routed through it."""

    def __init__(self, inner: ConnectorRegistry) -> None:
        super().__init__()
        self._inner = inner
        self.calls: list[dict[str, object]] = []

    def resolve(self, tool_name: str) -> tuple[ConnectorAdapter, ToolSpec]:
        adapter, spec = self._inner.resolve(tool_name)
        return _CountingAdapter(adapter, self.calls), spec


class _CountingAdapter:
    def __init__(self, inner: ConnectorAdapter, calls: list[dict[str, object]]) -> None:
        self._inner = inner
        self._calls = calls

    @property
    def adapter_id(self) -> str:
        return self._inner.adapter_id

    def tool_specs(self) -> Sequence[ToolSpec]:
        return self._inner.tool_specs()

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        context: ConnectorContext,
        arguments: BaseModel,
    ) -> ConnectorResult:
        self._calls.append(
            {
                "tool_name": tool_name,
                "mode": mode,
                "tenant_id": context.tenant_id,
                "correlation_id": context.correlation_id,
                "workflow_id": context.workflow_id,
                "arguments": arguments.model_dump(mode="json"),
            }
        )
        return self._inner.invoke(
            tool_name=tool_name, mode=mode, context=context, arguments=arguments
        )


def _email_recording_registry() -> tuple[ConnectorRegistry, _RecordingAdapter]:
    adapter = _RecordingAdapter(
        (
            ToolSpec(
                tool_name="email.propose_response",
                argument_contract=EmailMessageArgs,
                return_contract_ref="test.email.propose_response",
            ),
            ToolSpec(
                tool_name="email.send_response",
                argument_contract=EmailMessageArgs,
                return_contract_ref="test.email.send_response",
            ),
        )
    )
    registry = ConnectorRegistry()
    registry.register(adapter)
    return registry, adapter


def _crm_recording_registry() -> tuple[ConnectorRegistry, _RecordingAdapter]:
    adapter = _RecordingAdapter(
        (
            ToolSpec(
                tool_name="crm.create_lead",
                argument_contract=CrmCreateLeadArguments,
                return_contract_ref="test.crm.create_lead",
            ),
        )
    )
    registry = ConnectorRegistry()
    registry.register(adapter)
    return registry, adapter


def _calendar_recording_registry() -> tuple[ConnectorRegistry, _RecordingAdapter]:
    adapter = _RecordingAdapter(
        (
            ToolSpec(
                tool_name="calendar.create_hold",
                argument_contract=CalendarHoldCreationArgs,
                return_contract_ref="test.calendar.create_hold",
            ),
            ToolSpec(
                tool_name="calendar.cancel_hold",
                argument_contract=CalendarHoldCancellationArgs,
                return_contract_ref="test.calendar.cancel_hold",
            ),
        )
    )
    registry = ConnectorRegistry()
    registry.register(adapter)
    return registry, adapter


def _calendar_transient_registry() -> tuple[ConnectorRegistry, _TransientFailingAdapter]:
    adapter = _TransientFailingAdapter(
        (
            ToolSpec(
                tool_name="calendar.create_hold",
                argument_contract=CalendarHoldCreationArgs,
                return_contract_ref="test.calendar.create_hold",
            ),
        )
    )
    registry = ConnectorRegistry()
    registry.register(adapter)
    return registry, adapter


def _email_transient_registry() -> tuple[ConnectorRegistry, _TransientFailingAdapter]:
    adapter = _TransientFailingAdapter(
        (
            ToolSpec(
                tool_name="email.propose_response",
                argument_contract=EmailMessageArgs,
                return_contract_ref="test.email.propose_response",
            ),
        )
    )
    registry = ConnectorRegistry()
    registry.register(adapter)
    return registry, adapter


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
    registry, recording = _email_recording_registry()
    request = _request()

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), registry).invoke(request)

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
    assert len(recording.calls) == 1
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
    registry, transient = _email_transient_registry()
    request = _request(idempotency_key=f"transient-failure-{uuid4().hex}")

    with psycopg.connect(migrated_database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), registry)

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

    assert transient.calls == 2
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
    registry, recording = _email_recording_registry()
    request = _request(idempotency_key=f"idempotency-{uuid4().hex}")

    with psycopg.connect(migrated_database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), registry)
        first = gateway.invoke(request)
        second = gateway.invoke(request)

    assert first == second
    assert len(recording.calls) == 1


def test_write_request_downgrades_to_proposal_when_only_propose_grant_exists(
    migrated_database_url: str,
) -> None:
    registry, recording = _email_recording_registry()
    request = _request(tool_name="email.send_response", mode="write")

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), registry).invoke(request)

    assert response.verdict == "propose"
    assert response.enforced_mode == "propose"
    assert "downgraded" in response.reason
    assert recording.calls[0]["mode"] == "propose"


def test_missing_grant_blocks_without_connector_call(migrated_database_url: str) -> None:
    registry, recording = _email_recording_registry()
    request = _request(agent_id="lighthouse.validator")

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), registry).invoke(request)

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
    assert recording.calls == []
    assert row is not None
    assert row[0] == "block"
    assert "No allowed Tool Gateway grant" in row[1]


def test_seeded_denied_write_grant_blocks_before_downgrade(
    migrated_database_url: str,
) -> None:
    registry, recording = _email_recording_registry()
    request = _request(
        tenant_id="tenant_demo_alt",
        tool_name="email.send_response",
        mode="write",
    )

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), registry).invoke(request)

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
    assert recording.calls == []
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
    registry, recording = _crm_recording_registry()
    request = _crm_create_request(mode="write")

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), registry).invoke(request)
        approval_count = conn.execute("SELECT count(*) FROM approval_packages").fetchone()

    assert response.verdict == "approval_required"
    assert response.enforced_mode == "write"
    assert response.connector_invocation_id is None
    assert recording.calls == []
    assert approval_count == (0,)


def test_calendar_availability_dispatches_to_local_caldav_connector(
    migrated_database_url: str,
    radicale_base_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHORUS_CALDAV_BASE_URL", radicale_base_url)
    request = _calendar_availability_request()

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), default_registry(conn)).invoke(request)

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
        response = ToolGateway(ToolGatewayStore(conn), default_registry(conn)).invoke(request)

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


def test_calendar_write_grant_requires_approval_before_connector_execution(
    migrated_database_url: str,
) -> None:
    registry, recording = _calendar_recording_registry()
    request = _calendar_create_request()

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), registry).invoke(request)
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
    assert recording.calls == []
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
    registry, recording = _calendar_recording_registry()
    request = _calendar_create_request()

    with psycopg.connect(migrated_database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), registry)
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
    assert recording.calls == []


def test_calendar_cancel_write_creates_requested_approval_package(
    migrated_database_url: str,
) -> None:
    registry, recording = _calendar_recording_registry()
    request = _calendar_cancel_request()

    with psycopg.connect(migrated_database_url) as conn:
        response = ToolGateway(ToolGatewayStore(conn), registry).invoke(request)
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
    assert recording.calls == []
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
        approval_registry, _approval_recording = _calendar_recording_registry()
        approval_response = ToolGateway(ToolGatewayStore(conn), approval_registry).invoke(request)
        _approve_package(
            conn,
            tenant_id=request.tenant_id,
            approval_id=approval_response.output["approval_id"],
        )
        counting = _CountingRegistry(default_registry(conn))
        gateway = ToolGateway(ToolGatewayStore(conn), counting)

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
    assert len(counting.calls) == 1
    assert counting.calls[0]["tool_name"] == "calendar.create_hold"
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
    registry, recording = _calendar_recording_registry()
    request = _calendar_create_request()

    with psycopg.connect(migrated_database_url) as conn:
        approval_response = ToolGateway(ToolGatewayStore(conn), registry).invoke(request)
        _approve_package(
            conn,
            tenant_id=request.tenant_id,
            approval_id=approval_response.output["approval_id"],
            expired=True,
        )
        response = ToolGateway(ToolGatewayStore(conn), registry).apply_approved_calendar_write(
            request,
            approval_id=approval_response.output["approval_id"],
        )

    assert response.verdict == "block"
    assert response.connector_invocation_id is None
    assert response.output["failure_category"] == "approval_expired"
    assert recording.calls == []


def test_approved_calendar_apply_transient_failure_is_retry_classified(
    migrated_database_url: str,
) -> None:
    registry, transient = _calendar_transient_registry()
    request = _calendar_create_request()

    with psycopg.connect(migrated_database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), registry)
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

    assert transient.calls == 2
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
        counting = _CountingRegistry(default_registry(conn))
        gateway = ToolGateway(ToolGatewayStore(conn), counting)
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
    assert [call["tool_name"] for call in counting.calls] == [
        "calendar.create_hold",
        "calendar.cancel_hold",
    ]


def test_calendar_compensation_failure_blocks_with_escalation_category(
    migrated_database_url: str,
) -> None:
    rejecting = _RejectingCalendarAdapter()
    registry = ConnectorRegistry()
    registry.register(rejecting)
    request = _calendar_cancel_request()

    with psycopg.connect(migrated_database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), registry)
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
    assert rejecting.calls == 1
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

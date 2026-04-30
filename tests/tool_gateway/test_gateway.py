from __future__ import annotations

import os
from collections.abc import Iterator
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from chorus.connectors.local import ConnectorResult, ConnectorTransientError
from chorus.contracts.generated.events.audit_event import AuditEvent
from chorus.contracts.generated.tools.gateway_verdict import GatewayVerdict
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

    assert response.verdict == "approval_required"
    assert response.enforced_mode == "write"
    assert response.connector_invocation_id is None
    assert connector.calls == []

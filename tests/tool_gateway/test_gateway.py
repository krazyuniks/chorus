from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from pydantic import BaseModel

from chorus.connectors import (
    ConnectorAdapter,
    ConnectorContext,
    ConnectorRegistry,
    ConnectorResult,
    ConnectorTransientError,
    ToolSpec,
)
from chorus.contracts.generated.connector.uc1.outbound_comms_message_args import (
    OutboundCommsMessageArgs,
)
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
    """Connector adapter that records every dispatched call."""

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
            output={"recorded": True, "mode": mode, "tool_name": tool_name},
        )


class _TransientFailingAdapter:
    """Connector adapter that raises a transient failure."""

    adapter_id = "test_transient"

    def __init__(self, specs: Sequence[ToolSpec]) -> None:
        self._specs = tuple(specs)

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
        raise ConnectorTransientError("test_transient_failure")


def _outbound_comms_spec() -> ToolSpec:
    return ToolSpec(
        tool_name="outbound_comms.message",
        argument_contract=OutboundCommsMessageArgs,
        return_contract_ref="contracts/connector/uc1/outbound_comms_message_args.schema.json",
    )


def _outbound_arguments() -> dict[str, object]:
    return {
        "enquiry_ref": "enq_motor_private_001",
        "customer_ref": "cust_demo_001",
        "missing_data_request_ref": "mdr_demo_001",
        "to_email": "customer@example.com",
        "subject": "Information needed",
        "body_text": "Please confirm postcode and licence date.",
        "comms_policy_ref": "policy_uc1_outbound_comms_local_v1",
    }


def _build_request(
    *,
    mode: str = "propose",
    tool_name: str = "outbound_comms.message",
    arguments: dict[str, object] | None = None,
) -> ToolGatewayRequest:
    workflow_id = f"uc1-enq-gateway-{uuid4().hex}"
    return ToolGatewayRequest(
        tenant_id="tenant_demo",
        correlation_id=f"cor_{workflow_id.replace('-', '_')}",
        workflow_id=workflow_id,
        invocation_id=str(uuid4()),
        agent_id="uc1.request_drafter",
        tool_name=tool_name,
        mode=mode,
        idempotency_key=f"{workflow_id}:{tool_name}:{mode}",
        arguments=arguments or _outbound_arguments(),
    )


def _build_registry(adapter: ConnectorAdapter) -> ConnectorRegistry:
    registry = ConnectorRegistry()
    registry.register(adapter)
    return registry


def test_propose_grant_invokes_adapter_and_persists_audit(
    migrated_database_url: str,
) -> None:
    request = _build_request()
    adapter = _RecordingAdapter([_outbound_comms_spec()])
    registry = _build_registry(adapter)

    with psycopg.connect(migrated_database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), registry)
        response = gateway.invoke(request)
        conn.commit()

        verdicts = conn.execute(
            "SELECT verdict, enforced_mode FROM tool_action_audit WHERE workflow_id = %s",
            (request.workflow_id,),
        ).fetchall()

    assert response.verdict == "propose"
    assert response.enforced_mode == "propose"
    assert adapter.calls and adapter.calls[0]["mode"] == "propose"
    assert verdicts == [("propose", "propose")]


def test_approval_required_grant_blocks_until_approval(
    migrated_database_url: str,
) -> None:
    request = _build_request(mode="write")
    adapter = _RecordingAdapter([_outbound_comms_spec()])
    registry = _build_registry(adapter)

    with psycopg.connect(migrated_database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), registry)
        response = gateway.invoke(request)
        conn.commit()

    assert response.verdict == "approval_required"
    assert adapter.calls == []


def test_missing_grant_blocks_without_connector_call(
    migrated_database_url: str,
) -> None:
    adapter = _RecordingAdapter([_outbound_comms_spec()])
    registry = _build_registry(adapter)
    request = _build_request()
    request = ToolGatewayRequest(
        tenant_id=request.tenant_id,
        correlation_id=request.correlation_id,
        workflow_id=request.workflow_id,
        invocation_id=request.invocation_id,
        agent_id="uc1.unknown_agent",
        tool_name=request.tool_name,
        mode=request.mode,
        idempotency_key=request.idempotency_key,
        arguments=request.arguments,
    )

    with psycopg.connect(migrated_database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), registry)
        response = gateway.invoke(request)
        conn.commit()

    assert response.verdict == "block"
    assert adapter.calls == []


def test_transient_connector_failure_is_audited(
    migrated_database_url: str,
) -> None:
    request = _build_request()
    adapter = _TransientFailingAdapter([_outbound_comms_spec()])
    registry = _build_registry(adapter)

    with psycopg.connect(migrated_database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), registry)
        with pytest.raises(ConnectorTransientError):
            gateway.invoke(request)

        audit = conn.execute(
            "SELECT action FROM tool_action_audit WHERE workflow_id = %s",
            (request.workflow_id,),
        ).fetchone()

    assert audit == ("connector.transient_failure",)


def test_idempotent_response_is_replayed_without_second_connector_call(
    migrated_database_url: str,
) -> None:
    request = _build_request()
    adapter = _RecordingAdapter([_outbound_comms_spec()])
    registry = _build_registry(adapter)

    with psycopg.connect(migrated_database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), registry)
        first = gateway.invoke(request)
        conn.commit()
        second = gateway.invoke(request)
        conn.commit()

    assert first.verdict_id == second.verdict_id
    assert len(adapter.calls) == 1

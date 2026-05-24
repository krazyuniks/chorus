from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from dataclasses import replace
from typing import Any, cast
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

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
    default_registry,
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
    subject_id = uuid4()
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
        workflow_type="uc1_enquiry_qualification",
        subject_id=str(subject_id),
        subject_ref=f"enq_gateway_{subject_id.hex[:12]}",
        subject_summary="Motor cover gateway request",
    )


def _build_uc1_routing_request(
    *,
    tool_name: str,
    arguments: dict[str, object],
) -> ToolGatewayRequest:
    workflow_id = f"uc1-enq-routing-{uuid4().hex}"
    verdict_ref = arguments["verdict_ref"]
    return ToolGatewayRequest(
        tenant_id="tenant_demo",
        correlation_id=f"cor_{workflow_id.replace('-', '_')}",
        workflow_id=workflow_id,
        invocation_id=str(uuid4()),
        agent_id="uc1.qualifier",
        tool_name=tool_name,
        mode="write",
        idempotency_key=str(verdict_ref),
        arguments=arguments,
        workflow_type="uc1_enquiry_qualification",
        subject_id=str(uuid4()),
        subject_ref=f"enq_gateway_{uuid4().hex[:12]}",
        subject_summary="UC1 routing connector request",
    )


def _build_registry(adapter: ConnectorAdapter) -> ConnectorRegistry:
    registry = ConnectorRegistry()
    registry.register(adapter)
    return registry


class _ApprovalGrant:
    grant_id: UUID
    tenant_id: str
    agent_id: str
    agent_version: str
    tool_name: str
    mode: str
    allowed: bool
    approval_required: bool
    redaction_policy: dict[str, Any]

    def __init__(self) -> None:
        self.grant_id = uuid4()
        self.tenant_id = "tenant_demo"
        self.agent_id = "uc1.request_drafter"
        self.agent_version = "v1"
        self.tool_name = "outbound_comms.message"
        self.mode = "write"
        self.allowed = True
        self.approval_required = True
        self.redaction_policy = {"redact_fields": ["body_text"]}


class _InMemoryApprovalRecord:
    approval_id: UUID
    approval_state: str
    decision: str | None
    tenant_id: str
    correlation_id: str
    workflow_id: str
    workflow_type: str
    invocation_id: UUID
    agent_id: str
    agent_version: str
    requested_action: str
    tool_name: str
    requested_mode: str
    enforced_mode: str
    idempotency_key_ref: str
    expires_at: Any
    grant_id: UUID
    policy_version_refs: dict[str, Any]
    trace_join: dict[str, Any]
    metadata: dict[str, Any]

    def __init__(self, package: Any) -> None:
        self.approval_id = package.approval_id
        self.approval_state = "requested"
        self.decision = None
        self.tenant_id = package.tenant_id
        self.correlation_id = package.correlation_id
        self.workflow_id = package.workflow_id
        self.workflow_type = package.workflow_type
        self.invocation_id = UUID(package.invocation_id)
        self.agent_id = package.agent_id
        self.agent_version = package.agent_version
        self.requested_action = package.requested_action
        self.tool_name = package.tool_name
        self.requested_mode = package.requested_mode
        self.enforced_mode = package.enforced_mode
        self.idempotency_key_ref = package.idempotency_key_ref
        self.expires_at = package.expires_at
        self.grant_id = package.grant_id
        self.policy_version_refs = cast(dict[str, Any], package.policy_version_refs)
        self.trace_join = cast(dict[str, Any], package.trace_join)
        self.metadata = cast(dict[str, Any], package.metadata)

    def approve(self) -> None:
        self.approval_state = "approved"
        self.decision = "approved"

    def apply_summary(self, *, apply_idempotency_key: str) -> dict[str, Any]:
        return {
            "approval_id": str(self.approval_id),
            "approval_state": self.approval_state,
            "decision": self.decision,
            "requested_action": self.requested_action,
            "tool_name": self.tool_name,
            "apply_idempotency_key_ref": apply_idempotency_key,
            "subject_refs": self.metadata.get("subject_refs", {}),
            "action_refs": self.metadata.get("action_refs", {}),
        }


class _InMemoryGatewayStore:
    def __init__(self) -> None:
        self.grant = _ApprovalGrant()
        self.approval_package: Any | None = None
        self.approval_record: _InMemoryApprovalRecord | None = None
        self.audit_events: list[Any] = []

    def fetch_idempotent_response(self, **_: Any) -> None:
        return None

    def fetch_grant(self, **kwargs: Any) -> _ApprovalGrant | None:
        if (
            kwargs.get("tenant_id") == self.grant.tenant_id
            and kwargs.get("agent_id") == self.grant.agent_id
            and kwargs.get("tool_name") == self.grant.tool_name
            and kwargs.get("mode") == self.grant.mode
        ):
            return self.grant
        return None

    def fetch_denied_grant(self, **_: Any) -> None:
        return None

    def fetch_approval_package(
        self,
        *,
        tenant_id: str,
        approval_id: str | UUID,
    ) -> _InMemoryApprovalRecord | None:
        if (
            self.approval_record is not None
            and tenant_id == self.approval_record.tenant_id
            and UUID(str(approval_id)) == self.approval_record.approval_id
        ):
            return self.approval_record
        return None

    def record_audit(self, **kwargs: Any) -> None:
        audit_event = kwargs.get("audit_event")
        if audit_event is not None:
            self.audit_events.append(audit_event)
        approval_package = kwargs.get("approval_package")
        if approval_package is not None:
            self.approval_package = approval_package
            self.approval_record = _InMemoryApprovalRecord(approval_package)

    def commit(self) -> None:
        return None

    def approve_package(self) -> None:
        if self.approval_record is None:
            raise AssertionError("approval package was not recorded")
        self.approval_record.approve()


def test_approval_package_creation_uses_generic_safe_authority_refs() -> None:
    request = replace(
        _build_request(mode="write"),
        workflow_type="uc2_legal_services_intake_conflict_check",
        subject_id=str(uuid4()),
        subject_ref="legal_intake_gateway_001",
    )
    adapter = _RecordingAdapter([_outbound_comms_spec()])
    store = _InMemoryGatewayStore()
    gateway = ToolGateway(cast(ToolGatewayStore, store), _build_registry(adapter))

    response = gateway.invoke(request)
    package = store.approval_package

    assert response.verdict == "approval_required"
    assert adapter.calls == []
    assert package is not None
    assert package.workflow_type == "uc2_legal_services_intake_conflict_check"
    assert package.requested_action == "outbound_comms.message.write"
    assert package.policy_version_refs["approval_policy_ref"] == (
        "approval_policy.outbound_comms_message_write.local.v1"
    )
    assert package.policy_version_refs["sla_policy_ref"] == (
        "approval_sla.outbound_comms_message_write.local.v1"
    )
    assert store.audit_events[-1].details["subject"] == {
        "workflow_type": "uc2_legal_services_intake_conflict_check",
        "subject_id": request.subject_id,
        "subject_ref": "legal_intake_gateway_001",
        "subject_summary": "Motor cover gateway request",
    }
    assert package.metadata["scope"] == "generic_connector_write"
    assert package.metadata["subject_refs"]["subject_ref"] == "legal_intake_gateway_001"
    assert package.metadata["action_refs"] == {
        "comms_policy_ref": "policy_uc1_outbound_comms_local_v1",
        "customer_ref": "cust_demo_001",
        "enquiry_ref": "enq_motor_private_001",
        "missing_data_request_ref": "mdr_demo_001",
    }
    assert "to_email" not in package.metadata["action_refs"]
    assert "body_text" not in package.metadata["action_refs"]


def test_approval_apply_recheck_uses_generic_refs_not_raw_content() -> None:
    request = _build_request(mode="write")
    adapter = _RecordingAdapter([_outbound_comms_spec()])
    store = _InMemoryGatewayStore()
    gateway = ToolGateway(cast(ToolGatewayStore, store), _build_registry(adapter))
    requested = gateway.invoke(request)
    store.approve_package()

    redrafted_content = dict(request.arguments)
    redrafted_content["body_text"] = "Different body text stays outside approval refs."
    applied = gateway.apply_approved_write(
        replace(request, arguments=redrafted_content),
        approval_id=requested.output["approval_id"],
    )

    assert applied.verdict == "allow"
    assert applied.output["approval_apply_status"] == "applied"
    assert len(adapter.calls) == 1


def test_approval_apply_recheck_blocks_safe_ref_and_workflow_type_mismatch() -> None:
    request = _build_request(mode="write")
    adapter = _RecordingAdapter([_outbound_comms_spec()])
    store = _InMemoryGatewayStore()
    gateway = ToolGateway(cast(ToolGatewayStore, store), _build_registry(adapter))
    requested = gateway.invoke(request)
    store.approve_package()

    changed_ref = dict(request.arguments)
    changed_ref["missing_data_request_ref"] = "mdr_changed_001"

    ref_mismatch = gateway.apply_approved_write(
        replace(request, arguments=changed_ref),
        approval_id=requested.output["approval_id"],
    )
    workflow_type_mismatch = gateway.apply_approved_write(
        replace(request, workflow_type="uc3_ifa_suitability_intake"),
        approval_id=requested.output["approval_id"],
    )

    assert ref_mismatch.verdict == "block"
    assert ref_mismatch.output["failure_category"] == "approval_ref_mismatch"
    assert workflow_type_mismatch.verdict == "block"
    assert workflow_type_mismatch.output["failure_category"] == "authority_context_mismatch"
    assert adapter.calls == []


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
        approval = conn.execute(
            """
            SELECT requested_action, workflow_type, metadata, policy_version_refs
            FROM approval_packages
            WHERE workflow_id = %s
            """,
            (request.workflow_id,),
        ).fetchone()

    assert response.verdict == "approval_required"
    assert response.output["requested_action"] == "outbound_comms.message.write"
    assert response.output["approval_state"] == "requested"
    assert approval is not None
    assert approval[0] == "outbound_comms.message.write"
    assert approval[1] == "uc1_enquiry_qualification"
    assert approval[2]["scope"] == "generic_connector_write"
    assert approval[2]["subject_refs"]["subject_ref"] == request.subject_ref
    assert approval[2]["action_refs"]["missing_data_request_ref"] == "mdr_demo_001"
    assert approval[3]["approval_policy_ref"] == (
        "approval_policy.outbound_comms_message_write.local.v1"
    )
    assert adapter.calls == []


def test_approved_write_apply_invokes_generic_connector_path(
    migrated_database_url: str,
) -> None:
    request = _build_request(mode="write")
    adapter = _RecordingAdapter([_outbound_comms_spec()])
    registry = _build_registry(adapter)

    with psycopg.connect(migrated_database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), registry)
        requested = gateway.invoke(request)
        approval_id = requested.output["approval_id"]
        conn.execute(
            """
            UPDATE approval_packages
            SET approval_state = 'approved',
                decision = 'approved',
                decision_at = now(),
                updated_at = now()
            WHERE tenant_id = %s
              AND approval_id = %s
            """,
            (request.tenant_id, approval_id),
        )
        applied = gateway.apply_approved_write(request, approval_id=approval_id)
        conn.commit()

    assert requested.verdict == "approval_required"
    assert applied.verdict == "allow"
    assert applied.output["approval_apply_status"] == "applied"
    assert "calendar_apply_status" not in applied.output
    assert len(adapter.calls) == 1
    assert adapter.calls[0]["tool_name"] == "outbound_comms.message"
    assert adapter.calls[0]["mode"] == "write"


@pytest.mark.parametrize(
    ("tool_name", "arguments", "table_name", "ref_column", "status"),
    [
        (
            "crm.route_to_quoting_queue",
            {
                "enquiry_ref": "enq_gateway_accept_001",
                "customer_ref": "cust_gateway_accept_001",
                "product_family_category": "motor_private_car",
                "qualification_summary_ref": "qsum_gateway_accept_001",
                "verdict_ref": "verdict_gateway_accept_001",
                "routing_policy_ref": "policy_uc1_routing_v1",
            },
            "local_quoting_queue_routes",
            "queued_route_ref",
            "queued",
        ),
        (
            "referral_inbox.route",
            {
                "enquiry_ref": "enq_gateway_refer_001",
                "customer_ref": "cust_gateway_refer_001",
                "referral_destination_category": "specialist_broker_panel",
                "referral_reason_category": "complex_risk_outside_appetite",
                "verdict_ref": "verdict_gateway_refer_001",
                "routing_policy_ref": "policy_uc1_routing_v1",
            },
            "local_referral_inbox_routes",
            "referral_route_ref",
            "routed",
        ),
        (
            "decline_ledger.route",
            {
                "enquiry_ref": "enq_gateway_decline_001",
                "customer_ref": "cust_gateway_decline_001",
                "decline_reason_category": "outside_product_target_market",
                "verdict_ref": "verdict_gateway_decline_001",
                "routing_policy_ref": "policy_uc1_routing_v1",
            },
            "local_decline_ledger_routes",
            "decline_route_ref",
            "recorded",
        ),
    ],
)
def test_uc1_routing_connectors_persist_broker_firm_refs(
    migrated_database_url: str,
    tool_name: str,
    arguments: dict[str, object],
    table_name: str,
    ref_column: str,
    status: str,
) -> None:
    request = _build_uc1_routing_request(tool_name=tool_name, arguments=arguments)

    with psycopg.connect(migrated_database_url) as conn:
        gateway = ToolGateway(ToolGatewayStore(conn), default_registry(conn))
        response = gateway.invoke(request)
        conn.commit()
        persisted = _fetch_uc1_route_row(
            conn,
            table_name=table_name,
            ref_column=ref_column,
            verdict_ref=str(arguments["verdict_ref"]),
        )

    assert response.verdict == "allow"
    assert response.enforced_mode == "write"
    assert response.output[ref_column] == persisted[0]
    assert response.output["route_status"] == status
    assert persisted[1:] == (
        request.tenant_id,
        request.workflow_id,
        request.correlation_id,
        str(arguments["enquiry_ref"]),
        str(arguments["customer_ref"]),
        str(arguments["verdict_ref"]),
        status,
    )


def test_missing_grant_blocks_without_connector_call(
    migrated_database_url: str,
) -> None:
    adapter = _RecordingAdapter([_outbound_comms_spec()])
    registry = _build_registry(adapter)
    request = _build_request()
    request = replace(request, agent_id="uc1.unknown_agent")

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


def _fetch_uc1_route_row(
    conn: psycopg.Connection[object],
    *,
    table_name: str,
    ref_column: str,
    verdict_ref: str,
) -> tuple[str, str, str, str, str, str, str, str]:
    match (table_name, ref_column):
        case ("local_quoting_queue_routes", "queued_route_ref"):
            row = conn.execute(
                """
                SELECT
                    queued_route_ref,
                    tenant_id,
                    workflow_id,
                    correlation_id,
                    enquiry_ref,
                    customer_ref,
                    verdict_ref,
                    route_status
                FROM local_quoting_queue_routes
                WHERE verdict_ref = %s
                """,
                (verdict_ref,),
            ).fetchone()
        case ("local_referral_inbox_routes", "referral_route_ref"):
            row = conn.execute(
                """
                SELECT
                    referral_route_ref,
                    tenant_id,
                    workflow_id,
                    correlation_id,
                    enquiry_ref,
                    customer_ref,
                    verdict_ref,
                    route_status
                FROM local_referral_inbox_routes
                WHERE verdict_ref = %s
                """,
                (verdict_ref,),
            ).fetchone()
        case ("local_decline_ledger_routes", "decline_route_ref"):
            row = conn.execute(
                """
                SELECT
                    decline_route_ref,
                    tenant_id,
                    workflow_id,
                    correlation_id,
                    enquiry_ref,
                    customer_ref,
                    verdict_ref,
                    route_status
                FROM local_decline_ledger_routes
                WHERE verdict_ref = %s
                """,
                (verdict_ref,),
            ).fetchone()
        case _:
            raise AssertionError(f"unexpected UC1 route table/ref pair: {table_name}/{ref_column}")
    if row is None:
        raise AssertionError(f"route row for verdict_ref={verdict_ref!r} was not persisted")
    return cast(tuple[str, str, str, str, str, str, str, str], row)

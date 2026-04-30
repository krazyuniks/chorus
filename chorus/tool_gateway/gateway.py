"""Tool Gateway policy enforcement, connector invocation, and audit writes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, ValidationError

from chorus.connectors.local import (
    CompanyResearchArguments,
    CompanyResearchConnector,
    ConnectorError,
    ConnectorResult,
    ConnectorTransientError,
    CrmCreateLeadArguments,
    CrmLookupCompanyArguments,
    LocalCrmConnector,
    MailpitEmailConnector,
)
from chorus.contracts.generated.events.audit_event import AuditEvent
from chorus.contracts.generated.tools.email_message_args import EmailMessageArgs
from chorus.contracts.generated.tools.gateway_verdict import GatewayVerdict
from chorus.contracts.generated.tools.tool_call import ToolCall
from chorus.observability import current_otel_ids
from chorus.workflows.types import ToolGatewayRequest, ToolGatewayResponse


class ToolGatewayError(RuntimeError):
    """Raised when Tool Gateway policy or connector handling fails unexpectedly."""


class ToolConnector(Protocol):
    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        tenant_id: str,
        correlation_id: str,
        workflow_id: str,
        arguments: dict[str, Any],
    ) -> ConnectorResult: ...


class LocalToolConnector:
    """Routes authorised gateway calls to local/sandbox connectors."""

    def __init__(self, conn: Connection[Any], email_connector: MailpitEmailConnector | None = None):
        self._conn = conn
        self._email = email_connector or MailpitEmailConnector()
        self._crm = LocalCrmConnector(conn)
        self._research = CompanyResearchConnector()

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        tenant_id: str,
        correlation_id: str,
        workflow_id: str,
        arguments: dict[str, Any],
    ) -> ConnectorResult:
        match tool_name:
            case "email.propose_response" | "email.send_response":
                parsed = EmailMessageArgs.model_validate(arguments)
                return self._email.propose_response(
                    tenant_id=tenant_id,
                    correlation_id=correlation_id,
                    workflow_id=workflow_id,
                    arguments=parsed,
                    mode=mode,
                )
            case "crm.lookup_company":
                parsed = CrmLookupCompanyArguments.model_validate(arguments)
                return self._crm.lookup_company(tenant_id=tenant_id, arguments=parsed)
            case "crm.create_lead":
                parsed = CrmCreateLeadArguments.model_validate(arguments)
                return self._crm.create_lead(
                    tenant_id=tenant_id,
                    correlation_id=correlation_id,
                    arguments=parsed,
                )
            case "company_research.lookup":
                parsed = CompanyResearchArguments.model_validate(arguments)
                return self._research.lookup(parsed)
            case _:
                raise ToolGatewayError(f"Unsupported tool {tool_name!r}")


class ToolGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    agent_id: str
    agent_version: str
    tool_name: str
    mode: str
    allowed: bool
    approval_required: bool
    redaction_policy: dict[str, Any]


@dataclass(frozen=True)
class GatewayDecision:
    verdict: str
    enforced_mode: str
    reason: str
    grant: ToolGrant | None
    rewritten_arguments: dict[str, Any] | None = None
    approval_required: bool = False
    connector_allowed: bool = False


class ToolGatewayStore:
    """Postgres-backed grants, idempotency, and audit adapter."""

    def __init__(self, conn: Connection[Any]) -> None:
        self._conn = conn

    def set_tenant_context(self, tenant_id: str) -> None:
        self._conn.execute("SELECT set_config('app.tenant_id', %s, false)", (tenant_id,))

    def commit(self) -> None:
        self._conn.commit()

    def fetch_grant(
        self,
        *,
        tenant_id: str,
        agent_id: str,
        tool_name: str,
        mode: str,
    ) -> ToolGrant | None:
        self.set_tenant_context(tenant_id)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    tenant_id,
                    agent_id,
                    agent_version,
                    tool_name,
                    mode,
                    allowed,
                    approval_required,
                    redaction_policy
                FROM tool_grants
                WHERE tenant_id = %s
                  AND agent_id = %s
                  AND tool_name = %s
                  AND mode = %s
                  AND allowed
                ORDER BY agent_version DESC
                LIMIT 1
                """,
                (tenant_id, agent_id, tool_name, mode),
            )
            row = cur.fetchone()
        return ToolGrant.model_validate(row) if row is not None else None

    def fetch_denied_grant(
        self,
        *,
        tenant_id: str,
        agent_id: str,
        tool_name: str,
        mode: str,
    ) -> ToolGrant | None:
        self.set_tenant_context(tenant_id)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    tenant_id,
                    agent_id,
                    agent_version,
                    tool_name,
                    mode,
                    allowed,
                    approval_required,
                    redaction_policy
                FROM tool_grants
                WHERE tenant_id = %s
                  AND agent_id = %s
                  AND tool_name = %s
                  AND mode = %s
                  AND NOT allowed
                ORDER BY agent_version DESC
                LIMIT 1
                """,
                (tenant_id, agent_id, tool_name, mode),
            )
            row = cur.fetchone()
        return ToolGrant.model_validate(row) if row is not None else None

    def fetch_idempotent_response(
        self,
        *,
        tenant_id: str,
        tool_name: str,
        idempotency_key: str,
    ) -> ToolGatewayResponse | None:
        self.set_tenant_context(tenant_id)
        row = self._conn.execute(
            """
            SELECT raw_event->'details'->'gateway_response'
            FROM tool_action_audit
            WHERE tenant_id = %s
              AND tool_name = %s
              AND idempotency_key = %s
              AND raw_event->'details' ? 'gateway_response'
            ORDER BY occurred_at
            LIMIT 1
            """,
            (tenant_id, tool_name, idempotency_key),
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return ToolGatewayResponse(**row[0])

    def record_audit(
        self,
        *,
        request: ToolGatewayRequest,
        tool_call: ToolCall,
        verdict: GatewayVerdict,
        audit_event: AuditEvent,
        arguments_redacted: dict[str, Any],
        response: ToolGatewayResponse | None = None,
    ) -> None:
        details = audit_event.details
        self.set_tenant_context(request.tenant_id)
        with self._conn.transaction():
            self._conn.execute(
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
                    rewritten_arguments,
                    reason,
                    connector_invocation_id,
                    occurred_at,
                    raw_event,
                    metadata
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    audit_event.tenant_id,
                    audit_event.audit_event_id,
                    audit_event.correlation_id,
                    audit_event.workflow_id,
                    request.invocation_id,
                    tool_call.tool_call_id,
                    verdict.verdict_id,
                    audit_event.actor.type.value,
                    audit_event.actor.id,
                    audit_event.category.value,
                    audit_event.action,
                    request.tool_name,
                    request.mode,
                    verdict.enforced_mode.value,
                    verdict.verdict.value,
                    request.idempotency_key,
                    Jsonb(arguments_redacted),
                    Jsonb(verdict.rewritten_arguments),
                    verdict.reason,
                    verdict.connector_invocation_id,
                    audit_event.occurred_at,
                    Jsonb({**audit_event.model_dump(mode="json"), "details": details}),
                    Jsonb(current_otel_ids()),
                ),
            )


class ToolGateway:
    def __init__(self, store: ToolGatewayStore, connector: ToolConnector) -> None:
        self._store = store
        self._connector = connector

    def invoke(self, request: ToolGatewayRequest) -> ToolGatewayResponse:
        replay = self._store.fetch_idempotent_response(
            tenant_id=request.tenant_id,
            tool_name=request.tool_name,
            idempotency_key=request.idempotency_key,
        )
        if replay is not None:
            return replay

        now = _now()
        tool_call = _tool_call(request, now)
        decision = self._decide(request)
        connector_result: ConnectorResult | None = None
        connector_output: dict[str, Any] = {}

        if decision.connector_allowed:
            try:
                connector_result = self._connector.invoke(
                    tool_name=request.tool_name,
                    mode=decision.enforced_mode,
                    tenant_id=request.tenant_id,
                    correlation_id=request.correlation_id,
                    workflow_id=request.workflow_id,
                    arguments=decision.rewritten_arguments or request.arguments,
                )
                connector_output = connector_result.output
            except ConnectorTransientError as exc:
                decision = GatewayDecision(
                    verdict="block",
                    enforced_mode=decision.enforced_mode,
                    reason=f"Connector transient failure after authorised call: {exc}",
                    grant=decision.grant,
                    rewritten_arguments=decision.rewritten_arguments,
                    connector_allowed=False,
                )
                verdict = _gateway_verdict(
                    tool_call=tool_call,
                    tenant_id=request.tenant_id,
                    correlation_id=request.correlation_id,
                    decision=decision,
                    connector_invocation_id=None,
                    decided_at=_now(),
                )
                audit_event = _connector_failure_audit_event(
                    request=request,
                    tool_call=tool_call,
                    verdict=verdict,
                    occurred_at=verdict.decided_at,
                    error=str(exc),
                )
                self._store.record_audit(
                    request=request,
                    tool_call=tool_call,
                    verdict=verdict,
                    audit_event=audit_event,
                    arguments_redacted=_redact(request.arguments, decision.grant),
                )
                self._store.commit()
                raise
            except (ConnectorError, ValidationError) as exc:
                decision = GatewayDecision(
                    verdict="block",
                    enforced_mode=decision.enforced_mode,
                    reason=f"Connector rejected authorised call: {exc}",
                    grant=decision.grant,
                    rewritten_arguments=decision.rewritten_arguments,
                    connector_allowed=False,
                )

        verdict = _gateway_verdict(
            tool_call=tool_call,
            tenant_id=request.tenant_id,
            correlation_id=request.correlation_id,
            decision=decision,
            connector_invocation_id=(
                connector_result.connector_invocation_id if connector_result is not None else None
            ),
            decided_at=_now(),
        )
        response = ToolGatewayResponse(
            verdict_id=str(verdict.verdict_id),
            tool_call_id=str(tool_call.tool_call_id),
            audit_event_id=str(verdict.audit_event_id),
            verdict=verdict.verdict.value,
            enforced_mode=verdict.enforced_mode.value,
            reason=verdict.reason,
            connector_invocation_id=(
                str(verdict.connector_invocation_id)
                if verdict.connector_invocation_id is not None
                else None
            ),
            output=connector_output,
        )
        audit_event = _audit_event(
            request=request,
            tool_call=tool_call,
            verdict=verdict,
            response=response,
            occurred_at=verdict.decided_at,
        )
        self._store.record_audit(
            request=request,
            tool_call=tool_call,
            verdict=verdict,
            audit_event=audit_event,
            arguments_redacted=_redact(request.arguments, decision.grant),
            response=response,
        )
        return response

    def _decide(self, request: ToolGatewayRequest) -> GatewayDecision:
        try:
            _validate_tool_arguments(request.tool_name, request.arguments)
        except (ToolGatewayError, ValidationError) as exc:
            return GatewayDecision(
                verdict="block",
                enforced_mode=request.mode,
                reason=f"Tool argument schema validation failed: {exc}",
                grant=None,
            )

        denied_grant = self._store.fetch_denied_grant(
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            tool_name=request.tool_name,
            mode=request.mode,
        )
        if denied_grant is not None:
            return GatewayDecision(
                verdict="block",
                enforced_mode=request.mode,
                reason="Explicit Tool Gateway grant denies the requested agent, tool, and mode.",
                grant=denied_grant,
            )

        exact_grant = self._store.fetch_grant(
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            tool_name=request.tool_name,
            mode=request.mode,
        )
        if exact_grant is not None:
            if exact_grant.approval_required:
                return GatewayDecision(
                    verdict="approval_required",
                    enforced_mode=request.mode,
                    reason="Grant exists but requires approval before connector execution.",
                    grant=exact_grant,
                    approval_required=True,
                )
            if request.mode == "propose":
                return GatewayDecision(
                    verdict="propose",
                    enforced_mode="propose",
                    reason="Proposal-mode grant accepted; connector captured sandbox proposal.",
                    grant=exact_grant,
                    connector_allowed=True,
                )
            return GatewayDecision(
                verdict="allow",
                enforced_mode=request.mode,
                reason="Grant accepted for requested tool and mode.",
                grant=exact_grant,
                connector_allowed=True,
            )

        if request.mode == "write":
            propose_grant = self._store.fetch_grant(
                tenant_id=request.tenant_id,
                agent_id=request.agent_id,
                tool_name=request.tool_name,
                mode="propose",
            )
            if propose_grant is not None:
                return GatewayDecision(
                    verdict="propose",
                    enforced_mode="propose",
                    reason="Requested write was downgraded to proposal mode by grant policy.",
                    grant=propose_grant,
                    connector_allowed=True,
                )

        return GatewayDecision(
            verdict="block",
            enforced_mode=request.mode,
            reason="No allowed Tool Gateway grant matched the requested agent, tool, and mode.",
            grant=None,
        )


def _now() -> datetime:
    return datetime.now(UTC)


def _tool_call(request: ToolGatewayRequest, requested_at: datetime) -> ToolCall:
    return ToolCall.model_validate(
        {
            "schema_version": "1.0.0",
            "tool_call_id": str(uuid4()),
            "invocation_id": request.invocation_id,
            "tenant_id": request.tenant_id,
            "correlation_id": request.correlation_id,
            "agent_id": request.agent_id,
            "tool_name": request.tool_name,
            "mode": request.mode,
            "idempotency_key": request.idempotency_key,
            "arguments": request.arguments,
            "requested_at": requested_at.isoformat(),
        }
    )


def _gateway_verdict(
    *,
    tool_call: ToolCall,
    tenant_id: str,
    correlation_id: str,
    decision: GatewayDecision,
    connector_invocation_id: UUID | None,
    decided_at: datetime,
) -> GatewayVerdict:
    return GatewayVerdict.model_validate(
        {
            "schema_version": "1.0.0",
            "verdict_id": str(uuid4()),
            "tool_call_id": str(tool_call.tool_call_id),
            "tenant_id": tenant_id,
            "correlation_id": correlation_id,
            "verdict": decision.verdict,
            "enforced_mode": decision.enforced_mode,
            "reason": decision.reason,
            "rewritten_arguments": decision.rewritten_arguments,
            "approval_required": decision.approval_required,
            "audit_event_id": str(uuid4()),
            "connector_invocation_id": (
                str(connector_invocation_id) if connector_invocation_id is not None else None
            ),
            "decided_at": decided_at.isoformat(),
        }
    )


def _audit_event(
    *,
    request: ToolGatewayRequest,
    tool_call: ToolCall,
    verdict: GatewayVerdict,
    response: ToolGatewayResponse,
    occurred_at: datetime,
) -> AuditEvent:
    return AuditEvent.model_validate(
        {
            "schema_version": "1.0.0",
            "audit_event_id": str(verdict.audit_event_id),
            "occurred_at": occurred_at.isoformat(),
            "tenant_id": request.tenant_id,
            "correlation_id": request.correlation_id,
            "workflow_id": request.workflow_id,
            "actor": {"type": "agent", "id": request.agent_id},
            "category": "tool_gateway",
            "action": "tool_call.decided",
            "verdict": verdict.verdict.value,
            "details": {
                "tool_call": tool_call.model_dump(mode="json"),
                "gateway_verdict": verdict.model_dump(mode="json"),
                "gateway_response": response.__dict__,
            },
        }
    )


def _connector_failure_audit_event(
    *,
    request: ToolGatewayRequest,
    tool_call: ToolCall,
    verdict: GatewayVerdict,
    occurred_at: datetime,
    error: str,
) -> AuditEvent:
    return AuditEvent.model_validate(
        {
            "schema_version": "1.0.0",
            "audit_event_id": str(verdict.audit_event_id),
            "occurred_at": occurred_at.isoformat(),
            "tenant_id": request.tenant_id,
            "correlation_id": request.correlation_id,
            "workflow_id": request.workflow_id,
            "actor": {"type": "agent", "id": request.agent_id},
            "category": "connector",
            "action": "connector.transient_failure",
            "verdict": verdict.verdict.value,
            "details": {
                "tool_call": tool_call.model_dump(mode="json"),
                "gateway_verdict": verdict.model_dump(mode="json"),
                "connector_failure": {
                    "classification": "transient",
                    "message": error,
                    "retryable_by": "temporal_activity_retry_policy",
                },
            },
        }
    )


def _validate_tool_arguments(tool_name: str, arguments: dict[str, Any]) -> None:
    match tool_name:
        case "email.propose_response" | "email.send_response":
            EmailMessageArgs.model_validate(arguments)
        case "company_research.lookup":
            CompanyResearchArguments.model_validate(arguments)
        case "crm.lookup_company":
            CrmLookupCompanyArguments.model_validate(arguments)
        case "crm.create_lead":
            CrmCreateLeadArguments.model_validate(arguments)
        case _:
            raise ToolGatewayError(f"No argument schema registered for tool {tool_name!r}")


def _redact(arguments: dict[str, Any], grant: ToolGrant | None) -> dict[str, Any]:
    redacted = dict(arguments)
    policy = grant.redaction_policy if grant is not None else {}
    for field in policy.get("redact_fields", []):
        if isinstance(field, str) and field in redacted:
            redacted[field] = "[redacted]"
    return redacted

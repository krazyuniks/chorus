"""Tool Gateway policy enforcement, connector invocation, and audit writes.

The gateway dispatches through the `ConnectorRegistry`. Argument validation
and dispatch both resolve through the registered `ToolSpec` per tool; adding a
new connector is a registry registration, not a gateway edit.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, ValidationError

from chorus.connectors import (
    ConnectorContext,
    ConnectorError,
    ConnectorRegistry,
    ConnectorRegistryError,
    ConnectorResult,
    ConnectorTransientError,
)
from chorus.contracts.generated.audit.audit_event import AuditEvent
from chorus.contracts.generated.connector.gateway_verdict import GatewayVerdict
from chorus.contracts.generated.connector.tool_call import ToolCall
from chorus.observability import current_otel_ids
from chorus.workflows.types import ToolGatewayRequest, ToolGatewayResponse

_CALENDAR_WRITE_TOOLS = {"calendar.create_hold", "calendar.cancel_hold"}
_CONNECTOR_FAILURE_CATEGORIES = {
    "calendar_hold_invalid_time_window",
    "caldav_duplicate_uid_context_mismatch",
    "caldav_invalid_report_response",
    "caldav_protocol_error",
    "caldav_rejected",
    "caldav_transient_unavailable",
}


class ToolGatewayError(RuntimeError):
    """Raised when Tool Gateway policy or connector handling fails unexpectedly."""


class ToolGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grant_id: UUID
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


@dataclass(frozen=True)
class ApprovalPackage:
    approval_id: UUID
    approval_package_version: int
    tenant_id: str
    correlation_id: str
    workflow_id: str
    workflow_type: str
    invocation_id: str
    tool_call_id: UUID
    verdict_id: UUID
    source_audit_event_id: UUID
    agent_id: str
    agent_version: str
    requested_action: str
    tool_name: str
    requested_mode: str
    enforced_mode: str
    idempotency_key_ref: str
    redaction_policy_ref: str
    redaction_summary: dict[str, Any]
    approval_state: str
    reason_category: str
    requested_at: datetime
    decision_due_at: datetime
    expires_at: datetime
    sla_policy_ref: str
    reviewer_trust_domain: str
    requested_by_workload_principal_id: str | None
    requested_by_workload_session_id: str | None
    trust_domain: str
    grant_id: UUID
    policy_version_refs: dict[str, Any]
    trace_join: dict[str, Any]
    metadata: dict[str, Any]

    def response_output(self) -> dict[str, Any]:
        return {
            "approval_id": str(self.approval_id),
            "approval_state": self.approval_state,
            "requested_action": self.requested_action,
            "decision_due_at": self.decision_due_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }

    def audit_summary(self) -> dict[str, Any]:
        return {
            "approval_id": str(self.approval_id),
            "approval_package_version": self.approval_package_version,
            "approval_state": self.approval_state,
            "requested_action": self.requested_action,
            "tool_name": self.tool_name,
            "requested_mode": self.requested_mode,
            "enforced_mode": self.enforced_mode,
            "idempotency_key_ref": self.idempotency_key_ref,
            "redaction_summary": self.redaction_summary,
            "decision_due_at": self.decision_due_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "sla_policy_ref": self.sla_policy_ref,
            "grant_ref": f"tool_grant:{self.grant_id}",
            "trace_join": self.trace_join,
        }


@dataclass(frozen=True)
class ApprovalPackageRecord:
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
    expires_at: datetime
    grant_id: UUID
    policy_version_refs: dict[str, Any]
    trace_join: dict[str, Any]
    metadata: dict[str, Any]

    def apply_summary(self, *, apply_idempotency_key: str) -> dict[str, Any]:
        summary = {
            "approval_id": str(self.approval_id),
            "approval_state": self.approval_state,
            "decision": self.decision,
            "requested_action": self.requested_action,
            "tool_name": self.tool_name,
            "requested_mode": self.requested_mode,
            "enforced_mode": self.enforced_mode,
            "idempotency_key_ref": self.idempotency_key_ref,
            "apply_idempotency_key_ref": _safe_ref_hash(apply_idempotency_key),
            "expires_at": self.expires_at.isoformat(),
            "grant_ref": f"tool_grant:{self.grant_id}",
            "policy_version_refs": self.policy_version_refs,
            "subject_refs": self.metadata.get("subject_refs", {}),
            "action_refs": self.metadata.get("action_refs", {}),
            "trace_join": self.trace_join,
        }
        calendar_refs = self.metadata.get("calendar_refs")
        if isinstance(calendar_refs, dict):
            summary["calendar_refs"] = calendar_refs
        if self.tool_name == "calendar.cancel_hold":
            summary["compensation_category"] = "compensation_requested"
        return summary


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
                    grant_id,
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
                    grant_id,
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

    def fetch_approval_package(
        self,
        *,
        tenant_id: str,
        approval_id: UUID,
    ) -> ApprovalPackageRecord | None:
        self.set_tenant_context(tenant_id)
        row = self._conn.execute(
            """
            SELECT
                approval_id,
                approval_state,
                decision,
                tenant_id,
                correlation_id,
                workflow_id,
                workflow_type,
                invocation_id,
                agent_id,
                agent_version,
                requested_action,
                tool_name,
                requested_mode,
                enforced_mode,
                idempotency_key_ref,
                expires_at,
                grant_id,
                policy_version_refs,
                trace_join,
                metadata
            FROM approval_packages
            WHERE tenant_id = %s
              AND approval_id = %s
            """,
            (tenant_id, approval_id),
        ).fetchone()
        if row is None:
            return None
        return ApprovalPackageRecord(
            approval_id=row[0],
            approval_state=row[1],
            decision=row[2],
            tenant_id=row[3],
            correlation_id=row[4],
            workflow_id=row[5],
            workflow_type=row[6],
            invocation_id=row[7],
            agent_id=row[8],
            agent_version=row[9],
            requested_action=row[10],
            tool_name=row[11],
            requested_mode=row[12],
            enforced_mode=row[13],
            idempotency_key_ref=row[14],
            expires_at=row[15],
            grant_id=row[16],
            policy_version_refs=row[17],
            trace_join=row[18],
            metadata=row[19],
        )

    def record_audit(
        self,
        *,
        request: ToolGatewayRequest,
        tool_call: ToolCall,
        verdict: GatewayVerdict,
        audit_event: AuditEvent,
        arguments_redacted: dict[str, Any],
        response: ToolGatewayResponse | None = None,
        approval_package: ApprovalPackage | None = None,
    ) -> None:
        del response  # the gateway response lives inside `audit_event.details` already
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
            if approval_package is not None:
                self._conn.execute(
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
                        authority_context_id,
                        tool_authority_context_id,
                        agent_id,
                        agent_version,
                        task_kind,
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
                        escalation_policy_ref,
                        reviewer_actor_subject_ref,
                        reviewer_actor_session_id,
                        reviewer_role,
                        reviewer_trust_domain,
                        decision_at,
                        requested_by_workload_principal_id,
                        requested_by_workload_session_id,
                        decided_by_workload_principal_id,
                        decided_by_workload_session_id,
                        trust_domain,
                        grant_id,
                        policy_version_refs,
                        trace_join,
                        metadata
                    )
                    VALUES (
                        %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, %s,
                        NULL, NULL, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, NULL, NULL, NULL, NULL, %s, NULL, %s,
                        %s, NULL, NULL, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (tenant_id, tool_name, idempotency_key_ref) DO NOTHING
                    """,
                    (
                        approval_package.tenant_id,
                        approval_package.approval_id,
                        approval_package.approval_package_version,
                        approval_package.approval_state,
                        approval_package.reason_category,
                        approval_package.correlation_id,
                        approval_package.workflow_id,
                        approval_package.workflow_type,
                        approval_package.invocation_id,
                        approval_package.tool_call_id,
                        approval_package.verdict_id,
                        approval_package.source_audit_event_id,
                        approval_package.agent_id,
                        approval_package.agent_version,
                        approval_package.requested_action,
                        approval_package.tool_name,
                        approval_package.requested_mode,
                        approval_package.enforced_mode,
                        approval_package.idempotency_key_ref,
                        approval_package.redaction_policy_ref,
                        Jsonb(approval_package.redaction_summary),
                        approval_package.requested_at,
                        approval_package.decision_due_at,
                        approval_package.expires_at,
                        approval_package.sla_policy_ref,
                        approval_package.reviewer_trust_domain,
                        approval_package.requested_by_workload_principal_id,
                        approval_package.requested_by_workload_session_id,
                        approval_package.trust_domain,
                        approval_package.grant_id,
                        Jsonb(approval_package.policy_version_refs),
                        Jsonb(approval_package.trace_join),
                        Jsonb(approval_package.metadata),
                    ),
                )


class ToolGateway:
    def __init__(self, store: ToolGatewayStore, registry: ConnectorRegistry) -> None:
        self._store = store
        self._registry = registry

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
        decision, validated_arguments = self._decide(request)
        connector_result: ConnectorResult | None = None
        connector_output: dict[str, Any] = {}

        if decision.connector_allowed and validated_arguments is not None:
            try:
                adapter, _spec = self._registry.resolve(request.tool_name)
                connector_result = adapter.invoke(
                    tool_name=request.tool_name,
                    mode=decision.enforced_mode,
                    context=ConnectorContext(
                        tenant_id=request.tenant_id,
                        correlation_id=request.correlation_id,
                        workflow_id=request.workflow_id,
                    ),
                    arguments=validated_arguments,
                )
                connector_output = connector_result.output
            except ConnectorTransientError as exc:
                failure_category = _connector_failure_category(exc)
                decision = GatewayDecision(
                    verdict="block",
                    enforced_mode=decision.enforced_mode,
                    reason="Connector transient failure after authorised call.",
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
                    failure_category=failure_category,
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
            except (ConnectorError, ConnectorRegistryError, ValidationError) as exc:
                failure_category = _connector_failure_category(exc)
                decision = GatewayDecision(
                    verdict="block",
                    enforced_mode=decision.enforced_mode,
                    reason="Connector rejected authorised call.",
                    grant=decision.grant,
                    rewritten_arguments=decision.rewritten_arguments,
                    connector_allowed=False,
                )
                connector_output = {
                    "connector_status": "blocked",
                    "failure_category": failure_category,
                    "retry_category": "non_retryable",
                }

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
        approval_package: ApprovalPackage | None = None
        if _requires_approval_package(request, decision):
            approval_package = _approval_package(
                request=request,
                tool_call=tool_call,
                verdict=verdict,
                decision=decision,
                requested_at=verdict.decided_at,
            )
            connector_output = approval_package.response_output()

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
            approval_package=approval_package,
            occurred_at=verdict.decided_at,
        )
        self._store.record_audit(
            request=request,
            tool_call=tool_call,
            verdict=verdict,
            audit_event=audit_event,
            arguments_redacted=_redact(request.arguments, decision.grant),
            response=response,
            approval_package=approval_package,
        )
        return response

    def apply_approved_write(
        self,
        request: ToolGatewayRequest,
        *,
        approval_id: str | UUID,
    ) -> ToolGatewayResponse:
        """Apply an approved connector write package by re-entering the gateway."""

        approval_uuid = UUID(str(approval_id))
        if request.mode != "write":
            raise ToolGatewayError("Approval apply only supports write-mode tool requests.")

        apply_idempotency_key = _approval_apply_idempotency_key(
            request.idempotency_key,
            approval_uuid,
        )
        replay = self._store.fetch_idempotent_response(
            tenant_id=request.tenant_id,
            tool_name=request.tool_name,
            idempotency_key=apply_idempotency_key,
        )
        if replay is not None:
            return replay

        apply_request = replace(request, idempotency_key=apply_idempotency_key)
        now = _now()
        tool_call = _tool_call(apply_request, now)
        decision, validated_arguments, approval_package, failure_category = (
            self._decide_approval_apply(
                request=request,
                approval_id=approval_uuid,
                now=now,
            )
        )
        connector_result: ConnectorResult | None = None
        connector_output: dict[str, Any] = {}
        connector_failure: dict[str, Any] | None = None

        if decision.connector_allowed and validated_arguments is not None:
            try:
                adapter, _spec = self._registry.resolve(request.tool_name)
                connector_result = adapter.invoke(
                    tool_name=request.tool_name,
                    mode=decision.enforced_mode,
                    context=ConnectorContext(
                        tenant_id=request.tenant_id,
                        correlation_id=request.correlation_id,
                        workflow_id=request.workflow_id,
                    ),
                    arguments=validated_arguments,
                )
                connector_output = _approval_apply_success_output(
                    tool_name=request.tool_name,
                    approval_id=approval_uuid,
                    connector_output=connector_result.output,
                )
            except ConnectorTransientError as exc:
                failure_category = _connector_failure_category(exc)
                decision = GatewayDecision(
                    verdict="block",
                    enforced_mode=decision.enforced_mode,
                    reason="Connector transient failure after approved package apply.",
                    grant=decision.grant,
                    rewritten_arguments=decision.rewritten_arguments,
                    connector_allowed=False,
                )
                verdict = _gateway_verdict(
                    tool_call=tool_call,
                    tenant_id=apply_request.tenant_id,
                    correlation_id=apply_request.correlation_id,
                    decision=decision,
                    connector_invocation_id=None,
                    decided_at=_now(),
                )
                audit_event = _connector_failure_audit_event(
                    request=apply_request,
                    tool_call=tool_call,
                    verdict=verdict,
                    occurred_at=verdict.decided_at,
                    failure_category=failure_category,
                    extra_details={
                        "approval_apply": _approval_apply_summary(
                            approval_package=approval_package,
                            approval_id=approval_uuid,
                            apply_idempotency_key=apply_idempotency_key,
                        )
                    },
                )
                self._store.record_audit(
                    request=apply_request,
                    tool_call=tool_call,
                    verdict=verdict,
                    audit_event=audit_event,
                    arguments_redacted=_redact(request.arguments, decision.grant),
                )
                self._store.commit()
                raise
            except (ConnectorError, ConnectorRegistryError, ValidationError) as exc:
                failure_category = _connector_failure_category(exc)
                decision = GatewayDecision(
                    verdict="block",
                    enforced_mode=decision.enforced_mode,
                    reason="Connector rejected approved package apply.",
                    grant=decision.grant,
                    rewritten_arguments=decision.rewritten_arguments,
                    connector_allowed=False,
                )
                connector_failure = _connector_failure_details(
                    classification="non_retryable",
                    failure_category=failure_category,
                    retryable_by=None,
                )
                if request.tool_name == "calendar.cancel_hold":
                    connector_failure["compensation_category"] = "compensation_failed"
                    connector_failure["escalation_category"] = "calendar_compensation_failed"
                connector_output = _approval_apply_blocked_output(
                    tool_name=request.tool_name,
                    approval_id=approval_uuid,
                    failure_category=failure_category,
                    retry_category="non_retryable",
                )
                if request.tool_name == "calendar.cancel_hold":
                    connector_output["compensation_category"] = "compensation_failed"
                    connector_output["escalation_category"] = "calendar_compensation_failed"
        elif failure_category is not None:
            connector_output = _approval_apply_blocked_output(
                tool_name=request.tool_name,
                approval_id=approval_uuid,
                failure_category=failure_category,
            )
            if request.tool_name == "calendar.cancel_hold":
                connector_output["compensation_category"] = "compensation_blocked"

        verdict = _gateway_verdict(
            tool_call=tool_call,
            tenant_id=apply_request.tenant_id,
            correlation_id=apply_request.correlation_id,
            decision=decision,
            connector_invocation_id=(
                connector_result.connector_invocation_id if connector_result is not None else None
            ),
            decided_at=_now(),
        )
        extra_details = {
            "approval_apply": _approval_apply_summary(
                approval_package=approval_package,
                approval_id=approval_uuid,
                apply_idempotency_key=apply_idempotency_key,
            )
        }
        if connector_failure is not None:
            extra_details["connector_failure"] = connector_failure
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
            request=apply_request,
            tool_call=tool_call,
            verdict=verdict,
            response=response,
            occurred_at=verdict.decided_at,
            extra_details=extra_details,
        )
        self._store.record_audit(
            request=apply_request,
            tool_call=tool_call,
            verdict=verdict,
            audit_event=audit_event,
            arguments_redacted=_redact(request.arguments, decision.grant),
            response=response,
        )
        return response

    def apply_approved_calendar_write(
        self,
        request: ToolGatewayRequest,
        *,
        approval_id: str | UUID,
    ) -> ToolGatewayResponse:
        """Compatibility wrapper for the local calendar approval apply path."""

        if request.tool_name not in _CALENDAR_WRITE_TOOLS:
            raise ToolGatewayError("Calendar approval apply only supports calendar write tools.")
        return self.apply_approved_write(request, approval_id=approval_id)

    def _decide(self, request: ToolGatewayRequest) -> tuple[GatewayDecision, BaseModel | None]:
        try:
            validated_arguments = self._validate_arguments(request)
        except (ToolGatewayError, ConnectorRegistryError, ValidationError) as exc:
            return (
                GatewayDecision(
                    verdict="block",
                    enforced_mode=request.mode,
                    reason=f"Tool argument schema validation failed: {exc}",
                    grant=None,
                ),
                None,
            )

        denied_grant = self._store.fetch_denied_grant(
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            tool_name=request.tool_name,
            mode=request.mode,
        )
        if denied_grant is not None:
            return (
                GatewayDecision(
                    verdict="block",
                    enforced_mode=request.mode,
                    reason=(
                        "Explicit Tool Gateway grant denies the requested agent, tool, and mode."
                    ),
                    grant=denied_grant,
                ),
                None,
            )

        exact_grant = self._store.fetch_grant(
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            tool_name=request.tool_name,
            mode=request.mode,
        )
        if exact_grant is not None:
            if exact_grant.approval_required:
                return (
                    GatewayDecision(
                        verdict="approval_required",
                        enforced_mode=request.mode,
                        reason="Grant exists but requires approval before connector execution.",
                        grant=exact_grant,
                        approval_required=True,
                    ),
                    None,
                )
            if request.mode == "propose":
                return (
                    GatewayDecision(
                        verdict="propose",
                        enforced_mode="propose",
                        reason="Proposal-mode grant accepted; connector captured sandbox proposal.",
                        grant=exact_grant,
                        connector_allowed=True,
                    ),
                    validated_arguments,
                )
            return (
                GatewayDecision(
                    verdict="allow",
                    enforced_mode=request.mode,
                    reason="Grant accepted for requested tool and mode.",
                    grant=exact_grant,
                    connector_allowed=True,
                ),
                validated_arguments,
            )

        if request.mode == "write":
            propose_grant = self._store.fetch_grant(
                tenant_id=request.tenant_id,
                agent_id=request.agent_id,
                tool_name=request.tool_name,
                mode="propose",
            )
            if propose_grant is not None:
                return (
                    GatewayDecision(
                        verdict="propose",
                        enforced_mode="propose",
                        reason="Requested write was downgraded to proposal mode by grant policy.",
                        grant=propose_grant,
                        connector_allowed=True,
                    ),
                    validated_arguments,
                )

        return (
            GatewayDecision(
                verdict="block",
                enforced_mode=request.mode,
                reason="No allowed Tool Gateway grant matched the requested agent, tool, and mode.",
                grant=None,
            ),
            None,
        )

    def _decide_approval_apply(
        self,
        *,
        request: ToolGatewayRequest,
        approval_id: UUID,
        now: datetime,
    ) -> tuple[
        GatewayDecision,
        BaseModel | None,
        ApprovalPackageRecord | None,
        str | None,
    ]:
        try:
            validated_arguments = self._validate_arguments(request)
        except ToolGatewayError, ConnectorRegistryError, ValidationError:
            return (
                GatewayDecision(
                    verdict="block",
                    enforced_mode=request.mode,
                    reason="Tool argument schema validation failed.",
                    grant=None,
                ),
                None,
                None,
                "contract_validation_failed",
            )

        approval_package = self._store.fetch_approval_package(
            tenant_id=request.tenant_id,
            approval_id=approval_id,
        )
        if approval_package is None:
            return (
                GatewayDecision(
                    verdict="block",
                    enforced_mode=request.mode,
                    reason="No local approval package matched the apply request.",
                    grant=None,
                ),
                None,
                None,
                "approval_package_missing",
            )

        denied_grant = self._store.fetch_denied_grant(
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            tool_name=request.tool_name,
            mode=request.mode,
        )
        if denied_grant is not None:
            return (
                GatewayDecision(
                    verdict="block",
                    enforced_mode=request.mode,
                    reason="Explicit Tool Gateway grant denies the approved package apply.",
                    grant=denied_grant,
                ),
                None,
                approval_package,
                "grant_denied",
            )

        exact_grant = self._store.fetch_grant(
            tenant_id=request.tenant_id,
            agent_id=request.agent_id,
            tool_name=request.tool_name,
            mode=request.mode,
        )
        if exact_grant is None:
            return (
                GatewayDecision(
                    verdict="block",
                    enforced_mode=request.mode,
                    reason="No current Tool Gateway grant matched the approved package apply.",
                    grant=None,
                ),
                None,
                approval_package,
                "grant_missing",
            )
        if not exact_grant.approval_required:
            return (
                GatewayDecision(
                    verdict="block",
                    enforced_mode=request.mode,
                    reason=("Current grant no longer requires an approval package for apply."),
                    grant=exact_grant,
                ),
                None,
                approval_package,
                "grant_state_mismatch",
            )

        mismatch_category = _approval_package_mismatch_category(
            request=request,
            approval_package=approval_package,
            grant=exact_grant,
            now=now,
        )
        if mismatch_category is not None:
            return (
                GatewayDecision(
                    verdict="block",
                    enforced_mode=request.mode,
                    reason="Approved package failed gateway re-check.",
                    grant=exact_grant,
                ),
                None,
                approval_package,
                mismatch_category,
            )

        reason = (
            "Approved local calendar compensation package re-entered the Tool Gateway; "
            "connector execution permitted."
            if request.tool_name == "calendar.cancel_hold"
            else "Approved package re-entered the Tool Gateway; connector execution permitted."
        )
        return (
            GatewayDecision(
                verdict="allow",
                enforced_mode=request.mode,
                reason=reason,
                grant=exact_grant,
                connector_allowed=True,
            ),
            validated_arguments,
            approval_package,
            None,
        )

    def _validate_arguments(self, request: ToolGatewayRequest) -> BaseModel:
        try:
            _adapter, spec = self._registry.resolve(request.tool_name)
        except ConnectorRegistryError as exc:
            raise ToolGatewayError(str(exc)) from exc
        return spec.argument_contract.model_validate(request.arguments)


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


def _requires_approval_package(
    request: ToolGatewayRequest,
    decision: GatewayDecision,
) -> bool:
    return decision.approval_required and decision.grant is not None and request.mode == "write"


def _approval_package(
    *,
    request: ToolGatewayRequest,
    tool_call: ToolCall,
    verdict: GatewayVerdict,
    decision: GatewayDecision,
    requested_at: datetime,
) -> ApprovalPackage:
    if decision.grant is None:
        raise ToolGatewayError("Approval package creation requires an exact grant.")

    redacted_fields = _redacted_fields(decision.grant)
    idempotency_key_ref = _safe_ref_hash(request.idempotency_key)
    approval_id = uuid5(
        NAMESPACE_URL,
        f"chorus.approval:{request.tenant_id}:{request.tool_name}:{idempotency_key_ref}",
    )
    decision_due_at = requested_at + timedelta(hours=4)
    expires_at = requested_at + timedelta(hours=24)
    grant_ref = f"tool_grant:{decision.grant.grant_id}"
    policy_version_refs = _approval_policy_version_refs(
        grant=decision.grant,
        tool_name=request.tool_name,
        mode=request.mode,
    )

    return ApprovalPackage(
        approval_id=approval_id,
        approval_package_version=1,
        tenant_id=request.tenant_id,
        correlation_id=request.correlation_id,
        workflow_id=request.workflow_id,
        workflow_type=request.workflow_type,
        invocation_id=request.invocation_id,
        tool_call_id=tool_call.tool_call_id,
        verdict_id=verdict.verdict_id,
        source_audit_event_id=verdict.audit_event_id,
        agent_id=request.agent_id,
        agent_version=decision.grant.agent_version,
        requested_action=f"{request.tool_name}.{request.mode}",
        tool_name=request.tool_name,
        requested_mode=request.mode,
        enforced_mode=verdict.enforced_mode.value,
        idempotency_key_ref=idempotency_key_ref,
        redaction_policy_ref=f"{grant_ref}:redaction_policy",
        redaction_summary={
            "redaction_policy_ref": f"{grant_ref}:redaction_policy",
            "redacted_field_count": len(redacted_fields),
            "redacted_field_refs": redacted_fields,
        },
        approval_state="requested",
        reason_category="tool_write_risk",
        requested_at=requested_at,
        decision_due_at=decision_due_at,
        expires_at=expires_at,
        sla_policy_ref=policy_version_refs["sla_policy_ref"],
        reviewer_trust_domain="local.chorus",
        requested_by_workload_principal_id=None,
        requested_by_workload_session_id=None,
        trust_domain="local.chorus",
        grant_id=decision.grant.grant_id,
        policy_version_refs=policy_version_refs,
        trace_join=current_otel_ids(),
        metadata=_approval_package_metadata(request),
    )


def _approval_policy_version_refs(
    *,
    grant: ToolGrant,
    tool_name: str,
    mode: str,
) -> dict[str, str]:
    tool_policy_slug = tool_name.replace(".", "_").replace("-", "_")
    return {
        "tool_grant_ref": f"tool_grant:{grant.grant_id}",
        "approval_policy_ref": f"approval_policy.{tool_policy_slug}_{mode}.local.v1",
        "sla_policy_ref": f"approval_sla.{tool_policy_slug}_{mode}.local.v1",
    }


def _approval_package_metadata(request: ToolGatewayRequest) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "source": "tool_gateway.approval_required",
        "scope": "generic_connector_write",
        "subject_refs": _subject_refs(request),
        "action_refs": _safe_argument_refs(request.arguments),
    }
    calendar_refs = _calendar_argument_refs(request.tool_name, request.arguments)
    if calendar_refs:
        metadata["calendar_refs"] = calendar_refs
    return metadata


def _subject_refs(request: ToolGatewayRequest) -> dict[str, str]:
    subject_refs: dict[str, str] = {}
    if request.subject_id is not None:
        subject_refs["subject_id"] = request.subject_id
    if request.subject_ref is not None:
        subject_refs["subject_ref"] = request.subject_ref
    return subject_refs


def _safe_argument_refs(arguments: dict[str, Any]) -> dict[str, Any]:
    safe_refs: dict[str, Any] = {}
    for key, value in sorted(arguments.items()):
        if not (key.endswith("_ref") or key.endswith("_refs")):
            continue
        safe_value = _safe_argument_ref_value(value)
        if safe_value is not None:
            safe_refs[key] = safe_value
    return safe_refs


def _safe_argument_ref_value(value: Any) -> Any:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        safe_items: list[str] = []
        for item in cast(list[Any], value):
            if not isinstance(item, str):
                return None
            safe_items.append(item)
        return safe_items
    return None


def _safe_ref_hash(value: str) -> str:
    return f"sha256:{sha256(value.encode('utf-8')).hexdigest()}"


def _approval_apply_idempotency_key(idempotency_key: str, approval_id: UUID) -> str:
    return f"{idempotency_key}:approval_apply:{approval_id}"


def _approval_package_mismatch_category(
    *,
    request: ToolGatewayRequest,
    approval_package: ApprovalPackageRecord,
    grant: ToolGrant,
    now: datetime,
) -> str | None:
    expected_action = f"{request.tool_name}.{request.mode}"
    expected_metadata = _approval_package_metadata(request)
    checks = {
        "tenant_id": approval_package.tenant_id == request.tenant_id,
        "correlation_id": approval_package.correlation_id == request.correlation_id,
        "workflow_id": approval_package.workflow_id == request.workflow_id,
        "workflow_type": approval_package.workflow_type == request.workflow_type,
        "invocation_id": str(approval_package.invocation_id) == request.invocation_id,
        "agent_id": approval_package.agent_id == request.agent_id,
        "agent_version": approval_package.agent_version == grant.agent_version,
        "requested_action": approval_package.requested_action == expected_action,
        "tool_name": approval_package.tool_name == request.tool_name,
        "requested_mode": approval_package.requested_mode == request.mode,
        "enforced_mode": approval_package.enforced_mode == request.mode,
        "grant_id": approval_package.grant_id == grant.grant_id,
    }
    if not all(checks.values()):
        return "authority_context_mismatch"
    expected_policy_refs = _approval_policy_version_refs(
        grant=grant,
        tool_name=request.tool_name,
        mode=request.mode,
    )
    for key, value in expected_policy_refs.items():
        if approval_package.policy_version_refs.get(key) != value:
            return "policy_ref_mismatch"
    if approval_package.approval_state != "approved" or approval_package.decision != "approved":
        return "approval_state_not_approved"
    if approval_package.expires_at <= now:
        return "approval_expired"
    if approval_package.idempotency_key_ref != _safe_ref_hash(request.idempotency_key):
        return "idempotency_ref_mismatch"
    if approval_package.metadata.get("subject_refs", {}) != expected_metadata["subject_refs"]:
        return "approval_ref_mismatch"
    if approval_package.metadata.get("action_refs", {}) != expected_metadata["action_refs"]:
        return "approval_ref_mismatch"
    if request.tool_name in _CALENDAR_WRITE_TOOLS and approval_package.metadata.get(
        "calendar_refs", {}
    ) != expected_metadata.get("calendar_refs", {}):
        return "calendar_ref_mismatch"
    return None


def _approval_apply_summary(
    *,
    approval_package: ApprovalPackageRecord | None,
    approval_id: UUID,
    apply_idempotency_key: str,
) -> dict[str, Any]:
    if approval_package is None:
        return {
            "approval_id": str(approval_id),
            "approval_state": "missing",
            "apply_idempotency_key_ref": _safe_ref_hash(apply_idempotency_key),
        }
    return approval_package.apply_summary(apply_idempotency_key=apply_idempotency_key)


def _approval_apply_success_output(
    *,
    tool_name: str,
    approval_id: UUID,
    connector_output: dict[str, Any],
) -> dict[str, Any]:
    output = {
        **connector_output,
        "approval_id": str(approval_id),
        "approval_apply_status": "applied",
    }
    if tool_name in _CALENDAR_WRITE_TOOLS:
        output["calendar_apply_status"] = "applied"
    if tool_name == "calendar.cancel_hold":
        output["compensation_category"] = (
            "compensation_completed"
            if connector_output.get("cancellation_status") == "cancelled"
            else "compensation_idempotent_missing"
        )
    return output


def _approval_apply_blocked_output(
    *,
    tool_name: str,
    approval_id: UUID,
    failure_category: str,
    retry_category: str | None = None,
) -> dict[str, Any]:
    output = {
        "approval_id": str(approval_id),
        "approval_apply_status": "blocked",
        "failure_category": failure_category,
    }
    if retry_category is not None:
        output["retry_category"] = retry_category
    if tool_name in _CALENDAR_WRITE_TOOLS:
        output["calendar_apply_status"] = "blocked"
    return output


def _calendar_argument_refs(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "calendar.create_hold":
        return {
            "calendar_ref": arguments.get("calendar_ref"),
            "hold_ref": arguments.get("hold_ref"),
            "slot_ref": arguments.get("slot_ref"),
            "event_uid_ref": arguments.get("event_uid_ref"),
        }
    if tool_name == "calendar.cancel_hold":
        return {
            "calendar_ref": arguments.get("calendar_ref"),
            "hold_ref": arguments.get("hold_ref"),
            "event_uid_ref": arguments.get("event_uid_ref"),
            "compensation_ref": arguments.get("compensation_ref"),
            "cancellation_reason_category": arguments.get("cancellation_reason_category"),
        }
    return {}


def _connector_failure_category(exc: BaseException) -> str:
    raw_category = str(exc)
    if raw_category in _CONNECTOR_FAILURE_CATEGORIES:
        return raw_category
    if isinstance(exc, ConnectorTransientError):
        return "transient_connector_error"
    if isinstance(exc, ValidationError):
        return "contract_validation_failed"
    if isinstance(exc, ConnectorRegistryError):
        return "connector_not_registered"
    return "connector_rejected"


def _connector_failure_details(
    *,
    classification: str,
    failure_category: str,
    retryable_by: str | None,
) -> dict[str, Any]:
    return {
        "classification": classification,
        "failure_category": failure_category,
        "retryable_by": retryable_by,
    }


def _redacted_fields(grant: ToolGrant | None) -> list[str]:
    if grant is None:
        return []
    return [
        field for field in grant.redaction_policy.get("redact_fields", []) if isinstance(field, str)
    ]


def _audit_event(
    *,
    request: ToolGatewayRequest,
    tool_call: ToolCall,
    verdict: GatewayVerdict,
    response: ToolGatewayResponse,
    approval_package: ApprovalPackage | None = None,
    occurred_at: datetime,
    extra_details: dict[str, Any] | None = None,
) -> AuditEvent:
    details: dict[str, Any] = {
        "subject": _subject_context_for_request(request),
        "tool_call": tool_call.model_dump(mode="json"),
        "gateway_verdict": verdict.model_dump(mode="json"),
        "gateway_response": response.__dict__,
    }
    if approval_package is not None:
        details["approval_package"] = approval_package.audit_summary()
    if extra_details is not None:
        details.update(extra_details)

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
            "details": details,
        }
    )


def _connector_failure_audit_event(
    *,
    request: ToolGatewayRequest,
    tool_call: ToolCall,
    verdict: GatewayVerdict,
    occurred_at: datetime,
    failure_category: str,
    extra_details: dict[str, Any] | None = None,
) -> AuditEvent:
    details: dict[str, Any] = {
        "subject": _subject_context_for_request(request),
        "tool_call": tool_call.model_dump(mode="json"),
        "gateway_verdict": verdict.model_dump(mode="json"),
        "connector_failure": _connector_failure_details(
            classification="transient",
            failure_category=failure_category,
            retryable_by="temporal_activity_retry_policy",
        ),
    }
    if extra_details is not None:
        details.update(extra_details)
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
            "details": details,
        }
    )


def _subject_context_for_request(request: ToolGatewayRequest) -> dict[str, str]:
    subject: dict[str, str] = {"workflow_type": request.workflow_type}
    if request.subject_id is not None:
        subject["subject_id"] = request.subject_id
    if request.subject_ref is not None:
        subject["subject_ref"] = request.subject_ref
    if request.subject_summary is not None:
        subject["subject_summary"] = request.subject_summary
    return subject


def _redact(arguments: dict[str, Any], grant: ToolGrant | None) -> dict[str, Any]:
    redacted = dict(arguments)
    policy = grant.redaction_policy if grant is not None else {}
    for field in policy.get("redact_fields", []):
        if isinstance(field, str) and field in redacted:
            redacted[field] = "[redacted]"
    return redacted

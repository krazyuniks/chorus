"""Read access to the audit ports (decision-trail and tool-action audit)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import Connection
from pydantic import BaseModel, ConfigDict

from chorus.persistence._query import (
    clear_tenant_context,
    fetch_models,
    set_tenant_context,
)


class DecisionTrailEntryReadModel(BaseModel):
    """Reviewer-facing Agent Runtime decision trail row."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    invocation_id: UUID
    correlation_id: str
    workflow_id: str
    agent_id: str
    agent_role: str
    agent_version: str
    lifecycle_state: str
    prompt_reference: str
    prompt_hash: str
    provider: str
    model: str
    task_kind: str
    budget_cap_usd: Decimal
    input_summary: str
    output_summary: str
    justification: str
    outcome: str
    tool_call_ids: list[UUID]
    cost_amount: Decimal
    cost_currency: str
    duration_ms: int
    started_at: datetime
    completed_at: datetime
    contract_refs: list[str]
    raw_record: dict[str, Any]
    metadata: dict[str, Any]
    created_at: datetime


class ToolActionAuditReadModel(BaseModel):
    """Reviewer-facing Tool Gateway audit row."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    audit_event_id: UUID
    correlation_id: str
    workflow_id: str
    invocation_id: UUID | None
    tool_call_id: UUID | None
    verdict_id: UUID | None
    actor_type: str
    actor_id: str
    category: str
    action: str
    tool_name: str | None
    requested_mode: str | None
    enforced_mode: str | None
    verdict: str
    idempotency_key: str | None
    arguments_redacted: dict[str, Any]
    rewritten_arguments: dict[str, Any] | None
    reason: str | None
    connector_invocation_id: UUID | None
    occurred_at: datetime
    raw_event: dict[str, Any]
    created_at: datetime


class AuditPortStore:
    """Read surface for the decision-trail and tool-action audit ports."""

    def __init__(self, conn: Connection[Any]) -> None:
        self._conn = conn

    def set_tenant_context(self, tenant_id: str) -> None:
        set_tenant_context(self._conn, tenant_id)

    def clear_tenant_context(self) -> None:
        clear_tenant_context(self._conn)

    def list_decision_trail(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        limit: int = 500,
    ) -> list[DecisionTrailEntryReadModel]:
        if workflow_id is not None:
            return fetch_models(
                self._conn,
                DecisionTrailEntryReadModel,
                """
                SELECT
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
                    metadata,
                    created_at
                FROM decision_trail_entries
                WHERE tenant_id = %s AND workflow_id = %s
                ORDER BY started_at ASC, invocation_id ASC
                LIMIT %s
                """,
                (tenant_id, workflow_id, limit),
            )

        return fetch_models(
            self._conn,
            DecisionTrailEntryReadModel,
            """
            SELECT
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
                metadata,
                created_at
            FROM decision_trail_entries
            WHERE tenant_id = %s
            ORDER BY started_at ASC, invocation_id ASC
            LIMIT %s
            """,
            (tenant_id, limit),
        )

    def list_tool_action_audit(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        limit: int = 500,
    ) -> list[ToolActionAuditReadModel]:
        if workflow_id is not None:
            return fetch_models(
                self._conn,
                ToolActionAuditReadModel,
                """
                SELECT
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
                    created_at
                FROM tool_action_audit
                WHERE tenant_id = %s AND workflow_id = %s
                ORDER BY occurred_at ASC, audit_event_id ASC
                LIMIT %s
                """,
                (tenant_id, workflow_id, limit),
            )

        return fetch_models(
            self._conn,
            ToolActionAuditReadModel,
            """
            SELECT
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
                created_at
            FROM tool_action_audit
            WHERE tenant_id = %s
            ORDER BY occurred_at ASC, audit_event_id ASC
            LIMIT %s
            """,
            (tenant_id, limit),
        )

"""Projection and read-model access for the Phase 1A persistence slice."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, LiteralString
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from chorus.contracts.generated.events.workflow_event import EventType, WorkflowEvent
from chorus.observability import current_otel_ids

WorkflowStatus = Literal["received", "running", "completed", "escalated", "failed"]


class WorkflowRunReadModel(BaseModel):
    """Refresh-safe workflow projection consumed by the BFF/UI."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    workflow_id: str
    correlation_id: str
    lead_id: UUID
    status: WorkflowStatus
    current_step: str | None
    lead_summary: str
    last_event_id: UUID | None
    last_event_sequence: int
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime
    metadata: dict[str, Any]


class WorkflowHistoryEventReadModel(BaseModel):
    """Append-only workflow history row projected from Redpanda events."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    history_event_id: UUID
    workflow_id: str
    correlation_id: str
    source_event_id: UUID
    event_type: str
    sequence: int
    step: str | None
    payload: dict[str, Any]
    occurred_at: datetime
    created_at: datetime


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


class AgentRegistryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    agent_id: str
    role: str
    version: str
    lifecycle_state: str
    owner: str
    prompt_reference: str
    prompt_hash: str
    capability_tags: list[str]
    updated_at: datetime


class ModelRoutingPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: UUID
    tenant_id: str
    agent_role: str
    task_kind: str
    tenant_tier: str
    provider: str
    model: str
    parameters: dict[str, Any]
    budget_cap_usd: Decimal = Field(ge=0)
    fallback_policy: dict[str, Any]
    lifecycle_state: str


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


class RuntimePolicySnapshot(BaseModel):
    """Read-only governance policy state for later BFF/admin inspection."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    agents: list[AgentRegistryEntry]
    model_routes: list[ModelRoutingPolicy]
    tool_grants: list[ToolGrant]


def _status_for(event: WorkflowEvent) -> WorkflowStatus:
    match event.event_type:
        case EventType.LEAD_RECEIVED:
            return "received"
        case EventType.WORKFLOW_COMPLETED:
            return "completed"
        case EventType.WORKFLOW_ESCALATED:
            return "escalated"
        case EventType.WORKFLOW_FAILED:
            return "failed"
        case _:
            return "running"


def _current_step_for(event: WorkflowEvent) -> str | None:
    if event.step is not None:
        return event.step.value
    if event.event_type == EventType.WORKFLOW_COMPLETED:
        return "complete"
    if event.event_type == EventType.WORKFLOW_ESCALATED:
        return "escalate"
    return None


def _lead_summary_for(event: WorkflowEvent) -> str:
    lead_summary = event.payload.get("lead_summary")
    if isinstance(lead_summary, str):
        return lead_summary

    subject = event.payload.get("subject")
    if isinstance(subject, str):
        return subject

    return ""


def _metadata_for(event: WorkflowEvent) -> dict[str, Any]:
    metadata: dict[str, Any] = {"last_event_type": event.event_type.value}
    sender = event.payload.get("sender")
    if isinstance(sender, str):
        metadata["sender"] = sender
    message_id = event.payload.get("message_id")
    if isinstance(message_id, str):
        metadata["message_id"] = message_id
    source = event.payload.get("source")
    if isinstance(source, str):
        metadata["source"] = source
    return metadata


def _completed_at_for(status: WorkflowStatus, occurred_at: datetime) -> datetime | None:
    if status in {"completed", "escalated", "failed"}:
        return occurred_at
    return None


def _fetch_models[TModel: BaseModel](
    conn: Connection[Any],
    model_type: type[TModel],
    query: LiteralString,
    params: Sequence[object],
) -> list[TModel]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    return [model_type.model_validate(row) for row in rows]


class ProjectionStore:
    """Small synchronous adapter for projection writes and BFF read models."""

    def __init__(self, conn: Connection[Any]) -> None:
        self._conn = conn

    def set_tenant_context(self, tenant_id: str) -> None:
        self._conn.execute("SELECT set_config('app.tenant_id', %s, false)", (tenant_id,))

    def clear_tenant_context(self) -> None:
        self._conn.execute("SELECT set_config('app.tenant_id', '', false)")

    def append_outbox_event(self, event: WorkflowEvent) -> None:
        """Persist a workflow event outbox row using the canonical contract shape."""

        self._conn.execute(
            """
            INSERT INTO outbox_events (
                schema_name,
                schema_version,
                event_id,
                event_type,
                occurred_at,
                tenant_id,
                correlation_id,
                workflow_id,
                lead_id,
                sequence,
                step,
                payload,
                message_key,
                headers,
                metadata
            )
            VALUES (
                'workflow_event',
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            ON CONFLICT (event_id) DO NOTHING
            """,
            (
                event.schema_version,
                event.event_id,
                event.event_type.value,
                event.occurred_at,
                event.tenant_id,
                event.correlation_id,
                event.workflow_id,
                event.lead_id,
                event.sequence,
                event.step.value if event.step is not None else None,
                Jsonb(event.payload),
                event.correlation_id,
                Jsonb(
                    {
                        "correlation_id": event.correlation_id,
                        "workflow_id": event.workflow_id,
                        "tenant_id": event.tenant_id,
                    }
                ),
                Jsonb(current_otel_ids()),
            ),
        )

    def apply_workflow_event(self, event: WorkflowEvent) -> None:
        """Apply a workflow event to history and the refresh-safe read model."""

        status = _status_for(event)
        current_step = _current_step_for(event)
        completed_at = _completed_at_for(status, event.occurred_at)
        lead_summary = _lead_summary_for(event)
        metadata = _metadata_for(event)

        self._conn.execute(
            """
            INSERT INTO workflow_history_events (
                tenant_id,
                workflow_id,
                correlation_id,
                source_event_id,
                event_type,
                sequence,
                step,
                payload,
                occurred_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id, source_event_id) DO NOTHING
            """,
            (
                event.tenant_id,
                event.workflow_id,
                event.correlation_id,
                event.event_id,
                event.event_type.value,
                event.sequence,
                current_step,
                Jsonb(event.payload),
                event.occurred_at,
            ),
        )
        self._conn.execute(
            """
            INSERT INTO workflow_read_models (
                tenant_id,
                workflow_id,
                correlation_id,
                lead_id,
                status,
                current_step,
                lead_summary,
                last_event_id,
                last_event_sequence,
                started_at,
                completed_at,
                updated_at,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s)
            ON CONFLICT (tenant_id, workflow_id) DO UPDATE
            SET
                status = EXCLUDED.status,
                current_step = COALESCE(EXCLUDED.current_step, workflow_read_models.current_step),
                lead_summary = COALESCE(
                    NULLIF(EXCLUDED.lead_summary, ''),
                    workflow_read_models.lead_summary
                ),
                last_event_id = EXCLUDED.last_event_id,
                last_event_sequence = EXCLUDED.last_event_sequence,
                started_at = COALESCE(workflow_read_models.started_at, EXCLUDED.started_at),
                completed_at = COALESCE(EXCLUDED.completed_at, workflow_read_models.completed_at),
                updated_at = now(),
                metadata = workflow_read_models.metadata || EXCLUDED.metadata
            WHERE workflow_read_models.last_event_sequence < EXCLUDED.last_event_sequence
            """,
            (
                event.tenant_id,
                event.workflow_id,
                event.correlation_id,
                event.lead_id,
                status,
                current_step,
                lead_summary,
                event.event_id,
                event.sequence,
                event.occurred_at if event.event_type == EventType.WORKFLOW_STARTED else None,
                completed_at,
                Jsonb(metadata),
            ),
        )

    def record_workflow_event(self, event: WorkflowEvent) -> None:
        """Persist a workflow event to the transactional outbox.

        Activities use this interface after service-owned state changes.
        Read models are updated by the Redpanda projection worker consuming
        the relayed event stream, so replay and reconnect semantics stay
        aligned with the architecture evidence path.
        """

        with self._conn.transaction():
            self.append_outbox_event(event)

    def list_workflows(self, tenant_id: str, *, limit: int = 100) -> list[WorkflowRunReadModel]:
        return _fetch_models(
            self._conn,
            WorkflowRunReadModel,
            """
            SELECT
                tenant_id,
                workflow_id,
                correlation_id,
                lead_id,
                status,
                current_step,
                lead_summary,
                last_event_id,
                last_event_sequence,
                started_at,
                completed_at,
                updated_at,
                metadata
            FROM workflow_read_models
            WHERE tenant_id = %s
            ORDER BY updated_at DESC, workflow_id
            LIMIT %s
            """,
            (tenant_id, limit),
        )

    def get_workflow(self, tenant_id: str, workflow_id: str) -> WorkflowRunReadModel | None:
        rows = _fetch_models(
            self._conn,
            WorkflowRunReadModel,
            """
            SELECT
                tenant_id,
                workflow_id,
                correlation_id,
                lead_id,
                status,
                current_step,
                lead_summary,
                last_event_id,
                last_event_sequence,
                started_at,
                completed_at,
                updated_at,
                metadata
            FROM workflow_read_models
            WHERE tenant_id = %s AND workflow_id = %s
            """,
            (tenant_id, workflow_id),
        )
        return rows[0] if rows else None

    def list_workflow_history(
        self,
        tenant_id: str,
        workflow_id: str,
        *,
        after_sequence: int | None = None,
        limit: int = 500,
    ) -> list[WorkflowHistoryEventReadModel]:
        if after_sequence is not None:
            return _fetch_models(
                self._conn,
                WorkflowHistoryEventReadModel,
                """
                SELECT
                    tenant_id,
                    history_event_id,
                    workflow_id,
                    correlation_id,
                    source_event_id,
                    event_type,
                    sequence,
                    step,
                    payload,
                    occurred_at,
                    created_at
                FROM workflow_history_events
                WHERE tenant_id = %s AND workflow_id = %s AND sequence > %s
                ORDER BY sequence ASC, occurred_at ASC
                LIMIT %s
                """,
                (tenant_id, workflow_id, after_sequence, limit),
            )

        return _fetch_models(
            self._conn,
            WorkflowHistoryEventReadModel,
            """
            SELECT
                tenant_id,
                history_event_id,
                workflow_id,
                correlation_id,
                source_event_id,
                event_type,
                sequence,
                step,
                payload,
                occurred_at,
                created_at
            FROM workflow_history_events
            WHERE tenant_id = %s AND workflow_id = %s
            ORDER BY sequence ASC, occurred_at ASC
            LIMIT %s
            """,
            (tenant_id, workflow_id, limit),
        )

    def list_recent_workflow_history(
        self,
        tenant_id: str,
        *,
        limit: int = 100,
    ) -> list[WorkflowHistoryEventReadModel]:
        return _fetch_models(
            self._conn,
            WorkflowHistoryEventReadModel,
            """
            SELECT
                tenant_id,
                history_event_id,
                workflow_id,
                correlation_id,
                source_event_id,
                event_type,
                sequence,
                step,
                payload,
                occurred_at,
                created_at
            FROM workflow_history_events
            WHERE tenant_id = %s
            ORDER BY occurred_at DESC, sequence DESC
            LIMIT %s
            """,
            (tenant_id, limit),
        )

    def list_decision_trail(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        limit: int = 500,
    ) -> list[DecisionTrailEntryReadModel]:
        if workflow_id is not None:
            return _fetch_models(
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
                    created_at
                FROM decision_trail_entries
                WHERE tenant_id = %s AND workflow_id = %s
                ORDER BY started_at ASC, invocation_id ASC
                LIMIT %s
                """,
                (tenant_id, workflow_id, limit),
            )

        return _fetch_models(
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
            return _fetch_models(
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

        return _fetch_models(
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

    def runtime_policy_snapshot(self, tenant_id: str) -> RuntimePolicySnapshot:
        agents = _fetch_models(
            self._conn,
            AgentRegistryEntry,
            """
            SELECT
                tenant_id,
                agent_id,
                role,
                version,
                lifecycle_state,
                owner,
                prompt_reference,
                prompt_hash,
                capability_tags,
                updated_at
            FROM agent_registry
            WHERE tenant_id = %s
            ORDER BY role, agent_id, version
            """,
            (tenant_id,),
        )
        model_routes = _fetch_models(
            self._conn,
            ModelRoutingPolicy,
            """
            SELECT
                policy_id,
                tenant_id,
                agent_role,
                task_kind,
                tenant_tier,
                provider,
                model,
                parameters,
                budget_cap_usd,
                fallback_policy,
                lifecycle_state
            FROM model_routing_policies
            WHERE tenant_id = %s
            ORDER BY agent_role, task_kind
            """,
            (tenant_id,),
        )
        tool_grants = _fetch_models(
            self._conn,
            ToolGrant,
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
            ORDER BY agent_id, tool_name, mode
            """,
            (tenant_id,),
        )
        return RuntimePolicySnapshot(
            tenant_id=tenant_id,
            agents=agents,
            model_routes=model_routes,
            tool_grants=tool_grants,
        )

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
                headers
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
            ),
        )

    def apply_workflow_event(self, event: WorkflowEvent) -> None:
        """Apply a workflow event to history and the refresh-safe read model."""

        status = _status_for(event)
        current_step = _current_step_for(event)
        completed_at = _completed_at_for(status, event.occurred_at)
        lead_summary = _lead_summary_for(event)

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
                Jsonb({"last_event_type": event.event_type.value}),
            ),
        )

    def record_workflow_event(self, event: WorkflowEvent) -> None:
        """Persist a projection update and outbox row in one transaction."""

        with self._conn.transaction():
            self.append_outbox_event(event)
            self.apply_workflow_event(event)

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
                capability_tags
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

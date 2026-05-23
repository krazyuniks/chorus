"""Projection and read-model access for the workflow persistence slice."""

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

from chorus.contracts.generated.projection.workflow_event import EventType, WorkflowEvent
from chorus.observability import current_otel_ids

WorkflowStatus = Literal["received", "running", "completed", "escalated", "failed"]


class WorkflowRunReadModel(BaseModel):
    """Refresh-safe workflow projection consumed by the BFF/UI."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    workflow_id: str
    workflow_type: str
    correlation_id: str
    subject_id: UUID
    subject_ref: str | None
    status: WorkflowStatus
    current_step: str | None
    subject_summary: str
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


class CalendarProjectionReadModel(BaseModel):
    """Safe calendar approval/apply projection derived from local audit evidence."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    approval_id: UUID
    workflow_id: str
    correlation_id: str
    tool_name: str
    requested_action: str
    requested_mode: str
    enforced_mode: str
    approval_state: str
    idempotency_key_ref: str
    calendar_refs: dict[str, Any]
    projection_status: str
    source_audit_event_id: UUID
    latest_audit_event_id: UUID | None
    latest_verdict: str | None
    latest_reason: str | None
    connector_invocation_id: UUID | None
    retry_category: str | None
    compensation_category: str | None
    failure_category: str | None
    grant_ref: str | None
    policy_version_refs: dict[str, Any]
    trace_join: dict[str, Any]
    updated_at: datetime


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


class ProviderCatalogueEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalogue_id: str
    schema_version: str
    effective_from: datetime
    created_at: datetime


class ProviderCatalogueProvider(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalogue_id: str
    provider_id: str
    display_name: str
    provider_kind: str
    lifecycle_state: str
    credential_required: bool
    secret_ref_names: list[str]
    missing_credentials_behaviour: str
    data_boundary: dict[str, Any]
    operational_limits: dict[str, Any]
    audit: dict[str, Any]


class ProviderCatalogueModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalogue_id: str
    provider_id: str
    model_id: str
    display_name: str
    lifecycle_state: str
    supported_task_kinds: list[str]
    supports_structured_output: bool
    context_window_tokens: int | None
    cost_policy: dict[str, Any]


class ModelRouteVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_id: UUID
    route_version: int
    lifecycle_state: str
    tenant_id: str
    agent_role: str
    task_kind: str
    tenant_tier: str
    provider_catalogue_id: str
    provider_id: str
    model_id: str
    parameters: dict[str, Any]
    budget_cap_usd: Decimal = Field(ge=0)
    max_latency_ms: int = Field(ge=1)
    fallback_policy: dict[str, Any]
    eval_required: bool
    eval_fixture_refs: list[str]
    promotion: dict[str, Any]
    created_at: datetime


class RuntimePolicySnapshot(BaseModel):
    """Read-only governance policy state for later BFF/admin inspection."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    agents: list[AgentRegistryEntry]
    model_routes: list[ModelRoutingPolicy]
    tool_grants: list[ToolGrant]


class ProviderGovernanceSnapshot(BaseModel):
    """Read-only provider catalogue and route-version state."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    catalogues: list[ProviderCatalogueEntry]
    providers: list[ProviderCatalogueProvider]
    provider_models: list[ProviderCatalogueModel]
    route_versions: list[ModelRouteVersion]


def _status_for(event: WorkflowEvent) -> WorkflowStatus:
    match event.event_type:
        case EventType.ENQUIRY_RECEIVED:
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
        return event.step
    if event.event_type == EventType.WORKFLOW_COMPLETED:
        return "complete"
    if event.event_type == EventType.WORKFLOW_ESCALATED:
        return "escalate"
    return None


def _subject_summary_for(event: WorkflowEvent) -> str:
    enquiry_summary = event.payload.get("enquiry_summary")
    if isinstance(enquiry_summary, str):
        return enquiry_summary

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
    channel = event.payload.get("channel")
    if isinstance(channel, str):
        metadata["channel"] = channel
    adapter_id = event.payload.get("adapter_id")
    if isinstance(adapter_id, str):
        metadata["adapter_id"] = adapter_id
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
                workflow_type,
                subject_id,
                subject_ref,
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
                event.workflow_type.value,
                event.subject_id,
                event.subject_ref,
                event.sequence,
                event.step,
                Jsonb(event.payload),
                event.correlation_id,
                Jsonb(
                    {
                        "correlation_id": event.correlation_id,
                        "workflow_id": event.workflow_id,
                        "tenant_id": event.tenant_id,
                        "workflow_type": event.workflow_type.value,
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
        subject_summary = _subject_summary_for(event)
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
        if event.subject_id is None:
            return
        self._conn.execute(
            """
            INSERT INTO workflow_read_models (
                tenant_id,
                workflow_id,
                workflow_type,
                correlation_id,
                subject_id,
                subject_ref,
                status,
                current_step,
                subject_summary,
                last_event_id,
                last_event_sequence,
                started_at,
                completed_at,
                updated_at,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s)
            ON CONFLICT (tenant_id, workflow_id) DO UPDATE
            SET
                status = EXCLUDED.status,
                current_step = COALESCE(EXCLUDED.current_step, workflow_read_models.current_step),
                subject_summary = COALESCE(
                    NULLIF(EXCLUDED.subject_summary, ''),
                    workflow_read_models.subject_summary
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
                event.workflow_type.value,
                event.correlation_id,
                event.subject_id,
                event.subject_ref,
                status,
                current_step,
                subject_summary,
                event.event_id,
                event.sequence,
                event.occurred_at if event.event_type == EventType.WORKFLOW_STARTED else None,
                completed_at,
                Jsonb(metadata),
            ),
        )

    def record_workflow_event(self, event: WorkflowEvent) -> None:
        """Persist a workflow event to the transactional outbox."""

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
                workflow_type,
                correlation_id,
                subject_id,
                subject_ref,
                status,
                current_step,
                subject_summary,
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
                workflow_type,
                correlation_id,
                subject_id,
                subject_ref,
                status,
                current_step,
                subject_summary,
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
                    metadata,
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

    def list_calendar_projections(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        limit: int = 100,
    ) -> list[CalendarProjectionReadModel]:
        return _fetch_models(
            self._conn,
            CalendarProjectionReadModel,
            """
            SELECT
                p.tenant_id,
                p.approval_id,
                p.workflow_id,
                p.correlation_id,
                p.tool_name,
                p.requested_action,
                p.requested_mode,
                p.enforced_mode,
                p.approval_state,
                p.idempotency_key_ref,
                COALESCE(p.metadata->'calendar_refs', '{}'::jsonb) AS calendar_refs,
                CASE
                    WHEN latest.raw_event->'details'->'connector_failure'->>'classification'
                        = 'transient'
                        THEN 'calendar_hold_retry_pending'
                    WHEN latest.raw_event->'details'->'connector_failure'
                        ->>'compensation_category' = 'compensation_failed'
                        THEN 'calendar_hold_compensation_failed'
                    WHEN latest.raw_event->'details'->'gateway_response'->'output'
                        ->>'compensation_category' = 'compensation_completed'
                        THEN 'calendar_hold_cancelled'
                    WHEN p.tool_name = 'calendar.cancel_hold'
                        AND latest.raw_event->'details'->'gateway_response'->'output'
                            ->>'calendar_apply_status' = 'applied'
                        THEN 'calendar_hold_cancelled'
                    WHEN p.tool_name = 'calendar.create_hold'
                        AND latest.raw_event->'details'->'gateway_response'->'output'
                            ->>'calendar_apply_status' = 'applied'
                        THEN 'calendar_hold_created'
                    WHEN latest.verdict = 'block'
                        THEN 'calendar_hold_blocked'
                    WHEN p.approval_state = 'approved'
                        THEN 'calendar_hold_approved_pending_apply'
                    WHEN p.approval_state = 'denied'
                        THEN 'calendar_hold_denied'
                    WHEN p.approval_state IN ('expired', 'cancelled', 'superseded')
                        THEN 'calendar_hold_' || p.approval_state
                    ELSE 'calendar_hold_requested'
                END AS projection_status,
                p.source_audit_event_id,
                latest.audit_event_id AS latest_audit_event_id,
                latest.verdict AS latest_verdict,
                latest.reason AS latest_reason,
                latest.connector_invocation_id,
                COALESCE(
                    latest.raw_event->'details'->'gateway_response'->'output'->>'retry_category',
                    CASE
                        WHEN latest.raw_event->'details'->'connector_failure'
                            ->>'classification' = 'transient'
                            THEN 'temporal_activity_retry_policy'
                        ELSE NULL
                    END
                ) AS retry_category,
                COALESCE(
                    latest.raw_event->'details'->'gateway_response'->'output'
                        ->>'compensation_category',
                    latest.raw_event->'details'->'connector_failure'
                        ->>'compensation_category'
                ) AS compensation_category,
                COALESCE(
                    latest.raw_event->'details'->'gateway_response'->'output'
                        ->>'failure_category',
                    latest.raw_event->'details'->'connector_failure'
                        ->>'failure_category'
                ) AS failure_category,
                CASE
                    WHEN p.grant_id IS NULL THEN NULL
                    ELSE 'tool_grant:' || p.grant_id::text
                END AS grant_ref,
                p.policy_version_refs,
                p.trace_join,
                COALESCE(latest.occurred_at, p.updated_at) AS updated_at
            FROM approval_packages p
            LEFT JOIN LATERAL (
                SELECT
                    audit_event_id,
                    verdict,
                    reason,
                    connector_invocation_id,
                    raw_event,
                    occurred_at
                FROM tool_action_audit
                WHERE tenant_id = p.tenant_id
                  AND tool_name = p.tool_name
                  AND raw_event->'details'->'approval_apply'->>'approval_id'
                    = p.approval_id::text
                ORDER BY occurred_at DESC, audit_event_id DESC
                LIMIT 1
            ) latest ON true
            WHERE p.tenant_id = %s
              AND (%s::text IS NULL OR p.workflow_id = %s)
            ORDER BY COALESCE(latest.occurred_at, p.updated_at) DESC, p.approval_id
            LIMIT %s
            """,
            (tenant_id, workflow_id, workflow_id, limit),
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

    def provider_governance_snapshot(self, tenant_id: str) -> ProviderGovernanceSnapshot:
        catalogues = _fetch_models(
            self._conn,
            ProviderCatalogueEntry,
            """
            SELECT
                catalogue_id,
                schema_version,
                effective_from,
                created_at
            FROM provider_catalogues
            ORDER BY effective_from DESC, catalogue_id
            """,
            (),
        )
        providers = _fetch_models(
            self._conn,
            ProviderCatalogueProvider,
            """
            SELECT
                catalogue_id,
                provider_id,
                display_name,
                provider_kind,
                lifecycle_state,
                credential_required,
                secret_ref_names,
                missing_credentials_behaviour,
                data_boundary,
                operational_limits,
                audit
            FROM provider_catalogue_providers
            ORDER BY catalogue_id, provider_id
            """,
            (),
        )
        provider_models = _fetch_models(
            self._conn,
            ProviderCatalogueModel,
            """
            SELECT
                catalogue_id,
                provider_id,
                model_id,
                display_name,
                lifecycle_state,
                supported_task_kinds,
                supports_structured_output,
                context_window_tokens,
                cost_policy
            FROM provider_catalogue_models
            ORDER BY catalogue_id, provider_id, model_id
            """,
            (),
        )
        route_versions = _fetch_models(
            self._conn,
            ModelRouteVersion,
            """
            SELECT
                route_id,
                route_version,
                lifecycle_state,
                tenant_id,
                agent_role,
                task_kind,
                tenant_tier,
                provider_catalogue_id,
                provider_id,
                model_id,
                parameters,
                budget_cap_usd,
                max_latency_ms,
                fallback_policy,
                eval_required,
                eval_fixture_refs,
                promotion,
                created_at
            FROM model_route_versions
            WHERE tenant_id = %s
            ORDER BY agent_role, task_kind, route_version
            """,
            (tenant_id,),
        )
        return ProviderGovernanceSnapshot(
            tenant_id=tenant_id,
            catalogues=catalogues,
            providers=providers,
            provider_models=provider_models,
            route_versions=route_versions,
        )

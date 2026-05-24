"""Workflow projection writes and read access for the projection port.

The projection port owns the workflow event outbox + history + read-model
write side (`record_workflow_event` / `apply_workflow_event`), the workflow
read surface consumed by the BFF (`list_workflows`, `get_workflow`,
`list_workflow_history`, `list_recent_workflow_history`), and the calendar
projection that derives from approval packages + tool-action audit
(`list_calendar_projections`).

The audit ports (decision-trail + tool-action audit), the runtime-policy
snapshot, and the provider-governance snapshot each live in their own
sibling module after the R3 F decomposition.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict

from chorus.contracts.generated.projection.workflow_event import EventType, WorkflowEvent
from chorus.observability import current_otel_ids
from chorus.persistence._query import (
    clear_tenant_context,
    fetch_models,
    set_tenant_context,
)

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


class ProjectionStore:
    """Workflow projection writes plus the workflow and calendar read surface."""

    def __init__(self, conn: Connection[Any]) -> None:
        self._conn = conn

    def set_tenant_context(self, tenant_id: str) -> None:
        set_tenant_context(self._conn, tenant_id)

    def clear_tenant_context(self) -> None:
        clear_tenant_context(self._conn)

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
        return fetch_models(
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
        rows = fetch_models(
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
            return fetch_models(
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

        return fetch_models(
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
        return fetch_models(
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

    def list_calendar_projections(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        limit: int = 100,
    ) -> list[CalendarProjectionReadModel]:
        return fetch_models(
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

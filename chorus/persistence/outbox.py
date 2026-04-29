"""Transactional outbox state transitions for schema-governed workflow events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, cast
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row

from chorus.contracts.generated.events.workflow_event import WorkflowEvent


@dataclass(frozen=True)
class OutboxWorkflowEvent:
    """A claimed outbox row aligned to the canonical workflow_event contract."""

    outbox_id: UUID
    topic: str
    message_key: str
    attempts: int
    headers: dict[str, Any]
    event: WorkflowEvent


def _row_to_outbox_event(row: dict[str, Any]) -> OutboxWorkflowEvent:
    event = WorkflowEvent.model_validate(
        {
            "schema_version": row["schema_version"],
            "event_id": row["event_id"],
            "event_type": row["event_type"],
            "occurred_at": row["occurred_at"],
            "tenant_id": row["tenant_id"],
            "correlation_id": row["correlation_id"],
            "workflow_id": row["workflow_id"],
            "lead_id": row["lead_id"],
            "sequence": row["sequence"],
            "step": row["step"],
            "payload": row["payload"],
        }
    )
    raw_headers = row["headers"]
    headers = cast(dict[str, Any], raw_headers) if isinstance(raw_headers, dict) else {}
    return OutboxWorkflowEvent(
        outbox_id=row["outbox_id"],
        topic=row["topic"],
        message_key=row["message_key"],
        attempts=row["attempts"],
        headers=headers,
        event=event,
    )


class OutboxStore:
    """Owns safe claiming and lifecycle transitions for outbox rows."""

    def __init__(self, conn: Connection[Any]) -> None:
        self._conn = conn

    def claim_pending(self, *, limit: int = 100) -> list[OutboxWorkflowEvent]:
        """Claim due rows with `FOR UPDATE SKIP LOCKED` and mark them publishing.

        Claiming increments `attempts`, so each publishing lease corresponds to
        one concrete Redpanda publish attempt. Rows already sent are never
        returned; failed rows are retried only after `next_attempt_at`.
        """

        if limit < 1:
            return []

        with self._conn.transaction(), self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                WITH candidates AS (
                    SELECT outbox_id
                    FROM outbox_events
                    WHERE status IN ('pending', 'failed')
                      AND next_attempt_at <= now()
                    ORDER BY created_at, outbox_id
                    FOR UPDATE SKIP LOCKED
                    LIMIT %s
                )
                UPDATE outbox_events AS events
                SET
                    status = 'publishing',
                    attempts = events.attempts + 1,
                    last_error = NULL,
                    updated_at = now()
                FROM candidates
                WHERE events.outbox_id = candidates.outbox_id
                RETURNING
                    events.outbox_id,
                    events.schema_version,
                    events.event_id,
                    events.event_type,
                    events.occurred_at,
                    events.tenant_id,
                    events.correlation_id,
                    events.workflow_id,
                    events.lead_id,
                    events.sequence,
                    events.step,
                    events.payload,
                    events.topic,
                    events.message_key,
                    events.headers,
                    events.attempts
                """,
                (limit,),
            )
            rows = cur.fetchall()

        return [_row_to_outbox_event(row) for row in rows]

    def mark_sent(self, outbox_id: UUID) -> None:
        """Mark a claimed event sent. Repeating this transition is harmless."""

        self._conn.execute(
            """
            UPDATE outbox_events
            SET
                status = 'sent',
                sent_at = COALESCE(sent_at, now()),
                last_error = NULL,
                updated_at = now()
            WHERE outbox_id = %s
              AND status IN ('publishing', 'sent')
            """,
            (outbox_id,),
        )

    def mark_failed(
        self,
        outbox_id: UUID,
        *,
        error: str,
        retry_delay: timedelta = timedelta(seconds=30),
    ) -> None:
        """Mark a claimed event failed and schedule its next publish attempt."""

        retry_seconds = max(0.0, retry_delay.total_seconds())
        self._conn.execute(
            """
            UPDATE outbox_events
            SET
                status = 'failed',
                last_error = left(%s, 2000),
                next_attempt_at = now() + (%s * interval '1 second'),
                updated_at = now()
            WHERE outbox_id = %s
              AND status IN ('publishing', 'failed')
            """,
            (error, retry_seconds, outbox_id),
        )

    def release_stale_publishing(
        self,
        *,
        older_than: timedelta = timedelta(minutes=5),
    ) -> int:
        """Return abandoned publishing leases to the retry path."""

        older_than_seconds = max(0.0, older_than.total_seconds())
        result = self._conn.execute(
            """
            UPDATE outbox_events
            SET
                status = 'failed',
                last_error = 'publishing lease expired',
                next_attempt_at = now(),
                updated_at = now()
            WHERE status = 'publishing'
              AND updated_at < now() - (%s * interval '1 second')
            """,
            (older_than_seconds,),
        )
        return result.rowcount or 0

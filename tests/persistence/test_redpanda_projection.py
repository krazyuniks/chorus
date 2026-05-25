from __future__ import annotations

from uuid import uuid4

import psycopg

from chorus.contracts.generated.projection.workflow_event import WorkflowEvent
from chorus.persistence import OutboxStore, ProjectionStore
from chorus.persistence.redpanda import (
    RedpandaWorkflowEventConsumer,
    RedpandaWorkflowEventPublisher,
)

TEST_DATABASE_PREFIX = "chorus_redpanda_test"


def _workflow_event(*, topic_token: str) -> WorkflowEvent:
    return WorkflowEvent.model_validate(
        {
            "schema_version": "1.0.0",
            "event_id": str(uuid4()),
            "event_type": "workflow.started",
            "occurred_at": "2026-04-29T12:00:00Z",
            "tenant_id": "tenant_demo",
            "correlation_id": f"cor_{topic_token}",
            "workflow_id": f"uc1-enq-{topic_token}",
            "workflow_type": "uc1_enquiry_qualification",
            "subject_id": str(uuid4()),
            "subject_ref": f"enq_redpanda_{topic_token[:12]}",
            "sequence": 1,
            "step": "intake",
            "payload": {
                "subject_summary": "Redpanda projection fixture",
                "status": "started",
            },
        }
    )


def test_outbox_event_relays_through_redpanda_and_projects_idempotently(
    migrated_database_url: str,
    redpanda_bootstrap: str,
) -> None:
    topic_token = uuid4().hex
    topic = f"chorus.workflow.events.test.{topic_token}"
    event = _workflow_event(topic_token=topic_token)

    with psycopg.connect(migrated_database_url) as conn:
        store = ProjectionStore(conn)
        store.record_workflow_event(event)
        conn.execute(
            "UPDATE outbox_events SET topic = %s WHERE event_id = %s",
            (topic, event.event_id),
        )
        outbox = OutboxStore(conn)
        claimed = outbox.claim_pending(limit=1)

        publisher = RedpandaWorkflowEventPublisher(bootstrap_servers=redpanda_bootstrap)
        publisher.publish(claimed[0])
        outbox.mark_sent(claimed[0].outbox_id)

    consumer = RedpandaWorkflowEventConsumer(
        bootstrap_servers=redpanda_bootstrap,
        group_id=f"chorus-projection-test-{topic_token}",
        topics=(topic,),
    )
    try:
        consumed = None
        for _ in range(10):
            consumed = consumer.poll(timeout=1)
            if consumed is not None:
                break
        assert consumed is not None
        assert consumed.event == event

        with psycopg.connect(migrated_database_url) as conn:
            store = ProjectionStore(conn)
            store.apply_workflow_event(consumed.event)
            store.apply_workflow_event(consumed.event)
            consumer.commit()

            read_model = store.get_workflow("tenant_demo", event.workflow_id)
            status = conn.execute(
                """
                SELECT status, attempts, sent_at IS NOT NULL
                FROM outbox_events
                WHERE event_id = %s
                """,
                (event.event_id,),
            ).fetchone()
            history_count = conn.execute(
                "SELECT count(*) FROM workflow_history_events WHERE source_event_id = %s",
                (event.event_id,),
            ).fetchone()
    finally:
        consumer.close()

    assert read_model is not None
    assert read_model.status == "running"
    assert read_model.current_step == "intake"
    assert read_model.subject_summary == "Redpanda projection fixture"
    assert status == ("sent", 1, True)
    assert history_count == (1,)

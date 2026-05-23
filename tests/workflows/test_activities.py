from __future__ import annotations

from uuid import uuid4

from chorus.contracts.generated.projection.workflow_event import WorkflowEvent
from chorus.workflows.activities import WorkflowEventRecorder
from chorus.workflows.types import WorkflowEventCommand


class FakeWorkflowEventSink:
    def __init__(self) -> None:
        self.events: list[WorkflowEvent] = []

    def record_workflow_event(self, event: WorkflowEvent) -> None:
        self.events.append(event)


def test_workflow_event_recorder_uses_projection_store_interface() -> None:
    sink = FakeWorkflowEventSink()
    recorder = WorkflowEventRecorder(lambda: sink)
    subject_id = str(uuid4())

    result = recorder.record(
        WorkflowEventCommand(
            tenant_id="tenant_demo",
            correlation_id="cor_event_recorder",
            workflow_id="uc1-enq-event-recorder",
            workflow_type="uc1_enquiry_qualification",
            subject_id=subject_id,
            subject_ref="enq_motor_private_001",
            sequence=3,
            event_type="workflow.step.completed",
            step="missing_data_request_draft",
            payload={
                "enquiry_summary": "Motor cover enquiry",
                "draft_summary": "Drafted missing-data request",
            },
        )
    )

    assert result.sequence == 3
    assert result.event_type == "workflow.step.completed"
    assert result.step == "missing_data_request_draft"
    assert len(sink.events) == 1

    event = sink.events[0]
    assert event.schema_version == "1.0.0"
    assert event.tenant_id == "tenant_demo"
    assert event.workflow_id == "uc1-enq-event-recorder"
    assert event.workflow_type.value == "uc1_enquiry_qualification"
    assert str(event.subject_id) == subject_id
    assert event.subject_ref == "enq_motor_private_001"
    assert event.payload["draft_summary"] == "Drafted missing-data request"

from __future__ import annotations

from uuid import uuid4

from chorus.contracts.generated.events.workflow_event import WorkflowEvent
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

    result = recorder.record(
        WorkflowEventCommand(
            tenant_id="tenant_demo",
            correlation_id="cor_event_recorder",
            workflow_id="lighthouse-event-recorder",
            lead_id=str(uuid4()),
            sequence=3,
            event_type="workflow.step.completed",
            step="draft",
            payload={"lead_summary": "Need help", "draft_summary": "Drafted"},
        )
    )

    assert result.sequence == 3
    assert result.event_type == "workflow.step.completed"
    assert result.step == "draft"
    assert len(sink.events) == 1

    event = sink.events[0]
    assert event.schema_version == "1.0.0"
    assert event.tenant_id == "tenant_demo"
    assert event.workflow_id == "lighthouse-event-recorder"
    assert event.payload["draft_summary"] == "Drafted"

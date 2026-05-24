"""UC1 enquiry-qualification workflow tests on the shared spine.

The replay tests run the workflow against an in-memory time-skipping
WorkflowEnvironment and immediately replay the resulting Temporal history
against the workflow class - this gives the determinism evidence
``just test-replay`` needs without persisting JSON fixtures. Checkpoint G
(eval reshape) introduces captured-transcript replay fixtures; until then
the inline run-and-replay pattern is the durable substrate.
"""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest
from temporalio import activity
from temporalio.client import WorkflowHistory
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

from chorus.workflows.spine import (
    ACTIVITY_INVOKE_AGENT_RUNTIME,
    ACTIVITY_INVOKE_TOOL_GATEWAY,
    ACTIVITY_RECORD_RETRY_EXHAUSTION_DLQ,
    ACTIVITY_RECORD_WORKFLOW_EVENT,
)
from chorus.workflows.types import (
    AgentInvocationRequest,
    AgentInvocationResponse,
    EnquiryAttachmentSummary,
    EnquirySender,
    RetryExhaustionDlqCommand,
    RetryExhaustionDlqResult,
    ToolGatewayRequest,
    ToolGatewayResponse,
    Uc1EnquiryIntake,
    Uc1WorkflowResult,
    WorkflowEventCommand,
    WorkflowEventResult,
)
from chorus.workflows.uc1 import Uc1EnquiryQualificationWorkflow


def _sample_intake() -> Uc1EnquiryIntake:
    return Uc1EnquiryIntake(
        schema_version="1.0.0",
        enquiry_id=str(uuid4()),
        tenant_id="tenant_demo",
        correlation_id="cor_uc1_happy",
        channel="email",
        adapter_id="email-channel",
        message_id="<enquiry-motor-001@example.test>",
        received_at="2026-04-29T10:00:00+00:00",
        from_address=EnquirySender(display_name="Alex Morgan", email="alex.morgan@example.test"),
        to_recipients=["enquiries@broker-firm.local"],
        subject="Motor cover enquiry: 2018 hatchback",
        body_text="Looking for third-party fire and theft cover.",
        message_headers={"Message-ID": ["<enquiry-motor-001@example.test>"]},
        attachments_summary=[
            EnquiryAttachmentSummary(filename="brief.txt", content_type="text/plain", size_bytes=10)
        ],
        enquiry_ref="enq_motor_private_001",
    )


def _record_activity_factory(
    events: list[WorkflowEventCommand],
):
    @activity.defn(name=ACTIVITY_RECORD_WORKFLOW_EVENT)
    async def fake_record(command: WorkflowEventCommand) -> WorkflowEventResult:
        events.append(command)
        return WorkflowEventResult(
            event_id=str(uuid4()),
            sequence=command.sequence,
            event_type=command.event_type,
            step=command.step,
        )

    return fake_record


def _agent_activity_factory(
    *,
    failing: bool = False,
):
    @activity.defn(name=ACTIVITY_INVOKE_AGENT_RUNTIME)
    async def fake_agent(request: AgentInvocationRequest) -> AgentInvocationResponse:
        if failing:
            raise RuntimeError("classifier_failure_fixture")
        structured: dict[str, object] = {}
        next_step = "continue"
        if request.task_kind == "missing_data_request_draft":
            structured = {
                "draft_body_text": "Please confirm postcode and licence date.",
                "customer_ref": "cust_demo_001",
                "missing_data_request_ref": "mdr_demo_001",
            }
        if request.task_kind == "missing_data_request_validation":
            structured = {"validation": "approved"}
            next_step = "send"
        return AgentInvocationResponse(
            invocation_id=str(uuid4()),
            summary=f"{request.task_kind} complete",
            confidence=0.9,
            structured_data=structured,
            recommended_next_step=next_step,
            rationale="test boundary",
        )

    return fake_agent


def _gateway_activity_factory(*, verdict: str = "propose"):
    @activity.defn(name=ACTIVITY_INVOKE_TOOL_GATEWAY)
    async def fake_gateway(request: ToolGatewayRequest) -> ToolGatewayResponse:
        return ToolGatewayResponse(
            verdict_id=str(uuid4()),
            tool_call_id=str(uuid4()),
            audit_event_id=str(uuid4()),
            verdict=verdict,
            enforced_mode=request.mode,
            reason=f"test gateway {verdict}",
            connector_invocation_id=str(uuid4()),
            output={"accepted_arguments": request.arguments},
        )

    return fake_gateway


def _retry_exhaustion_dlq_activity_factory(commands: list[RetryExhaustionDlqCommand]):
    @activity.defn(name=ACTIVITY_RECORD_RETRY_EXHAUSTION_DLQ)
    async def fake_retry_exhaustion_dlq(
        command: RetryExhaustionDlqCommand,
    ) -> RetryExhaustionDlqResult:
        commands.append(command)
        return RetryExhaustionDlqResult(
            outbox_id=str(uuid4()),
            event_id=str(uuid4()),
            audit_event_id=str(uuid4()),
            action="workflow.retry_exhausted.dlq_recorded",
            outbox_status="dlq",
            verdict="recorded",
            reason=command.failure_reason,
            sequence=command.sequence,
        )

    return fake_retry_exhaustion_dlq


@pytest.mark.asyncio
async def test_uc1_workflow_happy_path_transitions_and_replays() -> None:
    events: list[WorkflowEventCommand] = []
    intake = _sample_intake()

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="test-uc1-happy",
            workflows=[Uc1EnquiryQualificationWorkflow],
            activities=[
                _record_activity_factory(events),
                _agent_activity_factory(),
                _gateway_activity_factory(),
            ],
        ),
    ):
        result = await env.client.execute_workflow(
            "Uc1EnquiryQualificationWorkflow",
            intake,
            id="uc1-workflow-happy-test",
            task_queue="test-uc1-happy",
            result_type=Uc1WorkflowResult,
        )
    assert result.outcome == "completed"
    assert result.path == [
        "intake",
        "classification",
        "qualification",
        "missing_data_request_draft",
        "missing_data_request_validation",
        "missing_data_request_send",
        "complete",
    ]
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert events[0].event_type == "enquiry.received"
    assert all(event.payload.get("subject_summary") == intake.subject for event in events)
    assert events[-1].event_type == "workflow.completed"


@pytest.mark.asyncio
async def test_uc1_workflow_replay_against_inline_history() -> None:
    events: list[WorkflowEventCommand] = []

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="test-uc1-replay",
            workflows=[Uc1EnquiryQualificationWorkflow],
            activities=[
                _record_activity_factory(events),
                _agent_activity_factory(),
                _gateway_activity_factory(),
            ],
        ),
    ):
        await env.client.execute_workflow(
            "Uc1EnquiryQualificationWorkflow",
            _sample_intake(),
            id="uc1-workflow-replay-test",
            task_queue="test-uc1-replay",
            result_type=Uc1WorkflowResult,
        )
        handle = env.client.get_workflow_handle("uc1-workflow-replay-test")
        history = await handle.fetch_history()

    replayer = Replayer(workflows=[Uc1EnquiryQualificationWorkflow])
    workflow_history = WorkflowHistory(history.workflow_id, history.events)
    await replayer.replay_workflow(workflow_history)


@pytest.mark.asyncio
async def test_uc1_workflow_escalates_on_gateway_block() -> None:
    events: list[WorkflowEventCommand] = []

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="test-uc1-block",
            workflows=[Uc1EnquiryQualificationWorkflow],
            activities=[
                _record_activity_factory(events),
                _agent_activity_factory(),
                _gateway_activity_factory(verdict="block"),
            ],
        ),
    ):
        intake = replace(
            _sample_intake(),
            tenant_id="tenant_demo_alt",
            correlation_id="cor_uc1_forbidden_write",
        )
        result = await env.client.execute_workflow(
            "Uc1EnquiryQualificationWorkflow",
            intake,
            id="uc1-workflow-forbidden-write-test",
            task_queue="test-uc1-block",
            result_type=Uc1WorkflowResult,
        )

    assert result.outcome == "escalated"
    assert result.escalation_reason == "tool gateway returned block"
    assert result.path[-1] == "escalate"
    assert events[-1].event_type == "workflow.escalated"


@pytest.mark.asyncio
async def test_uc1_workflow_passes_correlation_to_retry_dlq_activity() -> None:
    events: list[WorkflowEventCommand] = []
    dlq_commands: list[RetryExhaustionDlqCommand] = []
    intake = _sample_intake()

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="test-uc1-retry-dlq",
            workflows=[Uc1EnquiryQualificationWorkflow],
            activities=[
                _record_activity_factory(events),
                _agent_activity_factory(failing=True),
                _retry_exhaustion_dlq_activity_factory(dlq_commands),
            ],
        ),
    ):
        result = await env.client.execute_workflow(
            "Uc1EnquiryQualificationWorkflow",
            intake,
            id="uc1-workflow-retry-dlq-test",
            task_queue="test-uc1-retry-dlq",
            result_type=Uc1WorkflowResult,
        )

    assert result.outcome == "escalated"
    assert len(dlq_commands) == 1
    command = dlq_commands[0]
    assert command.workflow_type == "uc1_enquiry_qualification"
    assert command.workflow_actor_id == "uc1.workflow"
    assert command.subject_id == intake.enquiry_id
    assert command.subject_ref == "enq_motor_private_001"
    assert command.subject_summary == intake.subject
    assert command.failed_step == "classification"
    assert events[-1].event_type == "workflow.escalated"

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from temporalio import activity
from temporalio.client import WorkflowHistory
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

from chorus.workflows.lighthouse import (
    ACTIVITY_INVOKE_AGENT_RUNTIME,
    ACTIVITY_INVOKE_TOOL_GATEWAY,
    ACTIVITY_RECORD_WORKFLOW_EVENT,
    LighthouseWorkflow,
)
from chorus.workflows.types import (
    AgentInvocationRequest,
    AgentInvocationResponse,
    LeadSender,
    LighthouseWorkflowInput,
    LighthouseWorkflowResult,
    ToolGatewayRequest,
    ToolGatewayResponse,
    WorkflowEventCommand,
    WorkflowEventResult,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
HAPPY_HISTORY = FIXTURE_DIR / "lighthouse_happy_history.json"
LOW_CONFIDENCE_HISTORY = FIXTURE_DIR / "lighthouse_low_confidence_history.json"


def sample_lead() -> LighthouseWorkflowInput:
    return LighthouseWorkflowInput(
        schema_version="1.0.0",
        lead_id=str(uuid4()),
        tenant_id="tenant_demo",
        correlation_id="cor_workflow_happy",
        source="mailpit_smtp",
        message_id="<lead-acme-001@example.test>",
        received_at="2026-04-29T10:00:00+00:00",
        sender=LeadSender(display_name="Alex Morgan", email="alex.morgan@example.test"),
        recipients=["leads@chorus.local"],
        subject="Need help choosing a CRM automation partner",
        body_text="We are looking for help qualifying new inbound enquiries.",
        message_headers={"Message-ID": ["<lead-acme-001@example.test>"]},
        attachments_summary=[],
    )


def low_confidence_lead() -> LighthouseWorkflowInput:
    lead = sample_lead()
    return LighthouseWorkflowInput(
        schema_version=lead.schema_version,
        lead_id=lead.lead_id,
        tenant_id=lead.tenant_id,
        correlation_id="cor_workflow_low_confidence",
        source=lead.source,
        message_id="<lead-low-confidence-001@example.test>",
        received_at=lead.received_at,
        sender=lead.sender,
        recipients=lead.recipients,
        subject="Low-confidence research partner enquiry",
        body_text=(
            "This low-confidence research fixture has sparse company context and "
            "should trigger deeper research before qualification."
        ),
        message_headers={"Message-ID": ["<lead-low-confidence-001@example.test>"]},
        attachments_summary=lead.attachments_summary,
    )


def test_lighthouse_workflow_history_fixture_exists() -> None:
    assert HAPPY_HISTORY.exists()
    assert LOW_CONFIDENCE_HISTORY.exists()


@pytest.mark.asyncio
async def test_lighthouse_workflow_happy_path_transitions() -> None:
    events: list[WorkflowEventCommand] = []

    @activity.defn(name=ACTIVITY_RECORD_WORKFLOW_EVENT)
    async def fake_record(command: WorkflowEventCommand) -> WorkflowEventResult:
        events.append(command)
        return WorkflowEventResult(
            event_id=str(uuid4()),
            sequence=command.sequence,
            event_type=command.event_type,
            step=command.step,
        )

    @activity.defn(name=ACTIVITY_INVOKE_AGENT_RUNTIME)
    async def fake_agent(request: AgentInvocationRequest) -> AgentInvocationResponse:
        structured_data: dict[str, object] = {}
        next_step = "continue"
        if request.task_kind == "response_draft":
            structured_data = {"draft_response": "Draft response"}
        if request.task_kind == "response_validation":
            structured_data = {"validation": "approved"}
            next_step = "send"
        return AgentInvocationResponse(
            invocation_id=str(uuid4()),
            summary=f"{request.task_kind} complete",
            confidence=0.9,
            structured_data=structured_data,
            recommended_next_step=next_step,
            rationale="test boundary",
        )

    @activity.defn(name=ACTIVITY_INVOKE_TOOL_GATEWAY)
    async def fake_gateway(request: ToolGatewayRequest) -> ToolGatewayResponse:
        return ToolGatewayResponse(
            verdict_id=str(uuid4()),
            tool_call_id=str(uuid4()),
            audit_event_id=str(uuid4()),
            verdict="allow",
            enforced_mode=request.mode,
            reason="proposal accepted by test gateway",
            connector_invocation_id=str(uuid4()),
            output={"accepted_arguments": request.arguments},
        )

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="test-lighthouse",
            workflows=[LighthouseWorkflow],
            activities=[fake_record, fake_agent, fake_gateway],
        ),
    ):
        result = await env.client.execute_workflow(
            "LighthouseWorkflow",
            sample_lead(),
            id="lighthouse-workflow-happy-test",
            task_queue="test-lighthouse",
            result_type=LighthouseWorkflowResult,
        )

    assert result.outcome == "completed"
    assert result.path == [
        "intake",
        "research_qualification",
        "draft",
        "validation",
        "propose_send",
        "complete",
    ]
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert events[0].event_type == "lead.received"
    assert events[-1].event_type == "workflow.completed"


@pytest.mark.asyncio
async def test_lighthouse_workflow_low_confidence_research_loops_once() -> None:
    events: list[WorkflowEventCommand] = []
    agent_requests: list[AgentInvocationRequest] = []

    @activity.defn(name=ACTIVITY_RECORD_WORKFLOW_EVENT)
    async def fake_record(command: WorkflowEventCommand) -> WorkflowEventResult:
        events.append(command)
        return WorkflowEventResult(
            event_id=str(uuid4()),
            sequence=command.sequence,
            event_type=command.event_type,
            step=command.step,
        )

    @activity.defn(name=ACTIVITY_INVOKE_AGENT_RUNTIME)
    async def fake_agent(request: AgentInvocationRequest) -> AgentInvocationResponse:
        agent_requests.append(request)
        structured_data: dict[str, object] = {}
        next_step = "continue"
        confidence = 0.9
        if request.task_kind == "company_research":
            attempt = int(request.input["research_attempt"])
            if attempt == 1:
                next_step = "deeper_research"
                confidence = 0.42
            structured_data = {"research_attempt": attempt}
        if request.task_kind == "response_draft":
            structured_data = {"draft_response": "Draft response"}
        if request.task_kind == "response_validation":
            structured_data = {"validation": "approved"}
            next_step = "send"
        return AgentInvocationResponse(
            invocation_id=str(uuid4()),
            summary=f"{request.task_kind} complete",
            confidence=confidence,
            structured_data=structured_data,
            recommended_next_step=next_step,
            rationale="test boundary",
        )

    @activity.defn(name=ACTIVITY_INVOKE_TOOL_GATEWAY)
    async def fake_gateway(request: ToolGatewayRequest) -> ToolGatewayResponse:
        return ToolGatewayResponse(
            verdict_id=str(uuid4()),
            tool_call_id=str(uuid4()),
            audit_event_id=str(uuid4()),
            verdict="allow",
            enforced_mode=request.mode,
            reason="proposal accepted by test gateway",
            connector_invocation_id=str(uuid4()),
            output={"accepted_arguments": request.arguments},
        )

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="test-lighthouse-low-confidence",
            workflows=[LighthouseWorkflow],
            activities=[fake_record, fake_agent, fake_gateway],
        ),
    ):
        result = await env.client.execute_workflow(
            "LighthouseWorkflow",
            low_confidence_lead(),
            id="lighthouse-workflow-low-confidence-test",
            task_queue="test-lighthouse-low-confidence",
            result_type=LighthouseWorkflowResult,
        )

    assert result.outcome == "completed"
    assert result.path == [
        "intake",
        "research_qualification",
        "research_qualification",
        "draft",
        "validation",
        "propose_send",
        "complete",
    ]
    research_requests = [
        request for request in agent_requests if request.task_kind == "company_research"
    ]
    assert [request.input["research_attempt"] for request in research_requests] == [1, 2]
    assert research_requests[1].input["deeper_research"] is True
    completed_research_events = [
        event
        for event in events
        if event.event_type == "workflow.step.completed" and event.step == "research_qualification"
    ]
    assert completed_research_events[0].payload["recommended_next_step"] == "deeper_research"
    assert completed_research_events[0].payload["deeper_research_requested"] is True
    assert completed_research_events[1].payload["deeper_research_completed"] is True


@pytest.mark.asyncio
async def test_lighthouse_workflow_low_confidence_research_escalates_after_bound() -> None:
    agent_requests: list[AgentInvocationRequest] = []

    @activity.defn(name=ACTIVITY_RECORD_WORKFLOW_EVENT)
    async def fake_record(command: WorkflowEventCommand) -> WorkflowEventResult:
        return WorkflowEventResult(
            event_id=str(uuid4()),
            sequence=command.sequence,
            event_type=command.event_type,
            step=command.step,
        )

    @activity.defn(name=ACTIVITY_INVOKE_AGENT_RUNTIME)
    async def fake_agent(request: AgentInvocationRequest) -> AgentInvocationResponse:
        agent_requests.append(request)
        return AgentInvocationResponse(
            invocation_id=str(uuid4()),
            summary=f"{request.task_kind} remained ambiguous",
            confidence=0.42,
            structured_data={"research_attempt": request.input.get("research_attempt")},
            recommended_next_step="deeper_research",
            rationale="test boundary",
        )

    @activity.defn(name=ACTIVITY_INVOKE_TOOL_GATEWAY)
    async def fake_gateway(request: ToolGatewayRequest) -> ToolGatewayResponse:
        raise AssertionError(f"gateway should not be invoked after escalation: {request}")

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="test-lighthouse-low-confidence-escalate",
            workflows=[LighthouseWorkflow],
            activities=[fake_record, fake_agent, fake_gateway],
        ),
    ):
        result = await env.client.execute_workflow(
            "LighthouseWorkflow",
            low_confidence_lead(),
            id="lighthouse-workflow-low-confidence-escalate-test",
            task_queue="test-lighthouse-low-confidence-escalate",
            result_type=LighthouseWorkflowResult,
        )

    assert result.outcome == "escalated"
    assert result.path == [
        "intake",
        "research_qualification",
        "research_qualification",
        "escalate",
    ]
    assert result.escalation_reason == (
        "research confidence remained below threshold after deeper research"
    )
    assert [request.task_kind for request in agent_requests] == [
        "company_research",
        "company_research",
    ]


@pytest.mark.asyncio
async def test_lighthouse_workflow_replay_history() -> None:
    history = WorkflowHistory.from_json(
        "lighthouse-workflow-happy-fixture",
        HAPPY_HISTORY.read_text(encoding="utf-8"),
    )
    replayer = Replayer(workflows=[LighthouseWorkflow])
    await replayer.replay_workflow(history)


@pytest.mark.asyncio
async def test_lighthouse_workflow_low_confidence_replay_history() -> None:
    history = WorkflowHistory.from_json(
        "lighthouse-workflow-low-confidence-fixture",
        LOW_CONFIDENCE_HISTORY.read_text(encoding="utf-8"),
    )
    replayer = Replayer(workflows=[LighthouseWorkflow])
    await replayer.replay_workflow(history)

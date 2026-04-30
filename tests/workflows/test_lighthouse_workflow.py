from __future__ import annotations

from dataclasses import replace
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
FORBIDDEN_WRITE_HISTORY = FIXTURE_DIR / "lighthouse_forbidden_write_history.json"


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


def test_lighthouse_workflow_history_fixture_exists() -> None:
    assert HAPPY_HISTORY.exists()
    assert FORBIDDEN_WRITE_HISTORY.exists()


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
async def test_lighthouse_workflow_escalates_on_gateway_block() -> None:
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
            verdict="block",
            enforced_mode=request.mode,
            reason="explicit denied write grant",
            connector_invocation_id=None,
            output={},
        )

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="test-lighthouse-forbidden-write",
            workflows=[LighthouseWorkflow],
            activities=[fake_record, fake_agent, fake_gateway],
        ),
    ):
        lead = sample_lead()
        result = await env.client.execute_workflow(
            "LighthouseWorkflow",
            replace(
                lead,
                tenant_id="tenant_demo_alt",
                correlation_id="cor_workflow_forbidden_write",
            ),
            id="lighthouse-workflow-forbidden-write-test",
            task_queue="test-lighthouse-forbidden-write",
            result_type=LighthouseWorkflowResult,
        )

    assert result.outcome == "escalated"
    assert result.escalation_reason == "tool gateway returned block"
    assert result.path == [
        "intake",
        "research_qualification",
        "draft",
        "validation",
        "propose_send",
        "escalate",
    ]
    assert events[-1].event_type == "workflow.escalated"


@pytest.mark.asyncio
async def test_lighthouse_workflow_replay_history() -> None:
    history = WorkflowHistory.from_json(
        "lighthouse-workflow-happy-fixture",
        HAPPY_HISTORY.read_text(encoding="utf-8"),
    )
    replayer = Replayer(workflows=[LighthouseWorkflow])
    await replayer.replay_workflow(history)


@pytest.mark.asyncio
async def test_lighthouse_workflow_replay_forbidden_write_history() -> None:
    history = WorkflowHistory.from_json(
        "lighthouse-workflow-forbidden-write-fixture",
        FORBIDDEN_WRITE_HISTORY.read_text(encoding="utf-8"),
    )
    replayer = Replayer(workflows=[LighthouseWorkflow])
    await replayer.replay_workflow(history)

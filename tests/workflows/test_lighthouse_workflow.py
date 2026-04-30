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
VALIDATOR_REDRAFT_HISTORY = FIXTURE_DIR / "lighthouse_validator_redraft_history.json"


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


def validator_redraft_lead() -> LighthouseWorkflowInput:
    base = sample_lead()
    return LighthouseWorkflowInput(
        schema_version=base.schema_version,
        lead_id=base.lead_id,
        tenant_id=base.tenant_id,
        correlation_id="cor_workflow_validator_redraft",
        source=base.source,
        message_id="<lead-validator-redraft-001@example.test>",
        received_at=base.received_at,
        sender=base.sender,
        recipients=base.recipients,
        subject="validator-redraft fixture: pilot enquiry for inbound triage",
        body_text=(
            "This validator-redraft fixture intentionally seeds a thin first draft "
            "so the validator can request an operations-led pilot framing on the "
            "second pass."
        ),
        message_headers={"Message-ID": ["<lead-validator-redraft-001@example.test>"]},
        attachments_summary=base.attachments_summary,
    )


def test_lighthouse_workflow_history_fixture_exists() -> None:
    assert HAPPY_HISTORY.exists()
    assert VALIDATOR_REDRAFT_HISTORY.exists()


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
async def test_lighthouse_workflow_replay_history() -> None:
    history = WorkflowHistory.from_json(
        "lighthouse-workflow-happy-fixture",
        HAPPY_HISTORY.read_text(encoding="utf-8"),
    )
    replayer = Replayer(workflows=[LighthouseWorkflow])
    await replayer.replay_workflow(history)


@pytest.mark.asyncio
async def test_lighthouse_workflow_validator_redraft_loops_once() -> None:
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
        if request.task_kind == "response_draft":
            attempt = int(request.input.get("redraft_attempt", 1))
            structured_data = {
                "draft_response": f"Draft attempt {attempt}",
                "redraft_attempt": attempt,
            }
        if request.task_kind == "response_validation":
            attempt = int(request.input.get("redraft_attempt", 1))
            if attempt == 1:
                next_step = "redraft"
                structured_data = {
                    "validation": "redraft_requested",
                    "redraft_attempt": attempt,
                    "reason": {
                        "code": "tone_mismatch",
                        "guidance": "Reframe around an operations-led pilot.",
                    },
                }
            else:
                next_step = "send"
                structured_data = {
                    "validation": "approved",
                    "redraft_attempt": attempt,
                }
        return AgentInvocationResponse(
            invocation_id=str(uuid4()),
            summary=f"{request.task_kind} attempt {request.input.get('redraft_attempt', 1)}",
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
            task_queue="test-lighthouse-validator-redraft",
            workflows=[LighthouseWorkflow],
            activities=[fake_record, fake_agent, fake_gateway],
        ),
    ):
        result = await env.client.execute_workflow(
            "LighthouseWorkflow",
            validator_redraft_lead(),
            id="lighthouse-workflow-validator-redraft-test",
            task_queue="test-lighthouse-validator-redraft",
            result_type=LighthouseWorkflowResult,
        )

    assert result.outcome == "completed"
    assert result.path == [
        "intake",
        "research_qualification",
        "draft",
        "validation",
        "draft",
        "validation",
        "propose_send",
        "complete",
    ]
    draft_requests = [r for r in agent_requests if r.task_kind == "response_draft"]
    assert [r.input["redraft_attempt"] for r in draft_requests] == [1, 2]
    assert "validator_reason" not in draft_requests[0].input
    assert "validator_reason" in draft_requests[1].input
    assert draft_requests[1].input["validator_reason"]["structured"]["code"] == "tone_mismatch"

    validation_events = [
        e for e in events if e.event_type == "workflow.step.completed" and e.step == "validation"
    ]
    assert validation_events[0].payload["recommended_next_step"] == "redraft"
    assert validation_events[0].payload["redraft_requested"] is True
    assert validation_events[1].payload["recommended_next_step"] == "send"


@pytest.mark.asyncio
async def test_lighthouse_workflow_validator_redraft_escalates_after_bound() -> None:
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
        if request.task_kind == "response_validation":
            return AgentInvocationResponse(
                invocation_id=str(uuid4()),
                summary="validator persistently requests redraft",
                confidence=0.9,
                structured_data={
                    "validation": "redraft_requested",
                    "reason": {"code": "tone_mismatch"},
                },
                recommended_next_step="redraft",
                rationale="test boundary",
            )
        structured_data: dict[str, object] = {}
        if request.task_kind == "response_draft":
            structured_data = {
                "draft_response": "Draft response",
                "redraft_attempt": int(request.input.get("redraft_attempt", 1)),
            }
        return AgentInvocationResponse(
            invocation_id=str(uuid4()),
            summary=f"{request.task_kind} complete",
            confidence=0.9,
            structured_data=structured_data,
            recommended_next_step="continue",
            rationale="test boundary",
        )

    @activity.defn(name=ACTIVITY_INVOKE_TOOL_GATEWAY)
    async def fake_gateway(request: ToolGatewayRequest) -> ToolGatewayResponse:
        raise AssertionError(f"gateway should not be invoked after escalation: {request}")

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="test-lighthouse-validator-redraft-escalate",
            workflows=[LighthouseWorkflow],
            activities=[fake_record, fake_agent, fake_gateway],
        ),
    ):
        result = await env.client.execute_workflow(
            "LighthouseWorkflow",
            validator_redraft_lead(),
            id="lighthouse-workflow-validator-redraft-escalate-test",
            task_queue="test-lighthouse-validator-redraft-escalate",
            result_type=LighthouseWorkflowResult,
        )

    assert result.outcome == "escalated"
    assert result.escalation_reason == ("validator requested redraft beyond bounded attempts")
    assert result.path == [
        "intake",
        "research_qualification",
        "draft",
        "validation",
        "draft",
        "validation",
        "escalate",
    ]
    draft_count = sum(1 for r in agent_requests if r.task_kind == "response_draft")
    validation_count = sum(1 for r in agent_requests if r.task_kind == "response_validation")
    assert draft_count == 2
    assert validation_count == 2


@pytest.mark.asyncio
async def test_lighthouse_workflow_validator_redraft_replay_history() -> None:
    history = WorkflowHistory.from_json(
        "lighthouse-workflow-validator-redraft-fixture",
        VALIDATOR_REDRAFT_HISTORY.read_text(encoding="utf-8"),
    )
    replayer = Replayer(workflows=[LighthouseWorkflow])
    await replayer.replay_workflow(history)

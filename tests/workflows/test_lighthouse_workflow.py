from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from temporalio import activity
from temporalio.client import WorkflowHistory
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

from chorus.workflows.lighthouse import (
    ACTIVITY_INVOKE_AGENT_RUNTIME,
    ACTIVITY_INVOKE_TOOL_GATEWAY,
    ACTIVITY_RECORD_RETRY_EXHAUSTION_DLQ,
    ACTIVITY_RECORD_TOOL_FAILURE_COMPENSATION,
    ACTIVITY_RECORD_WORKFLOW_EVENT,
    LighthouseWorkflow,
)
from chorus.workflows.types import (
    AgentInvocationRequest,
    AgentInvocationResponse,
    LeadSender,
    LighthouseWorkflowInput,
    LighthouseWorkflowResult,
    RetryExhaustionDlqCommand,
    RetryExhaustionDlqResult,
    ToolFailureCompensationCommand,
    ToolFailureCompensationResult,
    ToolGatewayRequest,
    ToolGatewayResponse,
    WorkflowEventCommand,
    WorkflowEventResult,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
HAPPY_HISTORY = FIXTURE_DIR / "lighthouse_happy_history.json"
LOW_CONFIDENCE_HISTORY = FIXTURE_DIR / "lighthouse_low_confidence_history.json"
VALIDATOR_REDRAFT_HISTORY = FIXTURE_DIR / "lighthouse_validator_redraft_history.json"
FORBIDDEN_WRITE_HISTORY = FIXTURE_DIR / "lighthouse_forbidden_write_history.json"
CONNECTOR_FAILURE_HISTORY = FIXTURE_DIR / "lighthouse_connector_failure_history.json"
RETRY_EXHAUSTION_HISTORY = FIXTURE_DIR / "lighthouse_retry_exhaustion_history.json"


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


def connector_failure_lead() -> LighthouseWorkflowInput:
    base = sample_lead()
    return LighthouseWorkflowInput(
        schema_version=base.schema_version,
        lead_id=base.lead_id,
        tenant_id=base.tenant_id,
        correlation_id="cor_workflow_connector_failure",
        source=base.source,
        message_id="<lead-connector-failure-001@example.test>",
        received_at=base.received_at,
        sender=base.sender,
        recipients=base.recipients,
        subject="connector-failure fixture: Mailpit outage during proposal",
        body_text=(
            "This connector-failure fixture keeps the agent path ordinary but "
            "forces the local Mailpit connector to fail during proposal capture."
        ),
        message_headers={"Message-ID": ["<lead-connector-failure-001@example.test>"]},
        attachments_summary=base.attachments_summary,
    )


def retry_exhaustion_lead() -> LighthouseWorkflowInput:
    base = sample_lead()
    return LighthouseWorkflowInput(
        schema_version=base.schema_version,
        lead_id=base.lead_id,
        tenant_id=base.tenant_id,
        correlation_id="cor_workflow_retry_exhaustion",
        source=base.source,
        message_id="<lead-retry-exhaustion-001@example.test>",
        received_at=base.received_at,
        sender=base.sender,
        recipients=base.recipients,
        subject="retry-exhaustion fixture: persistent researcher failure",
        body_text=(
            "This retry-exhaustion fixture forces a persistent agent-runtime "
            "failure so the workflow records DLQ evidence and escalates."
        ),
        message_headers={"Message-ID": ["<lead-retry-exhaustion-001@example.test>"]},
        attachments_summary=base.attachments_summary,
    )


def test_lighthouse_workflow_history_fixture_exists() -> None:
    assert HAPPY_HISTORY.exists()
    assert LOW_CONFIDENCE_HISTORY.exists()
    assert VALIDATOR_REDRAFT_HISTORY.exists()
    assert FORBIDDEN_WRITE_HISTORY.exists()
    assert CONNECTOR_FAILURE_HISTORY.exists()
    assert RETRY_EXHAUSTION_HISTORY.exists()


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


@pytest.mark.asyncio
async def test_lighthouse_workflow_replay_forbidden_write_history() -> None:
    history = WorkflowHistory.from_json(
        "lighthouse-workflow-forbidden-write-fixture",
        FORBIDDEN_WRITE_HISTORY.read_text(encoding="utf-8"),
    )
    replayer = Replayer(workflows=[LighthouseWorkflow])
    await replayer.replay_workflow(history)


@pytest.mark.asyncio
async def test_lighthouse_workflow_connector_failure_compensates_and_escalates() -> None:
    events: list[WorkflowEventCommand] = []
    compensation_commands: list[ToolFailureCompensationCommand] = []
    gateway_attempts = 0

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
        nonlocal gateway_attempts
        gateway_attempts += 1
        raise ApplicationError("fixture transient connector failure")

    @activity.defn(name=ACTIVITY_RECORD_TOOL_FAILURE_COMPENSATION)
    async def fake_compensation(
        command: ToolFailureCompensationCommand,
    ) -> ToolFailureCompensationResult:
        compensation_commands.append(command)
        return ToolFailureCompensationResult(
            audit_event_id=str(uuid4()),
            action="connector.failure.compensated",
            verdict="recorded",
            reason=command.failure_reason,
        )

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="test-lighthouse-connector-failure",
            workflows=[LighthouseWorkflow],
            activities=[fake_record, fake_agent, fake_gateway, fake_compensation],
        ),
    ):
        result = await env.client.execute_workflow(
            "LighthouseWorkflow",
            connector_failure_lead(),
            id="lighthouse-workflow-connector-failure-test",
            task_queue="test-lighthouse-connector-failure",
            result_type=LighthouseWorkflowResult,
        )

    assert gateway_attempts == 3
    assert result.outcome == "escalated"
    assert result.escalation_reason == "tool gateway connector failure compensated and escalated"
    assert result.path == [
        "intake",
        "research_qualification",
        "draft",
        "validation",
        "propose_send",
        "escalate",
    ]
    assert len(compensation_commands) == 1
    compensation = compensation_commands[0]
    assert compensation.tool_name == "email.propose_response"
    assert compensation.mode == "propose"
    assert "fixture transient connector failure" in compensation.failure_reason

    completed_propose_send = [
        event
        for event in events
        if event.event_type == "workflow.step.completed" and event.step == "propose_send"
    ]
    assert completed_propose_send[0].payload["connector_failure"] is True
    assert events[-1].event_type == "workflow.escalated"


@pytest.mark.asyncio
async def test_lighthouse_workflow_connector_failure_replay_history() -> None:
    history = WorkflowHistory.from_json(
        "lighthouse-workflow-connector-failure-fixture",
        CONNECTOR_FAILURE_HISTORY.read_text(encoding="utf-8"),
    )
    replayer = Replayer(workflows=[LighthouseWorkflow])
    await replayer.replay_workflow(history)


@pytest.mark.asyncio
async def test_lighthouse_workflow_retry_exhaustion_records_dlq_and_escalates() -> None:
    events: list[WorkflowEventCommand] = []
    dlq_commands: list[RetryExhaustionDlqCommand] = []
    agent_attempts = 0

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
        nonlocal agent_attempts
        agent_attempts += 1
        raise ApplicationError("fixture persistent agent runtime failure")

    @activity.defn(name=ACTIVITY_INVOKE_TOOL_GATEWAY)
    async def fake_gateway(request: ToolGatewayRequest) -> ToolGatewayResponse:
        raise AssertionError(f"gateway should not be invoked after retry exhaustion: {request}")

    @activity.defn(name=ACTIVITY_RECORD_RETRY_EXHAUSTION_DLQ)
    async def fake_dlq(command: RetryExhaustionDlqCommand) -> RetryExhaustionDlqResult:
        dlq_commands.append(command)
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

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="test-lighthouse-retry-exhaustion",
            workflows=[LighthouseWorkflow],
            activities=[fake_record, fake_agent, fake_gateway, fake_dlq],
        ),
    ):
        result = await env.client.execute_workflow(
            "LighthouseWorkflow",
            retry_exhaustion_lead(),
            id="lighthouse-workflow-retry-exhaustion-test",
            task_queue="test-lighthouse-retry-exhaustion",
            result_type=LighthouseWorkflowResult,
        )

    assert agent_attempts == 3
    assert result.outcome == "escalated"
    assert result.escalation_reason == "activity retry policy exhausted; DLQ evidence recorded"
    assert result.path == ["intake", "research_qualification", "escalate"]
    assert len(dlq_commands) == 1
    dlq_command = dlq_commands[0]
    assert dlq_command.failed_activity == ACTIVITY_INVOKE_AGENT_RUNTIME
    assert dlq_command.failed_step == "research_qualification"
    assert dlq_command.attempts == 3
    assert "fixture persistent agent runtime failure" in dlq_command.failure_reason

    completed_research = [
        event
        for event in events
        if event.event_type == "workflow.step.completed" and event.step == "research_qualification"
    ]
    assert completed_research[0].payload["step_outcome"] == "retry_exhausted"
    assert completed_research[0].payload["dlq_required"] is True
    assert events[-1].event_type == "workflow.escalated"


@pytest.mark.asyncio
async def test_lighthouse_workflow_retry_exhaustion_replay_history() -> None:
    history = WorkflowHistory.from_json(
        "lighthouse-workflow-retry-exhaustion-fixture",
        RETRY_EXHAUSTION_HISTORY.read_text(encoding="utf-8"),
    )
    replayer = Replayer(workflows=[LighthouseWorkflow])
    await replayer.replay_workflow(history)

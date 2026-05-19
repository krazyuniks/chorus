from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from temporalio import activity
from temporalio.client import WorkflowHistory
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

from chorus.workflows.lighthouse import ACTIVITY_INVOKE_AGENT_RUNTIME, ACTIVITY_INVOKE_TOOL_GATEWAY
from chorus.workflows.support import (
    ACTIVITY_RECORD_SUPPORT_WORKFLOW_EVENT,
    STEP_SUPPORT_CLASSIFICATION,
    STEP_SUPPORT_COMPLETE,
    STEP_SUPPORT_CONTEXT_LOOKUP,
    STEP_SUPPORT_INTAKE,
    STEP_SUPPORT_PROPOSE,
    STEP_SUPPORT_RESOLUTION_PLAN,
    STEP_SUPPORT_VALIDATION,
    SUPPORT_AGENT_CONTRACT,
    SupportTriageWorkflow,
)
from chorus.workflows.types import (
    AgentInvocationRequest,
    AgentInvocationResponse,
    SupportWorkflowEventCommand,
    SupportWorkflowInput,
    SupportWorkflowResult,
    ToolGatewayRequest,
    ToolGatewayResponse,
    WorkflowEventResult,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SUPPORT_HAPPY_HISTORY = FIXTURE_DIR / "support_triage_happy_history.json"


def sample_support_request() -> SupportWorkflowInput:
    return SupportWorkflowInput(
        schema_version="1.0.0",
        request_ref="req_support_001",
        tenant_id="tenant_demo",
        correlation_id="cor_support_workflow_happy",
        source_ref="source_support_local_sandbox",
        received_at="2026-05-19T09:00:00+00:00",
        intake_channel_category="ticket_portal",
        account_ref="acct_demo_001",
        product_ref="prod_core_platform",
        case_ref="case_existing_001",
        severity_hint_category="sev_high",
        request_status_category="open",
        redacted_summary_ref="summary_support_001",
        attachment_refs=[],
        idempotency_ref="idem_support_001",
        routing_policy_ref="policy_support_triage_local_v1",
    )


def test_support_workflow_history_fixture_exists() -> None:
    assert SUPPORT_HAPPY_HISTORY.exists()


@pytest.mark.asyncio
async def test_support_workflow_happy_path_uses_agent_runtime_and_gateway_boundaries() -> None:
    events: list[SupportWorkflowEventCommand] = []
    agent_requests: list[AgentInvocationRequest] = []
    gateway_requests: list[ToolGatewayRequest] = []
    gateway_responses: list[ToolGatewayResponse] = []

    @activity.defn(name=ACTIVITY_RECORD_SUPPORT_WORKFLOW_EVENT)
    async def fake_record(command: SupportWorkflowEventCommand) -> WorkflowEventResult:
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
        output_refs = {
            "request_ref": "req_support_001",
            "case_ref": "case_existing_001",
        }
        next_step = "continue"
        verdict_category = "triage_continue"
        case_status_category = "open"
        if request.task_kind == "support_context_lookup":
            verdict_category = "needs_context"
        if request.task_kind == "support_resolution_plan":
            next_step = "propose_only"
            verdict_category = "propose_case_update"
            case_status_category = "pending_customer"
            output_refs |= {
                "resolution_plan_ref": "plan_support_001",
                "response_draft_ref": "response_support_001",
                "case_update_ref": "caseupd_support_001",
            }
        if request.task_kind == "support_validation":
            next_step = "complete"
            verdict_category = "propose_case_update"
            case_status_category = "pending_customer"
            output_refs |= {"validation_ref": "validation_support_001"}
        return AgentInvocationResponse(
            invocation_id=str(uuid4()),
            summary=f"{request.task_kind} complete",
            confidence=0.9,
            structured_data={
                "workflow_type": "support_triage",
                "verdict_category": verdict_category,
                "severity_category": "sev_high",
                "case_status_category": case_status_category,
                "resolution_category": "known_answer",
                "output_refs": output_refs,
                "evidence_refs": ["evidence_support_local_runtime"],
            },
            recommended_next_step=next_step,
            rationale="rationale_category_support_fixture_boundary",
        )

    @activity.defn(name=ACTIVITY_INVOKE_TOOL_GATEWAY)
    async def fake_gateway(request: ToolGatewayRequest) -> ToolGatewayResponse:
        gateway_requests.append(request)
        output: dict[str, object] = {}
        connector_invocation_id = str(uuid4())
        if request.tool_name == "ticket.lookup_case":
            output = {
                "lookup_status": "found",
                "case_ref": request.arguments["case_ref"],
                "case_status_category": "open",
            }
        elif request.tool_name == "ticket.lookup_duplicates":
            output = {
                "duplicate_status": "candidate_refs",
                "duplicate_case_refs": ["case_duplicate_001"],
            }
        elif request.tool_name == "ticket.propose_case_update":
            output = {
                "proposal_status": "recorded",
                "case_update_ref": request.arguments["case_update_ref"],
                "case_status_mutated": False,
            }
        verdict = "propose" if request.mode == "propose" else "allow"
        response = ToolGatewayResponse(
            verdict_id=str(uuid4()),
            tool_call_id=str(uuid4()),
            audit_event_id=str(uuid4()),
            verdict=verdict,
            enforced_mode=request.mode,
            reason="verdict_category_allow",
            connector_invocation_id=connector_invocation_id,
            output=output,
        )
        gateway_responses.append(response)
        return response

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="test-support-triage",
            workflows=[SupportTriageWorkflow],
            activities=[fake_record, fake_agent, fake_gateway],
        ),
    ):
        result = await env.client.execute_workflow(
            "SupportTriageWorkflow",
            sample_support_request(),
            id="support-triage-happy-test",
            task_queue="test-support-triage",
            result_type=SupportWorkflowResult,
        )

    assert result.outcome == "completed"
    assert result.path == [
        STEP_SUPPORT_INTAKE,
        STEP_SUPPORT_CLASSIFICATION,
        STEP_SUPPORT_CONTEXT_LOOKUP,
        STEP_SUPPORT_RESOLUTION_PLAN,
        STEP_SUPPORT_VALIDATION,
        STEP_SUPPORT_PROPOSE,
        STEP_SUPPORT_COMPLETE,
    ]
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert {event.workflow_type for event in events} == {"support_triage"}
    assert {event.request_ref for event in events} == {"req_support_001"}
    assert events[0].event_type == "workflow.started"
    assert events[-1].event_type == "workflow.completed"
    assert [request.expected_output_contract for request in agent_requests] == [
        SUPPORT_AGENT_CONTRACT,
        SUPPORT_AGENT_CONTRACT,
        SUPPORT_AGENT_CONTRACT,
        SUPPORT_AGENT_CONTRACT,
    ]
    assert [request.task_kind for request in agent_requests] == [
        "support_classification",
        "support_context_lookup",
        "support_resolution_plan",
        "support_validation",
    ]
    assert [request.tool_name for request in gateway_requests] == [
        "ticket.lookup_case",
        "ticket.lookup_duplicates",
        "ticket.propose_case_update",
    ]
    assert "ticket.update_status" not in {request.tool_name for request in gateway_requests}
    assert gateway_requests[-1].mode == "propose"
    assert gateway_requests[-1].agent_id == "support.resolution_planner"
    assert gateway_requests[-1].arguments["target_status_category"] == "pending_customer"
    assert gateway_responses[-1].output["case_status_mutated"] is False
    for request in gateway_requests:
        assert set(request.arguments).isdisjoint(
            {"body_text", "email", "prompt", "raw_output", "access_token", "api_key"}
        )
    for event in events:
        assert set(event.payload).isdisjoint(
            {"body_text", "email", "prompt", "raw_output", "access_token", "api_key"}
        )


@pytest.mark.asyncio
async def test_support_workflow_replay_history() -> None:
    history = WorkflowHistory.from_json(
        "support-triage-happy-fixture",
        SUPPORT_HAPPY_HISTORY.read_text(encoding="utf-8"),
    )
    replayer = Replayer(workflows=[SupportTriageWorkflow])
    await replayer.replay_workflow(history)

"""UC3 IFA suitability workflow tests on the shared spine."""

from __future__ import annotations

from uuid import uuid4

import pytest
from temporalio import activity
from temporalio.client import WorkflowHistory
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

from chorus.workflows.spine import (
    ACTIVITY_INVOKE_AGENT_RUNTIME,
    ACTIVITY_INVOKE_TOOL_GATEWAY,
    ACTIVITY_RECORD_WORKFLOW_EVENT,
    WorkflowStepKind,
)
from chorus.workflows.types import (
    AgentInvocationRequest,
    AgentInvocationResponse,
    ToolGatewayRequest,
    ToolGatewayResponse,
    Uc3AdviceEnquiry,
    Uc3AttachmentSummary,
    Uc3WorkflowResult,
    WorkflowEventCommand,
    WorkflowEventResult,
)
from chorus.workflows.uc3 import (
    UC3_IFA_SUITABILITY_INTAKE_DEFINITION,
    UC3_WORKFLOW_TYPE,
    Uc3IfaSuitabilityIntakeWorkflow,
)


def _sample_intake() -> Uc3AdviceEnquiry:
    return Uc3AdviceEnquiry(
        schema_version="1.0.0",
        advice_enquiry_id=str(uuid4()),
        tenant_id="tenant_demo",
        correlation_id="cor_uc3_happy",
        channel="web-form",
        adapter_id="web-form-channel",
        received_at="2026-05-01T09:30:00Z",
        source_payload_ref="source_payload_advice_web_001",
        advice_enquiry_ref="advice_enquiry_demo_001",
        subject_summary="ISA investment and portfolio review enquiry",
        advice_need_summary="Synthetic ISA review with capital-growth objective.",
        advice_need_categories=["isa_investment", "portfolio_review"],
        declared_objective_categories=["capital_growth", "tax_wrapper_use"],
        support_need_categories=["none_disclosed"],
        attachments_summary=[
            Uc3AttachmentSummary(
                attachment_ref="attachment_platform_summary_001",
                document_category="platform_summary",
                content_type="application/pdf",
                size_bytes=184231,
                sha256="sha256:" + "1" * 64,
            )
        ],
        prospective_retail_client_ref="prospective_client_demo_ifa_001",
        household_ref="household_demo_ifa_001",
        risk_preference_hint="medium",
        time_horizon_band="5_to_10_years",
        product_context_categories=["existing_platform_review"],
        idempotency_key_ref="advice_form_isa_review_001",
    )


def _record_activity_factory(events: list[WorkflowEventCommand]):
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
    advice_scope: str = "independent_advice_in_scope",
    fact_find_completeness: str = "complete_for_scope",
    risk_profile_status: str = "aligned",
    support_status: str = "clear",
    suitability_outcome: str = "suitable_subject_to_adviser_approval",
):
    @activity.defn(name=ACTIVITY_INVOKE_AGENT_RUNTIME)
    async def fake_agent(request: AgentInvocationRequest) -> AgentInvocationResponse:
        structured: dict[str, object]
        next_step = "continue"
        match request.task_kind:
            case "uc3_advice_scope_classification":
                structured = {
                    "advice_scope_ref": "advice_scope_demo_001",
                    "advice_scope": advice_scope,
                    "client_category": "retail_client",
                    "authority_status": "confirmed",
                }
            case "uc3_fact_find_summary":
                structured = {
                    "fact_find_summary_ref": "fact_find_demo_001",
                    "financial_situation_ref": "financial_situation_demo_001",
                    "objective_refs": ["objective_capital_growth_001"],
                    "knowledge_experience_ref": "knowledge_experience_demo_001",
                    "questionnaire_bundle_ref": "risk_questionnaire_demo_001",
                    "fact_find_completeness": fact_find_completeness,
                    "time_horizon_band": "5_to_10_years",
                    "risk_preference_band": "medium",
                    "liquidity_need_category": "medium",
                    "product_candidate_refs": ["product_candidate_model_portfolio_001"],
                }
                if fact_find_completeness != "complete_for_scope":
                    next_step = "fact_find_incomplete"
            case "uc3_risk_profile_assessment":
                structured = {
                    "risk_profile_ref": "risk_profile_demo_001",
                    "risk_profile_status": risk_profile_status,
                    "approval_package_ref": "approval_risk_profile_demo_001",
                }
                if risk_profile_status != "aligned":
                    next_step = "approval_required"
            case "uc3_consumer_duty_support_assessment":
                structured = {
                    "support_assessment_ref": "support_assessment_demo_001",
                    "support_status": support_status,
                    "vulnerability_marker_categories": ["none"],
                }
                if support_status != "clear":
                    next_step = "approval_required"
            case "uc3_suitability_conclusion":
                structured = {
                    "suitability_outcome": suitability_outcome,
                    "suitability_conclusion_ref": "suitability_conclusion_demo_001",
                    "suitability_report_ref": "suitability_report_demo_001",
                    "report_summary_ref": "report_summary_demo_001",
                    "consumer_understanding_check_ref": "consumer_understanding_demo_001",
                    "approval_package_ref": "approval_suitability_report_demo_001",
                    "policy_snapshot_ref": "policy_snapshot_uc3_default_v1",
                    "decline_reason_category": "unsuitable_objective",
                }
                if suitability_outcome == "manual_review":
                    next_step = "manual_review"
            case _:
                structured = {}
        return AgentInvocationResponse(
            invocation_id=str(uuid4()),
            summary=f"{request.task_kind} complete",
            confidence=0.9,
            structured_data=structured,
            recommended_next_step=next_step,
            rationale="test boundary",
        )

    return fake_agent


def _gateway_activity_factory(
    *,
    requests: list[ToolGatewayRequest],
    verdict_by_tool: dict[str, str] | None = None,
):
    verdict_overrides = verdict_by_tool or {}

    @activity.defn(name=ACTIVITY_INVOKE_TOOL_GATEWAY)
    async def fake_gateway(request: ToolGatewayRequest) -> ToolGatewayResponse:
        requests.append(request)
        verdict = verdict_overrides.get(request.tool_name, "allow")
        return ToolGatewayResponse(
            verdict_id=str(uuid4()),
            tool_call_id=str(uuid4()),
            audit_event_id=str(uuid4()),
            verdict=verdict,
            enforced_mode=request.mode,
            reason=f"test gateway {verdict} for {request.tool_name}",
            connector_invocation_id=str(uuid4()),
            output=_gateway_output_for(request),
        )

    return fake_gateway


def _gateway_output_for(request: ToolGatewayRequest) -> dict[str, object]:
    match request.tool_name:
        case "attitude_to_risk.profile":
            return {
                "risk_profile_ref": "risk_profile_demo_001",
                "profiler_band": request.arguments["stated_risk_preference_band"],
                "risk_profile_status": "aligned",
            }
        case "capacity_for_loss.assess":
            return {
                "capacity_for_loss_ref": "capacity_for_loss_demo_001",
                "capacity_for_loss_status": "adequate",
            }
        case "platform_research.run":
            return {
                "platform_research_ref": "platform_research_demo_001",
                "product_universe_coverage": "sufficient_independent_range",
                "target_market_status": "in_target_market",
            }
        case "suitability_report.draft":
            return {
                "suitability_report_ref": request.arguments["suitability_report_ref"],
                "draft_status": "recorded",
            }
        case "suitability_report.issue":
            return {
                "suitability_report_ref": request.arguments["suitability_report_ref"],
                "issue_instruction_ref": request.arguments["issue_instruction_ref"],
            }
        case "suitability_report.record_decline":
            return {"decline_ref": request.arguments["decline_ref"]}
        case "suitability_report.route_manual_review":
            return {"handoff_ref": request.arguments["handoff_ref"]}
        case _:
            return {}


def test_uc3_workflow_definition_declares_expected_spine_steps() -> None:
    definition = UC3_IFA_SUITABILITY_INTAKE_DEFINITION
    assert definition.workflow_type == UC3_WORKFLOW_TYPE
    assert [step.step_name for step in definition.steps] == [
        "intake",
        "advice_scope_classification",
        "fact_find_summary",
        "attitude_to_risk_profile",
        "risk_profile_assessment",
        "risk_profile_approval",
        "capacity_for_loss_assessment",
        "consumer_duty_support_assessment",
        "vulnerability_handoff_approval",
        "platform_research",
        "suitability_conclusion",
        "suitability_report_draft",
        "suitability_report_approval",
        "suitability_report_issue",
        "decline_advice_service",
        "manual_review",
        "close",
        "escalate",
    ]
    connectors = {
        step.step_name: step.connector_spec.tool_name
        for step in definition.steps
        if step.connector_spec is not None
    }
    assert connectors == {
        "attitude_to_risk_profile": "attitude_to_risk.profile",
        "capacity_for_loss_assessment": "capacity_for_loss.assess",
        "platform_research": "platform_research.run",
        "suitability_report_draft": "suitability_report.draft",
        "suitability_report_issue": "suitability_report.issue",
        "decline_advice_service": "suitability_report.record_decline",
        "manual_review": "suitability_report.route_manual_review",
    }
    assert {
        step.step_name for step in definition.steps if step.kind is WorkflowStepKind.APPROVAL_GATE
    } == {
        "risk_profile_approval",
        "vulnerability_handoff_approval",
        "suitability_report_approval",
    }


@pytest.mark.asyncio
async def test_uc3_workflow_happy_path_transitions_and_replays() -> None:
    events: list[WorkflowEventCommand] = []
    gateway_requests: list[ToolGatewayRequest] = []
    intake = _sample_intake()

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="test-uc3-happy",
            workflows=[Uc3IfaSuitabilityIntakeWorkflow],
            activities=[
                _record_activity_factory(events),
                _agent_activity_factory(),
                _gateway_activity_factory(requests=gateway_requests),
            ],
        ),
    ):
        result = await env.client.execute_workflow(
            "Uc3IfaSuitabilityIntakeWorkflow",
            intake,
            id="uc3-workflow-happy-test",
            task_queue="test-uc3-happy",
            result_type=Uc3WorkflowResult,
        )
        handle = env.client.get_workflow_handle("uc3-workflow-happy-test")
        history = await handle.fetch_history()

    assert result.outcome == "completed"
    assert result.path == [
        "intake",
        "advice_scope_classification",
        "fact_find_summary",
        "attitude_to_risk_profile",
        "risk_profile_assessment",
        "capacity_for_loss_assessment",
        "consumer_duty_support_assessment",
        "platform_research",
        "suitability_conclusion",
        "suitability_report_draft",
        "suitability_report_approval",
        "suitability_report_issue",
        "close",
    ]
    assert [request.tool_name for request in gateway_requests] == [
        "attitude_to_risk.profile",
        "capacity_for_loss.assess",
        "platform_research.run",
        "suitability_report.draft",
        "suitability_report.issue",
    ]
    assert all(request.workflow_type == UC3_WORKFLOW_TYPE for request in gateway_requests)
    assert all(request.subject_ref == intake.advice_enquiry_ref for request in gateway_requests)
    assert gateway_requests[-1].mode == "write"
    assert gateway_requests[-1].arguments["issue_instruction_ref"] == "issue_instruction_demo_001"
    forbidden_arg_keys = {
        "raw_client_financial_details",
        "vulnerability_narrative",
        "platform_credentials",
        "report_prose",
        "production_client_data",
    }
    assert all(forbidden_arg_keys.isdisjoint(request.arguments) for request in gateway_requests)
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert events[0].event_type == "enquiry.received"
    assert all(event.payload.get("subject_summary") == intake.subject_summary for event in events)
    assert events[-1].event_type == "workflow.completed"

    replayer = Replayer(workflows=[Uc3IfaSuitabilityIntakeWorkflow])
    workflow_history = WorkflowHistory(history.workflow_id, history.events)
    await replayer.replay_workflow(workflow_history)


@pytest.mark.asyncio
async def test_uc3_workflow_records_suitability_report_approval_required_branch() -> None:
    events: list[WorkflowEventCommand] = []
    gateway_requests: list[ToolGatewayRequest] = []

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="test-uc3-approval-required",
            workflows=[Uc3IfaSuitabilityIntakeWorkflow],
            activities=[
                _record_activity_factory(events),
                _agent_activity_factory(),
                _gateway_activity_factory(
                    requests=gateway_requests,
                    verdict_by_tool={"suitability_report.issue": "approval_required"},
                ),
            ],
        ),
    ):
        result = await env.client.execute_workflow(
            "Uc3IfaSuitabilityIntakeWorkflow",
            _sample_intake(),
            id="uc3-workflow-approval-required-test",
            task_queue="test-uc3-approval-required",
            result_type=Uc3WorkflowResult,
        )

    assert result.outcome == "approval_required"
    assert result.path[-3:] == ["suitability_report_approval", "suitability_report_issue", "close"]
    assert gateway_requests[-1].tool_name == "suitability_report.issue"
    assert gateway_requests[-1].mode == "write"
    assert events[-1].event_type == "workflow.completed"
    assert events[-1].payload["outcome"] == "approval_required"


@pytest.mark.asyncio
async def test_uc3_workflow_routes_risk_profile_approval_to_manual_review() -> None:
    events: list[WorkflowEventCommand] = []
    gateway_requests: list[ToolGatewayRequest] = []

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="test-uc3-risk-approval",
            workflows=[Uc3IfaSuitabilityIntakeWorkflow],
            activities=[
                _record_activity_factory(events),
                _agent_activity_factory(risk_profile_status="mismatch_requires_approval"),
                _gateway_activity_factory(requests=gateway_requests),
            ],
        ),
    ):
        result = await env.client.execute_workflow(
            "Uc3IfaSuitabilityIntakeWorkflow",
            _sample_intake(),
            id="uc3-workflow-risk-approval-test",
            task_queue="test-uc3-risk-approval",
            result_type=Uc3WorkflowResult,
        )

    assert result.outcome == "approval_required"
    assert result.path[-3:] == ["risk_profile_approval", "manual_review", "close"]
    assert gateway_requests[-1].tool_name == "suitability_report.route_manual_review"
    assert "capacity_for_loss.assess" not in [request.tool_name for request in gateway_requests]
    assert events[-1].payload["outcome"] == "approval_required"


@pytest.mark.parametrize(
    ("suitability_outcome", "expected_tool", "expected_outcome", "expected_step"),
    [
        (
            "unsuitable",
            "suitability_report.record_decline",
            "declined_advice_service",
            "decline_advice_service",
        ),
        (
            "manual_review",
            "suitability_report.route_manual_review",
            "manual_review",
            "manual_review",
        ),
    ],
)
@pytest.mark.asyncio
async def test_uc3_workflow_routes_decline_and_manual_review_branches(
    suitability_outcome: str,
    expected_tool: str,
    expected_outcome: str,
    expected_step: str,
) -> None:
    events: list[WorkflowEventCommand] = []
    gateway_requests: list[ToolGatewayRequest] = []

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue=f"test-uc3-{suitability_outcome}",
            workflows=[Uc3IfaSuitabilityIntakeWorkflow],
            activities=[
                _record_activity_factory(events),
                _agent_activity_factory(suitability_outcome=suitability_outcome),
                _gateway_activity_factory(requests=gateway_requests),
            ],
        ),
    ):
        result = await env.client.execute_workflow(
            "Uc3IfaSuitabilityIntakeWorkflow",
            _sample_intake(),
            id=f"uc3-workflow-{suitability_outcome}-test",
            task_queue=f"test-uc3-{suitability_outcome}",
            result_type=Uc3WorkflowResult,
        )

    assert result.outcome == expected_outcome
    assert result.path[-2:] == [expected_step, "close"]
    assert gateway_requests[-1].tool_name == expected_tool
    assert "suitability_report.draft" not in [request.tool_name for request in gateway_requests]
    assert events[-1].event_type == "workflow.completed"

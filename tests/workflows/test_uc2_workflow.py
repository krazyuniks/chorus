"""UC2 legal-services workflow tests on the shared spine."""

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
    Uc2AttachmentSummary,
    Uc2LegalIntake,
    Uc2PartyRoleHint,
    Uc2WorkflowResult,
    WorkflowEventCommand,
    WorkflowEventResult,
)
from chorus.workflows.uc2 import (
    UC2_LEGAL_SERVICES_INTAKE_CONFLICT_CHECK_DEFINITION,
    UC2_WORKFLOW_TYPE,
    Uc2LegalServicesIntakeConflictCheckWorkflow,
)


def _sample_intake() -> Uc2LegalIntake:
    return Uc2LegalIntake(
        schema_version="1.0.0",
        legal_intake_id=str(uuid4()),
        tenant_id="tenant_demo",
        correlation_id="cor_uc2_happy",
        channel="email",
        adapter_id="email-channel",
        received_at="2026-05-01T09:30:00Z",
        source_payload_ref="source_payload_legal_email_001",
        legal_intake_ref="legal_intake_demo_001",
        subject_summary="Commercial contract review enquiry",
        matter_scope_summary=(
            "Synthetic supplier-framework review with one corporate counterparty."
        ),
        party_role_hints=[
            Uc2PartyRoleHint(
                party_ref="party_prospective_client_001",
                role="prospective_client",
                party_category="organisation",
            ),
            Uc2PartyRoleHint(
                party_ref="party_counterparty_001",
                role="counterparty",
                party_category="organisation",
            ),
        ],
        attachments_summary=[
            Uc2AttachmentSummary(
                attachment_ref="attachment_heads_terms_001",
                document_category="heads_of_terms",
                content_type="application/pdf",
                size_bytes=84231,
                sha256="sha256:" + "0" * 64,
            )
        ],
        prospective_client_ref="prospective_client_demo_001",
        instructing_contact_ref="contact_instructing_001",
        matter_type_hint="commercial_contract",
        jurisdiction_categories=["england_and_wales"],
        known_party_refs=["party_prospective_client_001", "party_counterparty_001"],
        idempotency_key_ref="msgid_legal_intake_001",
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
    engagement_outcome: str = "accept_for_engagement",
    party_graph_ambiguous: bool = False,
    conflict_status: str = "no_conflict",
):
    @activity.defn(name=ACTIVITY_INVOKE_AGENT_RUNTIME)
    async def fake_agent(request: AgentInvocationRequest) -> AgentInvocationResponse:
        structured: dict[str, object]
        next_step = "continue"
        match request.task_kind:
            case "uc2_matter_classification":
                structured = {
                    "matter_type": "commercial_contract",
                    "matter_scope_ref": "mscope_demo_001",
                    "scope_summary_ref": "scope_summary_demo_001",
                    "jurisdiction_categories": ["england_and_wales"],
                }
            case "uc2_party_extraction":
                structured = {
                    "party_graph_ref": "pgraph_demo_001_v1",
                    "prospective_client_ref": "prospective_client_demo_001",
                    "entity_category": "company",
                    "authority_status": "uncertain" if party_graph_ambiguous else "confirmed",
                    "party_graph_ambiguous": party_graph_ambiguous,
                    "party_search_terms": [
                        {
                            "party_ref": "party_prospective_client_001",
                            "role": "prospective_client",
                            "party_category": "organisation",
                        },
                        {
                            "party_ref": "party_counterparty_001",
                            "role": "counterparty",
                            "party_category": "organisation",
                        },
                    ],
                    "beneficial_owner_refs": ["beneficial_owner_demo_001"],
                    "controller_refs": ["controller_demo_001"],
                }
                if party_graph_ambiguous:
                    next_step = "manual_review"
            case "uc2_conflict_determination":
                structured = {
                    "conflict_determination_ref": "conflict_determination_demo_001",
                    "conflict_status": conflict_status,
                    "confidentiality_safeguard_status": "not_required",
                    "aml_risk_rating": "standard",
                }
            case "uc2_engagement_decision":
                structured = {
                    "engagement_outcome": engagement_outcome,
                    "engagement_decision_ref": f"engagement_decision_demo_{engagement_outcome}",
                    "engagement_letter_ref": "engagement_letter_demo_001",
                    "matter_scope_ref": "mscope_demo_001",
                    "scope_summary_ref": "scope_summary_demo_001",
                    "approval_package_ref": "approval_engagement_letter_demo_001",
                    "policy_snapshot_ref": "policy_snapshot_uc2_default_v1",
                    "decline_reason_category": "manual_decision",
                }
                if engagement_outcome == "manual_review":
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
        case "conflict_check.search":
            return {
                "conflict_check_ref": "conflict_check_demo_001",
                "conflict_hit_refs": [],
            }
        case "kyc_bo.lookup":
            return {
                "cdd_record_ref": "cdd_record_demo_001",
                "cdd_status": "complete_standard",
                "beneficial_ownership_status": "complete",
                "beneficial_ownership_snapshot_ref": "bo_snapshot_demo_001",
            }
        case "aml_record_store.record_assessment":
            return {
                "aml_risk_assessment_ref": request.arguments["aml_risk_assessment_ref"],
                "aml_risk_rating": request.arguments["aml_risk_rating"],
                "aml_record_status": "recorded",
            }
        case "engagement_letter.draft":
            return {
                "engagement_letter_ref": request.arguments["engagement_letter_ref"],
                "draft_status": "recorded",
            }
        case "engagement_letter.send":
            return {
                "engagement_letter_ref": request.arguments["engagement_letter_ref"],
                "send_instruction_ref": request.arguments["send_instruction_ref"],
            }
        case "engagement_letter.record_decline":
            return {"decline_ref": request.arguments["decline_ref"]}
        case "engagement_letter.route_manual_review":
            return {"handoff_ref": request.arguments["handoff_ref"]}
        case _:
            return {}


def test_uc2_workflow_definition_declares_expected_spine_steps() -> None:
    definition = UC2_LEGAL_SERVICES_INTAKE_CONFLICT_CHECK_DEFINITION
    assert definition.workflow_type == UC2_WORKFLOW_TYPE
    assert [step.step_name for step in definition.steps] == [
        "intake",
        "matter_classification",
        "party_extraction",
        "conflict_check",
        "conflict_determination",
        "conflict_exception_approval",
        "kyc_beneficial_ownership",
        "aml_assessment",
        "aml_edd_approval",
        "engagement_decision",
        "engagement_letter_draft",
        "engagement_letter_send",
        "decline_to_act",
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
        "conflict_check": "conflict_check.search",
        "kyc_beneficial_ownership": "kyc_bo.lookup",
        "aml_assessment": "aml_record_store.record_assessment",
        "engagement_letter_draft": "engagement_letter.draft",
        "engagement_letter_send": "engagement_letter.send",
        "decline_to_act": "engagement_letter.record_decline",
        "manual_review": "engagement_letter.route_manual_review",
    }
    assert {
        step.step_name for step in definition.steps if step.kind is WorkflowStepKind.APPROVAL_GATE
    } == {
        "conflict_exception_approval",
        "aml_edd_approval",
        "engagement_letter_send",
    }


@pytest.mark.asyncio
async def test_uc2_workflow_happy_path_transitions_and_replays() -> None:
    events: list[WorkflowEventCommand] = []
    gateway_requests: list[ToolGatewayRequest] = []
    intake = _sample_intake()

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="test-uc2-happy",
            workflows=[Uc2LegalServicesIntakeConflictCheckWorkflow],
            activities=[
                _record_activity_factory(events),
                _agent_activity_factory(),
                _gateway_activity_factory(requests=gateway_requests),
            ],
        ),
    ):
        result = await env.client.execute_workflow(
            "Uc2LegalServicesIntakeConflictCheckWorkflow",
            intake,
            id="uc2-workflow-happy-test",
            task_queue="test-uc2-happy",
            result_type=Uc2WorkflowResult,
        )
        handle = env.client.get_workflow_handle("uc2-workflow-happy-test")
        history = await handle.fetch_history()

    assert result.outcome == "completed"
    assert result.path == [
        "intake",
        "matter_classification",
        "party_extraction",
        "conflict_check",
        "conflict_determination",
        "kyc_beneficial_ownership",
        "aml_assessment",
        "engagement_decision",
        "engagement_letter_draft",
        "engagement_letter_send",
        "close",
    ]
    assert [request.tool_name for request in gateway_requests] == [
        "conflict_check.search",
        "kyc_bo.lookup",
        "aml_record_store.record_assessment",
        "engagement_letter.draft",
        "engagement_letter.send",
    ]
    assert all(request.workflow_type == UC2_WORKFLOW_TYPE for request in gateway_requests)
    assert all(request.subject_ref == intake.legal_intake_ref for request in gateway_requests)
    assert gateway_requests[-1].mode == "write"
    assert gateway_requests[-1].arguments["send_instruction_ref"] == "send_instruction_demo_001"
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert events[0].event_type == "enquiry.received"
    assert all(event.payload.get("subject_summary") == intake.subject_summary for event in events)
    assert events[-1].event_type == "workflow.completed"

    replayer = Replayer(workflows=[Uc2LegalServicesIntakeConflictCheckWorkflow])
    workflow_history = WorkflowHistory(history.workflow_id, history.events)
    await replayer.replay_workflow(workflow_history)


@pytest.mark.asyncio
async def test_uc2_workflow_records_engagement_letter_approval_required_branch() -> None:
    events: list[WorkflowEventCommand] = []
    gateway_requests: list[ToolGatewayRequest] = []

    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="test-uc2-approval-required",
            workflows=[Uc2LegalServicesIntakeConflictCheckWorkflow],
            activities=[
                _record_activity_factory(events),
                _agent_activity_factory(engagement_outcome="accept_subject_to_approval"),
                _gateway_activity_factory(
                    requests=gateway_requests,
                    verdict_by_tool={"engagement_letter.send": "approval_required"},
                ),
            ],
        ),
    ):
        result = await env.client.execute_workflow(
            "Uc2LegalServicesIntakeConflictCheckWorkflow",
            _sample_intake(),
            id="uc2-workflow-approval-required-test",
            task_queue="test-uc2-approval-required",
            result_type=Uc2WorkflowResult,
        )

    assert result.outcome == "approval_required"
    assert result.path[-2:] == ["engagement_letter_send", "close"]
    assert gateway_requests[-1].tool_name == "engagement_letter.send"
    assert gateway_requests[-1].mode == "write"
    assert events[-1].event_type == "workflow.completed"
    assert events[-1].payload["outcome"] == "approval_required"


@pytest.mark.parametrize(
    ("engagement_outcome", "expected_tool", "expected_outcome", "expected_step"),
    [
        (
            "decline_to_act",
            "engagement_letter.record_decline",
            "declined_to_act",
            "decline_to_act",
        ),
        (
            "manual_review",
            "engagement_letter.route_manual_review",
            "manual_review",
            "manual_review",
        ),
    ],
)
@pytest.mark.asyncio
async def test_uc2_workflow_routes_decline_and_manual_review_branches(
    engagement_outcome: str,
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
            task_queue=f"test-uc2-{engagement_outcome}",
            workflows=[Uc2LegalServicesIntakeConflictCheckWorkflow],
            activities=[
                _record_activity_factory(events),
                _agent_activity_factory(engagement_outcome=engagement_outcome),
                _gateway_activity_factory(requests=gateway_requests),
            ],
        ),
    ):
        result = await env.client.execute_workflow(
            "Uc2LegalServicesIntakeConflictCheckWorkflow",
            _sample_intake(),
            id=f"uc2-workflow-{engagement_outcome}-test",
            task_queue=f"test-uc2-{engagement_outcome}",
            result_type=Uc2WorkflowResult,
        )

    assert result.outcome == expected_outcome
    assert result.path[-2:] == [expected_step, "close"]
    assert gateway_requests[-1].tool_name == expected_tool
    assert "engagement_letter.draft" not in [request.tool_name for request in gateway_requests]
    assert events[-1].event_type == "workflow.completed"

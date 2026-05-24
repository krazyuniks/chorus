"""UC3 independent-financial-advice suitability workflow on the shared spine.

The UC3 workflow is definition-first R4 work. It declares the suitability
intake lifecycle over the existing `WorkflowSpine` primitives and keeps every
effectful boundary behind the existing agent-runtime and Tool Gateway
activities. Connector adapters, grant seeds, approval-package apply semantics,
provider routes, intake adapters, projections, and eval playback land in later
P5 slices.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from temporalio import workflow

from chorus.workflows.spine import (
    EVENT_ENQUIRY_RECEIVED,
    EVENT_WORKFLOW_COMPLETED,
    EVENT_WORKFLOW_ESCALATED,
    EVENT_WORKFLOW_STARTED,
    STEP_ESCALATE,
    ActivityRetryExhaustedError,
    AgentSpec,
    ApprovalPolicy,
    ConnectorSpec,
    WorkflowDefinition,
    WorkflowSpine,
    WorkflowStepDefinition,
    WorkflowStepKind,
    activity_failure_reason,
)
from chorus.workflows.types import (
    AgentInvocationResponse,
    ToolGatewayResponse,
    Uc3AdviceEnquiry,
    Uc3WorkflowOutcome,
    Uc3WorkflowResult,
    WorkflowCorrelation,
)

UC3_WORKFLOW_TYPE = "uc3_ifa_suitability_intake"
UC3_WORKFLOW_ACTOR_ID = "uc3.workflow"

UC3_AGENT_IO_CONTRACT = "contracts/llm_provider/uc3_agent_io.schema.json"

STEP_INTAKE = "intake"
STEP_ADVICE_SCOPE_CLASSIFICATION = "advice_scope_classification"
STEP_FACT_FIND_SUMMARY = "fact_find_summary"
STEP_ATTITUDE_TO_RISK_PROFILE = "attitude_to_risk_profile"
STEP_RISK_PROFILE_ASSESSMENT = "risk_profile_assessment"
STEP_RISK_PROFILE_APPROVAL = "risk_profile_approval"
STEP_CAPACITY_FOR_LOSS_ASSESSMENT = "capacity_for_loss_assessment"
STEP_CONSUMER_DUTY_SUPPORT_ASSESSMENT = "consumer_duty_support_assessment"
STEP_VULNERABILITY_HANDOFF_APPROVAL = "vulnerability_handoff_approval"
STEP_PLATFORM_RESEARCH = "platform_research"
STEP_SUITABILITY_CONCLUSION = "suitability_conclusion"
STEP_SUITABILITY_REPORT_DRAFT = "suitability_report_draft"
STEP_SUITABILITY_REPORT_APPROVAL = "suitability_report_approval"
STEP_SUITABILITY_REPORT_ISSUE = "suitability_report_issue"
STEP_DECLINE_ADVICE_SERVICE = "decline_advice_service"
STEP_MANUAL_REVIEW = "manual_review"
STEP_CLOSE = "close"

_AGENT_ID_SCOPE_CLASSIFIER = "uc3.scope_classifier"
_AGENT_ID_FACT_FIND_SUMMARISER = "uc3.fact_find_summariser"
_AGENT_ID_RISK_ANALYST = "uc3.risk_analyst"
_AGENT_ID_CAPACITY_ASSESSOR = "uc3.capacity_assessor"
_AGENT_ID_SUPPORT_ASSESSOR = "uc3.support_assessor"
_AGENT_ID_RESEARCH_ANALYST = "uc3.research_analyst"
_AGENT_ID_SUITABILITY_DECIDER = "uc3.suitability_decider"

_DEFAULT_CONDUCT_HOOK_REFS = (
    "conduct_fca_cobs_2_1_client_best_interests",
    "conduct_fca_cobs_6_2b_independent_advice",
    "conduct_fca_cobs_9_suitability",
    "conduct_fca_prod_3_target_market",
    "conduct_fca_prin_2a_consumer_duty",
    "conduct_fca_vulnerability_fg21_1",
    "conduct_fca_cobs_9_recordkeeping",
)

UC3_STEP_INTAKE = WorkflowStepDefinition(step_name=STEP_INTAKE, kind=WorkflowStepKind.INTAKE)

UC3_STEP_ADVICE_SCOPE_CLASSIFICATION = WorkflowStepDefinition(
    step_name=STEP_ADVICE_SCOPE_CLASSIFICATION,
    kind=WorkflowStepKind.AGENT,
    agent_spec=AgentSpec(
        agent_role="advice_scope_classifier",
        task_kind="uc3_advice_scope_classification",
        expected_output_contract=UC3_AGENT_IO_CONTRACT,
    ),
)

UC3_STEP_FACT_FIND_SUMMARY = WorkflowStepDefinition(
    step_name=STEP_FACT_FIND_SUMMARY,
    kind=WorkflowStepKind.AGENT,
    agent_spec=AgentSpec(
        agent_role="fact_find_summariser",
        task_kind="uc3_fact_find_summary",
        expected_output_contract=UC3_AGENT_IO_CONTRACT,
    ),
)

UC3_STEP_ATTITUDE_TO_RISK_PROFILE = WorkflowStepDefinition(
    step_name=STEP_ATTITUDE_TO_RISK_PROFILE,
    kind=WorkflowStepKind.CONNECTOR,
    connector_spec=ConnectorSpec(
        agent_id=_AGENT_ID_RISK_ANALYST,
        tool_name="attitude_to_risk.profile",
        mode="read",
    ),
)

UC3_STEP_RISK_PROFILE_ASSESSMENT = WorkflowStepDefinition(
    step_name=STEP_RISK_PROFILE_ASSESSMENT,
    kind=WorkflowStepKind.AGENT,
    agent_spec=AgentSpec(
        agent_role="risk_profile_assessor",
        task_kind="uc3_risk_profile_assessment",
        expected_output_contract=UC3_AGENT_IO_CONTRACT,
    ),
)

UC3_STEP_RISK_PROFILE_APPROVAL = WorkflowStepDefinition(
    step_name=STEP_RISK_PROFILE_APPROVAL,
    kind=WorkflowStepKind.APPROVAL_GATE,
    approval_policy=ApprovalPolicy(
        agent_id=_AGENT_ID_RISK_ANALYST,
        tool_name="suitability_report.route_manual_review",
        requested_mode="write",
    ),
)

UC3_STEP_CAPACITY_FOR_LOSS_ASSESSMENT = WorkflowStepDefinition(
    step_name=STEP_CAPACITY_FOR_LOSS_ASSESSMENT,
    kind=WorkflowStepKind.CONNECTOR,
    connector_spec=ConnectorSpec(
        agent_id=_AGENT_ID_CAPACITY_ASSESSOR,
        tool_name="capacity_for_loss.assess",
        mode="read",
    ),
)

UC3_STEP_CONSUMER_DUTY_SUPPORT_ASSESSMENT = WorkflowStepDefinition(
    step_name=STEP_CONSUMER_DUTY_SUPPORT_ASSESSMENT,
    kind=WorkflowStepKind.AGENT,
    agent_spec=AgentSpec(
        agent_role="consumer_duty_support_assessor",
        task_kind="uc3_consumer_duty_support_assessment",
        expected_output_contract=UC3_AGENT_IO_CONTRACT,
    ),
)

UC3_STEP_VULNERABILITY_HANDOFF_APPROVAL = WorkflowStepDefinition(
    step_name=STEP_VULNERABILITY_HANDOFF_APPROVAL,
    kind=WorkflowStepKind.APPROVAL_GATE,
    approval_policy=ApprovalPolicy(
        agent_id=_AGENT_ID_SUPPORT_ASSESSOR,
        tool_name="suitability_report.route_manual_review",
        requested_mode="write",
    ),
)

UC3_STEP_PLATFORM_RESEARCH = WorkflowStepDefinition(
    step_name=STEP_PLATFORM_RESEARCH,
    kind=WorkflowStepKind.CONNECTOR,
    connector_spec=ConnectorSpec(
        agent_id=_AGENT_ID_RESEARCH_ANALYST,
        tool_name="platform_research.run",
        mode="read",
    ),
)

UC3_STEP_SUITABILITY_CONCLUSION = WorkflowStepDefinition(
    step_name=STEP_SUITABILITY_CONCLUSION,
    kind=WorkflowStepKind.AGENT,
    agent_spec=AgentSpec(
        agent_role="suitability_decider",
        task_kind="uc3_suitability_conclusion",
        expected_output_contract=UC3_AGENT_IO_CONTRACT,
    ),
)

UC3_STEP_SUITABILITY_REPORT_DRAFT = WorkflowStepDefinition(
    step_name=STEP_SUITABILITY_REPORT_DRAFT,
    kind=WorkflowStepKind.CONNECTOR,
    connector_spec=ConnectorSpec(
        agent_id=_AGENT_ID_SUITABILITY_DECIDER,
        tool_name="suitability_report.draft",
        mode="write",
    ),
)

UC3_STEP_SUITABILITY_REPORT_APPROVAL = WorkflowStepDefinition(
    step_name=STEP_SUITABILITY_REPORT_APPROVAL,
    kind=WorkflowStepKind.APPROVAL_GATE,
    approval_policy=ApprovalPolicy(
        agent_id=_AGENT_ID_SUITABILITY_DECIDER,
        tool_name="suitability_report.issue",
        requested_mode="write",
    ),
)

UC3_STEP_SUITABILITY_REPORT_ISSUE = WorkflowStepDefinition(
    step_name=STEP_SUITABILITY_REPORT_ISSUE,
    kind=WorkflowStepKind.CONNECTOR,
    connector_spec=ConnectorSpec(
        agent_id=_AGENT_ID_SUITABILITY_DECIDER,
        tool_name="suitability_report.issue",
        mode="write",
    ),
    approval_policy=ApprovalPolicy(
        agent_id=_AGENT_ID_SUITABILITY_DECIDER,
        tool_name="suitability_report.issue",
        requested_mode="write",
    ),
)

UC3_STEP_DECLINE_ADVICE_SERVICE = WorkflowStepDefinition(
    step_name=STEP_DECLINE_ADVICE_SERVICE,
    kind=WorkflowStepKind.CONNECTOR,
    connector_spec=ConnectorSpec(
        agent_id=_AGENT_ID_SUITABILITY_DECIDER,
        tool_name="suitability_report.record_decline",
        mode="write",
    ),
)

UC3_STEP_MANUAL_REVIEW = WorkflowStepDefinition(
    step_name=STEP_MANUAL_REVIEW,
    kind=WorkflowStepKind.CONNECTOR,
    connector_spec=ConnectorSpec(
        agent_id=_AGENT_ID_SUITABILITY_DECIDER,
        tool_name="suitability_report.route_manual_review",
        mode="write",
    ),
)

UC3_STEP_CLOSE = WorkflowStepDefinition(step_name=STEP_CLOSE, kind=WorkflowStepKind.TERMINAL)
UC3_STEP_ESCALATE = WorkflowStepDefinition(step_name=STEP_ESCALATE, kind=WorkflowStepKind.TERMINAL)

UC3_IFA_SUITABILITY_INTAKE_DEFINITION = WorkflowDefinition(
    workflow_type=UC3_WORKFLOW_TYPE,
    steps=(
        UC3_STEP_INTAKE,
        UC3_STEP_ADVICE_SCOPE_CLASSIFICATION,
        UC3_STEP_FACT_FIND_SUMMARY,
        UC3_STEP_ATTITUDE_TO_RISK_PROFILE,
        UC3_STEP_RISK_PROFILE_ASSESSMENT,
        UC3_STEP_RISK_PROFILE_APPROVAL,
        UC3_STEP_CAPACITY_FOR_LOSS_ASSESSMENT,
        UC3_STEP_CONSUMER_DUTY_SUPPORT_ASSESSMENT,
        UC3_STEP_VULNERABILITY_HANDOFF_APPROVAL,
        UC3_STEP_PLATFORM_RESEARCH,
        UC3_STEP_SUITABILITY_CONCLUSION,
        UC3_STEP_SUITABILITY_REPORT_DRAFT,
        UC3_STEP_SUITABILITY_REPORT_APPROVAL,
        UC3_STEP_SUITABILITY_REPORT_ISSUE,
        UC3_STEP_DECLINE_ADVICE_SERVICE,
        UC3_STEP_MANUAL_REVIEW,
        UC3_STEP_CLOSE,
        UC3_STEP_ESCALATE,
    ),
)


@workflow.defn(name="Uc3IfaSuitabilityIntakeWorkflow")
class Uc3IfaSuitabilityIntakeWorkflow:
    """UC3 suitability intake workflow.

    The workflow contains deterministic step composition and branch selection
    only. Agent execution, Tool Gateway dispatch, persistence, timestamps,
    event IDs, and connector side effects remain activity-owned.
    """

    @workflow.run
    async def run(self, intake: Uc3AdviceEnquiry) -> Uc3WorkflowResult:
        correlation = WorkflowCorrelation(
            tenant_id=intake.tenant_id,
            correlation_id=intake.correlation_id,
            workflow_id=workflow.info().workflow_id,
            workflow_type=UC3_WORKFLOW_TYPE,
            workflow_actor_id=UC3_WORKFLOW_ACTOR_ID,
            subject_id=intake.advice_enquiry_id,
            subject_ref=intake.advice_enquiry_ref,
            subject_summary=intake.subject_summary,
        )
        spine = WorkflowSpine(correlation)

        await spine.emit(
            EVENT_ENQUIRY_RECEIVED,
            STEP_INTAKE,
            {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "subject_summary": intake.subject_summary,
                "channel": intake.channel,
                "adapter_id": intake.adapter_id,
                "source_payload_ref": intake.source_payload_ref,
                "advice_need_categories": intake.advice_need_categories,
                "support_need_categories": intake.support_need_categories,
            },
        )
        await spine.emit(
            EVENT_WORKFLOW_STARTED,
            STEP_INTAKE,
            {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "channel": intake.channel,
            },
        )
        await spine.step(
            STEP_INTAKE,
            {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "channel": intake.channel,
                "advice_need_categories": intake.advice_need_categories,
                "attachment_count": len(intake.attachments_summary),
            },
        )

        scope = await self._agent_step(
            spine,
            intake,
            UC3_STEP_ADVICE_SCOPE_CLASSIFICATION,
            _scope_classification_input(intake),
            lambda response: {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "advice_scope_ref": _advice_scope_ref(intake, response.structured_data),
                "advice_scope": _advice_scope(response),
                "client_category": _string_value(response.structured_data.get("client_category")),
                "confidence": response.confidence,
            },
        )
        if isinstance(scope, Uc3WorkflowResult):
            return scope
        if _scope_requires_decline(scope):
            return await self._record_decline(
                spine,
                intake,
                reason_category="out_of_scope_advice",
                suitability_conclusion_ref=_default_ref("suitability_conclusion", intake),
                final_summary="advice service scope is out of frame for UC3",
            )
        if _scope_requires_manual_review(scope):
            return await self._route_manual_review(
                spine,
                intake,
                reason_category="advice_scope_unclear",
                destination_category="financial_adviser",
                final_summary="advice service scope requires adviser review",
            )

        fact_find = await self._agent_step(
            spine,
            intake,
            UC3_STEP_FACT_FIND_SUMMARY,
            _fact_find_input(intake, scope),
            lambda response: {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "fact_find_summary_ref": _fact_find_ref(intake, response.structured_data),
                "fact_find_completeness": _fact_find_completeness(response),
                "objective_refs": _objective_refs(intake, response.structured_data),
                "knowledge_experience_ref": _knowledge_experience_ref(
                    intake, response.structured_data
                ),
                "confidence": response.confidence,
            },
        )
        if isinstance(fact_find, Uc3WorkflowResult):
            return fact_find
        if _fact_find_requires_manual_review(fact_find):
            return await self._route_manual_review(
                spine,
                intake,
                outcome="fact_find_incomplete",
                reason_category="fact_find_gap",
                destination_category="financial_adviser",
                final_summary="necessary suitability information is missing or stale",
            )

        attitude_to_risk = await self._connector_step(
            spine,
            intake,
            UC3_STEP_ATTITUDE_TO_RISK_PROFILE,
            invocation_id=fact_find.invocation_id,
            idempotency_key=_questionnaire_bundle_ref(intake, fact_find.structured_data),
            arguments=_attitude_to_risk_arguments(intake=intake, fact_find=fact_find),
            payload_from_response=lambda response: {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "tool_name": _tool_name(UC3_STEP_ATTITUDE_TO_RISK_PROFILE),
                "gateway_verdict": response.verdict,
                "enforced_mode": response.enforced_mode,
                "risk_profile_ref": _risk_profile_ref(intake, fact_find, response.output),
                "profiler_band": _string_value(response.output.get("profiler_band")),
            },
        )
        if isinstance(attitude_to_risk, Uc3WorkflowResult):
            return attitude_to_risk

        risk_profile = await self._agent_step(
            spine,
            intake,
            UC3_STEP_RISK_PROFILE_ASSESSMENT,
            _risk_profile_input(
                intake=intake,
                fact_find=fact_find,
                attitude_to_risk=attitude_to_risk,
            ),
            lambda response: {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "risk_profile_ref": _risk_profile_ref(intake, fact_find, response.structured_data),
                "risk_profile_status": _risk_profile_status(response),
                "approval_required": _risk_profile_requires_approval(response),
                "confidence": response.confidence,
            },
        )
        if isinstance(risk_profile, Uc3WorkflowResult):
            return risk_profile
        if _risk_profile_requires_approval(risk_profile):
            await spine.step(
                STEP_RISK_PROFILE_APPROVAL,
                {
                    "advice_enquiry_ref": intake.advice_enquiry_ref,
                    "approval_required": True,
                    "approval_action": "risk_profile.override.write",
                    "risk_profile_ref": _risk_profile_ref(
                        intake, fact_find, risk_profile.structured_data
                    ),
                    "risk_profile_status": _risk_profile_status(risk_profile),
                },
            )
            return await self._route_manual_review(
                spine,
                intake,
                outcome="approval_required",
                reason_category="risk_profile_mismatch",
                destination_category="financial_adviser",
                suitability_conclusion_ref=_default_ref("suitability_conclusion", intake),
                final_summary="risk-profile mismatch requires adviser approval",
            )

        capacity = await self._connector_step(
            spine,
            intake,
            UC3_STEP_CAPACITY_FOR_LOSS_ASSESSMENT,
            invocation_id=risk_profile.invocation_id,
            idempotency_key=_financial_situation_ref(intake, fact_find.structured_data),
            arguments=_capacity_for_loss_arguments(intake=intake, fact_find=fact_find),
            payload_from_response=lambda response: {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "tool_name": _tool_name(UC3_STEP_CAPACITY_FOR_LOSS_ASSESSMENT),
                "gateway_verdict": response.verdict,
                "enforced_mode": response.enforced_mode,
                "capacity_for_loss_ref": _capacity_for_loss_ref(intake, response.output),
                "capacity_for_loss_status": _capacity_for_loss_status(response),
            },
        )
        if isinstance(capacity, Uc3WorkflowResult):
            return capacity
        if _capacity_requires_decline(capacity):
            return await self._record_decline(
                spine,
                intake,
                reason_category="capacity_for_loss_blocked",
                suitability_conclusion_ref=_default_ref("suitability_conclusion", intake),
                capacity_for_loss_ref=_capacity_for_loss_ref(intake, capacity.output),
                final_summary="capacity for loss blocks the advice service",
            )
        if _capacity_requires_manual_review(capacity):
            return await self._route_manual_review(
                spine,
                intake,
                reason_category="capacity_for_loss_concern",
                destination_category="financial_adviser",
                suitability_conclusion_ref=_default_ref("suitability_conclusion", intake),
                final_summary="capacity for loss requires adviser review",
            )

        support = await self._agent_step(
            spine,
            intake,
            UC3_STEP_CONSUMER_DUTY_SUPPORT_ASSESSMENT,
            _support_assessment_input(
                intake=intake,
                fact_find=fact_find,
                risk_profile=risk_profile,
                capacity=capacity,
            ),
            lambda response: {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "support_assessment_ref": _support_assessment_ref(intake, response.structured_data),
                "support_status": _support_status(response),
                "vulnerability_marker_categories": _vulnerability_marker_categories(response),
                "approval_required": _support_requires_approval(response),
                "confidence": response.confidence,
            },
        )
        if isinstance(support, Uc3WorkflowResult):
            return support
        if _support_requires_approval(support):
            await spine.step(
                STEP_VULNERABILITY_HANDOFF_APPROVAL,
                {
                    "advice_enquiry_ref": intake.advice_enquiry_ref,
                    "approval_required": True,
                    "approval_action": "vulnerability_handoff.review.write",
                    "support_assessment_ref": _support_assessment_ref(
                        intake, support.structured_data
                    ),
                    "support_status": _support_status(support),
                },
            )
            return await self._route_manual_review(
                spine,
                intake,
                outcome="approval_required",
                reason_category="vulnerability_support_required",
                destination_category="vulnerability_support_reviewer",
                suitability_conclusion_ref=_default_ref("suitability_conclusion", intake),
                final_summary="vulnerability or support need requires approved handoff",
            )

        platform_research = await self._connector_step(
            spine,
            intake,
            UC3_STEP_PLATFORM_RESEARCH,
            invocation_id=support.invocation_id,
            idempotency_key=_risk_profile_ref(intake, fact_find, risk_profile.structured_data),
            arguments=_platform_research_arguments(
                intake=intake,
                scope=scope,
                fact_find=fact_find,
                risk_profile=risk_profile,
                capacity=capacity,
            ),
            payload_from_response=lambda response: {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "tool_name": _tool_name(UC3_STEP_PLATFORM_RESEARCH),
                "gateway_verdict": response.verdict,
                "enforced_mode": response.enforced_mode,
                "platform_research_ref": _platform_research_ref(intake, response.output),
                "product_universe_coverage": _string_value(
                    response.output.get("product_universe_coverage")
                ),
                "target_market_status": _string_value(response.output.get("target_market_status")),
            },
        )
        if isinstance(platform_research, Uc3WorkflowResult):
            return platform_research
        if _platform_requires_decline(platform_research):
            return await self._record_decline(
                spine,
                intake,
                reason_category="negative_target_market",
                suitability_conclusion_ref=_default_ref("suitability_conclusion", intake),
                capacity_for_loss_ref=_capacity_for_loss_ref(intake, capacity.output),
                platform_research_ref=_platform_research_ref(intake, platform_research.output),
                final_summary="target-market evidence blocks the advice service",
            )
        if _platform_requires_manual_review(platform_research):
            return await self._route_manual_review(
                spine,
                intake,
                reason_category="product_universe_defect",
                destination_category="investment_committee",
                suitability_conclusion_ref=_default_ref("suitability_conclusion", intake),
                final_summary="product-universe evidence requires investment review",
            )

        suitability = await self._agent_step(
            spine,
            intake,
            UC3_STEP_SUITABILITY_CONCLUSION,
            _suitability_input(
                intake=intake,
                scope=scope,
                fact_find=fact_find,
                risk_profile=risk_profile,
                capacity=capacity,
                support=support,
                platform_research=platform_research,
            ),
            lambda response: {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "suitability_conclusion_ref": _suitability_conclusion_ref(
                    intake, response.structured_data
                ),
                "suitability_outcome": _suitability_outcome(response),
                "policy_snapshot_ref": _string_value(
                    response.structured_data.get("policy_snapshot_ref")
                ),
                "confidence": response.confidence,
            },
        )
        if isinstance(suitability, Uc3WorkflowResult):
            return suitability

        match _suitability_outcome(suitability):
            case "suitable_subject_to_adviser_approval":
                return await self._draft_and_issue_suitability_report(
                    spine,
                    intake,
                    fact_find=fact_find,
                    risk_profile=risk_profile,
                    capacity=capacity,
                    support=support,
                    platform_research=platform_research,
                    suitability=suitability,
                )
            case "unsuitable" | "out_of_scope":
                return await self._record_decline(
                    spine,
                    intake,
                    reason_category=_decline_reason_category(suitability),
                    suitability_conclusion_ref=_suitability_conclusion_ref(
                        intake, suitability.structured_data
                    ),
                    capacity_for_loss_ref=_capacity_for_loss_ref(intake, capacity.output),
                    platform_research_ref=_platform_research_ref(intake, platform_research.output),
                    final_summary="suitability conclusion blocks the advice service",
                )
            case "insufficient_information":
                return await self._route_manual_review(
                    spine,
                    intake,
                    outcome="fact_find_incomplete",
                    reason_category="fact_find_gap",
                    destination_category="financial_adviser",
                    suitability_conclusion_ref=_suitability_conclusion_ref(
                        intake, suitability.structured_data
                    ),
                    final_summary="suitability conclusion requires fact-find enrichment",
                )
            case _:
                return await self._route_manual_review(
                    spine,
                    intake,
                    reason_category=_review_reason_from_suitability(suitability),
                    destination_category="financial_adviser",
                    suitability_conclusion_ref=_suitability_conclusion_ref(
                        intake, suitability.structured_data
                    ),
                    final_summary="suitability conclusion requires manual review",
                )

    async def _agent_step(
        self,
        spine: WorkflowSpine,
        intake: Uc3AdviceEnquiry,
        step: WorkflowStepDefinition,
        input_payload: dict[str, Any],
        completion_payload: Callable[[AgentInvocationResponse], dict[str, Any]],
    ) -> AgentInvocationResponse | Uc3WorkflowResult:
        try:
            response = await spine.agent_call(step, input_payload)
        except ActivityRetryExhaustedError as exc:
            return await self._retry_exhaustion_escalate(spine, intake, exc)
        await spine.step(step.step_name, completion_payload(response))
        if _should_escalate(response):
            return await self._escalate(
                spine,
                intake,
                f"{step.step_name} requested escalation",
            )
        return response

    async def _connector_step(
        self,
        spine: WorkflowSpine,
        intake: Uc3AdviceEnquiry,
        step: WorkflowStepDefinition,
        *,
        invocation_id: str,
        idempotency_key: str,
        arguments: dict[str, Any],
        payload_from_response: Callable[[ToolGatewayResponse], dict[str, Any]],
    ) -> ToolGatewayResponse | Uc3WorkflowResult:
        try:
            response = await spine.connector_call(
                step,
                invocation_id=invocation_id,
                idempotency_key=idempotency_key,
                arguments=arguments,
            )
        except ActivityRetryExhaustedError as exc:
            return await self._retry_exhaustion_escalate(spine, intake, exc)
        await spine.step(step.step_name, payload_from_response(response))
        if response.verdict == "block":
            return await self._escalate(
                spine,
                intake,
                f"{_tool_name(step)} returned block",
            )
        return response

    async def _draft_and_issue_suitability_report(
        self,
        spine: WorkflowSpine,
        intake: Uc3AdviceEnquiry,
        *,
        fact_find: AgentInvocationResponse,
        risk_profile: AgentInvocationResponse,
        capacity: ToolGatewayResponse,
        support: AgentInvocationResponse,
        platform_research: ToolGatewayResponse,
        suitability: AgentInvocationResponse,
    ) -> Uc3WorkflowResult:
        draft_args = _suitability_report_draft_arguments(
            intake=intake,
            fact_find=fact_find,
            risk_profile=risk_profile,
            capacity=capacity,
            support=support,
            platform_research=platform_research,
            suitability=suitability,
        )
        draft = await self._connector_step(
            spine,
            intake,
            UC3_STEP_SUITABILITY_REPORT_DRAFT,
            invocation_id=suitability.invocation_id,
            idempotency_key=str(draft_args["suitability_report_ref"]),
            arguments=draft_args,
            payload_from_response=lambda response: {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "tool_name": _tool_name(UC3_STEP_SUITABILITY_REPORT_DRAFT),
                "gateway_verdict": response.verdict,
                "enforced_mode": response.enforced_mode,
                "suitability_report_ref": _string_value(
                    response.output.get("suitability_report_ref")
                )
                or draft_args["suitability_report_ref"],
            },
        )
        if isinstance(draft, Uc3WorkflowResult):
            return draft

        await spine.step(
            STEP_SUITABILITY_REPORT_APPROVAL,
            {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "approval_required": True,
                "approval_action": "suitability_report.issue.write",
                "suitability_report_ref": draft_args["suitability_report_ref"],
                "suitability_conclusion_ref": draft_args["suitability_conclusion_ref"],
            },
        )

        issue_args = _suitability_report_issue_arguments(
            intake=intake,
            support=support,
            suitability=suitability,
            draft=draft,
        )
        issue = await self._connector_step(
            spine,
            intake,
            UC3_STEP_SUITABILITY_REPORT_ISSUE,
            invocation_id=suitability.invocation_id,
            idempotency_key=str(issue_args["issue_instruction_ref"]),
            arguments=issue_args,
            payload_from_response=lambda response: {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "tool_name": _tool_name(UC3_STEP_SUITABILITY_REPORT_ISSUE),
                "gateway_verdict": response.verdict,
                "enforced_mode": response.enforced_mode,
                "approval_required": response.verdict in {"approval_required", "propose"},
                "suitability_report_ref": issue_args["suitability_report_ref"],
                "suitability_conclusion_ref": issue_args["suitability_conclusion_ref"],
            },
        )
        if isinstance(issue, Uc3WorkflowResult):
            return issue
        if issue.verdict in {"approval_required", "propose"}:
            return await self._close(
                spine,
                intake,
                outcome="approval_required",
                final_summary="suitability report issue requires approved Tool Gateway apply",
            )
        return await self._close(
            spine,
            intake,
            outcome="completed",
            final_summary=issue.reason,
        )

    async def _record_decline(
        self,
        spine: WorkflowSpine,
        intake: Uc3AdviceEnquiry,
        *,
        reason_category: str,
        suitability_conclusion_ref: str,
        final_summary: str,
        capacity_for_loss_ref: str | None = None,
        platform_research_ref: str | None = None,
    ) -> Uc3WorkflowResult:
        args = _decline_arguments(
            intake=intake,
            reason_category=reason_category,
            suitability_conclusion_ref=suitability_conclusion_ref,
            capacity_for_loss_ref=capacity_for_loss_ref,
            platform_research_ref=platform_research_ref,
        )
        declined = await self._connector_step(
            spine,
            intake,
            UC3_STEP_DECLINE_ADVICE_SERVICE,
            invocation_id=_manual_route_invocation_id(intake),
            idempotency_key=str(args["decline_ref"]),
            arguments=args,
            payload_from_response=lambda response: {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "tool_name": _tool_name(UC3_STEP_DECLINE_ADVICE_SERVICE),
                "gateway_verdict": response.verdict,
                "enforced_mode": response.enforced_mode,
                "decline_ref": args["decline_ref"],
                "decline_reason_category": reason_category,
            },
        )
        if isinstance(declined, Uc3WorkflowResult):
            return declined
        return await self._close(
            spine,
            intake,
            outcome="declined_advice_service",
            final_summary=final_summary,
        )

    async def _route_manual_review(
        self,
        spine: WorkflowSpine,
        intake: Uc3AdviceEnquiry,
        *,
        reason_category: str,
        destination_category: str,
        final_summary: str,
        outcome: Uc3WorkflowOutcome = "manual_review",
        suitability_conclusion_ref: str | None = None,
    ) -> Uc3WorkflowResult:
        args = _manual_review_arguments(
            intake=intake,
            reason_category=reason_category,
            destination_category=destination_category,
            suitability_conclusion_ref=suitability_conclusion_ref,
        )
        handoff = await self._connector_step(
            spine,
            intake,
            UC3_STEP_MANUAL_REVIEW,
            invocation_id=_manual_route_invocation_id(intake),
            idempotency_key=str(args["handoff_ref"]),
            arguments=args,
            payload_from_response=lambda response: {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "tool_name": _tool_name(UC3_STEP_MANUAL_REVIEW),
                "gateway_verdict": response.verdict,
                "enforced_mode": response.enforced_mode,
                "handoff_ref": args["handoff_ref"],
                "review_reason_category": reason_category,
                "review_destination_category": destination_category,
            },
        )
        if isinstance(handoff, Uc3WorkflowResult):
            return handoff
        return await self._close(spine, intake, outcome=outcome, final_summary=final_summary)

    async def _retry_exhaustion_escalate(
        self,
        spine: WorkflowSpine,
        intake: Uc3AdviceEnquiry,
        failure: ActivityRetryExhaustedError,
    ) -> Uc3WorkflowResult:
        failure_reason = activity_failure_reason(failure.source)
        await spine.step(
            failure.failed_step,
            {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "step_outcome": "retry_exhausted",
                "failed_activity": failure.failed_activity,
                "retry_attempts": 3,
                "failure_reason": failure_reason,
                "dlq_required": True,
            },
        )
        dlq_result = await spine.record_retry_exhaustion_dlq(failure=failure)
        spine.advance_sequence(by=max(0, dlq_result.sequence + 1 - spine.sequence))
        return await self._escalate(
            spine,
            intake,
            "activity retry policy exhausted; DLQ evidence recorded",
        )

    async def _escalate(
        self,
        spine: WorkflowSpine,
        intake: Uc3AdviceEnquiry,
        reason: str,
    ) -> Uc3WorkflowResult:
        await spine.step(
            STEP_ESCALATE,
            {"advice_enquiry_ref": intake.advice_enquiry_ref, "reason": reason},
        )
        await spine.emit(
            EVENT_WORKFLOW_ESCALATED,
            STEP_ESCALATE,
            {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "reason": reason,
                "outcome": "escalated",
            },
        )
        return Uc3WorkflowResult(
            workflow_id=spine.correlation.workflow_id,
            tenant_id=intake.tenant_id,
            correlation_id=intake.correlation_id,
            advice_enquiry_id=intake.advice_enquiry_id,
            advice_enquiry_ref=intake.advice_enquiry_ref,
            outcome="escalated",
            path=spine.path,
            final_summary=reason,
            escalation_reason=reason,
        )

    async def _close(
        self,
        spine: WorkflowSpine,
        intake: Uc3AdviceEnquiry,
        *,
        outcome: Uc3WorkflowOutcome,
        final_summary: str,
    ) -> Uc3WorkflowResult:
        await spine.step(
            STEP_CLOSE,
            {
                "advice_enquiry_ref": intake.advice_enquiry_ref,
                "outcome": outcome,
                "final_summary": final_summary,
            },
        )
        await spine.emit(
            EVENT_WORKFLOW_COMPLETED,
            STEP_CLOSE,
            {"advice_enquiry_ref": intake.advice_enquiry_ref, "outcome": outcome},
        )
        return Uc3WorkflowResult(
            workflow_id=spine.correlation.workflow_id,
            tenant_id=intake.tenant_id,
            correlation_id=intake.correlation_id,
            advice_enquiry_id=intake.advice_enquiry_id,
            advice_enquiry_ref=intake.advice_enquiry_ref,
            outcome=outcome,
            path=spine.path,
            final_summary=final_summary,
        )


def _scope_classification_input(intake: Uc3AdviceEnquiry) -> dict[str, Any]:
    return {
        **_base_input(intake),
        "declared_objective_categories": intake.declared_objective_categories,
        "product_context_categories": intake.product_context_categories,
    }


def _fact_find_input(
    intake: Uc3AdviceEnquiry,
    scope: AgentInvocationResponse,
) -> dict[str, Any]:
    return {
        **_base_input(intake),
        "scope_classification_summary": scope.summary,
        "scope_classification_data": scope.structured_data,
    }


def _risk_profile_input(
    *,
    intake: Uc3AdviceEnquiry,
    fact_find: AgentInvocationResponse,
    attitude_to_risk: ToolGatewayResponse,
) -> dict[str, Any]:
    return {
        **_base_input(intake),
        "fact_find_data": fact_find.structured_data,
        "attitude_to_risk_gateway_output": attitude_to_risk.output,
    }


def _support_assessment_input(
    *,
    intake: Uc3AdviceEnquiry,
    fact_find: AgentInvocationResponse,
    risk_profile: AgentInvocationResponse,
    capacity: ToolGatewayResponse,
) -> dict[str, Any]:
    return {
        **_base_input(intake),
        "fact_find_data": fact_find.structured_data,
        "risk_profile_data": risk_profile.structured_data,
        "capacity_gateway_output": capacity.output,
    }


def _suitability_input(
    *,
    intake: Uc3AdviceEnquiry,
    scope: AgentInvocationResponse,
    fact_find: AgentInvocationResponse,
    risk_profile: AgentInvocationResponse,
    capacity: ToolGatewayResponse,
    support: AgentInvocationResponse,
    platform_research: ToolGatewayResponse,
) -> dict[str, Any]:
    return {
        **_base_input(intake),
        "scope_classification_data": scope.structured_data,
        "fact_find_data": fact_find.structured_data,
        "risk_profile_data": risk_profile.structured_data,
        "capacity_gateway_output": capacity.output,
        "support_assessment_data": support.structured_data,
        "platform_research_gateway_output": platform_research.output,
    }


def _base_input(intake: Uc3AdviceEnquiry) -> dict[str, Any]:
    return {
        "advice_enquiry_id": intake.advice_enquiry_id,
        "advice_enquiry_ref": intake.advice_enquiry_ref,
        "channel": intake.channel,
        "adapter_id": intake.adapter_id,
        "source_payload_ref": intake.source_payload_ref,
        "subject_summary": intake.subject_summary,
        "advice_need_summary": intake.advice_need_summary,
        "advice_need_categories": intake.advice_need_categories,
        "support_need_categories": intake.support_need_categories,
        "prospective_retail_client_ref": intake.prospective_retail_client_ref,
        "household_ref": intake.household_ref,
        "introducer_ref": intake.introducer_ref,
        "risk_preference_hint": intake.risk_preference_hint,
        "time_horizon_band": intake.time_horizon_band,
        "attachment_refs": [attachment.attachment_ref for attachment in intake.attachments_summary],
    }


def _attitude_to_risk_arguments(
    *,
    intake: Uc3AdviceEnquiry,
    fact_find: AgentInvocationResponse,
) -> dict[str, Any]:
    return {
        "advice_enquiry_ref": intake.advice_enquiry_ref,
        "prospective_retail_client_ref": _prospective_client_ref(intake, fact_find.structured_data),
        "fact_find_summary_ref": _fact_find_ref(intake, fact_find.structured_data),
        "questionnaire_bundle_ref": _questionnaire_bundle_ref(intake, fact_find.structured_data),
        "stated_risk_preference_band": _risk_preference_band(intake, fact_find.structured_data),
        "time_horizon_band": _time_horizon_band(intake, fact_find.structured_data),
        "objective_refs": _objective_refs(intake, fact_find.structured_data),
        "knowledge_experience_ref": _knowledge_experience_ref(intake, fact_find.structured_data),
        "risk_context_categories": _risk_context_categories(fact_find),
        "profiler_policy_ref": "policy_uc3_attitude_to_risk_profile_v1",
        "conduct_hook_refs": [
            "conduct_fca_cobs_9_suitability",
            "conduct_fca_prin_2a_consumer_duty",
        ],
    }


def _capacity_for_loss_arguments(
    *,
    intake: Uc3AdviceEnquiry,
    fact_find: AgentInvocationResponse,
) -> dict[str, Any]:
    args: dict[str, Any] = {
        "advice_enquiry_ref": intake.advice_enquiry_ref,
        "prospective_retail_client_ref": _prospective_client_ref(intake, fact_find.structured_data),
        "fact_find_summary_ref": _fact_find_ref(intake, fact_find.structured_data),
        "financial_situation_ref": _financial_situation_ref(intake, fact_find.structured_data),
        "objective_refs": _objective_refs(intake, fact_find.structured_data),
        "time_horizon_band": _time_horizon_band(intake, fact_find.structured_data),
        "liquidity_need_category": _liquidity_need_category(fact_find),
        "dependency_context_refs": _dependency_refs(fact_find.structured_data),
        "stress_scenario_categories": [
            "market_fall_20_percent",
            "income_reduction",
            "emergency_reserve_depletion",
        ],
        "assessment_policy_ref": "policy_uc3_capacity_for_loss_assessment_v1",
        "conduct_hook_refs": [
            "conduct_fca_cobs_9_suitability",
            "conduct_fca_prin_2a_foreseeable_harm",
        ],
    }
    if intake.household_ref is not None:
        args["household_ref"] = intake.household_ref
    return args


def _platform_research_arguments(
    *,
    intake: Uc3AdviceEnquiry,
    scope: AgentInvocationResponse,
    fact_find: AgentInvocationResponse,
    risk_profile: AgentInvocationResponse,
    capacity: ToolGatewayResponse,
) -> dict[str, Any]:
    return {
        "advice_enquiry_ref": intake.advice_enquiry_ref,
        "advice_scope_ref": _advice_scope_ref(intake, scope.structured_data),
        "prospective_retail_client_ref": _prospective_client_ref(intake, fact_find.structured_data),
        "risk_profile_ref": _risk_profile_ref(intake, fact_find, risk_profile.structured_data),
        "capacity_for_loss_ref": _capacity_for_loss_ref(intake, capacity.output),
        "objective_refs": _objective_refs(intake, fact_find.structured_data),
        "product_universe_scope": _product_universe_scope(risk_profile),
        "product_candidate_refs": _product_candidate_refs(fact_find.structured_data),
        "target_market_categories": ["in_target_market"],
        "platform_constraint_categories": ["none_identified"],
        "research_policy_refs": {
            "platform_research_policy_ref": "policy_uc3_platform_research_v1",
            "independent_advice_policy_ref": "policy_uc3_independent_advice_v1",
            "prod_policy_ref": "policy_uc3_prod_target_market_v1",
        },
        "conduct_hook_refs": [
            "conduct_fca_cobs_6_2b_independent_advice",
            "conduct_fca_prod_3_target_market",
            "conduct_fca_prin_2a_consumer_duty",
        ],
    }


def _suitability_report_draft_arguments(
    *,
    intake: Uc3AdviceEnquiry,
    fact_find: AgentInvocationResponse,
    risk_profile: AgentInvocationResponse,
    capacity: ToolGatewayResponse,
    support: AgentInvocationResponse,
    platform_research: ToolGatewayResponse,
    suitability: AgentInvocationResponse,
) -> dict[str, Any]:
    return {
        "advice_enquiry_ref": intake.advice_enquiry_ref,
        "suitability_report_ref": _suitability_report_ref(intake, suitability.structured_data),
        "suitability_conclusion_ref": _suitability_conclusion_ref(
            intake, suitability.structured_data
        ),
        "prospective_retail_client_ref": _prospective_client_ref(intake, fact_find.structured_data),
        "fact_find_summary_ref": _fact_find_ref(intake, fact_find.structured_data),
        "risk_profile_ref": _risk_profile_ref(intake, fact_find, risk_profile.structured_data),
        "capacity_for_loss_ref": _capacity_for_loss_ref(intake, capacity.output),
        "platform_research_ref": _platform_research_ref(intake, platform_research.output),
        "support_assessment_ref": _support_assessment_ref(intake, support.structured_data),
        "report_summary_ref": _report_summary_ref(intake, suitability.structured_data),
        "template_ref": "template_uc3_suitability_report_standard_v1",
        "draft_basis_categories": _draft_basis_categories(risk_profile, capacity, support),
        "draft_policy_ref": "policy_uc3_suitability_report_draft_v1",
        "conduct_hook_refs": list(_DEFAULT_CONDUCT_HOOK_REFS),
    }


def _suitability_report_issue_arguments(
    *,
    intake: Uc3AdviceEnquiry,
    support: AgentInvocationResponse,
    suitability: AgentInvocationResponse,
    draft: ToolGatewayResponse,
) -> dict[str, Any]:
    return {
        "advice_enquiry_ref": intake.advice_enquiry_ref,
        "suitability_report_ref": _string_value(draft.output.get("suitability_report_ref"))
        or _suitability_report_ref(intake, suitability.structured_data),
        "suitability_conclusion_ref": _suitability_conclusion_ref(
            intake, suitability.structured_data
        ),
        "approval_package_ref": _string_value(
            suitability.structured_data.get("approval_package_ref")
        )
        or _default_ref("approval", intake),
        "adviser_approval_ref": _string_value(
            suitability.structured_data.get("adviser_approval_ref")
        )
        or _default_ref("approval_adviser", intake),
        "issue_instruction_ref": _default_ref("issue_instruction", intake),
        "prospective_retail_client_ref": _prospective_client_ref(
            intake, suitability.structured_data
        ),
        "support_assessment_ref": _support_assessment_ref(intake, support.structured_data),
        "consumer_understanding_check_ref": _consumer_understanding_ref(
            intake, suitability.structured_data
        ),
        "issue_channel_category": _issue_channel_category(suitability),
        "issue_policy_ref": "policy_uc3_suitability_report_issue_v1",
        "conduct_hook_refs": [
            "conduct_fca_cobs_9_report",
            "conduct_fca_prin_2a_consumer_understanding",
            "conduct_fca_cobs_9_recordkeeping",
        ],
    }


def _decline_arguments(
    *,
    intake: Uc3AdviceEnquiry,
    reason_category: str,
    suitability_conclusion_ref: str,
    capacity_for_loss_ref: str | None,
    platform_research_ref: str | None,
) -> dict[str, Any]:
    args = {
        "advice_enquiry_ref": intake.advice_enquiry_ref,
        "suitability_conclusion_ref": suitability_conclusion_ref,
        "decline_ref": _default_ref("decline", intake),
        "decline_reason_category": reason_category,
        "decline_summary_ref": _default_ref("decline_summary", intake),
        "routing_policy_ref": "policy_uc3_suitability_routing_v1",
        "conduct_hook_refs": list(_DEFAULT_CONDUCT_HOOK_REFS),
    }
    if capacity_for_loss_ref is not None:
        args["capacity_for_loss_ref"] = capacity_for_loss_ref
    if platform_research_ref is not None:
        args["platform_research_ref"] = platform_research_ref
    return args


def _manual_review_arguments(
    *,
    intake: Uc3AdviceEnquiry,
    reason_category: str,
    destination_category: str,
    suitability_conclusion_ref: str | None,
) -> dict[str, Any]:
    args = {
        "advice_enquiry_ref": intake.advice_enquiry_ref,
        "handoff_ref": _default_ref("manual_review", intake),
        "review_reason_category": reason_category,
        "review_destination_category": destination_category,
        "safe_summary_ref": _default_ref("review_summary", intake),
        "routing_policy_ref": "policy_uc3_manual_review_routing_v1",
        "conduct_hook_refs": list(_DEFAULT_CONDUCT_HOOK_REFS),
    }
    if suitability_conclusion_ref is not None:
        args["suitability_conclusion_ref"] = suitability_conclusion_ref
    return args


def _scope_requires_decline(response: AgentInvocationResponse) -> bool:
    return _advice_scope(response) in {
        "restricted_advice_out_of_scope",
        "targeted_support_out_of_scope",
        "execution_only_request",
        "declined_out_of_scope",
        "out_of_scope",
    }


def _scope_requires_manual_review(response: AgentInvocationResponse) -> bool:
    return (
        response.recommended_next_step == "manual_review"
        or _advice_scope(response) != "independent_advice_in_scope"
        or _string_value(response.structured_data.get("authority_status"))
        in {"uncertain", "missing"}
    )


def _fact_find_requires_manual_review(response: AgentInvocationResponse) -> bool:
    return response.recommended_next_step in {
        "manual_review",
        "fact_find_incomplete",
    } or _fact_find_completeness(response) in {
        "missing_necessary_information",
        "stale_information",
        "contradictory_information",
    }


def _risk_profile_requires_approval(response: AgentInvocationResponse) -> bool:
    return response.recommended_next_step == "approval_required" or _risk_profile_status(
        response
    ) in {
        "mismatch_requires_approval",
        "client_overstates_risk",
        "client_understates_loss_concern",
    }


def _support_requires_approval(response: AgentInvocationResponse) -> bool:
    return response.recommended_next_step == "approval_required" or _support_status(response) in {
        "approval_required",
        "requires_handoff",
    }


def _capacity_requires_decline(response: ToolGatewayResponse) -> bool:
    return _capacity_for_loss_status(response) in {"negative", "blocked"}


def _capacity_requires_manual_review(response: ToolGatewayResponse) -> bool:
    return _capacity_for_loss_status(response) in {"limited", "dependency_risk", "manual_review"}


def _platform_requires_decline(response: ToolGatewayResponse) -> bool:
    return _string_value(response.output.get("target_market_status")) == "negative_target_market"


def _platform_requires_manual_review(response: ToolGatewayResponse) -> bool:
    return _string_value(response.output.get("product_universe_coverage")) in {
        "too_narrow",
        "platform_biased",
        "manufacturer_data_missing",
        "manual_review",
    }


def _should_escalate(response: AgentInvocationResponse) -> bool:
    return response.recommended_next_step == "escalate" or response.confidence < 0.5


def _advice_scope(response: AgentInvocationResponse) -> str:
    return _string_value(response.structured_data.get("advice_scope")) or "manual_review"


def _fact_find_completeness(response: AgentInvocationResponse) -> str:
    return _string_value(response.structured_data.get("fact_find_completeness")) or "manual_review"


def _risk_profile_status(response: AgentInvocationResponse) -> str:
    return _string_value(response.structured_data.get("risk_profile_status")) or "manual_review"


def _capacity_for_loss_status(response: ToolGatewayResponse) -> str:
    return _string_value(response.output.get("capacity_for_loss_status")) or "manual_review"


def _support_status(response: AgentInvocationResponse) -> str:
    return _string_value(response.structured_data.get("support_status")) or "manual_review"


def _suitability_outcome(response: AgentInvocationResponse) -> str:
    return _string_value(response.structured_data.get("suitability_outcome")) or "manual_review"


def _decline_reason_category(response: AgentInvocationResponse) -> str:
    value = _string_value(response.structured_data.get("decline_reason_category"))
    if value:
        return value
    match _suitability_outcome(response):
        case "out_of_scope":
            return "out_of_scope_advice"
        case "unsuitable":
            return "unsuitable_objective"
        case _:
            return "manual_adviser_decision"


def _review_reason_from_suitability(response: AgentInvocationResponse) -> str:
    value = _string_value(response.structured_data.get("review_reason_category"))
    if value:
        return value
    if response.recommended_next_step == "escalate":
        return "technical_exception"
    return "advice_scope_unclear"


def _advice_scope_ref(intake: Uc3AdviceEnquiry, structured_data: dict[str, Any]) -> str:
    return _string_value(structured_data.get("advice_scope_ref")) or _default_ref(
        "advice_scope", intake
    )


def _fact_find_ref(intake: Uc3AdviceEnquiry, structured_data: dict[str, Any]) -> str:
    return _string_value(structured_data.get("fact_find_summary_ref")) or _default_ref(
        "fact_find", intake
    )


def _prospective_client_ref(intake: Uc3AdviceEnquiry, structured_data: dict[str, Any]) -> str:
    return (
        _string_value(structured_data.get("prospective_retail_client_ref"))
        or intake.prospective_retail_client_ref
        or _default_ref("prospective_client", intake)
    )


def _financial_situation_ref(intake: Uc3AdviceEnquiry, structured_data: dict[str, Any]) -> str:
    return _string_value(structured_data.get("financial_situation_ref")) or _default_ref(
        "financial_situation", intake
    )


def _questionnaire_bundle_ref(intake: Uc3AdviceEnquiry, structured_data: dict[str, Any]) -> str:
    return _string_value(structured_data.get("questionnaire_bundle_ref")) or _default_ref(
        "risk_questionnaire", intake
    )


def _knowledge_experience_ref(intake: Uc3AdviceEnquiry, structured_data: dict[str, Any]) -> str:
    return _string_value(structured_data.get("knowledge_experience_ref")) or _default_ref(
        "knowledge_experience", intake
    )


def _risk_profile_ref(
    intake: Uc3AdviceEnquiry,
    fact_find: AgentInvocationResponse,
    structured_data: dict[str, Any],
) -> str:
    return (
        _string_value(structured_data.get("risk_profile_ref"))
        or _string_value(structured_data.get("profile_ref"))
        or _default_ref("risk_profile", intake)
    )


def _capacity_for_loss_ref(intake: Uc3AdviceEnquiry, structured_data: dict[str, Any]) -> str:
    return _string_value(structured_data.get("capacity_for_loss_ref")) or _default_ref(
        "capacity_for_loss", intake
    )


def _support_assessment_ref(intake: Uc3AdviceEnquiry, structured_data: dict[str, Any]) -> str:
    return _string_value(structured_data.get("support_assessment_ref")) or _default_ref(
        "support_assessment", intake
    )


def _platform_research_ref(intake: Uc3AdviceEnquiry, structured_data: dict[str, Any]) -> str:
    return _string_value(structured_data.get("platform_research_ref")) or _default_ref(
        "platform_research", intake
    )


def _suitability_conclusion_ref(
    intake: Uc3AdviceEnquiry,
    structured_data: dict[str, Any],
) -> str:
    return _string_value(structured_data.get("suitability_conclusion_ref")) or _default_ref(
        "suitability_conclusion", intake
    )


def _suitability_report_ref(intake: Uc3AdviceEnquiry, structured_data: dict[str, Any]) -> str:
    return _string_value(structured_data.get("suitability_report_ref")) or _default_ref(
        "suitability_report", intake
    )


def _report_summary_ref(intake: Uc3AdviceEnquiry, structured_data: dict[str, Any]) -> str:
    return _string_value(structured_data.get("report_summary_ref")) or _default_ref(
        "report_summary", intake
    )


def _consumer_understanding_ref(intake: Uc3AdviceEnquiry, structured_data: dict[str, Any]) -> str:
    return _string_value(structured_data.get("consumer_understanding_check_ref")) or _default_ref(
        "consumer_understanding", intake
    )


def _objective_refs(intake: Uc3AdviceEnquiry, structured_data: dict[str, Any]) -> list[str]:
    values = _string_list_value(structured_data.get("objective_refs"))
    if values:
        return values
    categories = intake.declared_objective_categories or ["advice_need"]
    return [_default_ref(f"objective_{category}", intake) for category in categories[:12]]


def _dependency_refs(structured_data: dict[str, Any]) -> list[str]:
    return _string_list_value(structured_data.get("dependency_context_refs"))


def _risk_context_categories(response: AgentInvocationResponse) -> list[str]:
    values = _string_list_value(response.structured_data.get("risk_context_categories"))
    return values or ["none_identified"]


def _product_candidate_refs(structured_data: dict[str, Any]) -> list[str]:
    values = _string_list_value(structured_data.get("product_candidate_refs"))
    return values or ["product_candidate_uc3_default_model_portfolio"]


def _vulnerability_marker_categories(response: AgentInvocationResponse) -> list[str]:
    values = _string_list_value(response.structured_data.get("vulnerability_marker_categories"))
    return values or ["none"]


def _time_horizon_band(intake: Uc3AdviceEnquiry, structured_data: dict[str, Any]) -> str:
    value = _string_value(structured_data.get("time_horizon_band")) or intake.time_horizon_band
    return value or "unknown"


def _risk_preference_band(intake: Uc3AdviceEnquiry, structured_data: dict[str, Any]) -> str:
    return (
        _string_value(structured_data.get("risk_preference_band"))
        or intake.risk_preference_hint
        or "not_disclosed"
    )


def _liquidity_need_category(response: AgentInvocationResponse) -> str:
    return _string_value(response.structured_data.get("liquidity_need_category")) or "unknown"


def _product_universe_scope(response: AgentInvocationResponse) -> str:
    return (
        _string_value(response.structured_data.get("product_universe_scope"))
        or "independent_full_relevant_market"
    )


def _issue_channel_category(response: AgentInvocationResponse) -> str:
    return _string_value(response.structured_data.get("issue_channel_category")) or "email"


def _draft_basis_categories(
    risk_profile: AgentInvocationResponse,
    capacity: ToolGatewayResponse,
    support: AgentInvocationResponse,
) -> list[str]:
    values = _string_list_value(risk_profile.structured_data.get("draft_basis_categories"))
    if values:
        return values
    categories = ["standard_independent_advice"]
    if _risk_profile_status(risk_profile) == "aligned":
        categories.append("product_universe_review")
    if _capacity_for_loss_status(capacity) == "limited":
        categories.append("capacity_for_loss_limited")
    if _support_status(support) == "support_adjustment_recorded":
        categories.append("vulnerability_support_adjustment")
    return categories[:8]


def _manual_route_invocation_id(intake: Uc3AdviceEnquiry) -> str:
    return f"invocation_uc3_manual_route_{_ref_suffix(intake)}"


def _default_ref(prefix: str, intake: Uc3AdviceEnquiry) -> str:
    return f"{prefix}_{_ref_suffix(intake)}"


def _ref_suffix(intake: Uc3AdviceEnquiry) -> str:
    prefix = "advice_enquiry_"
    value = intake.advice_enquiry_ref
    if value.startswith(prefix):
        value = value[len(prefix) :]
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)
    return safe or "unknown"


def _string_value(value: object) -> str:
    return value if isinstance(value, str) else ""


def _string_list_value(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    return [item for item in items if isinstance(item, str)]


def _tool_name(step: WorkflowStepDefinition) -> str:
    if step.connector_spec is None:
        return ""
    return step.connector_spec.tool_name


__all__ = [
    "UC3_IFA_SUITABILITY_INTAKE_DEFINITION",
    "UC3_WORKFLOW_ACTOR_ID",
    "UC3_WORKFLOW_TYPE",
    "Uc3IfaSuitabilityIntakeWorkflow",
]

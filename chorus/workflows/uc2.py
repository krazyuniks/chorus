"""UC2 legal-services intake and conflict-check workflow on the shared spine.

The UC2 workflow is definition-first R4 work: it declares the legal intake
lifecycle over the existing `WorkflowSpine` primitives and keeps every
effectful boundary behind the existing agent-runtime and Tool Gateway
activities. Runtime connector adapters, provider routes, approval apply, DB
schema, projections, and eval fixtures land in later P4 slices.
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
    Uc2LegalIntake,
    Uc2WorkflowOutcome,
    Uc2WorkflowResult,
    WorkflowCorrelation,
)

UC2_WORKFLOW_TYPE = "uc2_legal_services_intake_conflict_check"
UC2_WORKFLOW_ACTOR_ID = "uc2.workflow"

UC2_AGENT_IO_CONTRACT = "contracts/llm_provider/uc2_agent_io.schema.json"

STEP_INTAKE = "intake"
STEP_MATTER_CLASSIFICATION = "matter_classification"
STEP_PARTY_EXTRACTION = "party_extraction"
STEP_CONFLICT_CHECK = "conflict_check"
STEP_CONFLICT_DETERMINATION = "conflict_determination"
STEP_CONFLICT_EXCEPTION_APPROVAL = "conflict_exception_approval"
STEP_KYC_BENEFICIAL_OWNERSHIP = "kyc_beneficial_ownership"
STEP_AML_ASSESSMENT = "aml_assessment"
STEP_AML_EDD_APPROVAL = "aml_edd_approval"
STEP_ENGAGEMENT_DECISION = "engagement_decision"
STEP_ENGAGEMENT_LETTER_DRAFT = "engagement_letter_draft"
STEP_ENGAGEMENT_LETTER_SEND = "engagement_letter_send"
STEP_DECLINE_TO_ACT = "decline_to_act"
STEP_MANUAL_REVIEW = "manual_review"
STEP_CLOSE = "close"

_AGENT_ID_CONFLICT_ANALYST = "uc2.conflict_analyst"
_AGENT_ID_AML_ASSESSOR = "uc2.aml_assessor"
_AGENT_ID_ENGAGEMENT_DECIDER = "uc2.engagement_decider"

_DEFAULT_CONDUCT_HOOK_REFS = (
    "conduct_sra_identify_client_8_1",
    "conduct_sra_conflict_6_1_6_2",
    "conduct_sra_confidentiality_6_3_6_5",
    "conduct_mlr_cdd_reg_27_28",
    "conduct_sra_accountability_7_1_7_2",
)

UC2_STEP_INTAKE = WorkflowStepDefinition(step_name=STEP_INTAKE, kind=WorkflowStepKind.INTAKE)

UC2_STEP_MATTER_CLASSIFICATION = WorkflowStepDefinition(
    step_name=STEP_MATTER_CLASSIFICATION,
    kind=WorkflowStepKind.AGENT,
    agent_spec=AgentSpec(
        agent_role="legal_matter_classifier",
        task_kind="uc2_matter_classification",
        expected_output_contract=UC2_AGENT_IO_CONTRACT,
    ),
)

UC2_STEP_PARTY_EXTRACTION = WorkflowStepDefinition(
    step_name=STEP_PARTY_EXTRACTION,
    kind=WorkflowStepKind.AGENT,
    agent_spec=AgentSpec(
        agent_role="legal_party_extractor",
        task_kind="uc2_party_extraction",
        expected_output_contract=UC2_AGENT_IO_CONTRACT,
    ),
)

UC2_STEP_CONFLICT_CHECK = WorkflowStepDefinition(
    step_name=STEP_CONFLICT_CHECK,
    kind=WorkflowStepKind.CONNECTOR,
    connector_spec=ConnectorSpec(
        agent_id=_AGENT_ID_CONFLICT_ANALYST,
        tool_name="conflict_check.search",
        mode="read",
    ),
)

UC2_STEP_CONFLICT_DETERMINATION = WorkflowStepDefinition(
    step_name=STEP_CONFLICT_DETERMINATION,
    kind=WorkflowStepKind.AGENT,
    agent_spec=AgentSpec(
        agent_role="conflict_analyst",
        task_kind="uc2_conflict_determination",
        expected_output_contract=UC2_AGENT_IO_CONTRACT,
    ),
)

UC2_STEP_CONFLICT_EXCEPTION_APPROVAL = WorkflowStepDefinition(
    step_name=STEP_CONFLICT_EXCEPTION_APPROVAL,
    kind=WorkflowStepKind.APPROVAL_GATE,
    approval_policy=ApprovalPolicy(
        agent_id=_AGENT_ID_CONFLICT_ANALYST,
        tool_name="engagement_letter.send",
        requested_mode="write",
    ),
)

UC2_STEP_KYC_BENEFICIAL_OWNERSHIP = WorkflowStepDefinition(
    step_name=STEP_KYC_BENEFICIAL_OWNERSHIP,
    kind=WorkflowStepKind.CONNECTOR,
    connector_spec=ConnectorSpec(
        agent_id=_AGENT_ID_AML_ASSESSOR,
        tool_name="kyc_bo.lookup",
        mode="read",
    ),
)

UC2_STEP_AML_ASSESSMENT = WorkflowStepDefinition(
    step_name=STEP_AML_ASSESSMENT,
    kind=WorkflowStepKind.CONNECTOR,
    connector_spec=ConnectorSpec(
        agent_id=_AGENT_ID_AML_ASSESSOR,
        tool_name="aml_record_store.record_assessment",
        mode="write",
    ),
)

UC2_STEP_AML_EDD_APPROVAL = WorkflowStepDefinition(
    step_name=STEP_AML_EDD_APPROVAL,
    kind=WorkflowStepKind.APPROVAL_GATE,
    approval_policy=ApprovalPolicy(
        agent_id=_AGENT_ID_AML_ASSESSOR,
        tool_name="aml_record_store.record_assessment",
        requested_mode="write",
    ),
)

UC2_STEP_ENGAGEMENT_DECISION = WorkflowStepDefinition(
    step_name=STEP_ENGAGEMENT_DECISION,
    kind=WorkflowStepKind.AGENT,
    agent_spec=AgentSpec(
        agent_role="engagement_decider",
        task_kind="uc2_engagement_decision",
        expected_output_contract=UC2_AGENT_IO_CONTRACT,
    ),
)

UC2_STEP_ENGAGEMENT_LETTER_DRAFT = WorkflowStepDefinition(
    step_name=STEP_ENGAGEMENT_LETTER_DRAFT,
    kind=WorkflowStepKind.CONNECTOR,
    connector_spec=ConnectorSpec(
        agent_id=_AGENT_ID_ENGAGEMENT_DECIDER,
        tool_name="engagement_letter.draft",
        mode="write",
    ),
)

UC2_STEP_ENGAGEMENT_LETTER_SEND = WorkflowStepDefinition(
    step_name=STEP_ENGAGEMENT_LETTER_SEND,
    kind=WorkflowStepKind.APPROVAL_GATE,
    connector_spec=ConnectorSpec(
        agent_id=_AGENT_ID_ENGAGEMENT_DECIDER,
        tool_name="engagement_letter.send",
        mode="write",
    ),
    approval_policy=ApprovalPolicy(
        agent_id=_AGENT_ID_ENGAGEMENT_DECIDER,
        tool_name="engagement_letter.send",
        requested_mode="write",
    ),
)

UC2_STEP_DECLINE_TO_ACT = WorkflowStepDefinition(
    step_name=STEP_DECLINE_TO_ACT,
    kind=WorkflowStepKind.CONNECTOR,
    connector_spec=ConnectorSpec(
        agent_id=_AGENT_ID_ENGAGEMENT_DECIDER,
        tool_name="engagement_letter.record_decline",
        mode="write",
    ),
)

UC2_STEP_MANUAL_REVIEW = WorkflowStepDefinition(
    step_name=STEP_MANUAL_REVIEW,
    kind=WorkflowStepKind.CONNECTOR,
    connector_spec=ConnectorSpec(
        agent_id=_AGENT_ID_ENGAGEMENT_DECIDER,
        tool_name="engagement_letter.route_manual_review",
        mode="write",
    ),
)

UC2_STEP_CLOSE = WorkflowStepDefinition(step_name=STEP_CLOSE, kind=WorkflowStepKind.TERMINAL)

UC2_STEP_ESCALATE = WorkflowStepDefinition(step_name=STEP_ESCALATE, kind=WorkflowStepKind.TERMINAL)

UC2_LEGAL_SERVICES_INTAKE_CONFLICT_CHECK_DEFINITION = WorkflowDefinition(
    workflow_type=UC2_WORKFLOW_TYPE,
    steps=(
        UC2_STEP_INTAKE,
        UC2_STEP_MATTER_CLASSIFICATION,
        UC2_STEP_PARTY_EXTRACTION,
        UC2_STEP_CONFLICT_CHECK,
        UC2_STEP_CONFLICT_DETERMINATION,
        UC2_STEP_CONFLICT_EXCEPTION_APPROVAL,
        UC2_STEP_KYC_BENEFICIAL_OWNERSHIP,
        UC2_STEP_AML_ASSESSMENT,
        UC2_STEP_AML_EDD_APPROVAL,
        UC2_STEP_ENGAGEMENT_DECISION,
        UC2_STEP_ENGAGEMENT_LETTER_DRAFT,
        UC2_STEP_ENGAGEMENT_LETTER_SEND,
        UC2_STEP_DECLINE_TO_ACT,
        UC2_STEP_MANUAL_REVIEW,
        UC2_STEP_CLOSE,
        UC2_STEP_ESCALATE,
    ),
)


@workflow.defn(name="Uc2LegalServicesIntakeConflictCheckWorkflow")
class Uc2LegalServicesIntakeConflictCheckWorkflow:
    """UC2 legal-services intake and conflict-check workflow.

    The workflow contains deterministic step composition and branch selection
    only. Agent execution, Tool Gateway dispatch, persistence, timestamps,
    event IDs, and connector side effects remain activity-owned.
    """

    @workflow.run
    async def run(self, intake: Uc2LegalIntake) -> Uc2WorkflowResult:
        correlation = WorkflowCorrelation(
            tenant_id=intake.tenant_id,
            correlation_id=intake.correlation_id,
            workflow_id=workflow.info().workflow_id,
            workflow_type=UC2_WORKFLOW_TYPE,
            workflow_actor_id=UC2_WORKFLOW_ACTOR_ID,
            subject_id=intake.legal_intake_id,
            subject_ref=intake.legal_intake_ref,
            subject_summary=intake.subject_summary,
        )
        spine = WorkflowSpine(correlation)

        await spine.emit(
            EVENT_ENQUIRY_RECEIVED,
            STEP_INTAKE,
            {
                "legal_intake_ref": intake.legal_intake_ref,
                "subject_summary": intake.subject_summary,
                "channel": intake.channel,
                "adapter_id": intake.adapter_id,
                "source_payload_ref": intake.source_payload_ref,
                "matter_scope_summary": intake.matter_scope_summary,
            },
        )
        await spine.emit(
            EVENT_WORKFLOW_STARTED,
            STEP_INTAKE,
            {
                "legal_intake_ref": intake.legal_intake_ref,
                "channel": intake.channel,
            },
        )
        await spine.step(
            STEP_INTAKE,
            {
                "legal_intake_ref": intake.legal_intake_ref,
                "channel": intake.channel,
                "party_hint_count": len(intake.party_role_hints),
                "attachment_count": len(intake.attachments_summary),
            },
        )

        classification = await self._agent_step(
            spine,
            intake,
            UC2_STEP_MATTER_CLASSIFICATION,
            _classification_input(intake),
            lambda response: {
                "legal_intake_ref": intake.legal_intake_ref,
                "matter_type": _string_value(response.structured_data.get("matter_type")),
                "matter_scope_ref": _matter_scope_ref(intake, response.structured_data),
                "classification_summary": response.summary,
                "confidence": response.confidence,
            },
        )
        if isinstance(classification, Uc2WorkflowResult):
            return classification

        party_graph = await self._agent_step(
            spine,
            intake,
            UC2_STEP_PARTY_EXTRACTION,
            _party_extraction_input(intake, classification),
            lambda response: {
                "legal_intake_ref": intake.legal_intake_ref,
                "party_graph_ref": _party_graph_ref(intake, response.structured_data),
                "prospective_client_ref": _prospective_client_ref(intake, response.structured_data),
                "authority_status": _string_value(response.structured_data.get("authority_status")),
                "party_graph_ambiguous": _bool_value(
                    response.structured_data.get("party_graph_ambiguous")
                ),
                "confidence": response.confidence,
            },
        )
        if isinstance(party_graph, Uc2WorkflowResult):
            return party_graph
        if _party_graph_needs_manual_review(party_graph):
            return await self._route_manual_review(
                spine,
                intake,
                reason_category="party_graph_ambiguous",
                destination_category="matter_owner",
                final_summary="party graph requires manual review",
            )

        conflict_check = await self._connector_step(
            spine,
            intake,
            UC2_STEP_CONFLICT_CHECK,
            invocation_id=party_graph.invocation_id,
            idempotency_key=_party_graph_ref(intake, party_graph.structured_data),
            arguments=_conflict_check_arguments(
                intake=intake,
                classification=classification,
                party_graph=party_graph,
            ),
            payload_from_response=lambda response: {
                "legal_intake_ref": intake.legal_intake_ref,
                "tool_name": _tool_name(UC2_STEP_CONFLICT_CHECK),
                "gateway_verdict": response.verdict,
                "enforced_mode": response.enforced_mode,
                "conflict_check_ref": _string_value(response.output.get("conflict_check_ref")),
            },
        )
        if isinstance(conflict_check, Uc2WorkflowResult):
            return conflict_check

        conflict_determination = await self._agent_step(
            spine,
            intake,
            UC2_STEP_CONFLICT_DETERMINATION,
            _conflict_determination_input(
                intake=intake,
                classification=classification,
                party_graph=party_graph,
                conflict_check=conflict_check,
            ),
            lambda response: {
                "legal_intake_ref": intake.legal_intake_ref,
                "conflict_determination_ref": _conflict_determination_ref(
                    intake, response.structured_data
                ),
                "conflict_status": _conflict_status(response),
                "confidentiality_safeguard_status": _string_value(
                    response.structured_data.get("confidentiality_safeguard_status")
                ),
                "confidence": response.confidence,
            },
        )
        if isinstance(conflict_determination, Uc2WorkflowResult):
            return conflict_determination
        if _requires_conflict_approval(conflict_determination):
            await spine.step(
                STEP_CONFLICT_EXCEPTION_APPROVAL,
                {
                    "legal_intake_ref": intake.legal_intake_ref,
                    "approval_required": True,
                    "approval_action": "conflict_exception.accept.write",
                    "conflict_status": _conflict_status(conflict_determination),
                },
            )
            return await self._route_manual_review(
                spine,
                intake,
                outcome="approval_required",
                reason_category="confidentiality_safeguard_missing",
                destination_category="partner",
                engagement_decision_ref=_default_ref("engagement_decision", intake),
                final_summary="conflict exception requires partner approval",
            )

        kyc = await self._connector_step(
            spine,
            intake,
            UC2_STEP_KYC_BENEFICIAL_OWNERSHIP,
            invocation_id=conflict_determination.invocation_id,
            idempotency_key=_prospective_client_ref(intake, party_graph.structured_data),
            arguments=_kyc_arguments(
                intake=intake,
                classification=classification,
                party_graph=party_graph,
            ),
            payload_from_response=lambda response: {
                "legal_intake_ref": intake.legal_intake_ref,
                "tool_name": _tool_name(UC2_STEP_KYC_BENEFICIAL_OWNERSHIP),
                "gateway_verdict": response.verdict,
                "enforced_mode": response.enforced_mode,
                "cdd_record_ref": _string_value(response.output.get("cdd_record_ref")),
                "cdd_status": _string_value(response.output.get("cdd_status")),
                "beneficial_ownership_status": _string_value(
                    response.output.get("beneficial_ownership_status")
                ),
            },
        )
        if isinstance(kyc, Uc2WorkflowResult):
            return kyc

        aml = await self._connector_step(
            spine,
            intake,
            UC2_STEP_AML_ASSESSMENT,
            invocation_id=conflict_determination.invocation_id,
            idempotency_key=_aml_risk_ref(intake, conflict_determination.structured_data),
            arguments=_aml_assessment_arguments(
                intake=intake,
                party_graph=party_graph,
                conflict_determination=conflict_determination,
                kyc=kyc,
            ),
            payload_from_response=lambda response: {
                "legal_intake_ref": intake.legal_intake_ref,
                "tool_name": _tool_name(UC2_STEP_AML_ASSESSMENT),
                "gateway_verdict": response.verdict,
                "enforced_mode": response.enforced_mode,
                "aml_risk_assessment_ref": _string_value(
                    response.output.get("aml_risk_assessment_ref")
                ),
                "aml_risk_rating": _string_value(response.output.get("aml_risk_rating")),
            },
        )
        if isinstance(aml, Uc2WorkflowResult):
            return aml
        if _requires_aml_approval(aml):
            await spine.step(
                STEP_AML_EDD_APPROVAL,
                {
                    "legal_intake_ref": intake.legal_intake_ref,
                    "approval_required": True,
                    "approval_action": "aml_edd.accept.write",
                    "aml_risk_rating": _string_value(aml.output.get("aml_risk_rating")),
                },
            )
            return await self._route_manual_review(
                spine,
                intake,
                outcome="approval_required",
                reason_category="edd_review_required",
                destination_category="mlro",
                engagement_decision_ref=_default_ref("engagement_decision", intake),
                final_summary="AML enhanced due diligence requires MLRO approval",
            )

        engagement_decision = await self._agent_step(
            spine,
            intake,
            UC2_STEP_ENGAGEMENT_DECISION,
            _engagement_decision_input(
                intake=intake,
                classification=classification,
                party_graph=party_graph,
                conflict_determination=conflict_determination,
                kyc=kyc,
                aml=aml,
            ),
            lambda response: {
                "legal_intake_ref": intake.legal_intake_ref,
                "engagement_decision_ref": _engagement_decision_ref(
                    intake, response.structured_data
                ),
                "engagement_outcome": _engagement_outcome(response),
                "policy_snapshot_ref": _string_value(
                    response.structured_data.get("policy_snapshot_ref")
                ),
                "confidence": response.confidence,
            },
        )
        if isinstance(engagement_decision, Uc2WorkflowResult):
            return engagement_decision

        match _engagement_outcome(engagement_decision):
            case "accept_for_engagement" | "accept_subject_to_approval":
                return await self._draft_and_route_engagement_letter(
                    spine,
                    intake,
                    party_graph=party_graph,
                    conflict_determination=conflict_determination,
                    kyc=kyc,
                    aml=aml,
                    engagement_decision=engagement_decision,
                )
            case "decline_to_act":
                return await self._record_decline(
                    spine,
                    intake,
                    conflict_determination=conflict_determination,
                    aml=aml,
                    engagement_decision=engagement_decision,
                )
            case _:
                return await self._route_manual_review(
                    spine,
                    intake,
                    reason_category=_review_reason_from_decision(engagement_decision),
                    destination_category="matter_owner",
                    engagement_decision_ref=_engagement_decision_ref(
                        intake, engagement_decision.structured_data
                    ),
                    final_summary="engagement decision requires manual review",
                )

    async def _agent_step(
        self,
        spine: WorkflowSpine,
        intake: Uc2LegalIntake,
        step: WorkflowStepDefinition,
        input_payload: dict[str, Any],
        completion_payload: Callable[[AgentInvocationResponse], dict[str, Any]],
    ) -> AgentInvocationResponse | Uc2WorkflowResult:
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
        intake: Uc2LegalIntake,
        step: WorkflowStepDefinition,
        *,
        invocation_id: str,
        idempotency_key: str,
        arguments: dict[str, Any],
        payload_from_response: Callable[[ToolGatewayResponse], dict[str, Any]],
    ) -> ToolGatewayResponse | Uc2WorkflowResult:
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

    async def _draft_and_route_engagement_letter(
        self,
        spine: WorkflowSpine,
        intake: Uc2LegalIntake,
        *,
        party_graph: AgentInvocationResponse,
        conflict_determination: AgentInvocationResponse,
        kyc: ToolGatewayResponse,
        aml: ToolGatewayResponse,
        engagement_decision: AgentInvocationResponse,
    ) -> Uc2WorkflowResult:
        draft_args = _engagement_letter_draft_arguments(
            intake=intake,
            party_graph=party_graph,
            conflict_determination=conflict_determination,
            aml=aml,
            engagement_decision=engagement_decision,
        )
        draft = await self._connector_step(
            spine,
            intake,
            UC2_STEP_ENGAGEMENT_LETTER_DRAFT,
            invocation_id=engagement_decision.invocation_id,
            idempotency_key=str(draft_args["engagement_letter_ref"]),
            arguments=draft_args,
            payload_from_response=lambda response: {
                "legal_intake_ref": intake.legal_intake_ref,
                "tool_name": _tool_name(UC2_STEP_ENGAGEMENT_LETTER_DRAFT),
                "gateway_verdict": response.verdict,
                "enforced_mode": response.enforced_mode,
                "engagement_letter_ref": _string_value(response.output.get("engagement_letter_ref"))
                or draft_args["engagement_letter_ref"],
            },
        )
        if isinstance(draft, Uc2WorkflowResult):
            return draft

        send_args = _engagement_letter_send_arguments(
            intake=intake,
            conflict_determination=conflict_determination,
            kyc=kyc,
            aml=aml,
            engagement_decision=engagement_decision,
            draft=draft,
        )
        send = await self._connector_step(
            spine,
            intake,
            UC2_STEP_ENGAGEMENT_LETTER_SEND,
            invocation_id=engagement_decision.invocation_id,
            idempotency_key=str(send_args["send_instruction_ref"]),
            arguments=send_args,
            payload_from_response=lambda response: {
                "legal_intake_ref": intake.legal_intake_ref,
                "tool_name": _tool_name(UC2_STEP_ENGAGEMENT_LETTER_SEND),
                "gateway_verdict": response.verdict,
                "enforced_mode": response.enforced_mode,
                "approval_required": response.verdict in {"approval_required", "propose"},
                "engagement_letter_ref": send_args["engagement_letter_ref"],
            },
        )
        if isinstance(send, Uc2WorkflowResult):
            return send
        if send.verdict in {"approval_required", "propose"}:
            return await self._close(
                spine,
                intake,
                outcome="approval_required",
                final_summary="engagement letter send requires approved Tool Gateway apply",
            )
        return await self._close(
            spine,
            intake,
            outcome="completed",
            final_summary=send.reason,
        )

    async def _record_decline(
        self,
        spine: WorkflowSpine,
        intake: Uc2LegalIntake,
        *,
        conflict_determination: AgentInvocationResponse,
        aml: ToolGatewayResponse,
        engagement_decision: AgentInvocationResponse,
    ) -> Uc2WorkflowResult:
        args = _decline_arguments(
            intake=intake,
            conflict_determination=conflict_determination,
            aml=aml,
            engagement_decision=engagement_decision,
        )
        declined = await self._connector_step(
            spine,
            intake,
            UC2_STEP_DECLINE_TO_ACT,
            invocation_id=engagement_decision.invocation_id,
            idempotency_key=str(args["decline_ref"]),
            arguments=args,
            payload_from_response=lambda response: {
                "legal_intake_ref": intake.legal_intake_ref,
                "tool_name": _tool_name(UC2_STEP_DECLINE_TO_ACT),
                "gateway_verdict": response.verdict,
                "enforced_mode": response.enforced_mode,
                "decline_ref": args["decline_ref"],
            },
        )
        if isinstance(declined, Uc2WorkflowResult):
            return declined
        return await self._close(
            spine,
            intake,
            outcome="declined_to_act",
            final_summary=declined.reason,
        )

    async def _route_manual_review(
        self,
        spine: WorkflowSpine,
        intake: Uc2LegalIntake,
        *,
        reason_category: str,
        destination_category: str,
        final_summary: str,
        outcome: Uc2WorkflowOutcome = "manual_review",
        engagement_decision_ref: str | None = None,
    ) -> Uc2WorkflowResult:
        args = _manual_review_arguments(
            intake=intake,
            reason_category=reason_category,
            destination_category=destination_category,
            engagement_decision_ref=engagement_decision_ref,
        )
        handoff = await self._connector_step(
            spine,
            intake,
            UC2_STEP_MANUAL_REVIEW,
            invocation_id=_manual_review_invocation_id(intake),
            idempotency_key=str(args["handoff_ref"]),
            arguments=args,
            payload_from_response=lambda response: {
                "legal_intake_ref": intake.legal_intake_ref,
                "tool_name": _tool_name(UC2_STEP_MANUAL_REVIEW),
                "gateway_verdict": response.verdict,
                "enforced_mode": response.enforced_mode,
                "handoff_ref": args["handoff_ref"],
                "review_reason_category": reason_category,
                "review_destination_category": destination_category,
            },
        )
        if isinstance(handoff, Uc2WorkflowResult):
            return handoff
        return await self._close(spine, intake, outcome=outcome, final_summary=final_summary)

    async def _retry_exhaustion_escalate(
        self,
        spine: WorkflowSpine,
        intake: Uc2LegalIntake,
        failure: ActivityRetryExhaustedError,
    ) -> Uc2WorkflowResult:
        failure_reason = activity_failure_reason(failure.source)
        await spine.step(
            failure.failed_step,
            {
                "legal_intake_ref": intake.legal_intake_ref,
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
        intake: Uc2LegalIntake,
        reason: str,
    ) -> Uc2WorkflowResult:
        await spine.step(
            STEP_ESCALATE,
            {"legal_intake_ref": intake.legal_intake_ref, "reason": reason},
        )
        await spine.emit(
            EVENT_WORKFLOW_ESCALATED,
            STEP_ESCALATE,
            {
                "legal_intake_ref": intake.legal_intake_ref,
                "reason": reason,
                "outcome": "escalated",
            },
        )
        return Uc2WorkflowResult(
            workflow_id=spine.correlation.workflow_id,
            tenant_id=intake.tenant_id,
            correlation_id=intake.correlation_id,
            legal_intake_id=intake.legal_intake_id,
            legal_intake_ref=intake.legal_intake_ref,
            outcome="escalated",
            path=spine.path,
            final_summary=reason,
            escalation_reason=reason,
        )

    async def _close(
        self,
        spine: WorkflowSpine,
        intake: Uc2LegalIntake,
        *,
        outcome: Uc2WorkflowOutcome,
        final_summary: str,
    ) -> Uc2WorkflowResult:
        await spine.step(
            STEP_CLOSE,
            {
                "legal_intake_ref": intake.legal_intake_ref,
                "outcome": outcome,
                "final_summary": final_summary,
            },
        )
        await spine.emit(
            EVENT_WORKFLOW_COMPLETED,
            STEP_CLOSE,
            {"legal_intake_ref": intake.legal_intake_ref, "outcome": outcome},
        )
        return Uc2WorkflowResult(
            workflow_id=spine.correlation.workflow_id,
            tenant_id=intake.tenant_id,
            correlation_id=intake.correlation_id,
            legal_intake_id=intake.legal_intake_id,
            legal_intake_ref=intake.legal_intake_ref,
            outcome=outcome,
            path=spine.path,
            final_summary=final_summary,
        )


def _classification_input(intake: Uc2LegalIntake) -> dict[str, Any]:
    return {
        **_base_input(intake),
        "matter_type_hint": intake.matter_type_hint,
        "jurisdiction_categories": intake.jurisdiction_categories,
        "known_party_refs": intake.known_party_refs,
    }


def _party_extraction_input(
    intake: Uc2LegalIntake,
    classification: AgentInvocationResponse,
) -> dict[str, Any]:
    return {
        **_base_input(intake),
        "classification_summary": classification.summary,
        "classification_data": classification.structured_data,
    }


def _conflict_determination_input(
    *,
    intake: Uc2LegalIntake,
    classification: AgentInvocationResponse,
    party_graph: AgentInvocationResponse,
    conflict_check: ToolGatewayResponse,
) -> dict[str, Any]:
    return {
        **_base_input(intake),
        "classification_summary": classification.summary,
        "classification_data": classification.structured_data,
        "party_graph_summary": party_graph.summary,
        "party_graph_data": party_graph.structured_data,
        "conflict_check_verdict": conflict_check.verdict,
        "conflict_check_output": conflict_check.output,
    }


def _engagement_decision_input(
    *,
    intake: Uc2LegalIntake,
    classification: AgentInvocationResponse,
    party_graph: AgentInvocationResponse,
    conflict_determination: AgentInvocationResponse,
    kyc: ToolGatewayResponse,
    aml: ToolGatewayResponse,
) -> dict[str, Any]:
    return {
        **_base_input(intake),
        "classification_data": classification.structured_data,
        "party_graph_data": party_graph.structured_data,
        "conflict_determination_data": conflict_determination.structured_data,
        "kyc_gateway_output": kyc.output,
        "aml_gateway_output": aml.output,
    }


def _base_input(intake: Uc2LegalIntake) -> dict[str, Any]:
    return {
        "legal_intake_id": intake.legal_intake_id,
        "legal_intake_ref": intake.legal_intake_ref,
        "channel": intake.channel,
        "adapter_id": intake.adapter_id,
        "source_payload_ref": intake.source_payload_ref,
        "subject_summary": intake.subject_summary,
        "matter_scope_summary": intake.matter_scope_summary,
        "prospective_client_ref": intake.prospective_client_ref,
        "instructing_contact_ref": intake.instructing_contact_ref,
        "party_role_hints": [
            {
                "party_ref": hint.party_ref,
                "role": hint.role,
                "party_category": hint.party_category,
            }
            for hint in intake.party_role_hints
        ],
        "attachment_refs": [attachment.attachment_ref for attachment in intake.attachments_summary],
    }


def _conflict_check_arguments(
    *,
    intake: Uc2LegalIntake,
    classification: AgentInvocationResponse,
    party_graph: AgentInvocationResponse,
) -> dict[str, Any]:
    jurisdiction_categories = (
        _string_list_value(classification.structured_data.get("jurisdiction_categories"))
        or intake.jurisdiction_categories
        or ["england_and_wales"]
    )
    return {
        "legal_intake_ref": intake.legal_intake_ref,
        "party_graph_ref": _party_graph_ref(intake, party_graph.structured_data),
        "matter_scope_ref": _matter_scope_ref(intake, classification.structured_data),
        "prospective_client_ref": _prospective_client_ref(intake, party_graph.structured_data),
        "party_search_terms": _party_search_terms(intake, party_graph.structured_data),
        "conflict_search_categories": [
            "current_client",
            "former_client",
            "adverse_party",
            "confidential_information",
        ],
        "jurisdiction_categories": jurisdiction_categories,
        "conflict_policy_ref": "policy_uc2_conflict_check_v1",
        "conduct_hook_refs": [
            "conduct_sra_conflict_6_1_6_2",
            "conduct_sra_confidentiality_6_3_6_5",
        ],
    }


def _kyc_arguments(
    *,
    intake: Uc2LegalIntake,
    classification: AgentInvocationResponse,
    party_graph: AgentInvocationResponse,
) -> dict[str, Any]:
    return {
        "legal_intake_ref": intake.legal_intake_ref,
        "party_graph_ref": _party_graph_ref(intake, party_graph.structured_data),
        "prospective_client_ref": _prospective_client_ref(intake, party_graph.structured_data),
        "entity_category": _string_value(party_graph.structured_data.get("entity_category"))
        or "company",
        "jurisdiction_categories": _string_list_value(
            classification.structured_data.get("jurisdiction_categories")
        )
        or intake.jurisdiction_categories
        or ["england_and_wales"],
        "beneficial_owner_refs": _string_list_value(
            party_graph.structured_data.get("beneficial_owner_refs")
        ),
        "controller_refs": _string_list_value(party_graph.structured_data.get("controller_refs")),
        "requested_evidence_categories": [
            "corporate_identity",
            "beneficial_ownership",
            "controller_identity",
            "authority_to_instruct",
        ],
        "lookup_policy_ref": "policy_uc2_kyc_bo_lookup_v1",
        "conduct_hook_refs": [
            "conduct_mlr_cdd_reg_27_28",
            "conduct_sra_identify_client_8_1",
        ],
    }


def _aml_assessment_arguments(
    *,
    intake: Uc2LegalIntake,
    party_graph: AgentInvocationResponse,
    conflict_determination: AgentInvocationResponse,
    kyc: ToolGatewayResponse,
) -> dict[str, Any]:
    cdd_status = _string_value(kyc.output.get("cdd_status")) or "complete_standard"
    bo_status = _string_value(kyc.output.get("beneficial_ownership_status")) or "complete"
    aml_rating = _aml_rating_from(kyc.output, conflict_determination.structured_data)
    return {
        "legal_intake_ref": intake.legal_intake_ref,
        "aml_risk_assessment_ref": _aml_risk_ref(intake, conflict_determination.structured_data),
        "prospective_client_ref": _prospective_client_ref(intake, party_graph.structured_data),
        "cdd_record_ref": _string_value(kyc.output.get("cdd_record_ref"))
        or _default_ref("cdd_record", intake),
        "beneficial_ownership_snapshot_ref": _string_value(
            kyc.output.get("beneficial_ownership_snapshot_ref")
        )
        or _default_ref("bo_snapshot", intake),
        "cdd_status": cdd_status,
        "beneficial_ownership_status": bo_status,
        "aml_risk_rating": aml_rating,
        "risk_factor_categories": _risk_factor_categories(aml_rating),
        "assessment_summary_ref": _default_ref("aml_summary", intake),
        "policy_refs": {
            "aml_policy_ref": "policy_uc2_aml_record_v1",
            "firm_risk_assessment_ref": "policy_uc2_firm_risk_assessment_2025",
            "sector_risk_source_ref": "policy_uc2_sra_sector_risk_2025",
        },
        "conduct_hook_refs": [
            "conduct_mlr_cdd_reg_27_28",
            "conduct_mlr_edd_reg_33",
            "conduct_mlr_recordkeeping_reg_40",
        ],
    }


def _engagement_letter_draft_arguments(
    *,
    intake: Uc2LegalIntake,
    party_graph: AgentInvocationResponse,
    conflict_determination: AgentInvocationResponse,
    aml: ToolGatewayResponse,
    engagement_decision: AgentInvocationResponse,
) -> dict[str, Any]:
    return {
        "legal_intake_ref": intake.legal_intake_ref,
        "engagement_letter_ref": _engagement_letter_ref(
            intake,
            engagement_decision.structured_data,
        ),
        "engagement_decision_ref": _engagement_decision_ref(
            intake, engagement_decision.structured_data
        ),
        "prospective_client_ref": _prospective_client_ref(intake, party_graph.structured_data),
        "matter_scope_ref": _matter_scope_ref(intake, engagement_decision.structured_data),
        "scope_summary_ref": _scope_summary_ref(intake, engagement_decision.structured_data),
        "conflict_determination_ref": _conflict_determination_ref(
            intake, conflict_determination.structured_data
        ),
        "aml_risk_assessment_ref": _string_value(aml.output.get("aml_risk_assessment_ref"))
        or _aml_risk_ref(intake, conflict_determination.structured_data),
        "template_ref": "template_uc2_engagement_letter_standard_v1",
        "draft_basis_categories": _draft_basis_categories(engagement_decision),
        "draft_policy_ref": "policy_uc2_engagement_letter_draft_v1",
        "conduct_hook_refs": list(_DEFAULT_CONDUCT_HOOK_REFS),
    }


def _engagement_letter_send_arguments(
    *,
    intake: Uc2LegalIntake,
    conflict_determination: AgentInvocationResponse,
    kyc: ToolGatewayResponse,
    aml: ToolGatewayResponse,
    engagement_decision: AgentInvocationResponse,
    draft: ToolGatewayResponse,
) -> dict[str, Any]:
    return {
        "legal_intake_ref": intake.legal_intake_ref,
        "engagement_letter_ref": _string_value(draft.output.get("engagement_letter_ref"))
        or _engagement_letter_ref(intake, engagement_decision.structured_data),
        "engagement_decision_ref": _engagement_decision_ref(
            intake, engagement_decision.structured_data
        ),
        "approval_package_ref": _string_value(
            engagement_decision.structured_data.get("approval_package_ref")
        )
        or _default_ref("approval", intake),
        "send_instruction_ref": _default_ref("send_instruction", intake),
        "prospective_client_ref": _prospective_client_ref(
            intake, engagement_decision.structured_data
        ),
        "matter_scope_ref": _matter_scope_ref(intake, engagement_decision.structured_data),
        "conflict_determination_ref": _conflict_determination_ref(
            intake, conflict_determination.structured_data
        ),
        "aml_risk_assessment_ref": _string_value(aml.output.get("aml_risk_assessment_ref"))
        or _aml_risk_ref(intake, conflict_determination.structured_data),
        "cdd_record_ref": _string_value(kyc.output.get("cdd_record_ref"))
        or _default_ref("cdd_record", intake),
        "send_channel_category": "email",
        "send_policy_ref": "policy_uc2_engagement_letter_send_v1",
        "conduct_hook_refs": [
            "conduct_sra_identify_client_8_1",
            "conduct_mlr_cdd_reg_27_28",
            "conduct_sra_accountability_7_1_7_2",
        ],
    }


def _decline_arguments(
    *,
    intake: Uc2LegalIntake,
    conflict_determination: AgentInvocationResponse,
    aml: ToolGatewayResponse,
    engagement_decision: AgentInvocationResponse,
) -> dict[str, Any]:
    return {
        "legal_intake_ref": intake.legal_intake_ref,
        "engagement_decision_ref": _engagement_decision_ref(
            intake, engagement_decision.structured_data
        ),
        "decline_ref": _default_ref("decline", intake),
        "decline_reason_category": _decline_reason_category(
            conflict_determination=conflict_determination,
            aml=aml,
            engagement_decision=engagement_decision,
        ),
        "conflict_determination_ref": _conflict_determination_ref(
            intake, conflict_determination.structured_data
        ),
        "aml_risk_assessment_ref": _string_value(aml.output.get("aml_risk_assessment_ref"))
        or _aml_risk_ref(intake, conflict_determination.structured_data),
        "decline_summary_ref": _default_ref("decline_summary", intake),
        "routing_policy_ref": "policy_uc2_engagement_routing_v1",
        "conduct_hook_refs": list(_DEFAULT_CONDUCT_HOOK_REFS),
    }


def _manual_review_arguments(
    *,
    intake: Uc2LegalIntake,
    reason_category: str,
    destination_category: str,
    engagement_decision_ref: str | None,
) -> dict[str, Any]:
    args = {
        "legal_intake_ref": intake.legal_intake_ref,
        "handoff_ref": _default_ref("manual_review", intake),
        "review_reason_category": reason_category,
        "review_destination_category": destination_category,
        "safe_summary_ref": _default_ref("review_summary", intake),
        "routing_policy_ref": "policy_uc2_manual_review_routing_v1",
        "conduct_hook_refs": list(_DEFAULT_CONDUCT_HOOK_REFS),
    }
    if engagement_decision_ref is not None:
        args["engagement_decision_ref"] = engagement_decision_ref
    return args


def _party_search_terms(
    intake: Uc2LegalIntake,
    structured_data: dict[str, Any],
) -> list[dict[str, Any]]:
    from_agent = _dict_list_value(structured_data.get("party_search_terms"))
    if from_agent:
        return from_agent
    return [
        {
            "party_ref": hint.party_ref,
            "role": hint.role,
            "party_category": hint.party_category,
        }
        for hint in intake.party_role_hints
    ] or [
        {
            "party_ref": "party_unknown_prospective_client",
            "role": "unknown",
            "party_category": "unknown",
        }
    ]


def _party_graph_needs_manual_review(response: AgentInvocationResponse) -> bool:
    return (
        _bool_value(response.structured_data.get("party_graph_ambiguous"))
        or _string_value(response.structured_data.get("authority_status"))
        in {"uncertain", "missing"}
        or response.recommended_next_step == "manual_review"
    )


def _requires_conflict_approval(response: AgentInvocationResponse) -> bool:
    return _conflict_status(response) in {
        "permitted_exception_candidate",
        "confidentiality_risk",
    }


def _requires_aml_approval(response: ToolGatewayResponse) -> bool:
    return _string_value(response.output.get("aml_risk_rating")) in {"high", "edd_required"}


def _should_escalate(response: AgentInvocationResponse) -> bool:
    return response.recommended_next_step == "escalate" or response.confidence < 0.5


def _engagement_outcome(response: AgentInvocationResponse) -> str:
    for key in ("engagement_outcome", "outcome", "decision_outcome"):
        value = _string_value(response.structured_data.get(key))
        if value:
            return value
    if response.recommended_next_step == "manual_review":
        return "manual_review"
    return "manual_review"


def _review_reason_from_decision(response: AgentInvocationResponse) -> str:
    value = _string_value(response.structured_data.get("review_reason_category"))
    if value:
        return value
    if response.recommended_next_step == "escalate":
        return "technical_exception"
    return "unknown_conflict_hit"


def _decline_reason_category(
    *,
    conflict_determination: AgentInvocationResponse,
    aml: ToolGatewayResponse,
    engagement_decision: AgentInvocationResponse,
) -> str:
    value = _string_value(engagement_decision.structured_data.get("decline_reason_category"))
    if value:
        return value
    conflict_status = _conflict_status(conflict_determination)
    if conflict_status in {"own_interest_conflict", "client_conflict_blocked"}:
        return conflict_status
    if conflict_status == "confidentiality_risk":
        return "confidentiality_risk_blocked"
    aml_rating = _string_value(aml.output.get("aml_risk_rating"))
    if aml_rating == "blocked":
        return "aml_blocked"
    return "manual_decision"


def _conflict_status(response: AgentInvocationResponse) -> str:
    return _string_value(response.structured_data.get("conflict_status")) or "unknown_manual_review"


def _aml_rating_from(
    kyc_output: dict[str, Any],
    conflict_data: dict[str, Any],
) -> str:
    aml_rating = _string_value(conflict_data.get("aml_risk_rating")) or _string_value(
        kyc_output.get("aml_risk_rating")
    )
    if aml_rating:
        return aml_rating
    if _string_value(kyc_output.get("cdd_status")) == "edd_required":
        return "edd_required"
    if _string_value(kyc_output.get("cdd_status")) == "blocked":
        return "blocked"
    return "standard"


def _risk_factor_categories(aml_rating: str) -> list[str]:
    if aml_rating in {"low", "standard"}:
        return ["none_identified"]
    if aml_rating == "edd_required":
        return ["complex_ownership"]
    if aml_rating == "high":
        return ["sector_risk_factor"]
    return ["source_of_funds_ambiguity"]


def _draft_basis_categories(response: AgentInvocationResponse) -> list[str]:
    values = _string_list_value(response.structured_data.get("draft_basis_categories"))
    return values or ["standard_terms", "scope_exclusions"]


def _party_graph_ref(intake: Uc2LegalIntake, structured_data: dict[str, Any]) -> str:
    return _string_value(structured_data.get("party_graph_ref")) or _default_ref("pgraph", intake)


def _matter_scope_ref(intake: Uc2LegalIntake, structured_data: dict[str, Any]) -> str:
    return _string_value(structured_data.get("matter_scope_ref")) or _default_ref("mscope", intake)


def _scope_summary_ref(intake: Uc2LegalIntake, structured_data: dict[str, Any]) -> str:
    return _string_value(structured_data.get("scope_summary_ref")) or _default_ref(
        "scope_summary", intake
    )


def _prospective_client_ref(intake: Uc2LegalIntake, structured_data: dict[str, Any]) -> str:
    return (
        _string_value(structured_data.get("prospective_client_ref"))
        or intake.prospective_client_ref
        or _default_ref("prospective_client", intake)
    )


def _conflict_determination_ref(
    intake: Uc2LegalIntake,
    structured_data: dict[str, Any],
) -> str:
    return _string_value(structured_data.get("conflict_determination_ref")) or _default_ref(
        "conflict_determination", intake
    )


def _aml_risk_ref(intake: Uc2LegalIntake, structured_data: dict[str, Any]) -> str:
    return _string_value(structured_data.get("aml_risk_assessment_ref")) or _default_ref(
        "aml_risk", intake
    )


def _engagement_decision_ref(intake: Uc2LegalIntake, structured_data: dict[str, Any]) -> str:
    return _string_value(structured_data.get("engagement_decision_ref")) or _default_ref(
        "engagement_decision", intake
    )


def _engagement_letter_ref(intake: Uc2LegalIntake, structured_data: dict[str, Any]) -> str:
    return _string_value(structured_data.get("engagement_letter_ref")) or _default_ref(
        "engagement_letter", intake
    )


def _manual_review_invocation_id(intake: Uc2LegalIntake) -> str:
    return f"invocation_uc2_manual_review_{_ref_suffix(intake)}"


def _default_ref(prefix: str, intake: Uc2LegalIntake) -> str:
    return f"{prefix}_{_ref_suffix(intake)}"


def _ref_suffix(intake: Uc2LegalIntake) -> str:
    prefix = "legal_intake_"
    value = intake.legal_intake_ref
    if value.startswith(prefix):
        value = value[len(prefix) :]
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)
    return safe or "unknown"


def _string_value(value: object) -> str:
    return value if isinstance(value, str) else ""


def _bool_value(value: object) -> bool:
    return value if isinstance(value, bool) else False


def _string_list_value(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    return [item for item in items if isinstance(item, str)]


def _dict_list_value(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    return [dict(cast(dict[str, Any], item)) for item in items if isinstance(item, dict)]


def _tool_name(step: WorkflowStepDefinition) -> str:
    if step.connector_spec is None:
        return ""
    return step.connector_spec.tool_name


__all__ = [
    "UC2_LEGAL_SERVICES_INTAKE_CONFLICT_CHECK_DEFINITION",
    "UC2_WORKFLOW_ACTOR_ID",
    "UC2_WORKFLOW_TYPE",
    "Uc2LegalServicesIntakeConflictCheckWorkflow",
]

"""UC1 enquiry-qualification workflow on the shared spine.

UC1 (UK personal-lines insurance broking inbound quote qualification) is the
first use case running on the shared `WorkflowSpine`. The workflow itself
keeps only deterministic branching and safe-ref assembly; agent execution,
connector dispatch, event IDs, timestamps, and persistence are owned by the
spine activities.

For UC1 ubiquitous language, see `docs/domain-model.md`. For port mapping
and the UC2 / UC3 deltas, see `docs/r1-adapter-mapping.md`.
"""

from __future__ import annotations

from typing import Any

from temporalio import workflow
from temporalio.exceptions import ActivityError

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
    Uc1EnquiryIntake,
    Uc1WorkflowResult,
    WorkflowCorrelation,
)

UC1_WORKFLOW_TYPE = "uc1_enquiry_qualification"

UC1_AGENT_IO_CONTRACT = "contracts/llm_provider/uc1_agent_io.schema.json"

STEP_INTAKE = "intake"
STEP_CLASSIFICATION = "classification"
STEP_QUALIFICATION = "qualification"
STEP_MISSING_DATA_REQUEST_DRAFT = "missing_data_request_draft"
STEP_MISSING_DATA_REQUEST_VALIDATION = "missing_data_request_validation"
STEP_MISSING_DATA_REQUEST_SEND = "missing_data_request_send"
STEP_COMPLETE = "complete"

_CONFIDENCE_THRESHOLD = 0.5
_MAX_DEEPER_CONTEXT_ATTEMPTS = 2
_MAX_REDRAFT_ATTEMPTS = 2

_AGENT_ID_REQUEST_DRAFTER = "uc1.request_drafter"

UC1_STEP_INTAKE = WorkflowStepDefinition(step_name=STEP_INTAKE, kind=WorkflowStepKind.INTAKE)

UC1_STEP_CLASSIFICATION = WorkflowStepDefinition(
    step_name=STEP_CLASSIFICATION,
    kind=WorkflowStepKind.AGENT,
    agent_spec=AgentSpec(
        agent_role="classifier",
        task_kind="enquiry_classification",
        expected_output_contract=UC1_AGENT_IO_CONTRACT,
    ),
)

UC1_STEP_QUALIFICATION = WorkflowStepDefinition(
    step_name=STEP_QUALIFICATION,
    kind=WorkflowStepKind.AGENT,
    agent_spec=AgentSpec(
        agent_role="qualifier",
        task_kind="enquiry_qualification",
        expected_output_contract=UC1_AGENT_IO_CONTRACT,
    ),
)

UC1_STEP_REQUEST_DRAFT = WorkflowStepDefinition(
    step_name=STEP_MISSING_DATA_REQUEST_DRAFT,
    kind=WorkflowStepKind.AGENT,
    agent_spec=AgentSpec(
        agent_role="request_drafter",
        task_kind="missing_data_request_draft",
        expected_output_contract=UC1_AGENT_IO_CONTRACT,
    ),
)

UC1_STEP_REQUEST_VALIDATION = WorkflowStepDefinition(
    step_name=STEP_MISSING_DATA_REQUEST_VALIDATION,
    kind=WorkflowStepKind.AGENT,
    agent_spec=AgentSpec(
        agent_role="validator",
        task_kind="missing_data_request_validation",
        expected_output_contract=UC1_AGENT_IO_CONTRACT,
    ),
)

UC1_STEP_REQUEST_SEND = WorkflowStepDefinition(
    step_name=STEP_MISSING_DATA_REQUEST_SEND,
    kind=WorkflowStepKind.APPROVAL_GATE,
    connector_spec=ConnectorSpec(
        agent_id=_AGENT_ID_REQUEST_DRAFTER,
        tool_name="outbound_comms.message",
        mode="propose",
    ),
    approval_policy=ApprovalPolicy(
        agent_id=_AGENT_ID_REQUEST_DRAFTER,
        tool_name="outbound_comms.message",
        requested_mode="write",
    ),
)

UC1_STEP_COMPLETE = WorkflowStepDefinition(step_name=STEP_COMPLETE, kind=WorkflowStepKind.TERMINAL)

UC1_STEP_ESCALATE = WorkflowStepDefinition(step_name=STEP_ESCALATE, kind=WorkflowStepKind.TERMINAL)

UC1_ENQUIRY_QUALIFICATION_DEFINITION = WorkflowDefinition(
    workflow_type=UC1_WORKFLOW_TYPE,
    steps=(
        UC1_STEP_INTAKE,
        UC1_STEP_CLASSIFICATION,
        UC1_STEP_QUALIFICATION,
        UC1_STEP_REQUEST_DRAFT,
        UC1_STEP_REQUEST_VALIDATION,
        UC1_STEP_REQUEST_SEND,
        UC1_STEP_COMPLETE,
        UC1_STEP_ESCALATE,
    ),
)


@workflow.defn(name="Uc1EnquiryQualificationWorkflow")
class Uc1EnquiryQualificationWorkflow:
    """UC1 enquiry qualification workflow.

    The workflow contains only deterministic branching. Event IDs,
    timestamps, database writes, LLM provider calls, gateway calls, and
    connector dispatch are all activity-owned through the spine.
    """

    @workflow.run
    async def run(self, intake: Uc1EnquiryIntake) -> Uc1WorkflowResult:
        correlation = WorkflowCorrelation(
            tenant_id=intake.tenant_id,
            correlation_id=intake.correlation_id,
            workflow_id=workflow.info().workflow_id,
            workflow_type=UC1_WORKFLOW_TYPE,
            subject_id=intake.enquiry_id,
            subject_ref=intake.enquiry_ref,
        )
        spine = WorkflowSpine(correlation)

        await spine.emit(
            EVENT_ENQUIRY_RECEIVED,
            STEP_INTAKE,
            {
                "enquiry_summary": intake.subject,
                "subject": intake.subject,
                "channel": intake.channel,
                "adapter_id": intake.adapter_id,
                "sender": intake.from_address.email,
                "message_id": intake.message_id,
                "enquiry_ref": intake.enquiry_ref,
            },
        )
        await spine.emit(
            EVENT_WORKFLOW_STARTED,
            STEP_INTAKE,
            {"enquiry_summary": intake.subject, "enquiry_ref": intake.enquiry_ref},
        )
        await spine.step(
            STEP_INTAKE,
            {
                "enquiry_summary": intake.subject,
                "channel": intake.channel,
                "body_chars": len(intake.body_text),
            },
        )

        classification = await self._classify_enquiry(spine, intake)
        if classification is None:
            return self._completed_or_escalated(spine, "classification failed")

        try:
            qualification = await spine.agent_call(
                UC1_STEP_QUALIFICATION,
                {
                    "enquiry_ref": intake.enquiry_ref,
                    "enquiry_subject": intake.subject,
                    "classification_summary": classification.summary,
                    "classification_data": classification.structured_data,
                },
            )
        except ActivityRetryExhaustedError as exc:
            return await self._retry_exhaustion_escalate(spine, intake, exc)
        await spine.step(
            STEP_QUALIFICATION,
            {
                "enquiry_ref": intake.enquiry_ref,
                "classification_summary": classification.summary,
                "qualification_summary": qualification.summary,
                "confidence": min(classification.confidence, qualification.confidence),
            },
        )
        if _should_escalate(qualification):
            return await self._escalate(spine, intake, "qualifier requested escalation")

        validated = await self._draft_and_validate_request(
            spine,
            intake,
            classification=classification,
            qualification=qualification,
        )
        if validated is None:
            return await self._escalate(spine, intake, "missing-data request validation failed")
        draft, validation = validated

        propose_arguments = _request_arguments_for(
            intake=intake,
            draft=draft,
            validation=validation,
        )
        idempotency_key = f"{correlation.workflow_id}:outbound_comms.message"
        try:
            gateway_result = await spine.connector_call(
                UC1_STEP_REQUEST_SEND,
                invocation_id=validation.invocation_id,
                idempotency_key=idempotency_key,
                arguments=propose_arguments,
            )
        except ActivityRetryExhaustedError as exc:
            return await self._retry_exhaustion_escalate(spine, intake, exc)
        except ActivityError as exc:
            failure_reason = activity_failure_reason(exc)
            await spine.step(
                STEP_MISSING_DATA_REQUEST_SEND,
                {
                    "enquiry_ref": intake.enquiry_ref,
                    "gateway_verdict": "connector_failure",
                    "enforced_mode": UC1_STEP_REQUEST_SEND.connector_spec.mode
                    if UC1_STEP_REQUEST_SEND.connector_spec is not None
                    else "propose",
                    "tool_name": "outbound_comms.message",
                    "connector_failure": True,
                    "compensation_required": True,
                    "failure_reason": failure_reason,
                },
            )
            await spine.compensate_tool_failure(
                step=UC1_STEP_REQUEST_SEND,
                invocation_id=validation.invocation_id,
                idempotency_key=idempotency_key,
                arguments=propose_arguments,
                failure_reason=failure_reason,
            )
            return await self._escalate(
                spine,
                intake,
                "outbound comms connector failure compensated and escalated",
            )

        await spine.step(
            STEP_MISSING_DATA_REQUEST_SEND,
            {
                "enquiry_ref": intake.enquiry_ref,
                "gateway_verdict": gateway_result.verdict,
                "enforced_mode": gateway_result.enforced_mode,
                "tool_name": "outbound_comms.message",
            },
        )
        if gateway_result.verdict in {"block", "approval_required"}:
            return await self._escalate(
                spine,
                intake,
                f"tool gateway returned {gateway_result.verdict}",
            )

        await spine.step(
            STEP_COMPLETE,
            {"enquiry_ref": intake.enquiry_ref, "final_summary": gateway_result.reason},
        )
        await spine.emit(
            EVENT_WORKFLOW_COMPLETED,
            STEP_COMPLETE,
            {"enquiry_ref": intake.enquiry_ref, "outcome": "completed"},
        )
        return Uc1WorkflowResult(
            workflow_id=correlation.workflow_id,
            tenant_id=intake.tenant_id,
            correlation_id=intake.correlation_id,
            enquiry_id=intake.enquiry_id,
            outcome="completed",
            path=spine.path,
            final_summary=gateway_result.reason,
        )

    async def _classify_enquiry(
        self,
        spine: WorkflowSpine,
        intake: Uc1EnquiryIntake,
    ) -> AgentInvocationResponse | None:
        classification: AgentInvocationResponse | None = None
        attempt = 1
        previous: AgentInvocationResponse | None = None
        while attempt <= _MAX_DEEPER_CONTEXT_ATTEMPTS:
            try:
                classification = await spine.agent_call(
                    UC1_STEP_CLASSIFICATION,
                    _classification_input(
                        intake=intake,
                        attempt=attempt,
                        previous=previous,
                    ),
                )
            except ActivityRetryExhaustedError as exc:
                await self._retry_exhaustion_escalate(spine, intake, exc)
                return None
            assert classification is not None
            if not _needs_deeper_context(classification):
                break
            should_retry = attempt < _MAX_DEEPER_CONTEXT_ATTEMPTS
            await spine.step(
                STEP_CLASSIFICATION,
                {
                    "enquiry_ref": intake.enquiry_ref,
                    "classification_attempt": attempt,
                    "classification_summary": classification.summary,
                    "confidence": classification.confidence,
                    "recommended_next_step": classification.recommended_next_step,
                    "deeper_context_requested": should_retry,
                    "deeper_context_exhausted": not should_retry,
                },
            )
            if not should_retry:
                await self._escalate(
                    spine,
                    intake,
                    "classification confidence remained below threshold after deeper context",
                )
                return None
            previous = classification
            attempt += 1

        if classification is None:
            await self._escalate(spine, intake, "classifier did not produce a result")
            return None
        if classification.recommended_next_step == "escalate":
            await self._escalate(spine, intake, "classifier requested escalation")
            return None
        await spine.step(
            STEP_CLASSIFICATION,
            {
                "enquiry_ref": intake.enquiry_ref,
                "classification_summary": classification.summary,
                "confidence": classification.confidence,
                "classification_attempt": attempt,
                "deeper_context_completed": attempt > 1,
            },
        )
        return classification

    async def _draft_and_validate_request(
        self,
        spine: WorkflowSpine,
        intake: Uc1EnquiryIntake,
        *,
        classification: AgentInvocationResponse,
        qualification: AgentInvocationResponse,
    ) -> tuple[AgentInvocationResponse, AgentInvocationResponse] | None:
        redraft_attempt = 1
        validator_reason: dict[str, Any] | None = None
        while True:
            try:
                draft = await spine.agent_call(
                    UC1_STEP_REQUEST_DRAFT,
                    _draft_input(
                        intake=intake,
                        classification_summary=classification.summary,
                        qualification_summary=qualification.summary,
                        redraft_attempt=redraft_attempt,
                        validator_reason=validator_reason,
                    ),
                )
            except ActivityRetryExhaustedError as exc:
                await self._retry_exhaustion_escalate(spine, intake, exc)
                return None
            await spine.step(
                STEP_MISSING_DATA_REQUEST_DRAFT,
                {
                    "enquiry_ref": intake.enquiry_ref,
                    "draft_summary": draft.summary,
                    "draft_body_text": draft.structured_data.get("draft_body_text", draft.summary),
                    "redraft_attempt": redraft_attempt,
                },
            )
            if _should_escalate(draft):
                await self._escalate(spine, intake, "request drafter requested escalation")
                return None

            try:
                validation = await spine.agent_call(
                    UC1_STEP_REQUEST_VALIDATION,
                    {
                        "enquiry_ref": intake.enquiry_ref,
                        "draft_body_text": draft.structured_data.get(
                            "draft_body_text", draft.summary
                        ),
                        "redraft_attempt": redraft_attempt,
                    },
                )
            except ActivityRetryExhaustedError as exc:
                await self._retry_exhaustion_escalate(spine, intake, exc)
                return None
            should_retry_redraft = (
                validation.recommended_next_step == "redraft"
                and redraft_attempt < _MAX_REDRAFT_ATTEMPTS
            )
            await spine.step(
                STEP_MISSING_DATA_REQUEST_VALIDATION,
                {
                    "enquiry_ref": intake.enquiry_ref,
                    "validation_summary": validation.summary,
                    "recommended_next_step": validation.recommended_next_step,
                    "redraft_attempt": redraft_attempt,
                    "redraft_requested": should_retry_redraft,
                    "redraft_exhausted": (
                        validation.recommended_next_step == "redraft" and not should_retry_redraft
                    ),
                },
            )
            if validation.recommended_next_step == "redraft":
                if not should_retry_redraft:
                    await self._escalate(
                        spine,
                        intake,
                        "validator requested redraft beyond bounded attempts",
                    )
                    return None
                validator_reason = _validator_reason_payload(validation)
                redraft_attempt += 1
                continue
            if _should_escalate(validation):
                await self._escalate(spine, intake, "validator requested escalation")
                return None
            return draft, validation

    async def _retry_exhaustion_escalate(
        self,
        spine: WorkflowSpine,
        intake: Uc1EnquiryIntake,
        failure: ActivityRetryExhaustedError,
    ) -> Uc1WorkflowResult:
        failure_reason = activity_failure_reason(failure.source)
        await spine.step(
            failure.failed_step,
            {
                "enquiry_ref": intake.enquiry_ref,
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
        intake: Uc1EnquiryIntake,
        reason: str,
    ) -> Uc1WorkflowResult:
        await spine.step(
            STEP_ESCALATE,
            {"enquiry_ref": intake.enquiry_ref, "reason": reason},
        )
        await spine.emit(
            EVENT_WORKFLOW_ESCALATED,
            STEP_ESCALATE,
            {"enquiry_ref": intake.enquiry_ref, "reason": reason, "outcome": "escalated"},
        )
        return Uc1WorkflowResult(
            workflow_id=spine.correlation.workflow_id,
            tenant_id=intake.tenant_id,
            correlation_id=intake.correlation_id,
            enquiry_id=intake.enquiry_id,
            outcome="escalated",
            path=spine.path,
            final_summary=reason,
            escalation_reason=reason,
        )

    def _completed_or_escalated(self, spine: WorkflowSpine, reason: str) -> Uc1WorkflowResult:
        return Uc1WorkflowResult(
            workflow_id=spine.correlation.workflow_id,
            tenant_id=spine.correlation.tenant_id,
            correlation_id=spine.correlation.correlation_id,
            enquiry_id=spine.correlation.subject_id,
            outcome="escalated",
            path=spine.path,
            final_summary=reason,
            escalation_reason=reason,
        )


def _should_escalate(response: AgentInvocationResponse) -> bool:
    return (
        response.recommended_next_step == "escalate" or response.confidence < _CONFIDENCE_THRESHOLD
    )


def _needs_deeper_context(response: AgentInvocationResponse) -> bool:
    return (
        response.recommended_next_step == "deeper_context"
        or response.confidence < _CONFIDENCE_THRESHOLD
    )


def _classification_input(
    *,
    intake: Uc1EnquiryIntake,
    attempt: int,
    previous: AgentInvocationResponse | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "enquiry_ref": intake.enquiry_ref,
        "enquiry_subject": intake.subject,
        "enquiry_body_text": intake.body_text,
        "channel": intake.channel,
        "sender": intake.from_address.email,
        "classification_attempt": attempt,
    }
    if previous is not None:
        payload.update(
            {
                "deeper_context": True,
                "previous_summary": previous.summary,
                "previous_confidence": previous.confidence,
                "previous_recommended_next_step": previous.recommended_next_step,
            }
        )
    return payload


def _draft_input(
    *,
    intake: Uc1EnquiryIntake,
    classification_summary: str,
    qualification_summary: str,
    redraft_attempt: int,
    validator_reason: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "enquiry_ref": intake.enquiry_ref,
        "enquiry_subject": intake.subject,
        "enquiry_body_text": intake.body_text,
        "classification_summary": classification_summary,
        "qualification_summary": qualification_summary,
        "redraft_attempt": redraft_attempt,
    }
    if validator_reason is not None:
        payload["validator_reason"] = validator_reason
    return payload


def _validator_reason_payload(validation: AgentInvocationResponse) -> dict[str, Any]:
    structured_reason = validation.structured_data.get("reason")
    payload: dict[str, Any] = {
        "summary": validation.summary,
        "rationale": validation.rationale,
    }
    if isinstance(structured_reason, dict):
        payload["structured"] = structured_reason
    elif structured_reason is not None:
        payload["structured"] = {"value": structured_reason}
    return payload


def _request_arguments_for(
    *,
    intake: Uc1EnquiryIntake,
    draft: AgentInvocationResponse,
    validation: AgentInvocationResponse,
) -> dict[str, Any]:
    del validation
    structured = draft.structured_data
    customer_ref = (
        structured.get("customer_ref")
        if isinstance(structured.get("customer_ref"), str)
        else "cust_unknown"
    )
    received_digest = "".join(ch for ch in intake.received_at if ch.isdigit())[:14] or "0"
    missing_data_request_ref = (
        structured.get("missing_data_request_ref")
        if isinstance(structured.get("missing_data_request_ref"), str)
        else f"mdr_{intake.enquiry_ref}_{int(received_digest):x}"
    )
    body_text = draft.structured_data.get("draft_body_text", draft.summary)
    if not isinstance(body_text, str) or not body_text:
        body_text = draft.summary
    subject = f"Information needed: {intake.subject}"
    return {
        "enquiry_ref": intake.enquiry_ref,
        "customer_ref": customer_ref,
        "missing_data_request_ref": missing_data_request_ref,
        "to_email": intake.from_address.email,
        "subject": subject,
        "body_text": body_text,
        "comms_policy_ref": "policy_uc1_outbound_comms_local_v1",
    }

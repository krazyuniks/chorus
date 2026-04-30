"""Deterministic Temporal workflow for the Lighthouse happy path."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

from chorus.workflows.types import (
    AgentInvocationRequest,
    AgentInvocationResponse,
    LighthouseWorkflowInput,
    LighthouseWorkflowResult,
    ToolGatewayRequest,
    ToolGatewayResponse,
    WorkflowEventCommand,
)

ACTIVITY_RECORD_WORKFLOW_EVENT = "lighthouse.record_workflow_event"
ACTIVITY_INVOKE_AGENT_RUNTIME = "lighthouse.invoke_agent_runtime"
ACTIVITY_INVOKE_TOOL_GATEWAY = "lighthouse.invoke_tool_gateway"

EVENT_LEAD_RECEIVED = "lead.received"
EVENT_WORKFLOW_STARTED = "workflow.started"
EVENT_STEP_STARTED = "workflow.step.started"
EVENT_STEP_COMPLETED = "workflow.step.completed"
EVENT_WORKFLOW_COMPLETED = "workflow.completed"
EVENT_WORKFLOW_ESCALATED = "workflow.escalated"
EVENT_WORKFLOW_FAILED = "workflow.failed"

STEP_INTAKE = "intake"
STEP_RESEARCH_QUALIFICATION = "research_qualification"
STEP_DRAFT = "draft"
STEP_VALIDATION = "validation"
STEP_PROPOSE_SEND = "propose_send"
STEP_COMPLETE = "complete"
STEP_ESCALATE = "escalate"

_ACTIVITY_TIMEOUT = timedelta(seconds=30)
_ACTIVITY_RETRY = RetryPolicy(maximum_attempts=3)
_MAX_RESEARCH_ATTEMPTS = 2
_CONFIDENCE_THRESHOLD = 0.5
_MAX_REDRAFT_ATTEMPTS = 2


@workflow.defn
class LighthouseWorkflow:
    """Phase 1A Lighthouse workflow.

    The workflow contains only deterministic branch logic. Event IDs,
    timestamps, database writes, model/runtime calls, gateway calls, and
    connector work are all activity-owned.
    """

    @workflow.run
    async def run(self, lead: LighthouseWorkflowInput) -> LighthouseWorkflowResult:
        workflow_id = workflow.info().workflow_id
        sequence = 1
        path: list[str] = []

        sequence = await self._emit(
            lead,
            workflow_id,
            sequence,
            EVENT_LEAD_RECEIVED,
            STEP_INTAKE,
            {
                "lead_summary": lead.subject,
                "subject": lead.subject,
                "sender": lead.sender.email,
                "message_id": lead.message_id,
                "source": lead.source,
            },
        )
        sequence = await self._emit(
            lead,
            workflow_id,
            sequence,
            EVENT_WORKFLOW_STARTED,
            STEP_INTAKE,
            {"lead_summary": lead.subject},
        )

        sequence = await self._step(
            lead,
            workflow_id,
            sequence,
            path,
            STEP_INTAKE,
            {"lead_summary": lead.subject, "body_chars": len(lead.body_text)},
        )

        research: AgentInvocationResponse | None = None
        research_attempt = 1
        previous_research: AgentInvocationResponse | None = None
        while research_attempt <= _MAX_RESEARCH_ATTEMPTS:
            research = await self._agent(
                lead,
                workflow_id,
                "researcher",
                "company_research",
                _research_input(
                    lead=lead,
                    attempt=research_attempt,
                    previous_research=previous_research,
                ),
            )
            if not _needs_deeper_research(research):
                break

            should_retry = research_attempt < _MAX_RESEARCH_ATTEMPTS
            sequence = await self._step(
                lead,
                workflow_id,
                sequence,
                path,
                STEP_RESEARCH_QUALIFICATION,
                {
                    "lead_summary": lead.subject,
                    "research_attempt": research_attempt,
                    "research_summary": research.summary,
                    "confidence": research.confidence,
                    "recommended_next_step": research.recommended_next_step,
                    "deeper_research_requested": should_retry,
                    "deeper_research_exhausted": not should_retry,
                },
            )
            if not should_retry:
                return await self._escalate(
                    lead,
                    workflow_id,
                    sequence,
                    path,
                    "research confidence remained below threshold after deeper research",
                )
            previous_research = research
            research_attempt += 1

        if research is None:
            return await self._escalate(
                lead,
                workflow_id,
                sequence,
                path,
                "research did not produce a result",
            )
        if research.recommended_next_step == "escalate":
            return await self._escalate(
                lead,
                workflow_id,
                sequence,
                path,
                "researcher requested escalation",
            )

        qualification = await self._agent(
            lead,
            workflow_id,
            "qualifier",
            "lead_qualification",
            {
                "lead_subject": lead.subject,
                "research_summary": research.summary,
                "research_data": research.structured_data,
            },
        )
        sequence = await self._step(
            lead,
            workflow_id,
            sequence,
            path,
            STEP_RESEARCH_QUALIFICATION,
            {
                "lead_summary": lead.subject,
                "research_summary": research.summary,
                "qualification_summary": qualification.summary,
                "confidence": min(research.confidence, qualification.confidence),
                "research_attempt": research_attempt,
                "deeper_research_completed": research_attempt > 1,
            },
        )
        if _should_escalate(qualification):
            return await self._escalate(
                lead,
                workflow_id,
                sequence,
                path,
                "qualification requested escalation",
            )

        redraft_attempt = 1
        validator_reason: dict[str, Any] | None = None
        draft: AgentInvocationResponse | None = None
        validation: AgentInvocationResponse | None = None
        while True:
            draft = await self._agent(
                lead,
                workflow_id,
                "drafter",
                "response_draft",
                _draft_input(
                    lead=lead,
                    research_summary=research.summary,
                    qualification_summary=qualification.summary,
                    redraft_attempt=redraft_attempt,
                    validator_reason=validator_reason,
                ),
            )
            sequence = await self._step(
                lead,
                workflow_id,
                sequence,
                path,
                STEP_DRAFT,
                {
                    "lead_summary": lead.subject,
                    "draft_summary": draft.summary,
                    "draft_response": draft.structured_data.get("draft_response", draft.summary),
                    "redraft_attempt": redraft_attempt,
                },
            )
            if _should_escalate(draft):
                return await self._escalate(
                    lead,
                    workflow_id,
                    sequence,
                    path,
                    "drafter requested escalation",
                )

            validation = await self._agent(
                lead,
                workflow_id,
                "validator",
                "response_validation",
                {
                    "lead_subject": lead.subject,
                    "draft_response": draft.structured_data.get("draft_response", draft.summary),
                    "redraft_attempt": redraft_attempt,
                },
            )
            should_retry_redraft = (
                validation.recommended_next_step == "redraft"
                and redraft_attempt < _MAX_REDRAFT_ATTEMPTS
            )
            sequence = await self._step(
                lead,
                workflow_id,
                sequence,
                path,
                STEP_VALIDATION,
                {
                    "lead_summary": lead.subject,
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
                    return await self._escalate(
                        lead,
                        workflow_id,
                        sequence,
                        path,
                        "validator requested redraft beyond bounded attempts",
                    )
                validator_reason = _validator_reason_payload(validation)
                redraft_attempt += 1
                continue
            if _should_escalate(validation):
                return await self._escalate(
                    lead,
                    workflow_id,
                    sequence,
                    path,
                    "validator requested escalation",
                )
            break

        gateway_result = await self._gateway(
            lead,
            workflow_id,
            validation.invocation_id,
            "lighthouse.drafter",
            "email.propose_response",
            "propose",
            f"{workflow_id}:email.propose_response",
            {
                "to": lead.sender.email,
                "subject": f"Re: {lead.subject}",
                "body_text": draft.structured_data.get("draft_response", draft.summary),
            },
        )
        sequence = await self._step(
            lead,
            workflow_id,
            sequence,
            path,
            STEP_PROPOSE_SEND,
            {
                "lead_summary": lead.subject,
                "gateway_verdict": gateway_result.verdict,
                "enforced_mode": gateway_result.enforced_mode,
            },
        )
        if gateway_result.verdict in {"block", "approval_required"}:
            return await self._escalate(
                lead,
                workflow_id,
                sequence,
                path,
                f"tool gateway returned {gateway_result.verdict}",
            )

        sequence = await self._step(
            lead,
            workflow_id,
            sequence,
            path,
            STEP_COMPLETE,
            {"lead_summary": lead.subject, "final_summary": gateway_result.reason},
        )
        await self._emit(
            lead,
            workflow_id,
            sequence,
            EVENT_WORKFLOW_COMPLETED,
            STEP_COMPLETE,
            {"lead_summary": lead.subject, "outcome": "completed"},
        )
        return LighthouseWorkflowResult(
            workflow_id=workflow_id,
            tenant_id=lead.tenant_id,
            correlation_id=lead.correlation_id,
            lead_id=lead.lead_id,
            outcome="completed",
            path=path,
            final_summary=gateway_result.reason,
        )

    async def _step(
        self,
        lead: LighthouseWorkflowInput,
        workflow_id: str,
        sequence: int,
        path: list[str],
        step: str,
        payload: dict[str, Any],
    ) -> int:
        sequence = await self._emit(
            lead,
            workflow_id,
            sequence,
            EVENT_STEP_STARTED,
            step,
            {"lead_summary": lead.subject},
        )
        path.append(step)
        return await self._emit(lead, workflow_id, sequence, EVENT_STEP_COMPLETED, step, payload)

    async def _emit(
        self,
        lead: LighthouseWorkflowInput,
        workflow_id: str,
        sequence: int,
        event_type: str,
        step: str | None,
        payload: dict[str, Any],
    ) -> int:
        await workflow.execute_activity(
            ACTIVITY_RECORD_WORKFLOW_EVENT,
            WorkflowEventCommand(
                tenant_id=lead.tenant_id,
                correlation_id=lead.correlation_id,
                workflow_id=workflow_id,
                lead_id=lead.lead_id,
                sequence=sequence,
                event_type=event_type,
                step=step,
                payload=payload,
            ),
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            retry_policy=_ACTIVITY_RETRY,
        )
        return sequence + 1

    async def _agent(
        self,
        lead: LighthouseWorkflowInput,
        workflow_id: str,
        agent_role: str,
        task_kind: str,
        input_payload: dict[str, Any],
    ) -> AgentInvocationResponse:
        return await workflow.execute_activity(
            ACTIVITY_INVOKE_AGENT_RUNTIME,
            AgentInvocationRequest(
                tenant_id=lead.tenant_id,
                correlation_id=lead.correlation_id,
                workflow_id=workflow_id,
                lead_id=lead.lead_id,
                agent_role=agent_role,
                task_kind=task_kind,
                input=input_payload,
                expected_output_contract="contracts/agents/lighthouse_agent_io.schema.json",
            ),
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            retry_policy=_ACTIVITY_RETRY,
            result_type=AgentInvocationResponse,
        )

    async def _gateway(
        self,
        lead: LighthouseWorkflowInput,
        workflow_id: str,
        invocation_id: str,
        agent_id: str,
        tool_name: str,
        mode: str,
        idempotency_key: str,
        arguments: dict[str, Any],
    ) -> ToolGatewayResponse:
        return await workflow.execute_activity(
            ACTIVITY_INVOKE_TOOL_GATEWAY,
            ToolGatewayRequest(
                tenant_id=lead.tenant_id,
                correlation_id=lead.correlation_id,
                workflow_id=workflow_id,
                invocation_id=invocation_id,
                agent_id=agent_id,
                tool_name=tool_name,
                mode=mode,
                idempotency_key=idempotency_key,
                arguments=arguments,
            ),
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            retry_policy=_ACTIVITY_RETRY,
            result_type=ToolGatewayResponse,
        )

    async def _escalate(
        self,
        lead: LighthouseWorkflowInput,
        workflow_id: str,
        sequence: int,
        path: list[str],
        reason: str,
    ) -> LighthouseWorkflowResult:
        sequence = await self._step(
            lead,
            workflow_id,
            sequence,
            path,
            STEP_ESCALATE,
            {"lead_summary": lead.subject, "reason": reason},
        )
        await self._emit(
            lead,
            workflow_id,
            sequence,
            EVENT_WORKFLOW_ESCALATED,
            STEP_ESCALATE,
            {"lead_summary": lead.subject, "reason": reason, "outcome": "escalated"},
        )
        return LighthouseWorkflowResult(
            workflow_id=workflow_id,
            tenant_id=lead.tenant_id,
            correlation_id=lead.correlation_id,
            lead_id=lead.lead_id,
            outcome="escalated",
            path=path,
            final_summary=reason,
            escalation_reason=reason,
        )


def _should_escalate(response: AgentInvocationResponse) -> bool:
    return (
        response.recommended_next_step == "escalate" or response.confidence < _CONFIDENCE_THRESHOLD
    )


def _needs_deeper_research(response: AgentInvocationResponse) -> bool:
    return (
        response.recommended_next_step == "deeper_research"
        or response.confidence < _CONFIDENCE_THRESHOLD
    )


def _research_input(
    *,
    lead: LighthouseWorkflowInput,
    attempt: int,
    previous_research: AgentInvocationResponse | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "lead_subject": lead.subject,
        "lead_body": lead.body_text,
        "sender": lead.sender.email,
        "research_attempt": attempt,
    }
    if previous_research is not None:
        payload.update(
            {
                "deeper_research": True,
                "previous_research_summary": previous_research.summary,
                "previous_research_confidence": previous_research.confidence,
                "previous_recommended_next_step": previous_research.recommended_next_step,
            }
        )
    return payload


def _draft_input(
    *,
    lead: LighthouseWorkflowInput,
    research_summary: str,
    qualification_summary: str,
    redraft_attempt: int,
    validator_reason: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "lead_subject": lead.subject,
        "lead_body": lead.body_text,
        "research_summary": research_summary,
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

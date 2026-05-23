"""Deterministic Temporal workflow for the local Support Desk Triage proof."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

from temporalio import workflow
from temporalio.common import RetryPolicy

from chorus.workflows.lighthouse import (
    ACTIVITY_INVOKE_AGENT_RUNTIME,
    ACTIVITY_INVOKE_TOOL_GATEWAY,
    EVENT_STEP_COMPLETED,
    EVENT_STEP_STARTED,
    EVENT_WORKFLOW_COMPLETED,
    EVENT_WORKFLOW_ESCALATED,
    EVENT_WORKFLOW_STARTED,
)
from chorus.workflows.types import (
    AgentInvocationRequest,
    AgentInvocationResponse,
    SupportWorkflowEventCommand,
    SupportWorkflowInput,
    SupportWorkflowResult,
    ToolGatewayRequest,
    ToolGatewayResponse,
)

ACTIVITY_RECORD_SUPPORT_WORKFLOW_EVENT = "support.record_workflow_event"

SUPPORT_WORKFLOW_TYPE = "support_triage"

STEP_SUPPORT_INTAKE = "support_intake"
STEP_SUPPORT_CLASSIFICATION = "support_classification"
STEP_SUPPORT_CONTEXT_LOOKUP = "support_context_lookup"
STEP_SUPPORT_RESOLUTION_PLAN = "support_resolution_plan"
STEP_SUPPORT_VALIDATION = "support_validation"
STEP_SUPPORT_PROPOSE = "support_propose"
STEP_SUPPORT_COMPLETE = "support_complete"
STEP_SUPPORT_ESCALATE = "support_escalate"

SUPPORT_AGENT_CONTRACT = "contracts/llm_provider/support_agent_io.schema.json"

_ACTIVITY_TIMEOUT = timedelta(seconds=30)
_ACTIVITY_RETRY = RetryPolicy(maximum_attempts=3)


@workflow.defn
class SupportTriageWorkflow:
    """Phase 2D support workflow proof.

    The workflow keeps only deterministic branching and safe-ref assembly in
    workflow code. Agent execution, ticket lookup/proposal, event IDs,
    timestamps, persistence, and connector dispatch remain activity-owned.
    """

    @workflow.run
    async def run(self, request: SupportWorkflowInput) -> SupportWorkflowResult:
        workflow_id = workflow.info().workflow_id
        subject_id = _support_subject_id(request.request_ref)
        sequence = 1
        path: list[str] = []

        sequence = await self._emit(
            request,
            workflow_id,
            subject_id,
            sequence,
            EVENT_WORKFLOW_STARTED,
            STEP_SUPPORT_INTAKE,
            {
                "workflow_type": SUPPORT_WORKFLOW_TYPE,
                "request_ref": request.request_ref,
                "account_ref": request.account_ref,
                "product_ref": request.product_ref,
                "case_ref": request.case_ref,
                "severity_category": _normalised_severity(request.severity_hint_category),
                "case_status_category": request.request_status_category,
                "redacted_summary_ref": request.redacted_summary_ref,
                "source_ref": request.source_ref,
            },
        )

        sequence = await self._step(
            request,
            workflow_id,
            subject_id,
            sequence,
            path,
            STEP_SUPPORT_INTAKE,
            {
                "workflow_type": SUPPORT_WORKFLOW_TYPE,
                "request_ref": request.request_ref,
                "account_ref": request.account_ref,
                "product_ref": request.product_ref,
                "case_ref": request.case_ref,
                "intake_channel_category": request.intake_channel_category,
            },
        )

        if request.case_ref is None:
            return await self._escalate(
                request,
                workflow_id,
                subject_id,
                sequence,
                path,
                "missing_case_ref",
            )

        classification = await self._agent(
            request,
            workflow_id,
            "support_classifier",
            "support_classification",
            _support_agent_input(request),
        )
        sequence = await self._step(
            request,
            workflow_id,
            subject_id,
            sequence,
            path,
            STEP_SUPPORT_CLASSIFICATION,
            {
                "workflow_type": SUPPORT_WORKFLOW_TYPE,
                "request_ref": request.request_ref,
                "case_ref": request.case_ref,
                "severity_category": _severity_from(classification, request),
                "case_status_category": _case_status_from(classification, request),
                "verdict_category": classification.structured_data.get("verdict_category"),
            },
        )
        if _should_escalate(classification):
            return await self._escalate(
                request,
                workflow_id,
                subject_id,
                sequence,
                path,
                "classifier_escalation",
            )

        context = await self._agent(
            request,
            workflow_id,
            "support_context_researcher",
            "support_context_lookup",
            _support_agent_input(
                request,
                prior_invocation_refs=[_invocation_ref(classification.invocation_id)],
            ),
        )
        lookup = await self._gateway(
            request,
            workflow_id,
            context.invocation_id,
            "support.context_researcher",
            "ticket.lookup_case",
            "read",
            f"{workflow_id}:ticket.lookup_case:{request.case_ref}",
            {
                "case_ref": request.case_ref,
                "request_ref": request.request_ref,
                "account_ref": request.account_ref,
                "product_ref": request.product_ref,
                "lookup_policy_ref": _policy_ref(request),
                "include_history_category": "bounded_recent_status_refs",
            },
        )
        duplicates = await self._gateway(
            request,
            workflow_id,
            context.invocation_id,
            "support.context_researcher",
            "ticket.lookup_duplicates",
            "read",
            f"{workflow_id}:ticket.lookup_duplicates:{request.request_ref}",
            {
                "request_ref": request.request_ref,
                "case_ref": request.case_ref,
                "account_ref": request.account_ref,
                "product_ref": request.product_ref,
                "severity_category": _severity_from(classification, request),
                "status_categories": ["new", "open", "pending_customer", "pending_internal"],
                "duplicate_scope_category": "same_account_product_open",
                "lookup_policy_ref": _policy_ref(request),
            },
        )
        sequence = await self._step(
            request,
            workflow_id,
            subject_id,
            sequence,
            path,
            STEP_SUPPORT_CONTEXT_LOOKUP,
            {
                "workflow_type": SUPPORT_WORKFLOW_TYPE,
                "request_ref": request.request_ref,
                "case_ref": request.case_ref,
                "lookup_verdict": lookup.verdict,
                "duplicate_lookup_verdict": duplicates.verdict,
                "duplicate_status": duplicates.output.get("duplicate_status"),
            },
        )
        if lookup.verdict == "block" or duplicates.verdict == "block":
            return await self._escalate(
                request,
                workflow_id,
                subject_id,
                sequence,
                path,
                "context_lookup_blocked",
            )

        plan = await self._agent(
            request,
            workflow_id,
            "support_resolution_planner",
            "support_resolution_plan",
            _support_agent_input(
                request,
                prior_invocation_refs=[_invocation_ref(context.invocation_id)],
                extra={
                    "context_lookup_status": lookup.output.get("lookup_status"),
                    "duplicate_status": duplicates.output.get("duplicate_status"),
                },
            ),
        )
        plan_refs = _output_refs(plan)
        sequence = await self._step(
            request,
            workflow_id,
            subject_id,
            sequence,
            path,
            STEP_SUPPORT_RESOLUTION_PLAN,
            {
                "workflow_type": SUPPORT_WORKFLOW_TYPE,
                "request_ref": request.request_ref,
                "case_ref": request.case_ref,
                "resolution_plan_ref": plan_refs.get("resolution_plan_ref"),
                "response_draft_ref": plan_refs.get("response_draft_ref"),
                "case_update_ref": plan_refs.get("case_update_ref"),
                "verdict_category": plan.structured_data.get("verdict_category"),
            },
        )
        if _should_escalate(plan):
            return await self._escalate(
                request,
                workflow_id,
                subject_id,
                sequence,
                path,
                "resolution_plan_escalation",
            )

        validation = await self._agent(
            request,
            workflow_id,
            "support_validator",
            "support_validation",
            _support_agent_input(
                request,
                prior_invocation_refs=[_invocation_ref(plan.invocation_id)],
                extra={"resolution_plan_ref": plan_refs.get("resolution_plan_ref")},
            ),
        )
        sequence = await self._step(
            request,
            workflow_id,
            subject_id,
            sequence,
            path,
            STEP_SUPPORT_VALIDATION,
            {
                "workflow_type": SUPPORT_WORKFLOW_TYPE,
                "request_ref": request.request_ref,
                "case_ref": request.case_ref,
                "validation_ref": _output_refs(validation).get("validation_ref"),
                "recommended_next_step": validation.recommended_next_step,
                "verdict_category": validation.structured_data.get("verdict_category"),
            },
        )
        if _should_escalate(validation) or validation.recommended_next_step == "redraft":
            return await self._escalate(
                request,
                workflow_id,
                subject_id,
                sequence,
                path,
                "validation_escalation",
            )

        proposal = await self._gateway(
            request,
            workflow_id,
            plan.invocation_id,
            "support.resolution_planner",
            "ticket.propose_case_update",
            "propose",
            f"{workflow_id}:ticket.propose_case_update:{request.request_ref}",
            {
                "request_ref": request.request_ref,
                "case_ref": request.case_ref,
                "account_ref": request.account_ref,
                "product_ref": request.product_ref,
                "severity_category": _severity_from(classification, request),
                "target_status_category": _target_status_from(plan),
                "resolution_plan_ref": _ref_or_default(
                    plan_refs.get("resolution_plan_ref"),
                    "plan",
                    request.request_ref,
                ),
                "response_draft_ref": _ref_or_default(
                    plan_refs.get("response_draft_ref"),
                    "response",
                    request.request_ref,
                ),
                "case_update_ref": _ref_or_default(
                    plan_refs.get("case_update_ref"),
                    "caseupd",
                    request.request_ref,
                ),
                "update_reason_category": "resolution_plan_ready",
                "policy_ref": _policy_ref(request),
            },
        )
        sequence = await self._step(
            request,
            workflow_id,
            subject_id,
            sequence,
            path,
            STEP_SUPPORT_PROPOSE,
            {
                "workflow_type": SUPPORT_WORKFLOW_TYPE,
                "request_ref": request.request_ref,
                "case_ref": request.case_ref,
                "gateway_verdict": proposal.verdict,
                "enforced_mode": proposal.enforced_mode,
                "case_update_ref": proposal.output.get("case_update_ref"),
                "case_status_mutated": proposal.output.get("case_status_mutated"),
            },
        )
        if proposal.verdict in {"block", "approval_required"}:
            return await self._escalate(
                request,
                workflow_id,
                subject_id,
                sequence,
                path,
                f"proposal_{proposal.verdict}",
            )

        sequence = await self._step(
            request,
            workflow_id,
            subject_id,
            sequence,
            path,
            STEP_SUPPORT_COMPLETE,
            {
                "workflow_type": SUPPORT_WORKFLOW_TYPE,
                "request_ref": request.request_ref,
                "case_ref": request.case_ref,
                "proposal_status": proposal.output.get("proposal_status"),
            },
        )
        await self._emit(
            request,
            workflow_id,
            subject_id,
            sequence,
            EVENT_WORKFLOW_COMPLETED,
            STEP_SUPPORT_COMPLETE,
            {
                "workflow_type": SUPPORT_WORKFLOW_TYPE,
                "request_ref": request.request_ref,
                "case_ref": request.case_ref,
                "outcome": "completed",
            },
        )
        return SupportWorkflowResult(
            workflow_id=workflow_id,
            tenant_id=request.tenant_id,
            correlation_id=request.correlation_id,
            request_ref=request.request_ref,
            outcome="completed",
            path=path,
            final_summary="support case update proposed through local ticket desk",
        )

    async def _step(
        self,
        request: SupportWorkflowInput,
        workflow_id: str,
        subject_id: str,
        sequence: int,
        path: list[str],
        step: str,
        payload: dict[str, Any],
    ) -> int:
        sequence = await self._emit(
            request,
            workflow_id,
            subject_id,
            sequence,
            EVENT_STEP_STARTED,
            step,
            {
                "workflow_type": SUPPORT_WORKFLOW_TYPE,
                "request_ref": request.request_ref,
                "case_ref": request.case_ref,
            },
        )
        path.append(step)
        return await self._emit(
            request,
            workflow_id,
            subject_id,
            sequence,
            EVENT_STEP_COMPLETED,
            step,
            payload,
        )

    async def _emit(
        self,
        request: SupportWorkflowInput,
        workflow_id: str,
        subject_id: str,
        sequence: int,
        event_type: str,
        step: str | None,
        payload: dict[str, Any],
    ) -> int:
        await workflow.execute_activity(
            ACTIVITY_RECORD_SUPPORT_WORKFLOW_EVENT,
            SupportWorkflowEventCommand(
                tenant_id=request.tenant_id,
                correlation_id=request.correlation_id,
                workflow_id=workflow_id,
                workflow_type=SUPPORT_WORKFLOW_TYPE,
                request_ref=request.request_ref,
                subject_ref=request.request_ref,
                subject_id=subject_id,
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
        request: SupportWorkflowInput,
        workflow_id: str,
        agent_role: str,
        task_kind: str,
        input_payload: dict[str, Any],
    ) -> AgentInvocationResponse:
        return await workflow.execute_activity(
            ACTIVITY_INVOKE_AGENT_RUNTIME,
            AgentInvocationRequest(
                tenant_id=request.tenant_id,
                correlation_id=request.correlation_id,
                workflow_id=workflow_id,
                lead_id=request.request_ref,
                agent_role=agent_role,
                task_kind=task_kind,
                input=input_payload,
                expected_output_contract=SUPPORT_AGENT_CONTRACT,
            ),
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            retry_policy=_ACTIVITY_RETRY,
            result_type=AgentInvocationResponse,
        )

    async def _gateway(
        self,
        request: SupportWorkflowInput,
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
                tenant_id=request.tenant_id,
                correlation_id=request.correlation_id,
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
        request: SupportWorkflowInput,
        workflow_id: str,
        subject_id: str,
        sequence: int,
        path: list[str],
        reason_category: str,
    ) -> SupportWorkflowResult:
        sequence = await self._step(
            request,
            workflow_id,
            subject_id,
            sequence,
            path,
            STEP_SUPPORT_ESCALATE,
            {
                "workflow_type": SUPPORT_WORKFLOW_TYPE,
                "request_ref": request.request_ref,
                "case_ref": request.case_ref,
                "escalation_category": reason_category,
            },
        )
        await self._emit(
            request,
            workflow_id,
            subject_id,
            sequence,
            EVENT_WORKFLOW_ESCALATED,
            STEP_SUPPORT_ESCALATE,
            {
                "workflow_type": SUPPORT_WORKFLOW_TYPE,
                "request_ref": request.request_ref,
                "case_ref": request.case_ref,
                "outcome": "escalated",
                "escalation_category": reason_category,
            },
        )
        return SupportWorkflowResult(
            workflow_id=workflow_id,
            tenant_id=request.tenant_id,
            correlation_id=request.correlation_id,
            request_ref=request.request_ref,
            outcome="escalated",
            path=path,
            final_summary="support triage escalated",
            escalation_reason=reason_category,
        )


def _support_subject_id(request_ref: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"chorus:support_triage:{request_ref}"))


def _support_agent_input(
    request: SupportWorkflowInput,
    *,
    prior_invocation_refs: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    input_refs: dict[str, Any] = {
        "request_ref": request.request_ref,
        "account_ref": request.account_ref,
        "product_ref": request.product_ref,
        "redacted_summary_ref": request.redacted_summary_ref,
    }
    if request.case_ref is not None:
        input_refs["case_ref"] = request.case_ref
    if prior_invocation_refs:
        input_refs["prior_invocation_refs"] = prior_invocation_refs

    payload: dict[str, Any] = {
        "workflow_type": SUPPORT_WORKFLOW_TYPE,
        "input_refs": input_refs,
        "severity_hint_category": request.severity_hint_category,
        "request_status_category": request.request_status_category,
        "routing_policy_ref": _policy_ref(request),
    }
    if extra:
        payload.update(extra)
    return payload


def _policy_ref(request: SupportWorkflowInput) -> str:
    return request.routing_policy_ref or "policy_support_triage_local_v1"


def _invocation_ref(invocation_id: str) -> str:
    return f"inv_{invocation_id.replace('-', '_')}"


def _output_refs(response: AgentInvocationResponse) -> dict[str, str]:
    raw_output_refs = response.structured_data.get("output_refs")
    if not isinstance(raw_output_refs, dict):
        return {}
    output_refs = cast(dict[object, object], raw_output_refs)
    refs: dict[str, str] = {}
    for key, value in output_refs.items():
        if isinstance(key, str) and isinstance(value, str):
            refs[key] = value
    return refs


def _should_escalate(response: AgentInvocationResponse) -> bool:
    return response.recommended_next_step in {"escalate", "reject"} or (
        response.structured_data.get("verdict_category") == "escalate_to_human"
    )


def _severity_from(response: AgentInvocationResponse, request: SupportWorkflowInput) -> str:
    value = response.structured_data.get("severity_category")
    if isinstance(value, str):
        return value
    return _normalised_severity(request.severity_hint_category)


def _case_status_from(response: AgentInvocationResponse, request: SupportWorkflowInput) -> str:
    value = response.structured_data.get("case_status_category")
    if isinstance(value, str):
        return value
    return request.request_status_category


def _target_status_from(response: AgentInvocationResponse) -> str:
    value = response.structured_data.get("case_status_category")
    if isinstance(value, str) and value in {
        "open",
        "pending_customer",
        "pending_internal",
        "resolved",
        "escalated",
    }:
        return value
    return "pending_customer"


def _normalised_severity(severity_hint_category: str) -> str:
    if severity_hint_category == "unknown":
        return "sev_medium"
    return severity_hint_category


def _ref_or_default(value: str | None, prefix: str, request_ref: str) -> str:
    if value:
        return value
    suffix = request_ref.removeprefix("req_")
    return f"{prefix}_{suffix}"

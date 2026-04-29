"""Temporal activities for Lighthouse Workstream B.

The Agent Runtime and Tool Gateway functions are deliberately contract-shaped
placeholders. Workstreams C and D should replace their internals behind these
activity names without changing the Lighthouse workflow.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

import psycopg
from temporalio import activity

from chorus.contracts.generated.agents.lighthouse_agent_io import LighthouseAgentIO
from chorus.contracts.generated.events.workflow_event import WorkflowEvent
from chorus.contracts.generated.tools.gateway_verdict import GatewayVerdict
from chorus.contracts.generated.tools.tool_call import ToolCall
from chorus.persistence import ProjectionStore
from chorus.persistence.migrate import database_url_from_env
from chorus.workflows.lighthouse import (
    ACTIVITY_INVOKE_AGENT_RUNTIME,
    ACTIVITY_INVOKE_TOOL_GATEWAY,
    ACTIVITY_RECORD_WORKFLOW_EVENT,
)
from chorus.workflows.mailpit import MailpitPoller, TemporalWorkflowStarter
from chorus.workflows.types import (
    AgentCitation,
    AgentInvocationRequest,
    AgentInvocationResponse,
    MailpitPollConfig,
    MailpitPollResult,
    ToolGatewayRequest,
    ToolGatewayResponse,
    WorkflowEventCommand,
    WorkflowEventResult,
)


class WorkflowEventSink(Protocol):
    def record_workflow_event(self, event: WorkflowEvent) -> None: ...


def _now() -> datetime:
    return datetime.now(UTC)


class WorkflowEventRecorder:
    def __init__(self, sink_factory: Callable[[], WorkflowEventSink]) -> None:
        self._sink_factory = sink_factory

    def record(self, command: WorkflowEventCommand) -> WorkflowEventResult:
        event = WorkflowEvent.model_validate(
            {
                "schema_version": "1.0.0",
                "event_id": str(uuid4()),
                "event_type": command.event_type,
                "occurred_at": _now().isoformat(),
                "tenant_id": command.tenant_id,
                "correlation_id": command.correlation_id,
                "workflow_id": command.workflow_id,
                "lead_id": command.lead_id,
                "sequence": command.sequence,
                "step": command.step,
                "payload": command.payload,
            }
        )
        self._sink_factory().record_workflow_event(event)
        return WorkflowEventResult(
            event_id=str(event.event_id),
            sequence=event.sequence,
            event_type=event.event_type.value,
            step=event.step.value if event.step is not None else None,
        )


def _postgres_sink_factory() -> WorkflowEventSink:
    database_url = os.environ.get("CHORUS_DATABASE_URL", database_url_from_env())
    conn = psycopg.connect(database_url)

    class _ProjectionSink:
        def record_workflow_event(self, event: WorkflowEvent) -> None:
            try:
                ProjectionStore(conn).record_workflow_event(event)
            finally:
                conn.close()

    return _ProjectionSink()


@activity.defn(name=ACTIVITY_RECORD_WORKFLOW_EVENT)
def record_workflow_event_activity(command: WorkflowEventCommand) -> WorkflowEventResult:
    return WorkflowEventRecorder(_postgres_sink_factory).record(command)


@activity.defn(name=ACTIVITY_INVOKE_AGENT_RUNTIME)
def invoke_agent_runtime_activity(request: AgentInvocationRequest) -> AgentInvocationResponse:
    """Stable Agent Runtime activity boundary for Workstream C.

    The placeholder validates a generated Lighthouse agent contract and returns
    deterministic-looking demo output. It does not call a model provider or
    write decision-trail rows; Workstream C owns that implementation behind
    this activity name.
    """

    invocation_id = uuid4()
    summary, next_step, structured_data = _placeholder_agent_output(request)
    contract = LighthouseAgentIO.model_validate(
        {
            "schema_version": "1.0.0",
            "task_id": str(uuid4()),
            "tenant_id": request.tenant_id,
            "correlation_id": request.correlation_id,
            "workflow_id": request.workflow_id,
            "agent_role": request.agent_role,
            "task_kind": request.task_kind,
            "input": request.input,
            "expected_output_contract": request.expected_output_contract,
            "result": {
                "summary": summary,
                "confidence": 0.88,
                "structured_data": structured_data,
                "recommended_next_step": next_step,
                "rationale": "Phase 1A placeholder for the Agent Runtime boundary.",
                "citations": [],
            },
        }
    )
    return AgentInvocationResponse(
        invocation_id=str(invocation_id),
        summary=contract.result.summary,
        confidence=contract.result.confidence,
        structured_data=contract.result.structured_data,
        recommended_next_step=contract.result.recommended_next_step.value,
        rationale=contract.result.rationale,
        citations=[
            AgentCitation(source=citation.source, reference=citation.reference)
            for citation in contract.result.citations
        ],
    )


def _placeholder_agent_output(
    request: AgentInvocationRequest,
) -> tuple[str, str, dict[str, object]]:
    match request.task_kind:
        case "company_research":
            return (
                "Identified a small operations-led services business from the lead email.",
                "continue",
                {"company_name": "Acme Field Services", "fit": "operations automation"},
            )
        case "lead_qualification":
            return (
                "Lead qualifies for a lightweight Lighthouse pilot conversation.",
                "continue",
                {"qualification": "qualified", "priority": "normal"},
            )
        case "response_draft":
            return (
                "Drafted a concise response proposing a discovery call and pilot outline.",
                "continue",
                {
                    "draft_response": (
                        "Thanks for getting in touch. A lightweight pilot could qualify "
                        "new enquiries, research company context, and prepare response "
                        "drafts for your account team to review."
                    )
                },
            )
        case "response_validation":
            return (
                "Draft is suitable for proposal mode in the local sandbox.",
                "send",
                {"validation": "approved"},
            )
        case _:
            return (
                "Input accepted for Lighthouse processing.",
                "continue",
                {"classification": "lead"},
            )


@activity.defn(name=ACTIVITY_INVOKE_TOOL_GATEWAY)
def invoke_tool_gateway_activity(request: ToolGatewayRequest) -> ToolGatewayResponse:
    """Stable Tool Gateway activity boundary for Workstream D.

    The placeholder validates generated ToolCall and GatewayVerdict contracts.
    It does not perform connector IO or persist tool audit; Workstream D owns
    grants, idempotency, audit, and real connector calls behind this activity.
    """

    now = _now().isoformat()
    tool_call = ToolCall.model_validate(
        {
            "schema_version": "1.0.0",
            "tool_call_id": str(uuid4()),
            "invocation_id": request.invocation_id,
            "tenant_id": request.tenant_id,
            "correlation_id": request.correlation_id,
            "agent_id": request.agent_id,
            "tool_name": request.tool_name,
            "mode": request.mode,
            "idempotency_key": request.idempotency_key,
            "arguments": request.arguments,
            "requested_at": now,
        }
    )
    verdict = GatewayVerdict.model_validate(
        {
            "schema_version": "1.0.0",
            "verdict_id": str(uuid4()),
            "tool_call_id": str(tool_call.tool_call_id),
            "tenant_id": request.tenant_id,
            "correlation_id": request.correlation_id,
            "verdict": "allow",
            "enforced_mode": request.mode,
            "reason": "Phase 1A placeholder accepted contract-shaped gateway request.",
            "rewritten_arguments": None,
            "approval_required": False,
            "audit_event_id": str(uuid4()),
            "connector_invocation_id": str(uuid4()),
            "decided_at": now,
        }
    )
    return ToolGatewayResponse(
        verdict_id=str(verdict.verdict_id),
        tool_call_id=str(tool_call.tool_call_id),
        audit_event_id=str(verdict.audit_event_id),
        verdict=verdict.verdict.value,
        enforced_mode=verdict.enforced_mode.value,
        reason=verdict.reason,
        connector_invocation_id=(
            str(verdict.connector_invocation_id)
            if verdict.connector_invocation_id is not None
            else None
        ),
        output={"accepted_arguments": request.arguments},
    )


@activity.defn(name="lighthouse.poll_mailpit")
async def poll_mailpit_activity(config: MailpitPollConfig) -> MailpitPollResult:
    starter = await TemporalWorkflowStarter.connect(
        target_host=config.temporal_target_host,
        namespace=config.temporal_namespace,
        task_queue=config.task_queue,
    )
    poller = MailpitPoller(config, starter)
    return await poller.poll_once()


async def poll_mailpit_once(config: MailpitPollConfig) -> MailpitPollResult:
    """Run the intake poller directly for CLI/demo use."""

    return await poll_mailpit_activity(config)


def run_poll_mailpit_once(config: MailpitPollConfig) -> MailpitPollResult:
    return asyncio.run(poll_mailpit_once(config))

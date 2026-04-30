# ruff: noqa: E402
"""One-shot generator for the connector-failure replay history fixture.

Run with `uv run python scripts/generate_connector_failure_history.py`.
The script starts a time-skipping Temporal environment, runs the workflow
with deterministic fixture activities, and writes the captured history JSON
to `tests/workflows/fixtures/lighthouse_connector_failure_history.json`.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from chorus.workflows.lighthouse import (
    ACTIVITY_INVOKE_AGENT_RUNTIME,
    ACTIVITY_INVOKE_TOOL_GATEWAY,
    ACTIVITY_RECORD_TOOL_FAILURE_COMPENSATION,
    ACTIVITY_RECORD_WORKFLOW_EVENT,
    LighthouseWorkflow,
)
from chorus.workflows.types import (
    AgentInvocationRequest,
    AgentInvocationResponse,
    LeadSender,
    LighthouseWorkflowInput,
    ToolFailureCompensationCommand,
    ToolFailureCompensationResult,
    ToolGatewayRequest,
    ToolGatewayResponse,
    WorkflowEventCommand,
    WorkflowEventResult,
)

OUTPUT = ROOT / "tests" / "workflows" / "fixtures" / "lighthouse_connector_failure_history.json"


def fixture_lead() -> LighthouseWorkflowInput:
    return LighthouseWorkflowInput(
        schema_version="1.0.0",
        lead_id="9b6c2f2a-4a3f-4c1e-9a87-0d11d0a4f004",
        tenant_id="tenant_demo",
        correlation_id="cor_workflow_connector_failure_fixture",
        source="mailpit_smtp",
        message_id="<lead-connector-failure-001@example.test>",
        received_at="2026-04-29T10:00:00+00:00",
        sender=LeadSender(display_name="Alex Morgan", email="alex.morgan@example.test"),
        recipients=["leads@chorus.local"],
        subject="connector-failure fixture: Mailpit outage during proposal",
        body_text=(
            "This connector-failure fixture keeps the agent path ordinary but "
            "forces the local Mailpit connector to fail during proposal capture."
        ),
        message_headers={"Message-ID": ["<lead-connector-failure-001@example.test>"]},
        attachments_summary=[],
    )


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
    structured_data: dict[str, object] = {}
    next_step = "continue"
    if request.task_kind == "response_draft":
        structured_data = {"draft_response": "Draft response"}
    if request.task_kind == "response_validation":
        structured_data = {"validation": "approved"}
        next_step = "send"
    return AgentInvocationResponse(
        invocation_id=str(uuid4()),
        summary=f"{request.task_kind} fixture invocation",
        confidence=0.9,
        structured_data=structured_data,
        recommended_next_step=next_step,
        rationale="fixture boundary",
    )


@activity.defn(name=ACTIVITY_INVOKE_TOOL_GATEWAY)
async def fake_gateway(request: ToolGatewayRequest) -> ToolGatewayResponse:
    raise ApplicationError("fixture transient connector failure")


@activity.defn(name=ACTIVITY_RECORD_TOOL_FAILURE_COMPENSATION)
async def fake_compensation(
    command: ToolFailureCompensationCommand,
) -> ToolFailureCompensationResult:
    return ToolFailureCompensationResult(
        audit_event_id=str(uuid4()),
        action="connector.failure.compensated",
        verdict="recorded",
        reason=command.failure_reason,
    )


async def _generate() -> None:
    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="fixture-lighthouse-connector-failure",
            workflows=[LighthouseWorkflow],
            activities=[fake_record, fake_agent, fake_gateway, fake_compensation],
        ),
    ):
        handle = await env.client.start_workflow(
            "LighthouseWorkflow",
            fixture_lead(),
            id="lighthouse-workflow-connector-failure-fixture",
            task_queue="fixture-lighthouse-connector-failure",
        )
        await handle.result()
        history = await handle.fetch_history()

    OUTPUT.write_text(history.to_json(), encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(_generate())

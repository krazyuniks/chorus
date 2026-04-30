"""One-shot generator for the validator-redraft replay history fixture.

Run with `uv run python scripts/generate_validator_redraft_history.py`.
The script starts a time-skipping Temporal environment, runs the workflow
with deterministic fixture activities, and writes the captured history JSON
to `tests/workflows/fixtures/lighthouse_validator_redraft_history.json`.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from chorus.workflows.lighthouse import (
    ACTIVITY_INVOKE_AGENT_RUNTIME,
    ACTIVITY_INVOKE_TOOL_GATEWAY,
    ACTIVITY_RECORD_WORKFLOW_EVENT,
    LighthouseWorkflow,
)
from chorus.workflows.types import (
    AgentInvocationRequest,
    AgentInvocationResponse,
    LeadSender,
    LighthouseWorkflowInput,
    ToolGatewayRequest,
    ToolGatewayResponse,
    WorkflowEventCommand,
    WorkflowEventResult,
)

OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "workflows"
    / "fixtures"
    / "lighthouse_validator_redraft_history.json"
)


def fixture_lead() -> LighthouseWorkflowInput:
    return LighthouseWorkflowInput(
        schema_version="1.0.0",
        lead_id="9b6c2f2a-4a3f-4c1e-9a87-0d11d0a4f001",
        tenant_id="tenant_demo",
        correlation_id="cor_workflow_validator_redraft_fixture",
        source="mailpit_smtp",
        message_id="<lead-validator-redraft-001@example.test>",
        received_at="2026-04-29T10:00:00+00:00",
        sender=LeadSender(display_name="Alex Morgan", email="alex.morgan@example.test"),
        recipients=["leads@chorus.local"],
        subject="validator-redraft fixture: pilot enquiry for inbound triage",
        body_text=(
            "This validator-redraft fixture intentionally seeds a thin first draft "
            "so the validator can request an operations-led pilot framing on the "
            "second pass."
        ),
        message_headers={"Message-ID": ["<lead-validator-redraft-001@example.test>"]},
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
    confidence = 0.9
    if request.task_kind == "response_draft":
        attempt = int(request.input.get("redraft_attempt", 1))
        structured_data = {
            "draft_response": f"Draft attempt {attempt}",
            "redraft_attempt": attempt,
        }
    if request.task_kind == "response_validation":
        attempt = int(request.input.get("redraft_attempt", 1))
        if attempt == 1:
            next_step = "redraft"
            structured_data = {
                "validation": "redraft_requested",
                "redraft_attempt": attempt,
                "reason": {
                    "code": "tone_mismatch",
                    "guidance": "Reframe around an operations-led pilot.",
                },
            }
        else:
            next_step = "send"
            structured_data = {"validation": "approved", "redraft_attempt": attempt}
    return AgentInvocationResponse(
        invocation_id=str(uuid4()),
        summary=f"{request.task_kind} fixture invocation",
        confidence=confidence,
        structured_data=structured_data,
        recommended_next_step=next_step,
        rationale="fixture boundary",
    )


@activity.defn(name=ACTIVITY_INVOKE_TOOL_GATEWAY)
async def fake_gateway(request: ToolGatewayRequest) -> ToolGatewayResponse:
    return ToolGatewayResponse(
        verdict_id=str(uuid4()),
        tool_call_id=str(uuid4()),
        audit_event_id=str(uuid4()),
        verdict="allow",
        enforced_mode=request.mode,
        reason="proposal accepted by fixture gateway",
        connector_invocation_id=str(uuid4()),
        output={"accepted_arguments": request.arguments},
    )


async def _generate() -> None:
    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="fixture-lighthouse-validator-redraft",
            workflows=[LighthouseWorkflow],
            activities=[fake_record, fake_agent, fake_gateway],
        ),
    ):
        handle = await env.client.start_workflow(
            "LighthouseWorkflow",
            fixture_lead(),
            id="lighthouse-workflow-validator-redraft-fixture",
            task_queue="fixture-lighthouse-validator-redraft",
        )
        await handle.result()
        history = await handle.fetch_history()

    OUTPUT.write_text(history.to_json(), encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(_generate())

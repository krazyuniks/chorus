# ruff: noqa: E402
"""One-shot generator for the retry-exhaustion replay history fixture.

Run with `uv run python scripts/generate_retry_exhaustion_history.py`.
The script starts a time-skipping Temporal environment, runs the workflow
with deterministic fixture activities, and writes the captured history JSON
to `tests/workflows/fixtures/lighthouse_retry_exhaustion_history.json`.
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
    ACTIVITY_RECORD_RETRY_EXHAUSTION_DLQ,
    ACTIVITY_RECORD_WORKFLOW_EVENT,
    LighthouseWorkflow,
)
from chorus.workflows.types import (
    AgentInvocationRequest,
    AgentInvocationResponse,
    LeadSender,
    LighthouseWorkflowInput,
    RetryExhaustionDlqCommand,
    RetryExhaustionDlqResult,
    ToolGatewayRequest,
    ToolGatewayResponse,
    WorkflowEventCommand,
    WorkflowEventResult,
)

OUTPUT = ROOT / "tests" / "workflows" / "fixtures" / "lighthouse_retry_exhaustion_history.json"


def fixture_lead() -> LighthouseWorkflowInput:
    return LighthouseWorkflowInput(
        schema_version="1.0.0",
        lead_id="9b6c2f2a-4a3f-4c1e-9a87-0d11d0a4f005",
        tenant_id="tenant_demo",
        correlation_id="cor_workflow_retry_exhaustion_fixture",
        source="mailpit_smtp",
        message_id="<lead-retry-exhaustion-001@example.test>",
        received_at="2026-04-29T10:00:00+00:00",
        sender=LeadSender(display_name="Alex Morgan", email="alex.morgan@example.test"),
        recipients=["leads@chorus.local"],
        subject="retry-exhaustion fixture: persistent researcher failure",
        body_text=(
            "This retry-exhaustion fixture forces a persistent agent-runtime "
            "failure so the workflow records DLQ evidence and escalates."
        ),
        message_headers={"Message-ID": ["<lead-retry-exhaustion-001@example.test>"]},
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
    raise ApplicationError("fixture persistent agent runtime failure")


@activity.defn(name=ACTIVITY_INVOKE_TOOL_GATEWAY)
async def fake_gateway(request: ToolGatewayRequest) -> ToolGatewayResponse:
    raise AssertionError(f"gateway should not be invoked after retry exhaustion: {request}")


@activity.defn(name=ACTIVITY_RECORD_RETRY_EXHAUSTION_DLQ)
async def fake_dlq(command: RetryExhaustionDlqCommand) -> RetryExhaustionDlqResult:
    return RetryExhaustionDlqResult(
        outbox_id=str(uuid4()),
        event_id=str(uuid4()),
        audit_event_id=str(uuid4()),
        action="workflow.retry_exhausted.dlq_recorded",
        outbox_status="dlq",
        verdict="recorded",
        reason=command.failure_reason,
        sequence=command.sequence,
    )


async def _generate() -> None:
    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="fixture-lighthouse-retry-exhaustion",
            workflows=[LighthouseWorkflow],
            activities=[fake_record, fake_agent, fake_gateway, fake_dlq],
        ),
    ):
        handle = await env.client.start_workflow(
            "LighthouseWorkflow",
            fixture_lead(),
            id="lighthouse-workflow-retry-exhaustion-fixture",
            task_queue="fixture-lighthouse-retry-exhaustion",
        )
        await handle.result()
        history = await handle.fetch_history()

    OUTPUT.write_text(history.to_json(), encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(_generate())

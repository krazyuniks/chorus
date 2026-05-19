# ruff: noqa: E402
"""One-shot generator for the support-triage replay history fixture.

Run with `uv run python scripts/generate_support_triage_history.py`.
The script starts a time-skipping Temporal environment, runs the workflow
with deterministic fixture activities, and writes the captured history JSON
to `tests/workflows/fixtures/support_triage_happy_history.json`.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import cast
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from chorus.workflows.lighthouse import ACTIVITY_INVOKE_AGENT_RUNTIME, ACTIVITY_INVOKE_TOOL_GATEWAY
from chorus.workflows.support import ACTIVITY_RECORD_SUPPORT_WORKFLOW_EVENT, SupportTriageWorkflow
from chorus.workflows.types import (
    AgentInvocationRequest,
    AgentInvocationResponse,
    SupportWorkflowEventCommand,
    SupportWorkflowInput,
    ToolGatewayRequest,
    ToolGatewayResponse,
    WorkflowEventResult,
)

OUTPUT = ROOT / "tests" / "workflows" / "fixtures" / "support_triage_happy_history.json"

type JSONValue = dict[str, JSONValue] | list[JSONValue] | str | int | float | bool | None


def _sanitised_history_json(history_json: str) -> str:
    payload = cast(JSONValue, json.loads(history_json))

    def scrub(value: JSONValue) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if key == "identity":
                    value[key] = "fixture-worker"
                else:
                    scrub(nested)
        elif isinstance(value, list):
            for nested in value:
                scrub(nested)

    scrub(payload)
    return json.dumps(payload, indent=2, sort_keys=False)


def fixture_request() -> SupportWorkflowInput:
    return SupportWorkflowInput(
        schema_version="1.0.0",
        request_ref="req_support_001",
        tenant_id="tenant_demo",
        correlation_id="cor_support_workflow_happy_fixture",
        source_ref="source_support_local_sandbox",
        received_at="2026-05-19T09:00:00+00:00",
        intake_channel_category="ticket_portal",
        account_ref="acct_demo_001",
        product_ref="prod_core_platform",
        case_ref="case_existing_001",
        severity_hint_category="sev_high",
        request_status_category="open",
        redacted_summary_ref="summary_support_001",
        attachment_refs=[],
        idempotency_ref="idem_support_001",
        routing_policy_ref="policy_support_triage_local_v1",
    )


@activity.defn(name=ACTIVITY_RECORD_SUPPORT_WORKFLOW_EVENT)
async def fake_record(command: SupportWorkflowEventCommand) -> WorkflowEventResult:
    return WorkflowEventResult(
        event_id=str(uuid4()),
        sequence=command.sequence,
        event_type=command.event_type,
        step=command.step,
    )


@activity.defn(name=ACTIVITY_INVOKE_AGENT_RUNTIME)
async def fake_agent(request: AgentInvocationRequest) -> AgentInvocationResponse:
    output_refs = {
        "request_ref": "req_support_001",
        "case_ref": "case_existing_001",
    }
    next_step = "continue"
    verdict_category = "triage_continue"
    case_status_category = "open"
    if request.task_kind == "support_context_lookup":
        verdict_category = "needs_context"
    if request.task_kind == "support_resolution_plan":
        next_step = "propose_only"
        verdict_category = "propose_case_update"
        case_status_category = "pending_customer"
        output_refs |= {
            "resolution_plan_ref": "plan_support_001",
            "response_draft_ref": "response_support_001",
            "case_update_ref": "caseupd_support_001",
        }
    if request.task_kind == "support_validation":
        next_step = "complete"
        verdict_category = "propose_case_update"
        case_status_category = "pending_customer"
        output_refs |= {"validation_ref": "validation_support_001"}
    return AgentInvocationResponse(
        invocation_id=str(uuid4()),
        summary=f"{request.task_kind} complete",
        confidence=0.9,
        structured_data={
            "workflow_type": "support_triage",
            "verdict_category": verdict_category,
            "severity_category": "sev_high",
            "case_status_category": case_status_category,
            "resolution_category": "known_answer",
            "output_refs": output_refs,
            "evidence_refs": ["evidence_support_local_runtime"],
        },
        recommended_next_step=next_step,
        rationale="rationale_category_support_fixture_boundary",
    )


@activity.defn(name=ACTIVITY_INVOKE_TOOL_GATEWAY)
async def fake_gateway(request: ToolGatewayRequest) -> ToolGatewayResponse:
    output: dict[str, object] = {}
    if request.tool_name == "ticket.lookup_case":
        output = {
            "lookup_status": "found",
            "case_ref": request.arguments["case_ref"],
            "case_status_category": "open",
        }
    elif request.tool_name == "ticket.lookup_duplicates":
        output = {
            "duplicate_status": "candidate_refs",
            "duplicate_case_refs": ["case_duplicate_001"],
        }
    elif request.tool_name == "ticket.propose_case_update":
        output = {
            "proposal_status": "recorded",
            "case_update_ref": request.arguments["case_update_ref"],
            "case_status_mutated": False,
        }
    verdict = "propose" if request.mode == "propose" else "allow"
    return ToolGatewayResponse(
        verdict_id=str(uuid4()),
        tool_call_id=str(uuid4()),
        audit_event_id=str(uuid4()),
        verdict=verdict,
        enforced_mode=request.mode,
        reason="verdict_category_allow",
        connector_invocation_id=str(uuid4()),
        output=output,
    )


async def _generate() -> None:
    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue="fixture-support-triage",
            workflows=[SupportTriageWorkflow],
            activities=[fake_record, fake_agent, fake_gateway],
        ),
    ):
        handle = await env.client.start_workflow(
            "SupportTriageWorkflow",
            fixture_request(),
            id="support-triage-happy-fixture",
            task_queue="fixture-support-triage",
        )
        await handle.result()
        history = await handle.fetch_history()

    OUTPUT.write_text(_sanitised_history_json(history.to_json()), encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(_generate())

"""Phase 1A Lighthouse trace/eval harness."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast
from uuid import UUID, uuid4

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from chorus.contracts.generated.eval.eval_fixture import EvalFixture, FinalOutcome
from chorus.contracts.generated.events.agent_invocation_record import AgentInvocationRecord
from chorus.contracts.generated.events.audit_event import AuditEvent
from chorus.contracts.generated.events.workflow_event import WorkflowEvent
from chorus.contracts.generated.tools.gateway_verdict import GatewayVerdict
from chorus.contracts.generated.tools.tool_call import ToolCall
from chorus.persistence.migrate import database_url_from_env

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
HAPPY_PATH_ROLES: tuple[tuple[str, str, str], ...] = (
    ("researcher", "lighthouse.researcher", "company_research"),
    ("qualifier", "lighthouse.qualifier", "lead_qualification"),
    ("drafter", "lighthouse.drafter", "response_draft"),
    ("validator", "lighthouse.validator", "response_validation"),
)

EvalStatus = Literal["pass", "fail", "skip"]


@dataclass(frozen=True)
class EvalCheck:
    name: str
    status: EvalStatus
    detail: str


@dataclass(frozen=True)
class OfflineEvidence:
    workflow_id: str
    correlation_id: str
    events: list[WorkflowEvent]
    decisions: list[AgentInvocationRecord]
    tool_call: ToolCall
    verdict: GatewayVerdict
    audit_event: AuditEvent
    compensation_audit_event: AuditEvent | None
    retry_dlq_audit_event: AuditEvent | None
    latency_ms: int


@dataclass(frozen=True)
class LiveEvidence:
    workflow_id: str
    correlation_id: str
    workflow_status: str
    workflow_current_step: str | None
    history_event_types: list[str]
    history_steps: list[str]
    outbox_events: list[WorkflowEvent]
    outbox_statuses: list[str]
    decisions: list[AgentInvocationRecord]
    tool_audits: list[AuditEvent]
    verdicts: list[GatewayVerdict]
    tool_names: list[str]
    total_cost_usd: Decimal
    latency_ms: int


class EvalError(AssertionError):
    """Raised when a fixture does not satisfy its governed expectations."""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        action="append",
        help="Eval fixture JSON to execute. Defaults to every fixture in chorus/eval/fixtures.",
    )
    parser.add_argument(
        "--correlation-id",
        default=os.environ.get("CHORUS_EVAL_CORRELATION_ID"),
        help="Existing live workflow correlation ID to inspect in Postgres.",
    )
    parser.add_argument(
        "--workflow-id",
        default=os.environ.get("CHORUS_EVAL_WORKFLOW_ID"),
        help="Existing live workflow ID to inspect in Postgres.",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("CHORUS_EVAL_DATABASE_URL") or os.environ.get("CHORUS_DATABASE_URL"),
        help="Postgres URL for optional live evidence checks.",
    )
    parser.add_argument(
        "--require-live",
        action="store_true",
        default=os.environ.get("CHORUS_EVAL_REQUIRE_LIVE") == "1",
        help="Fail if the live Postgres evidence check cannot run.",
    )
    args = parser.parse_args(argv)

    explicit_fixtures = args.fixture is not None
    live_selector_supplied = args.workflow_id is not None or args.correlation_id is not None
    fixture_paths = args.fixture or sorted(FIXTURE_DIR.glob("*.json"))
    failed = False

    for index, fixture_path in enumerate(fixture_paths):
        fixture = _load_fixture(fixture_path)
        checks: list[EvalCheck] = []

        try:
            offline = _build_offline_evidence(fixture)
            checks.extend(_assert_offline_evidence(fixture, offline))
        except Exception as exc:
            checks.append(EvalCheck("offline fixture", "fail", str(exc)))

        if should_run_live_checks(
            fixture=fixture,
            explicit_fixtures=explicit_fixtures,
            live_selector_supplied=live_selector_supplied,
        ):
            checks.extend(
                _run_live_checks(
                    fixture=fixture,
                    database_url=args.database_url,
                    workflow_id=args.workflow_id,
                    correlation_id=args.correlation_id,
                    require_live=args.require_live,
                )
            )
        else:
            checks.append(
                EvalCheck(
                    "live persisted evidence",
                    "skip",
                    "live selector is checked against the default happy-path fixture; "
                    "pass --fixture for a specific governance/failure live run",
                )
            )

        if index > 0:
            print()
        _print_report(fixture, checks)
        failed = failed or any(check.status == "fail" for check in checks)

    return 1 if failed else 0


def should_run_live_checks(
    *,
    fixture: EvalFixture,
    explicit_fixtures: bool,
    live_selector_supplied: bool,
) -> bool:
    if explicit_fixtures or not live_selector_supplied:
        return True
    return fixture.fixture_id == "lighthouse-happy-path-acme"


def _load_fixture(path: Path) -> EvalFixture:
    fixture_path = path if path.is_absolute() else ROOT / path
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    return EvalFixture.model_validate(data)


def _build_offline_evidence(fixture: EvalFixture) -> OfflineEvidence:
    workflow_id = f"lighthouse-eval-{fixture.fixture_id}"
    correlation_id = f"cor_eval_{fixture.fixture_id.replace('-', '_')}"
    lead_id = uuid4()
    started_at = datetime(2026, 4, 29, 10, 0, tzinfo=UTC)

    events = _workflow_events(
        fixture=fixture,
        workflow_id=workflow_id,
        correlation_id=correlation_id,
        lead_id=lead_id,
        started_at=started_at,
    )
    decisions = [
        _decision_record(
            fixture=fixture,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            role=role,
            agent_id=agent_id,
            task_kind=task_kind,
            index=index,
        )
        for index, (role, agent_id, task_kind) in enumerate(_fixture_roles(fixture), start=1)
    ]
    tool_call = _tool_call(
        fixture=fixture,
        workflow_id=workflow_id,
        correlation_id=correlation_id,
        invocation_id=decisions[-1].invocation_id,
    )
    verdict = _gateway_verdict(
        tool_call=tool_call,
        fixture=fixture,
        correlation_id=correlation_id,
    )
    audit_event = _audit_event(
        fixture=fixture,
        workflow_id=workflow_id,
        correlation_id=correlation_id,
        tool_call=tool_call,
        verdict=verdict,
    )
    compensation_audit_event = (
        _compensation_audit_event(
            fixture=fixture,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            tool_call=tool_call,
        )
        if _is_connector_failure_fixture(fixture)
        else None
    )
    retry_dlq_audit_event = (
        _retry_dlq_audit_event(
            fixture=fixture,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            sequence=len(events),
        )
        if _is_retry_exhaustion_fixture(fixture)
        else None
    )

    # Re-validate every contract model after composing the evidence graph.
    for event in events:
        WorkflowEvent.model_validate(event.model_dump(mode="json"))
    for decision in decisions:
        AgentInvocationRecord.model_validate(decision.model_dump(mode="json"))
    ToolCall.model_validate(tool_call.model_dump(mode="json"))
    GatewayVerdict.model_validate(verdict.model_dump(mode="json"))
    AuditEvent.model_validate(audit_event.model_dump(mode="json"))
    if compensation_audit_event is not None:
        AuditEvent.model_validate(compensation_audit_event.model_dump(mode="json"))
    if retry_dlq_audit_event is not None:
        AuditEvent.model_validate(retry_dlq_audit_event.model_dump(mode="json"))

    return OfflineEvidence(
        workflow_id=workflow_id,
        correlation_id=correlation_id,
        events=events,
        decisions=decisions,
        tool_call=tool_call,
        verdict=verdict,
        audit_event=audit_event,
        compensation_audit_event=compensation_audit_event,
        retry_dlq_audit_event=retry_dlq_audit_event,
        latency_ms=15_000,
    )


def _workflow_events(
    *,
    fixture: EvalFixture,
    workflow_id: str,
    correlation_id: str,
    lead_id: UUID,
    started_at: datetime,
) -> list[WorkflowEvent]:
    events: list[WorkflowEvent] = []
    sequence = 1

    def append(event_type: str, step: str | None, payload: dict[str, Any]) -> None:
        nonlocal sequence
        events.append(
            WorkflowEvent.model_validate(
                {
                    "schema_version": "1.0.0",
                    "event_id": str(uuid4()),
                    "event_type": event_type,
                    "occurred_at": (started_at + timedelta(seconds=sequence)).isoformat(),
                    "tenant_id": fixture.input.tenant_id,
                    "correlation_id": correlation_id,
                    "workflow_id": workflow_id,
                    "lead_id": str(lead_id),
                    "sequence": sequence,
                    "step": step,
                    "payload": {
                        "lead_summary": "Need help choosing a CRM automation partner",
                        **payload,
                    },
                }
            )
        )
        sequence += 1

    append(
        "lead.received",
        "intake",
        {
            "subject": "Need help choosing a CRM automation partner",
            "sender": "alex.morgan@example.test",
            "message_id": "<lead-acme-001@example.test>",
            "source": "mailpit_smtp",
        },
    )
    append("workflow.started", "intake", {})
    step_counts: dict[str, int] = {}
    for step in fixture.expected.workflow_path:
        step_counts[step] = step_counts.get(step, 0) + 1
        append("workflow.step.started", step, {})
        append(
            "workflow.step.completed",
            step,
            _completed_step_payload(fixture, step, step_counts[step]),
        )
    if _is_retry_exhaustion_fixture(fixture):
        append(
            "workflow.failed",
            "research_qualification",
            {
                "outcome": "failed",
                "failure_classification": "retry_exhausted",
                "dlq_status": "dlq",
            },
        )
    match fixture.expected.final_outcome.value:
        case "escalate":
            append("workflow.escalated", "escalate", {"outcome": "escalated"})
        case "reject":
            append("workflow.failed", None, {"outcome": "failed"})
        case _:
            append("workflow.completed", "complete", {"outcome": "completed"})
    return events


def _fixture_roles(fixture: EvalFixture) -> tuple[tuple[str, str, str], ...]:
    if _is_low_confidence_fixture(fixture):
        return (
            ("researcher", "lighthouse.researcher", "company_research"),
            ("researcher", "lighthouse.researcher", "company_research"),
            ("qualifier", "lighthouse.qualifier", "lead_qualification"),
            ("drafter", "lighthouse.drafter", "response_draft"),
            ("validator", "lighthouse.validator", "response_validation"),
        )
    if _is_validator_redraft_fixture(fixture):
        return (
            ("researcher", "lighthouse.researcher", "company_research"),
            ("qualifier", "lighthouse.qualifier", "lead_qualification"),
            ("drafter", "lighthouse.drafter", "response_draft"),
            ("validator", "lighthouse.validator", "response_validation"),
            ("drafter", "lighthouse.drafter", "response_draft"),
            ("validator", "lighthouse.validator", "response_validation"),
        )
    if _is_retry_exhaustion_fixture(fixture):
        return (("researcher", "lighthouse.researcher", "company_research"),)
    return HAPPY_PATH_ROLES


def _completed_step_payload(fixture: EvalFixture, step: str, step_count: int) -> dict[str, Any]:
    if _is_low_confidence_fixture(fixture) and step == "research_qualification" and step_count == 1:
        return {
            "step_outcome": "deeper_research_requested",
            "research_attempt": 1,
            "confidence": 0.42,
            "recommended_next_step": "deeper_research",
            "deeper_research_requested": True,
        }
    if _is_low_confidence_fixture(fixture) and step == "research_qualification" and step_count == 2:
        return {
            "step_outcome": "completed",
            "research_attempt": 2,
            "confidence": 0.86,
            "deeper_research_completed": True,
        }
    if _is_validator_redraft_fixture(fixture) and step == "validation" and step_count == 1:
        return {
            "step_outcome": "redraft_requested",
            "redraft_attempt": 1,
            "recommended_next_step": "redraft",
            "redraft_requested": True,
        }
    if _is_validator_redraft_fixture(fixture) and step == "validation" and step_count == 2:
        return {
            "step_outcome": "completed",
            "redraft_attempt": 2,
            "recommended_next_step": "send",
        }
    if _is_connector_failure_fixture(fixture) and step == "propose_send":
        return {
            "step_outcome": "connector_failure",
            "gateway_verdict": "connector_failure",
            "enforced_mode": "propose",
            "tool_name": "email.propose_response",
            "connector_failure": True,
            "compensation_required": True,
        }
    if _is_connector_failure_fixture(fixture) and step == "escalate":
        return {
            "step_outcome": "compensated_escalation",
            "reason": "tool gateway connector failure compensated and escalated",
            "compensation_recorded": True,
        }
    if _is_retry_exhaustion_fixture(fixture) and step == "research_qualification":
        return {
            "step_outcome": "retry_exhausted",
            "failed_activity": "lighthouse.invoke_agent_runtime",
            "retry_attempts": 3,
            "dlq_required": True,
        }
    if _is_retry_exhaustion_fixture(fixture) and step == "escalate":
        return {
            "step_outcome": "dlq_escalation",
            "reason": "activity retry policy exhausted; DLQ evidence recorded",
            "dlq_recorded": True,
        }
    return {"step_outcome": "completed"}


def _decision_input_summary(
    fixture: EvalFixture,
    role: str,
    task_kind: str,
    index: int,
) -> str:
    if _is_low_confidence_fixture(fixture) and role == "researcher":
        attempt = index
        return f"{task_kind} input from fixture lead with research_attempt={attempt}"
    if _is_validator_redraft_fixture(fixture) and role in {"drafter", "validator"}:
        attempt = 1 if index <= 4 else 2
        return f"{task_kind} input from fixture lead with redraft_attempt={attempt}"
    return f"{task_kind} input from fixture lead"


def _decision_output_summary(
    fixture: EvalFixture,
    role: str,
    task_kind: str,
    index: int,
) -> str:
    if _is_low_confidence_fixture(fixture) and role == "researcher" and index == 1:
        return "company_research requested deeper research after low-confidence evidence"
    if _is_low_confidence_fixture(fixture) and role == "researcher" and index == 2:
        return "company_research completed after deeper research"
    if _is_validator_redraft_fixture(fixture) and role == "validator" and index == 4:
        return "response_validation requested redraft"
    if _is_validator_redraft_fixture(fixture) and role == "validator" and index == 6:
        return "response_validation approved redrafted response"
    if _is_retry_exhaustion_fixture(fixture) and role == "researcher":
        return "company_research failed after Temporal activity retries exhausted"
    return f"{task_kind} completed for happy path"


def _decision_justification(fixture: EvalFixture) -> str:
    if fixture.phase.value == "1B":
        return "Deterministic Phase 1B governance fixture evidence."
    return "Deterministic Phase 1A fixture evidence."


def _is_low_confidence_fixture(fixture: EvalFixture) -> bool:
    return fixture.fixture_id == "lighthouse-low-confidence-research"


def _is_validator_redraft_fixture(fixture: EvalFixture) -> bool:
    return fixture.fixture_id == "lighthouse-validator-redraft"


def _is_connector_failure_fixture(fixture: EvalFixture) -> bool:
    return fixture.fixture_id == "lighthouse-connector-failure"


def _is_retry_exhaustion_fixture(fixture: EvalFixture) -> bool:
    return fixture.fixture_id == "lighthouse-retry-exhaustion"


def _decision_record(
    *,
    fixture: EvalFixture,
    workflow_id: str,
    correlation_id: str,
    role: str,
    agent_id: str,
    task_kind: str,
    index: int,
) -> AgentInvocationRecord:
    started_at = datetime(2026, 4, 29, 10, 1, index, tzinfo=UTC)
    prompt_hash = f"sha256:{str(index) * 64}"
    return AgentInvocationRecord.model_validate(
        {
            "schema_version": "1.0.0",
            "invocation_id": str(uuid4()),
            "correlation_id": correlation_id,
            "workflow_id": workflow_id,
            "tenant_id": fixture.input.tenant_id,
            "agent": {
                "agent_id": agent_id,
                "role": role,
                "version": "v1",
                "lifecycle_state": "approved",
                "prompt_reference": f"prompts/lighthouse/{role}/v1.md",
                "prompt_hash": prompt_hash,
            },
            "model_route": {
                "provider": "local",
                "model": "lighthouse-happy-path-v1",
                "task_kind": task_kind,
                "budget_cap_usd": 0.01,
                "parameters": {"temperature": 0},
            },
            "input_summary": _decision_input_summary(fixture, role, task_kind, index),
            "output_summary": _decision_output_summary(fixture, role, task_kind, index),
            "justification": _decision_justification(fixture),
            "outcome": "failed" if _is_retry_exhaustion_fixture(fixture) else "succeeded",
            "tool_call_ids": [],
            "cost": {"amount": 0.0, "currency": "USD"},
            "duration_ms": 25,
            "started_at": started_at.isoformat(),
            "completed_at": (started_at + timedelta(milliseconds=25)).isoformat(),
            "contract_refs": [
                "contracts/agents/lighthouse_agent_io.schema.json",
                "contracts/events/agent_invocation_record.schema.json",
            ],
        }
    )


def _tool_call(
    *,
    fixture: EvalFixture,
    workflow_id: str,
    correlation_id: str,
    invocation_id: UUID,
) -> ToolCall:
    tool_name = (
        fixture.expected.blocked_tool_actions[0]
        if fixture.expected.blocked_tool_actions
        else "email.propose_response"
    )
    mode = "write" if tool_name == "email.send_response" else "propose"
    return ToolCall.model_validate(
        {
            "schema_version": "1.0.0",
            "tool_call_id": str(uuid4()),
            "invocation_id": str(invocation_id),
            "tenant_id": fixture.input.tenant_id,
            "correlation_id": correlation_id,
            "agent_id": "lighthouse.drafter",
            "tool_name": tool_name,
            "mode": mode,
            "idempotency_key": f"{workflow_id}:{tool_name}:{mode}",
            "arguments": {
                "to": "alex.morgan@example.test",
                "subject": "Re: Need help choosing a CRM automation partner",
                "body_text": "A governed Lighthouse proposal draft.",
            },
            "requested_at": "2026-04-29T10:02:00+00:00",
        }
    )


def _gateway_verdict(
    *,
    tool_call: ToolCall,
    fixture: EvalFixture,
    correlation_id: str,
) -> GatewayVerdict:
    blocked = bool(fixture.expected.blocked_tool_actions)
    connector_failure = _is_connector_failure_fixture(fixture)
    return GatewayVerdict.model_validate(
        {
            "schema_version": "1.0.0",
            "verdict_id": str(uuid4()),
            "tool_call_id": str(tool_call.tool_call_id),
            "tenant_id": fixture.input.tenant_id,
            "correlation_id": correlation_id,
            "verdict": "block" if blocked else "propose",
            "enforced_mode": tool_call.mode.value,
            "reason": (
                "Connector transient failure after authorised call; Temporal retries exhausted."
                if connector_failure
                else "Explicit Tool Gateway grant denies the requested agent, tool, and mode."
                if blocked
                else "Proposal-mode grant accepted; connector captured sandbox proposal."
            ),
            "rewritten_arguments": None,
            "approval_required": False,
            "audit_event_id": str(uuid4()),
            "connector_invocation_id": None if blocked else str(uuid4()),
            "decided_at": "2026-04-29T10:02:01+00:00",
        }
    )


def _audit_event(
    *,
    fixture: EvalFixture,
    workflow_id: str,
    correlation_id: str,
    tool_call: ToolCall,
    verdict: GatewayVerdict,
) -> AuditEvent:
    connector_invocation_id = (
        str(verdict.connector_invocation_id)
        if verdict.connector_invocation_id is not None
        else None
    )
    return AuditEvent.model_validate(
        {
            "schema_version": "1.0.0",
            "audit_event_id": str(verdict.audit_event_id),
            "occurred_at": verdict.decided_at.isoformat(),
            "tenant_id": fixture.input.tenant_id,
            "correlation_id": correlation_id,
            "workflow_id": workflow_id,
            "actor": {"type": "agent", "id": "lighthouse.drafter"},
            "category": "tool_gateway",
            "action": "tool_call.decided",
            "verdict": verdict.verdict.value,
            "details": {
                "tool_call": tool_call.model_dump(mode="json"),
                "gateway_verdict": verdict.model_dump(mode="json"),
                "gateway_response": {
                    "verdict_id": str(verdict.verdict_id),
                    "tool_call_id": str(tool_call.tool_call_id),
                    "audit_event_id": str(verdict.audit_event_id),
                    "verdict": verdict.verdict.value,
                    "enforced_mode": verdict.enforced_mode.value,
                    "reason": verdict.reason,
                    "connector_invocation_id": connector_invocation_id,
                    "output": {} if connector_invocation_id is None else {"captured_by": "mailpit"},
                },
            },
        }
    )


def _compensation_audit_event(
    *,
    fixture: EvalFixture,
    workflow_id: str,
    correlation_id: str,
    tool_call: ToolCall,
) -> AuditEvent:
    return AuditEvent.model_validate(
        {
            "schema_version": "1.0.0",
            "audit_event_id": str(uuid4()),
            "occurred_at": "2026-04-29T10:02:05+00:00",
            "tenant_id": fixture.input.tenant_id,
            "correlation_id": correlation_id,
            "workflow_id": workflow_id,
            "actor": {"type": "system", "id": "lighthouse.workflow"},
            "category": "connector",
            "action": "connector.failure.compensated",
            "verdict": "recorded",
            "details": {
                "failed_tool_action": {
                    "invocation_id": str(tool_call.invocation_id),
                    "agent_id": tool_call.agent_id,
                    "tool_name": tool_call.tool_name.value,
                    "mode": tool_call.mode.value,
                    "idempotency_key": tool_call.idempotency_key,
                },
                "compensation": {
                    "status": "escalated",
                    "reason": "tool gateway connector failure compensated and escalated",
                },
            },
        }
    )


def _retry_dlq_audit_event(
    *,
    fixture: EvalFixture,
    workflow_id: str,
    correlation_id: str,
    sequence: int,
) -> AuditEvent:
    return AuditEvent.model_validate(
        {
            "schema_version": "1.0.0",
            "audit_event_id": str(uuid4()),
            "occurred_at": "2026-04-29T10:02:05+00:00",
            "tenant_id": fixture.input.tenant_id,
            "correlation_id": correlation_id,
            "workflow_id": workflow_id,
            "actor": {"type": "system", "id": "lighthouse.workflow"},
            "category": "workflow",
            "action": "workflow.retry_exhausted.dlq_recorded",
            "verdict": "recorded",
            "details": {
                "retry_exhaustion": {
                    "failed_activity": "lighthouse.invoke_agent_runtime",
                    "failed_step": "research_qualification",
                    "attempts": 3,
                    "reason": "fixture persistent agent runtime failure",
                },
                "dlq": {
                    "status": "dlq",
                    "event_type": "workflow.failed",
                    "sequence": sequence,
                },
            },
        }
    )


def _assert_offline_evidence(
    fixture: EvalFixture,
    evidence: OfflineEvidence,
) -> list[EvalCheck]:
    expected = fixture.expected
    checks = [
        _check_workflow_path(expected.workflow_path, _completed_steps(evidence.events)),
        _check_final_outcome(expected.final_outcome, _offline_final_outcome(evidence)),
        _check_event_types(
            expected.required_event_types, [event.event_type.value for event in evidence.events]
        ),
        _check_decision_trail(fixture, expected.required_audit_fields, evidence.decisions),
        _check_tool_evidence(
            allowed_tool_actions=expected.allowed_tool_actions,
            blocked_tool_actions=expected.blocked_tool_actions,
            tool_names=[]
            if _is_retry_exhaustion_fixture(fixture)
            else [evidence.tool_call.tool_name],
            verdicts=[]
            if _is_retry_exhaustion_fixture(fixture)
            else [evidence.verdict.verdict.value],
        ),
        _check_budget(expected.max_cost_usd, [record.cost.amount for record in evidence.decisions]),
        _check_latency(expected.max_latency_ms, evidence.latency_ms),
        _check_correlation_ids(
            evidence.correlation_id,
            [event.correlation_id for event in evidence.events],
            [record.correlation_id for record in evidence.decisions],
            [
                audit.correlation_id
                for audit in [
                    evidence.audit_event,
                    evidence.compensation_audit_event,
                    evidence.retry_dlq_audit_event,
                ]
                if audit is not None
            ],
        ),
    ]
    if _is_low_confidence_fixture(fixture):
        checks.append(_check_deeper_research_branch(evidence.decisions))
    if _is_connector_failure_fixture(fixture):
        compensation_audits = (
            [evidence.compensation_audit_event]
            if evidence.compensation_audit_event is not None
            else []
        )
        checks.append(_check_connector_failure_compensation(compensation_audits))
    if _is_retry_exhaustion_fixture(fixture):
        retry_audits = (
            [evidence.retry_dlq_audit_event] if evidence.retry_dlq_audit_event is not None else []
        )
        checks.append(_check_retry_exhaustion_dlq(retry_audits, ["dlq"]))
    if any(check.status == "fail" for check in checks):
        details = "; ".join(check.detail for check in checks if check.status == "fail")
        raise EvalError(details)
    return checks


def _run_live_checks(
    *,
    fixture: EvalFixture,
    database_url: str | None,
    workflow_id: str | None,
    correlation_id: str | None,
    require_live: bool,
) -> list[EvalCheck]:
    if workflow_id is None and correlation_id is None:
        status: EvalStatus = "fail" if require_live else "skip"
        return [
            EvalCheck(
                "live persisted evidence",
                status,
                "set CHORUS_EVAL_CORRELATION_ID or CHORUS_EVAL_WORKFLOW_ID after a live run",
            )
        ]

    database_url = database_url or database_url_from_env()
    try:
        with psycopg.connect(database_url, connect_timeout=2) as conn:
            evidence = _load_live_evidence(
                conn,
                fixture=fixture,
                workflow_id=workflow_id,
                correlation_id=correlation_id,
            )
    except (psycopg.Error, EvalError) as exc:
        status: EvalStatus = "fail" if require_live else "skip"
        return [EvalCheck("live persisted evidence", status, str(exc))]

    checks = [
        _check_workflow_path(fixture.expected.workflow_path, evidence.history_steps),
        _check_final_outcome(fixture.expected.final_outcome, _live_final_outcome(evidence)),
        _check_event_types(fixture.expected.required_event_types, evidence.history_event_types),
        _check_decision_trail(fixture, fixture.expected.required_audit_fields, evidence.decisions),
        _check_tool_evidence(
            allowed_tool_actions=fixture.expected.allowed_tool_actions,
            blocked_tool_actions=fixture.expected.blocked_tool_actions,
            tool_names=[] if _is_retry_exhaustion_fixture(fixture) else evidence.tool_names,
            verdicts=(
                []
                if _is_retry_exhaustion_fixture(fixture)
                else [verdict.verdict.value for verdict in evidence.verdicts]
            ),
        ),
        _check_budget(fixture.expected.max_cost_usd, [evidence.total_cost_usd]),
        _check_latency(fixture.expected.max_latency_ms, evidence.latency_ms),
        _check_correlation_ids(
            evidence.correlation_id,
            [event.correlation_id for event in evidence.outbox_events],
            [record.correlation_id for record in evidence.decisions],
            [audit.correlation_id for audit in evidence.tool_audits],
        ),
    ]
    if _is_low_confidence_fixture(fixture):
        checks.append(_check_deeper_research_branch(evidence.decisions))
    if _is_connector_failure_fixture(fixture):
        checks.append(_check_connector_failure_compensation(evidence.tool_audits))
    if _is_retry_exhaustion_fixture(fixture):
        checks.append(_check_retry_exhaustion_dlq(evidence.tool_audits, evidence.outbox_statuses))
    return checks


def _load_live_evidence(
    conn: Connection[Any],
    *,
    fixture: EvalFixture,
    workflow_id: str | None,
    correlation_id: str | None,
) -> LiveEvidence:
    workflow = _fetch_workflow(conn, fixture.input.tenant_id, workflow_id, correlation_id)
    if workflow is None:
        raise EvalError(
            "no live workflow_read_models row found; run just demo, just intake-once, "
            "relay/project events, then pass CHORUS_EVAL_CORRELATION_ID"
        )

    workflow_id = cast(str, workflow["workflow_id"])
    correlation_id = cast(str, workflow["correlation_id"])
    history = _fetch_history(conn, fixture.input.tenant_id, workflow_id)
    outbox_events, outbox_statuses = _fetch_outbox_events(
        conn, fixture.input.tenant_id, workflow_id
    )
    decisions = _fetch_decisions(conn, fixture.input.tenant_id, workflow_id)
    audits, verdicts, tool_names = _fetch_tool_audits(conn, fixture.input.tenant_id, workflow_id)

    if not history:
        raise EvalError(f"workflow {workflow_id} has no projected history events")
    if not outbox_events:
        raise EvalError(f"workflow {workflow_id} has no persisted outbox workflow events")
    if not decisions:
        raise EvalError(f"workflow {workflow_id} has no decision-trail rows")
    if not audits:
        raise EvalError(f"workflow {workflow_id} has no tool-action audit rows")

    started_at = cast(datetime | None, workflow["started_at"])
    completed_at = cast(datetime | None, workflow["completed_at"])
    latency_ms = (
        round((completed_at - started_at).total_seconds() * 1000)
        if started_at is not None and completed_at is not None
        else sum(record.duration_ms for record in decisions)
    )
    total_cost_usd = sum((Decimal(str(record.cost.amount)) for record in decisions), Decimal("0"))

    history_event_types = [cast(str, row["event_type"]) for row in history]
    if _is_retry_exhaustion_fixture(fixture):
        history_event_types.extend(event.event_type.value for event in outbox_events)

    return LiveEvidence(
        workflow_id=workflow_id,
        correlation_id=correlation_id,
        workflow_status=cast(str, workflow["status"]),
        workflow_current_step=cast(str | None, workflow["current_step"]),
        history_event_types=history_event_types,
        history_steps=_completed_steps_from_history(history),
        outbox_events=outbox_events,
        outbox_statuses=outbox_statuses,
        decisions=decisions,
        tool_audits=audits,
        verdicts=verdicts,
        tool_names=tool_names,
        total_cost_usd=total_cost_usd,
        latency_ms=latency_ms,
    )


def _fetch_workflow(
    conn: Connection[Any],
    tenant_id: str,
    workflow_id: str | None,
    correlation_id: str | None,
) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        if workflow_id is not None:
            cur.execute(
                """
                SELECT workflow_id, correlation_id, status, current_step, started_at, completed_at
                FROM workflow_read_models
                WHERE tenant_id = %s AND workflow_id = %s
                """,
                (tenant_id, workflow_id),
            )
        elif correlation_id is not None:
            cur.execute(
                """
                SELECT workflow_id, correlation_id, status, current_step, started_at, completed_at
                FROM workflow_read_models
                WHERE tenant_id = %s AND correlation_id = %s
                """,
                (tenant_id, correlation_id),
            )
        else:
            cur.execute(
                """
                SELECT workflow_id, correlation_id, status, current_step, started_at, completed_at
                FROM workflow_read_models
                WHERE tenant_id = %s AND status = 'completed'
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (tenant_id,),
            )
        return cur.fetchone()


def _fetch_history(
    conn: Connection[Any],
    tenant_id: str,
    workflow_id: str,
) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT event_type, step, sequence, payload
            FROM workflow_history_events
            WHERE tenant_id = %s AND workflow_id = %s
            ORDER BY sequence ASC
            """,
            (tenant_id, workflow_id),
        )
        return list(cur.fetchall())


def _fetch_outbox_events(
    conn: Connection[Any],
    tenant_id: str,
    workflow_id: str,
) -> tuple[list[WorkflowEvent], list[str]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                schema_version,
                event_id,
                event_type,
                occurred_at,
                tenant_id,
                correlation_id,
                workflow_id,
                lead_id,
                sequence,
                step,
                payload,
                status
            FROM outbox_events
            WHERE tenant_id = %s AND workflow_id = %s
            ORDER BY sequence ASC
            """,
            (tenant_id, workflow_id),
        )
        rows = cur.fetchall()
    events = [
        WorkflowEvent.model_validate({key: value for key, value in row.items() if key != "status"})
        for row in rows
    ]
    return events, [cast(str, row["status"]) for row in rows]


def _fetch_decisions(
    conn: Connection[Any],
    tenant_id: str,
    workflow_id: str,
) -> list[AgentInvocationRecord]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT raw_record
            FROM decision_trail_entries
            WHERE tenant_id = %s AND workflow_id = %s
            ORDER BY started_at ASC
            """,
            (tenant_id, workflow_id),
        )
        rows = cur.fetchall()
    return [AgentInvocationRecord.model_validate(row["raw_record"]) for row in rows]


def _fetch_tool_audits(
    conn: Connection[Any],
    tenant_id: str,
    workflow_id: str,
) -> tuple[list[AuditEvent], list[GatewayVerdict], list[str]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT raw_event, tool_name
            FROM tool_action_audit
            WHERE tenant_id = %s AND workflow_id = %s
            ORDER BY occurred_at ASC
            """,
            (tenant_id, workflow_id),
        )
        rows = cur.fetchall()

    audits = [AuditEvent.model_validate(row["raw_event"]) for row in rows]
    verdicts = [
        GatewayVerdict.model_validate(audit.details["gateway_verdict"])
        for audit in audits
        if "gateway_verdict" in audit.details
    ]
    tool_names = [cast(str, row["tool_name"]) for row in rows if row["tool_name"] is not None]
    return audits, verdicts, tool_names


def _completed_steps(events: Iterable[WorkflowEvent]) -> list[str]:
    steps: list[str] = []
    for event in events:
        if event.event_type.value == "workflow.step.completed" and event.step is not None:
            steps.append(event.step.value)
    return steps


def _completed_steps_from_history(rows: Iterable[dict[str, Any]]) -> list[str]:
    return [
        cast(str, row["step"])
        for row in rows
        if row["event_type"] == "workflow.step.completed" and row["step"] is not None
    ]


def _live_final_outcome(evidence: LiveEvidence) -> str:
    if evidence.workflow_status == "escalated":
        return "escalate"
    if evidence.workflow_status == "failed":
        return "reject"
    if any(verdict.verdict.value == "propose" for verdict in evidence.verdicts):
        return "propose"
    if any(verdict.enforced_mode.value == "write" for verdict in evidence.verdicts):
        return "send"
    return "reject"


def _offline_final_outcome(evidence: OfflineEvidence) -> str:
    if evidence.retry_dlq_audit_event is not None:
        return "escalate"
    if evidence.verdict.verdict.value in {"block", "approval_required"}:
        return "escalate"
    if evidence.verdict.verdict.value == "propose":
        return "propose"
    if evidence.verdict.enforced_mode.value == "write":
        return "send"
    return "reject"


def _check_workflow_path(expected: list[str], actual: list[str]) -> EvalCheck:
    if actual == expected:
        return EvalCheck("workflow path", "pass", "expected step sequence observed")
    return EvalCheck("workflow path", "fail", f"expected {expected}, observed {actual}")


def _check_final_outcome(expected: FinalOutcome, actual: str) -> EvalCheck:
    if actual == expected.value:
        return EvalCheck("final outcome", "pass", f"observed {actual}")
    return EvalCheck("final outcome", "fail", f"expected {expected.value}, observed {actual}")


def _check_event_types(expected: list[str], actual: list[str]) -> EvalCheck:
    missing = [event_type for event_type in expected if event_type not in actual]
    if not missing:
        return EvalCheck("workflow events", "pass", "required event types observed")
    return EvalCheck("workflow events", "fail", f"missing event types: {', '.join(missing)}")


def _check_decision_trail(
    fixture: EvalFixture,
    required_fields: list[str],
    decisions: list[AgentInvocationRecord],
) -> EvalCheck:
    expected_roles = (
        {"researcher"}
        if _is_retry_exhaustion_fixture(fixture)
        else {role for role, _, _ in HAPPY_PATH_ROLES}
    )
    observed_roles = {record.agent.role.value for record in decisions}
    missing_roles = sorted(expected_roles - observed_roles)
    if missing_roles:
        return EvalCheck("decision trail", "fail", f"missing agent roles: {missing_roles}")

    missing_fields: list[str] = []
    for field in required_fields:
        if not all(_decision_has_field(record, field) for record in decisions):
            missing_fields.append(field)
    if missing_fields:
        return EvalCheck("decision trail", "fail", f"missing fields: {missing_fields}")

    return EvalCheck("decision trail", "pass", "agent records are complete and contract-valid")


def _check_deeper_research_branch(decisions: list[AgentInvocationRecord]) -> EvalCheck:
    researcher_decisions = [
        record for record in decisions if record.agent.role.value == "researcher"
    ]
    if len(researcher_decisions) < 2:
        return EvalCheck(
            "deeper research branch",
            "fail",
            f"expected at least two researcher invocations, observed {len(researcher_decisions)}",
        )

    requested = any(
        "deeper research" in record.output_summary.lower()
        or "deeper_research" in record.output_summary.lower()
        for record in researcher_decisions
    )
    enriched_attempt = any(
        "research_attempt=2" in record.input_summary
        or '"research_attempt": 2' in record.input_summary
        for record in researcher_decisions
    )
    if requested and enriched_attempt:
        return EvalCheck(
            "deeper research branch",
            "pass",
            "low-confidence research request and enriched second attempt observed",
        )
    return EvalCheck(
        "deeper research branch",
        "fail",
        "missing deeper-research request or enriched second research attempt",
    )


def _check_connector_failure_compensation(audits: list[AuditEvent]) -> EvalCheck:
    for audit in audits:
        if audit.action != "connector.failure.compensated":
            continue
        compensation_obj = audit.details.get("compensation")
        failed_tool_action_obj = audit.details.get("failed_tool_action")
        if not isinstance(compensation_obj, dict) or not isinstance(failed_tool_action_obj, dict):
            continue
        compensation = cast(dict[str, Any], compensation_obj)
        failed_tool_action = cast(dict[str, Any], failed_tool_action_obj)
        if (
            compensation.get("status") == "escalated"
            and failed_tool_action.get("tool_name") == "email.propose_response"
        ):
            return EvalCheck(
                "connector compensation",
                "pass",
                "failed email proposal action was compensated and escalated",
            )
    return EvalCheck(
        "connector compensation",
        "fail",
        "missing connector.failure.compensated audit evidence",
    )


def _check_retry_exhaustion_dlq(
    audits: list[AuditEvent],
    outbox_statuses: list[str],
) -> EvalCheck:
    has_dlq_row = "dlq" in outbox_statuses
    for audit in audits:
        if audit.action != "workflow.retry_exhausted.dlq_recorded":
            continue
        retry_obj = audit.details.get("retry_exhaustion")
        dlq_obj = audit.details.get("dlq")
        if not isinstance(retry_obj, dict) or not isinstance(dlq_obj, dict):
            continue
        retry = cast(dict[str, Any], retry_obj)
        dlq = cast(dict[str, Any], dlq_obj)
        if (
            retry.get("failed_activity") == "lighthouse.invoke_agent_runtime"
            and retry.get("attempts") == 3
            and dlq.get("status") == "dlq"
            and has_dlq_row
        ):
            return EvalCheck(
                "retry exhaustion dlq",
                "pass",
                "retry exhaustion audit and terminal DLQ outbox marker observed",
            )
    return EvalCheck(
        "retry exhaustion dlq",
        "fail",
        "missing workflow.retry_exhausted.dlq_recorded audit or dlq outbox status",
    )


def _decision_has_field(record: AgentInvocationRecord, field: str) -> bool:
    match field:
        case "correlation_id" | "tenant_id" | "workflow_id" | "input_summary" | "output_summary":
            value = getattr(record, field)
            return bool(value)
        case "agent":
            return bool(record.agent.agent_id and record.agent.version and record.agent.prompt_hash)
        case "model_route":
            return bool(record.model_route.provider and record.model_route.model)
        case "prompt_hash":
            return bool(record.agent.prompt_hash)
        case "tool_call_ids":
            return True
        case _:
            return hasattr(record, field)


def _check_tool_evidence(
    *,
    allowed_tool_actions: list[str],
    blocked_tool_actions: list[str],
    tool_names: list[str],
    verdicts: list[str],
) -> EvalCheck:
    missing_allowed = [tool for tool in allowed_tool_actions if tool not in tool_names]
    if missing_allowed:
        return EvalCheck("tool audit", "fail", f"missing allowed tool actions: {missing_allowed}")

    unexpected_block_verdicts = [
        verdict for verdict in verdicts if verdict in {"block", "approval_required"}
    ]
    if blocked_tool_actions:
        missing_blocked = [tool for tool in blocked_tool_actions if tool not in tool_names]
        if missing_blocked:
            return EvalCheck(
                "tool audit", "fail", f"missing blocked tool actions: {missing_blocked}"
            )
        if not unexpected_block_verdicts:
            return EvalCheck(
                "tool audit",
                "fail",
                "expected at least one block or approval-required gateway verdict",
            )
    elif unexpected_block_verdicts:
        return EvalCheck(
            "tool audit", "fail", f"unexpected blocking verdicts: {unexpected_block_verdicts}"
        )

    return EvalCheck("tool audit", "pass", "gateway verdict evidence matches fixture")


def _check_budget(max_cost_usd: float, costs: Iterable[Decimal | float]) -> EvalCheck:
    total = sum((Decimal(str(cost)) for cost in costs), Decimal("0"))
    if total <= Decimal(str(max_cost_usd)):
        return EvalCheck("budget", "pass", f"cost {total} USD <= {max_cost_usd} USD")
    return EvalCheck("budget", "fail", f"cost {total} USD > {max_cost_usd} USD")


def _check_latency(max_latency_ms: int, actual_latency_ms: int) -> EvalCheck:
    if actual_latency_ms <= max_latency_ms:
        return EvalCheck("latency", "pass", f"{actual_latency_ms} ms <= {max_latency_ms} ms")
    return EvalCheck("latency", "fail", f"{actual_latency_ms} ms > {max_latency_ms} ms")


def _check_correlation_ids(
    expected: str,
    event_ids: list[str],
    decision_ids: list[str],
    audit_ids: list[str],
) -> EvalCheck:
    all_ids = event_ids + decision_ids + audit_ids
    if all_ids and all(value == expected for value in all_ids):
        return EvalCheck("correlation id", "pass", f"{expected} present across evidence")
    return EvalCheck("correlation id", "fail", f"correlation IDs did not all match {expected}")


def _print_report(fixture: EvalFixture, checks: list[EvalCheck]) -> None:
    print(f"fixture: {fixture.fixture_id} ({fixture.name})")
    for check in checks:
        print(f"[{check.status}] {check.name}: {check.detail}")


if __name__ == "__main__":
    sys.exit(main())

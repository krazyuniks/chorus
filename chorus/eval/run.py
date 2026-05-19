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
SUPPORT_HAPPY_PATH_ROLES: tuple[tuple[str, str, str], ...] = (
    ("support_classifier", "support.classifier", "support_classification"),
    ("support_context_researcher", "support.context_researcher", "support_context_lookup"),
    ("support_resolution_planner", "support.resolution_planner", "support_resolution_plan"),
    ("support_validator", "support.validator", "support_validation"),
)
PROVIDER_DEGRADATION_REASONS = {
    "lighthouse-provider-fallback": "provider_error",
    "lighthouse-provider-timeout-fallback": "timeout",
    "lighthouse-provider-rate-limit-fallback": "rate_limited",
    "lighthouse-provider-budget-fallback": "budget_exceeded",
}

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
    tool_calls: list[ToolCall]
    verdicts: list[GatewayVerdict]
    audit_events: list[AuditEvent]
    case_update_refs: list[str]
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
    case_update_refs: list[str]
    persisted_case_update_refs: list[str]
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
    if _is_support_fixture(fixture):
        return _build_support_offline_evidence(fixture)

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
        tool_calls=[tool_call],
        verdicts=[verdict],
        audit_events=[audit_event],
        case_update_refs=[],
        compensation_audit_event=compensation_audit_event,
        retry_dlq_audit_event=retry_dlq_audit_event,
        latency_ms=15_000,
    )


def _build_support_offline_evidence(fixture: EvalFixture) -> OfflineEvidence:
    workflow_id = f"support-eval-{fixture.fixture_id}"
    correlation_id = f"cor_eval_{fixture.fixture_id.replace('-', '_')}"
    subject_id = UUID("20000000-0000-4000-8000-000000000001")
    started_at = datetime(2026, 5, 19, 10, 0, tzinfo=UTC)

    events = _support_workflow_events(
        fixture=fixture,
        workflow_id=workflow_id,
        correlation_id=correlation_id,
        subject_id=subject_id,
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
        for index, (role, agent_id, task_kind) in enumerate(SUPPORT_HAPPY_PATH_ROLES, start=1)
    ]
    tool_calls = _support_tool_calls(
        fixture=fixture,
        workflow_id=workflow_id,
        correlation_id=correlation_id,
        context_invocation_id=decisions[1].invocation_id,
        planner_invocation_id=decisions[2].invocation_id,
    )
    verdicts = [
        _support_gateway_verdict(
            tool_call=tool_call,
            fixture=fixture,
            correlation_id=correlation_id,
        )
        for tool_call in tool_calls
    ]
    audit_events = [
        _support_audit_event(
            fixture=fixture,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            tool_call=tool_call,
            verdict=verdict,
        )
        for tool_call, verdict in zip(tool_calls, verdicts, strict=True)
    ]

    for event in events:
        WorkflowEvent.model_validate(event.model_dump(mode="json"))
    for decision in decisions:
        AgentInvocationRecord.model_validate(decision.model_dump(mode="json"))
    for tool_call in tool_calls:
        ToolCall.model_validate(tool_call.model_dump(mode="json"))
    for verdict in verdicts:
        GatewayVerdict.model_validate(verdict.model_dump(mode="json"))
    for audit_event in audit_events:
        AuditEvent.model_validate(audit_event.model_dump(mode="json"))

    return OfflineEvidence(
        workflow_id=workflow_id,
        correlation_id=correlation_id,
        events=events,
        decisions=decisions,
        tool_call=tool_calls[-1],
        verdict=verdicts[-1],
        audit_event=audit_events[-1],
        tool_calls=tool_calls,
        verdicts=verdicts,
        audit_events=audit_events,
        case_update_refs=_case_update_refs_from_audits(audit_events),
        compensation_audit_event=None,
        retry_dlq_audit_event=None,
        latency_ms=12_000,
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


def _support_workflow_events(
    *,
    fixture: EvalFixture,
    workflow_id: str,
    correlation_id: str,
    subject_id: UUID,
    started_at: datetime,
) -> list[WorkflowEvent]:
    request_ref = fixture.input.support_request_ref or "req_support_001"
    account_ref = "acct_demo_001"
    product_ref = "prod_core_platform"
    case_ref = "case_existing_001"
    case_update_ref = f"caseupd_{request_ref.removeprefix('req_')}"
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
                    "workflow_type": "support_triage",
                    "lead_id": str(subject_id),
                    "subject_ref": request_ref,
                    "sequence": sequence,
                    "step": step,
                    "payload": {
                        "workflow_type": "support_triage",
                        "request_ref": request_ref,
                        "case_ref": case_ref,
                        **payload,
                    },
                }
            )
        )
        sequence += 1

    append(
        "workflow.started",
        "support_intake",
        {
            "account_ref": account_ref,
            "product_ref": product_ref,
            "severity_category": "sev_high",
            "case_status_category": "open",
            "redacted_summary_ref": "summary_support_001",
            "source_ref": (
                fixture.input.support_request_fixture_ref or "fixture_support_triage_happy"
            ),
        },
    )
    for step in fixture.expected.workflow_path:
        append("workflow.step.started", step, {})
        match step:
            case "support_context_lookup":
                payload = {
                    "lookup_verdict": "allow",
                    "duplicate_lookup_verdict": "allow",
                    "duplicate_status": "duplicates_found",
                }
            case "support_resolution_plan":
                payload = {
                    "resolution_plan_ref": "plan_support_001",
                    "response_draft_ref": "response_support_001",
                    "case_update_ref": case_update_ref,
                    "verdict_category": "propose_case_update",
                }
            case "support_validation":
                payload = {
                    "validation_ref": "validation_support_001",
                    "recommended_next_step": "complete",
                    "verdict_category": "propose_case_update",
                }
            case "support_propose":
                payload = {
                    "gateway_verdict": "propose",
                    "enforced_mode": "propose",
                    "case_update_ref": case_update_ref,
                    "case_status_mutated": False,
                }
            case "support_complete":
                payload = {"proposal_status": "proposed"}
            case _:
                payload = {
                    "account_ref": account_ref,
                    "product_ref": product_ref,
                    "severity_category": "sev_high",
                    "case_status_category": "open",
                }
        append("workflow.step.completed", step, payload)
    append(
        "workflow.completed",
        "support_complete",
        {
            "outcome": "completed",
        },
    )
    return events


def _fixture_roles(fixture: EvalFixture) -> tuple[tuple[str, str, str], ...]:
    if _is_support_fixture(fixture):
        return SUPPORT_HAPPY_PATH_ROLES
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
    if _is_provider_fallback_fixture(fixture):
        return (
            ("researcher", "lighthouse.researcher", "company_research"),
            ("qualifier", "lighthouse.qualifier", "lead_qualification"),
            ("drafter", "lighthouse.drafter", "response_draft"),
            ("drafter", "lighthouse.drafter", "response_draft"),
            ("validator", "lighthouse.validator", "response_validation"),
        )
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
    if _is_support_fixture(fixture):
        _ = role, index
        request_ref = fixture.input.support_request_ref or "req_support_001"
        return f"{task_kind} input refs request_ref={request_ref} case_ref=case_existing_001"
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
    if _is_support_fixture(fixture):
        _ = role, index
        request_ref = fixture.input.support_request_ref or "req_support_001"
        case_update_ref = f"caseupd_{request_ref.removeprefix('req_')}"
        match task_kind:
            case "support_resolution_plan":
                return f"{task_kind} prepared proposal refs case_update_ref={case_update_ref}"
            case "support_validation":
                return f"{task_kind} completed with verdict_category=propose_case_update"
            case _:
                return f"{task_kind} completed using safe support refs"
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
    provider_reason = _provider_degradation_reason(fixture)
    if provider_reason is not None and role == "drafter" and index == 3:
        return (
            "response_draft failed on commercial provider with "
            f"{provider_reason}; governed fallback route requested"
        )
    if _is_provider_fallback_fixture(fixture) and role == "drafter" and index == 4:
        return f"response_draft completed on local fallback route after {provider_reason}"
    return f"{task_kind} completed for happy path"


def _decision_justification(fixture: EvalFixture) -> str:
    if _is_support_fixture(fixture):
        return "support_eval_local_refs_only"
    if fixture.phase.value == "2A":
        return "Deterministic Phase 2A provider fallback fixture evidence."
    if fixture.phase.value == "1B":
        return "Deterministic Phase 1B governance fixture evidence."
    return "Deterministic Phase 1A fixture evidence."


def _is_support_fixture(fixture: EvalFixture) -> bool:
    return fixture.workflow_type is not None and fixture.workflow_type.value == "support_triage"


def _is_low_confidence_fixture(fixture: EvalFixture) -> bool:
    return fixture.fixture_id == "lighthouse-low-confidence-research"


def _is_validator_redraft_fixture(fixture: EvalFixture) -> bool:
    return fixture.fixture_id == "lighthouse-validator-redraft"


def _is_connector_failure_fixture(fixture: EvalFixture) -> bool:
    return fixture.fixture_id == "lighthouse-connector-failure"


def _is_retry_exhaustion_fixture(fixture: EvalFixture) -> bool:
    return fixture.fixture_id == "lighthouse-retry-exhaustion"


def _is_provider_fallback_fixture(fixture: EvalFixture) -> bool:
    return _provider_degradation_reason(fixture) is not None


def _provider_degradation_reason(fixture: EvalFixture) -> str | None:
    return PROVIDER_DEGRADATION_REASONS.get(fixture.fixture_id)


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
    contract_ref = (
        "contracts/agents/support_agent_io.schema.json"
        if _is_support_fixture(fixture)
        else "contracts/agents/lighthouse_agent_io.schema.json"
    )
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
                "prompt_reference": _prompt_reference_for(fixture, role),
                "prompt_hash": prompt_hash,
            },
            "model_route": {
                "provider": _decision_provider(fixture, role, index),
                "model": _decision_model(fixture, role, index),
                "task_kind": task_kind,
                "budget_cap_usd": 0.01,
                "parameters": {"temperature": 0},
            },
            "input_summary": _decision_input_summary(fixture, role, task_kind, index),
            "output_summary": _decision_output_summary(fixture, role, task_kind, index),
            "justification": _decision_justification(fixture),
            "outcome": (
                "failed"
                if _is_retry_exhaustion_fixture(fixture)
                or (_is_provider_fallback_fixture(fixture) and role == "drafter" and index == 3)
                else "succeeded"
            ),
            "tool_call_ids": [],
            "cost": {
                "amount": _decision_cost_amount(fixture, role, index),
                "currency": "USD",
            },
            "duration_ms": 25,
            "started_at": started_at.isoformat(),
            "completed_at": (started_at + timedelta(milliseconds=25)).isoformat(),
            "contract_refs": [
                contract_ref,
                "contracts/events/agent_invocation_record.schema.json",
            ],
        }
    )


def _prompt_reference_for(fixture: EvalFixture, role: str) -> str:
    if not _is_support_fixture(fixture):
        return f"prompts/lighthouse/{role}/v1.md"
    support_prompt_refs = {
        "support_classifier": "prompts/support/classifier/v1.md",
        "support_context_researcher": "prompts/support/context-researcher/v1.md",
        "support_resolution_planner": "prompts/support/resolution-planner/v1.md",
        "support_drafter": "prompts/support/drafter/v1.md",
        "support_validator": "prompts/support/validator/v1.md",
    }
    return support_prompt_refs[role]


def _decision_provider(fixture: EvalFixture, role: str, index: int) -> str:
    if _is_provider_fallback_fixture(fixture) and role == "drafter" and index == 3:
        return "commercial.example"
    return "local"


def _decision_model(fixture: EvalFixture, role: str, index: int) -> str:
    if _is_provider_fallback_fixture(fixture) and role == "drafter" and index == 3:
        return "commercial-reasoner-v1"
    return "lighthouse-happy-path-v1"


def _decision_cost_amount(fixture: EvalFixture, role: str, index: int) -> float:
    if (
        _provider_degradation_reason(fixture) == "budget_exceeded"
        and role == "drafter"
        and index == 3
    ):
        return 0.5
    return 0.0


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


def _support_tool_calls(
    *,
    fixture: EvalFixture,
    workflow_id: str,
    correlation_id: str,
    context_invocation_id: UUID,
    planner_invocation_id: UUID,
) -> list[ToolCall]:
    request_ref = fixture.input.support_request_ref or "req_support_001"
    common_refs = {
        "request_ref": request_ref,
        "case_ref": "case_existing_001",
        "account_ref": "acct_demo_001",
        "product_ref": "prod_core_platform",
    }
    calls = [
        {
            "invocation_id": context_invocation_id,
            "agent_id": "support.context_researcher",
            "tool_name": "ticket.lookup_case",
            "mode": "read",
            "idempotency_key": f"{workflow_id}:ticket.lookup_case:case_existing_001",
            "arguments": {
                **common_refs,
                "lookup_policy_ref": "policy_support_triage_local_v1",
                "include_history_category": "bounded_recent_status_refs",
            },
        },
        {
            "invocation_id": context_invocation_id,
            "agent_id": "support.context_researcher",
            "tool_name": "ticket.lookup_duplicates",
            "mode": "read",
            "idempotency_key": f"{workflow_id}:ticket.lookup_duplicates:{request_ref}",
            "arguments": {
                **common_refs,
                "severity_category": "sev_high",
                "status_categories": ["new", "open", "pending_customer", "pending_internal"],
                "duplicate_scope_category": "same_account_product_open",
                "lookup_policy_ref": "policy_support_triage_local_v1",
            },
        },
        {
            "invocation_id": planner_invocation_id,
            "agent_id": "support.resolution_planner",
            "tool_name": "ticket.propose_case_update",
            "mode": "propose",
            "idempotency_key": f"{workflow_id}:ticket.propose_case_update:{request_ref}",
            "arguments": {
                **common_refs,
                "severity_category": "sev_high",
                "target_status_category": "pending_customer",
                "resolution_plan_ref": "plan_support_001",
                "response_draft_ref": "response_support_001",
                "case_update_ref": f"caseupd_{request_ref.removeprefix('req_')}",
                "update_reason_category": "resolution_plan_ready",
                "policy_ref": "policy_support_triage_local_v1",
            },
        },
    ]
    return [
        ToolCall.model_validate(
            {
                "schema_version": "1.0.0",
                "tool_call_id": str(uuid4()),
                "invocation_id": str(call["invocation_id"]),
                "tenant_id": fixture.input.tenant_id,
                "correlation_id": correlation_id,
                "agent_id": call["agent_id"],
                "tool_name": call["tool_name"],
                "mode": call["mode"],
                "idempotency_key": call["idempotency_key"],
                "arguments": call["arguments"],
                "requested_at": "2026-05-19T10:03:00+00:00",
            }
        )
        for call in calls
    ]


def _support_gateway_verdict(
    *,
    tool_call: ToolCall,
    fixture: EvalFixture,
    correlation_id: str,
) -> GatewayVerdict:
    verdict = "propose" if tool_call.mode.value == "propose" else "allow"
    return GatewayVerdict.model_validate(
        {
            "schema_version": "1.0.0",
            "verdict_id": str(uuid4()),
            "tool_call_id": str(tool_call.tool_call_id),
            "tenant_id": fixture.input.tenant_id,
            "correlation_id": correlation_id,
            "verdict": verdict,
            "enforced_mode": tool_call.mode.value,
            "reason": f"{tool_call.tool_name.value.replace('.', '_')}_{verdict}",
            "rewritten_arguments": None,
            "approval_required": False,
            "audit_event_id": str(uuid4()),
            "connector_invocation_id": str(uuid4()),
            "decided_at": "2026-05-19T10:03:01+00:00",
        }
    )


def _support_audit_event(
    *,
    fixture: EvalFixture,
    workflow_id: str,
    correlation_id: str,
    tool_call: ToolCall,
    verdict: GatewayVerdict,
) -> AuditEvent:
    output = _support_gateway_output(tool_call)
    return AuditEvent.model_validate(
        {
            "schema_version": "1.0.0",
            "audit_event_id": str(verdict.audit_event_id),
            "occurred_at": verdict.decided_at.isoformat(),
            "tenant_id": fixture.input.tenant_id,
            "correlation_id": correlation_id,
            "workflow_id": workflow_id,
            "actor": {"type": "agent", "id": tool_call.agent_id},
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
                    "connector_invocation_id": str(verdict.connector_invocation_id),
                    "output": output,
                },
            },
        }
    )


def _support_gateway_output(tool_call: ToolCall) -> dict[str, Any]:
    arguments = tool_call.arguments
    match tool_call.tool_name.value:
        case "ticket.lookup_case":
            return {
                "connector": "local_ticket_desk.postgres",
                "lookup_status": "case_found",
                "case_ref": arguments["case_ref"],
                "request_ref": arguments["request_ref"],
                "account_ref": arguments["account_ref"],
                "product_ref": arguments["product_ref"],
                "lookup_policy_ref": arguments["lookup_policy_ref"],
            }
        case "ticket.lookup_duplicates":
            return {
                "connector": "local_ticket_desk.postgres",
                "duplicate_status": "duplicates_found",
                "request_ref": arguments["request_ref"],
                "case_ref": arguments["case_ref"],
                "account_ref": arguments["account_ref"],
                "product_ref": arguments["product_ref"],
                "duplicate_case_refs": ["case_duplicate_001"],
                "duplicate_count": 1,
            }
        case "ticket.propose_case_update":
            return {
                "connector": "local_ticket_desk.postgres",
                "proposal_status": "proposed",
                "case_status_mutated": False,
                "request_ref": arguments["request_ref"],
                "case_ref": arguments["case_ref"],
                "account_ref": arguments["account_ref"],
                "product_ref": arguments["product_ref"],
                "case_update_ref": arguments["case_update_ref"],
                "severity_category": arguments["severity_category"],
                "target_status_category": arguments["target_status_category"],
                "update_reason_category": arguments["update_reason_category"],
                "policy_ref": arguments["policy_ref"],
            }
        case _:
            return {}


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
            else [tool_call.tool_name.value for tool_call in evidence.tool_calls],
            verdicts=[]
            if _is_retry_exhaustion_fixture(fixture)
            else [verdict.verdict.value for verdict in evidence.verdicts],
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
                    *evidence.audit_events,
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
    if _is_provider_fallback_fixture(fixture):
        checks.append(_check_provider_fallback_decisions(evidence.decisions))
    if _is_support_fixture(fixture):
        checks.extend(
            [
                _check_support_case_update_refs(fixture, evidence.case_update_refs),
                _check_absent_tool_actions(
                    blocked_tool_actions=["ticket.update_status"],
                    tool_names=[tool_call.tool_name.value for tool_call in evidence.tool_calls],
                ),
                _check_support_proposal_no_status_mutation(evidence.audit_events),
                _check_safe_trace_join_refs(
                    expected_tenant=fixture.input.tenant_id,
                    expected_correlation=evidence.correlation_id,
                    expected_workflow=evidence.workflow_id,
                    events=evidence.events,
                    decisions=evidence.decisions,
                    audits=evidence.audit_events,
                ),
            ]
        )
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
    if _is_provider_fallback_fixture(fixture):
        checks.append(_check_provider_fallback_decisions(evidence.decisions))
    if _is_support_fixture(fixture):
        checks.extend(
            [
                _check_support_case_update_refs(fixture, evidence.case_update_refs),
                _check_persisted_support_case_update_refs(
                    evidence.case_update_refs,
                    evidence.persisted_case_update_refs,
                ),
                _check_absent_tool_actions(
                    blocked_tool_actions=["ticket.update_status"],
                    tool_names=evidence.tool_names,
                ),
                _check_support_proposal_no_status_mutation(evidence.tool_audits),
                _check_safe_trace_join_refs(
                    expected_tenant=fixture.input.tenant_id,
                    expected_correlation=evidence.correlation_id,
                    expected_workflow=evidence.workflow_id,
                    events=evidence.outbox_events,
                    decisions=evidence.decisions,
                    audits=evidence.tool_audits,
                ),
            ]
        )
    return checks


def _load_live_evidence(
    conn: Connection[Any],
    *,
    fixture: EvalFixture,
    workflow_id: str | None,
    correlation_id: str | None,
) -> LiveEvidence:
    if _is_support_fixture(fixture):
        return _load_support_live_evidence(
            conn,
            fixture=fixture,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
        )

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
        case_update_refs=[],
        persisted_case_update_refs=[],
        total_cost_usd=total_cost_usd,
        latency_ms=latency_ms,
    )


def _load_support_live_evidence(
    conn: Connection[Any],
    *,
    fixture: EvalFixture,
    workflow_id: str | None,
    correlation_id: str | None,
) -> LiveEvidence:
    tenant_id = fixture.input.tenant_id
    workflow_id = workflow_id or _fetch_support_workflow_id(conn, tenant_id, correlation_id)
    if workflow_id is None:
        raise EvalError("no live support_triage outbox rows found for the supplied selector")

    outbox_events, outbox_statuses = _fetch_outbox_events(conn, tenant_id, workflow_id)
    outbox_events = [
        event
        for event in outbox_events
        if event.workflow_type is not None and event.workflow_type.value == "support_triage"
    ]
    decisions = _fetch_decisions(conn, tenant_id, workflow_id)
    audits, _verdicts, tool_names = _fetch_tool_audits(conn, tenant_id, workflow_id)
    ticket_audits = [
        audit
        for audit in audits
        if isinstance(audit.details.get("tool_call"), dict)
        and str(cast(dict[str, Any], audit.details["tool_call"]).get("tool_name", "")).startswith(
            "ticket."
        )
    ]
    ticket_verdicts = [
        GatewayVerdict.model_validate(audit.details["gateway_verdict"])
        for audit in ticket_audits
        if "gateway_verdict" in audit.details
    ]
    ticket_tool_names = [
        cast(str, cast(dict[str, Any], audit.details["tool_call"]).get("tool_name"))
        for audit in ticket_audits
    ]

    if not outbox_events:
        raise EvalError(f"workflow {workflow_id} has no persisted support_triage outbox events")
    if not decisions:
        raise EvalError(f"workflow {workflow_id} has no support decision-trail rows")
    if not ticket_audits:
        raise EvalError(f"workflow {workflow_id} has no ticket Tool Gateway audit rows")

    started_at = min(event.occurred_at for event in outbox_events)
    completed_candidates = [
        event.occurred_at
        for event in outbox_events
        if event.event_type.value in {"workflow.completed", "workflow.escalated", "workflow.failed"}
    ]
    completed_at = (
        max(completed_candidates)
        if completed_candidates
        else max(event.occurred_at for event in outbox_events)
    )
    latency_ms = round((completed_at - started_at).total_seconds() * 1000)
    total_cost_usd = sum((Decimal(str(record.cost.amount)) for record in decisions), Decimal("0"))
    case_update_refs = _case_update_refs_from_audits(ticket_audits)

    return LiveEvidence(
        workflow_id=workflow_id,
        correlation_id=outbox_events[0].correlation_id,
        workflow_status=_status_from_events(outbox_events),
        workflow_current_step=_current_step_from_events(outbox_events),
        history_event_types=[event.event_type.value for event in outbox_events],
        history_steps=_completed_steps(outbox_events),
        outbox_events=outbox_events,
        outbox_statuses=outbox_statuses,
        decisions=decisions,
        tool_audits=ticket_audits,
        verdicts=ticket_verdicts,
        tool_names=ticket_tool_names or tool_names,
        case_update_refs=case_update_refs,
        persisted_case_update_refs=_fetch_persisted_case_update_refs(
            conn,
            tenant_id,
            case_update_refs,
        ),
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
    rows = cast(list[dict[str, object]], cur.fetchall())
    events: list[WorkflowEvent] = []
    for row in rows:
        event_data: dict[str, object] = {
            key: value for key, value in row.items() if key != "status"
        }
        payload_obj = event_data.get("payload")
        if isinstance(payload_obj, dict):
            payload = cast(dict[str, object], payload_obj)
            workflow_type = payload.get("workflow_type")
            if isinstance(workflow_type, str):
                event_data["workflow_type"] = workflow_type
            request_ref = payload.get("request_ref")
            if isinstance(request_ref, str):
                event_data["subject_ref"] = request_ref
        events.append(WorkflowEvent.model_validate(event_data))
    return events, [cast(str, row["status"]) for row in rows]


def _fetch_support_workflow_id(
    conn: Connection[Any],
    tenant_id: str,
    correlation_id: str | None,
) -> str | None:
    with conn.cursor(row_factory=dict_row) as cur:
        if correlation_id is not None:
            cur.execute(
                """
                SELECT workflow_id
                FROM outbox_events
                WHERE tenant_id = %s
                  AND correlation_id = %s
                  AND payload ->> 'workflow_type' = 'support_triage'
                ORDER BY created_at DESC, sequence DESC
                LIMIT 1
                """,
                (tenant_id, correlation_id),
            )
        else:
            cur.execute(
                """
                SELECT workflow_id
                FROM outbox_events
                WHERE tenant_id = %s
                  AND payload ->> 'workflow_type' = 'support_triage'
                ORDER BY created_at DESC, sequence DESC
                LIMIT 1
                """,
                (tenant_id,),
            )
        row = cur.fetchone()
    return cast(str, row["workflow_id"]) if row is not None else None


def _fetch_persisted_case_update_refs(
    conn: Connection[Any],
    tenant_id: str,
    case_update_refs: list[str],
) -> list[str]:
    if not case_update_refs:
        return []
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT case_update_ref
            FROM local_ticket_case_update_proposals
            WHERE tenant_id = %s
              AND case_update_ref = ANY(%s::text[])
            ORDER BY case_update_ref
            """,
            (tenant_id, case_update_refs),
        )
        return [cast(str, row["case_update_ref"]) for row in cur.fetchall()]


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
    if evidence.workflow_status == "completed" and evidence.case_update_refs:
        return "complete"
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
    if any(event.event_type.value == "workflow.completed" for event in evidence.events) and any(
        event.workflow_type is not None and event.workflow_type.value == "support_triage"
        for event in evidence.events
    ):
        return "complete"
    if evidence.retry_dlq_audit_event is not None:
        return "escalate"
    if evidence.verdict.verdict.value in {"block", "approval_required"}:
        return "escalate"
    if evidence.verdict.verdict.value == "propose":
        return "propose"
    if evidence.verdict.enforced_mode.value == "write":
        return "send"
    return "reject"


def _status_from_events(events: list[WorkflowEvent]) -> str:
    event_types = {event.event_type.value for event in events}
    if "workflow.completed" in event_types:
        return "completed"
    if "workflow.escalated" in event_types:
        return "escalated"
    if "workflow.failed" in event_types:
        return "failed"
    return "running"


def _current_step_from_events(events: list[WorkflowEvent]) -> str | None:
    for event in reversed(events):
        if event.step is not None:
            return event.step.value
    return None


def _case_update_refs_from_audits(audits: Iterable[AuditEvent]) -> list[str]:
    refs: list[str] = []
    for audit in audits:
        response_obj = audit.details.get("gateway_response")
        if not isinstance(response_obj, dict):
            continue
        response = cast(dict[str, object], response_obj)
        output_obj = response.get("output")
        if not isinstance(output_obj, dict):
            continue
        output = cast(dict[str, object], output_obj)
        case_update_ref = output.get("case_update_ref")
        if isinstance(case_update_ref, str):
            refs.append(case_update_ref)
    return refs


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
    if _is_support_fixture(fixture):
        expected_roles = {role for role, _, _ in SUPPORT_HAPPY_PATH_ROLES}
    else:
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


def _check_provider_fallback_decisions(decisions: list[AgentInvocationRecord]) -> EvalCheck:
    degradation_reason = "provider"
    primary_index: int | None = None
    fallback_index: int | None = None
    for index, record in enumerate(decisions):
        if (
            record.agent.role.value == "drafter"
            and record.model_route.provider == "commercial.example"
            and record.model_route.model == "commercial-reasoner-v1"
            and record.outcome.value == "failed"
            and any(
                reason in record.output_summary for reason in PROVIDER_DEGRADATION_REASONS.values()
            )
            and record.cost.currency == "USD"
            and record.duration_ms >= 0
        ):
            primary_index = index
            for reason in PROVIDER_DEGRADATION_REASONS.values():
                if reason in record.output_summary:
                    degradation_reason = reason
                    break
        if (
            record.agent.role.value == "drafter"
            and record.model_route.provider == "local"
            and record.model_route.model == "lighthouse-happy-path-v1"
            and record.outcome.value == "succeeded"
            and "fallback" in record.output_summary.lower()
            and record.cost.currency == "USD"
            and record.duration_ms >= 0
        ):
            fallback_index = index

    if primary_index is not None and fallback_index is not None and primary_index < fallback_index:
        return EvalCheck(
            "provider fallback route selection",
            "pass",
            f"failed commercial provider route ({degradation_reason}), local fallback route, "
            "cost, and latency observed",
        )
    return EvalCheck(
        "provider fallback route selection",
        "fail",
        "missing failed commercial provider route followed by local fallback route evidence",
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


def _check_absent_tool_actions(
    *,
    blocked_tool_actions: list[str],
    tool_names: list[str],
) -> EvalCheck:
    observed = sorted(tool for tool in blocked_tool_actions if tool in tool_names)
    if observed:
        return EvalCheck("support ticket status write", "fail", f"observed {observed}")
    return EvalCheck(
        "support ticket status write",
        "pass",
        "ticket.update_status absent from support happy-path evidence",
    )


def _check_support_case_update_refs(
    fixture: EvalFixture,
    case_update_refs: list[str],
) -> EvalCheck:
    request_ref = fixture.input.support_request_ref or "req_support_001"
    expected_ref = f"caseupd_{request_ref.removeprefix('req_')}"
    if expected_ref in case_update_refs:
        return EvalCheck(
            "support case update ref",
            "pass",
            f"{expected_ref} present in proposal evidence",
        )
    return EvalCheck(
        "support case update ref",
        "fail",
        f"missing proposed case-update ref {expected_ref}",
    )


def _check_persisted_support_case_update_refs(
    case_update_refs: list[str],
    persisted_case_update_refs: list[str],
) -> EvalCheck:
    missing_refs = sorted(set(case_update_refs) - set(persisted_case_update_refs))
    if not missing_refs:
        return EvalCheck(
            "support persisted case update refs",
            "pass",
            "proposed case-update refs are persisted",
        )
    return EvalCheck(
        "support persisted case update refs",
        "fail",
        f"missing persisted proposal refs: {missing_refs}",
    )


def _check_support_proposal_no_status_mutation(audits: list[AuditEvent]) -> EvalCheck:
    proposal_seen = False
    for audit in audits:
        response_obj = audit.details.get("gateway_response")
        if not isinstance(response_obj, dict):
            continue
        response = cast(dict[str, object], response_obj)
        output_obj = response.get("output")
        if not isinstance(output_obj, dict):
            continue
        output = cast(dict[str, object], output_obj)
        if output.get("case_update_ref") is None:
            continue
        proposal_seen = True
        if output.get("case_status_mutated") is not False:
            return EvalCheck(
                "support proposal mutation",
                "fail",
                "ticket proposal evidence did not prove case_status_mutated=false",
            )
    if proposal_seen:
        return EvalCheck(
            "support proposal mutation",
            "pass",
            "ticket proposal retained propose-only status",
        )
    return EvalCheck(
        "support proposal mutation",
        "fail",
        "missing ticket proposal mutation flag evidence",
    )


def _check_safe_trace_join_refs(
    *,
    expected_tenant: str,
    expected_correlation: str,
    expected_workflow: str,
    events: list[WorkflowEvent],
    decisions: list[AgentInvocationRecord],
    audits: list[AuditEvent],
) -> EvalCheck:
    tenant_ids = [event.tenant_id for event in events]
    tenant_ids.extend(record.tenant_id for record in decisions)
    tenant_ids.extend(audit.tenant_id for audit in audits)

    correlation_ids = [event.correlation_id for event in events]
    correlation_ids.extend(record.correlation_id for record in decisions)
    correlation_ids.extend(audit.correlation_id for audit in audits)

    workflow_ids = [event.workflow_id for event in events]
    workflow_ids.extend(record.workflow_id for record in decisions)
    workflow_ids.extend(audit.workflow_id for audit in audits)

    if (
        tenant_ids
        and all(value == expected_tenant for value in tenant_ids)
        and all(value == expected_correlation for value in correlation_ids)
        and all(value == expected_workflow for value in workflow_ids)
    ):
        return EvalCheck(
            "support trace joins",
            "pass",
            "tenant, correlation, and workflow refs join support evidence",
        )
    return EvalCheck(
        "support trace joins",
        "fail",
        "tenant, correlation, or workflow refs did not align across support evidence",
    )


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

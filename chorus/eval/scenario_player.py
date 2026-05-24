"""Drive the recorded-replay route through a UC1 scenario and collect the
captured-run artefacts the invariant suite asserts over.

This is the offline substrate the R3 G eval uses: each fixture's `scenario`
field maps to a deterministic sequence of LLM provider invocations through
the recorded-replay adapter (ADR 0018), interleaved with a synthesised
projection-event stream and connector-call audit. The result mirrors the
shape an actual UC1 run on the live stack would persist - decision-trail
entries, transcripts, tool-action audit rows, projection events - so the
invariants can run identically against either source.

The path-enumeration eval era is retired; this player exists so the
invariants have something concrete to assert about offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from chorus.contracts.generated.eval.eval_fixture import EvalFixture, Scenario
from chorus.llm_provider import (
    InvocationArgs,
    InvocationMessage,
    LLMProviderInvocationError,
    RouteCatalogue,
    default_route_catalogue,
)
from chorus.llm_provider.adapter_replay import ADAPTER_VERSION as REPLAY_ADAPTER_VERSION

UC1_AGENT_CONTRACT_REF = "contracts/llm_provider/uc1_agent_io.schema.json"
PIPELINE_VERSION = "agent-runtime-pipeline-v1"
RECORDED_REPLAY_ROUTE = "recorded-replay"
RECORDED_REPLAY_PROVIDER = "local"
RECORDED_REPLAY_MODEL = "uc1-happy-path-v1"
RECORDED_REPLAY_BUDGET_USD = Decimal("0.05")

# UC1 pipeline stage ordering. Each stage corresponds to one LLM provider
# invocation and one workflow.step.* event pair in the projection stream.
PIPELINE_STAGES: tuple[tuple[str, str], ...] = (
    ("classifier", "enquiry_classification"),
    ("qualifier", "enquiry_qualification"),
    ("request_drafter", "missing_data_request_draft"),
    ("validator", "missing_data_request_validation"),
)


@dataclass(frozen=True)
class DecisionTrailRecord:
    invocation_id: UUID
    correlation_id: str
    workflow_id: str
    tenant_id: str
    agent_id: str
    agent_role: str
    agent_version: str
    prompt_reference: str
    prompt_hash: str
    provider: str
    model: str
    task_kind: str
    input_summary: str
    output_summary: str
    justification: str
    outcome: str
    cost_amount_usd: Decimal
    duration_ms: int
    started_at: datetime
    completed_at: datetime
    contract_refs: list[str]
    structured_data: dict[str, Any]


@dataclass(frozen=True)
class TranscriptRecord:
    transcript_id: UUID
    invocation_id: UUID
    correlation_id: str
    workflow_id: str
    tenant_id: str
    route_id: str
    provider_id: str
    model_id: str
    adapter_version: str
    parameters: dict[str, Any]
    request_messages: list[dict[str, Any]]
    response_messages: list[dict[str, Any]]
    structured_data: dict[str, Any]
    started_at: datetime
    completed_at: datetime


@dataclass(frozen=True)
class ToolActionRecord:
    audit_event_id: UUID
    invocation_id: UUID | None
    correlation_id: str
    workflow_id: str
    tenant_id: str
    actor_type: str
    actor_id: str
    category: str
    action: str
    tool_name: str | None
    requested_mode: str | None
    enforced_mode: str | None
    verdict: str
    reason: str | None
    approval_required: bool
    approval_granted: bool | None
    occurred_at: datetime


@dataclass(frozen=True)
class ProjectionEvent:
    event_id: UUID
    correlation_id: str
    workflow_id: str
    tenant_id: str
    workflow_type: str
    subject_id: UUID
    subject_ref: str
    sequence: int
    event_type: str
    step: str | None
    occurred_at: datetime
    payload: dict[str, Any]


@dataclass
class CapturedRun:
    """Offline-synthesised analogue of a real UC1 run's persisted artefacts."""

    fixture: EvalFixture
    decisions: list[DecisionTrailRecord] = field(default_factory=lambda: [])
    transcripts: list[TranscriptRecord] = field(default_factory=lambda: [])
    tool_actions: list[ToolActionRecord] = field(default_factory=lambda: [])
    projection_events: list[ProjectionEvent] = field(default_factory=lambda: [])
    terminal_outcome: str = ""


def play_scenario(
    fixture: EvalFixture,
    *,
    route_catalogue: RouteCatalogue | None = None,
) -> CapturedRun:
    """Drive a fixture's scenario through the recorded-replay adapter."""

    catalogue = route_catalogue or default_route_catalogue()
    correlation_id = f"cor_eval_{fixture.fixture_id.replace('-', '_')}"
    workflow_id = f"uc1-eval-{fixture.fixture_id}"
    tenant_id = fixture.input.tenant_id
    subject_id = uuid4()
    subject_ref = f"enq_eval_{fixture.fixture_id.replace('-', '_')[:24]}"
    started_at = datetime(2026, 4, 29, 10, 0, tzinfo=UTC)

    run = CapturedRun(fixture=fixture)
    sequence_cursor = _SequenceCursor()
    clock = _Clock(started_at)

    _emit(
        run,
        clock,
        sequence_cursor,
        correlation_id=correlation_id,
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        subject_id=subject_id,
        subject_ref=subject_ref,
        event_type="enquiry.received",
        step="intake",
        payload={"subject_summary": "intake payload"},
    )
    _emit(
        run,
        clock,
        sequence_cursor,
        correlation_id=correlation_id,
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        subject_id=subject_id,
        subject_ref=subject_ref,
        event_type="workflow.started",
        step="intake",
        payload={"subject_summary": "intake payload"},
    )

    scenario = fixture.scenario
    if scenario == Scenario.RETRY_EXHAUSTION:
        _play_retry_exhaustion(
            run,
            catalogue,
            clock,
            sequence_cursor,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            subject_id=subject_id,
            subject_ref=subject_ref,
        )
        return run

    enquiry_input = _enquiry_input_for(scenario)

    for agent_role, task_kind in PIPELINE_STAGES:
        if scenario == Scenario.VALIDATOR_REDRAFT and task_kind in {
            "missing_data_request_draft",
            "missing_data_request_validation",
        }:
            attempt_one = {**enquiry_input, "redraft_attempt": 1}
            _invoke_stage(
                run,
                catalogue,
                clock,
                sequence_cursor,
                correlation_id=correlation_id,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                subject_id=subject_id,
                subject_ref=subject_ref,
                agent_role=agent_role,
                task_kind=task_kind,
                enquiry_input=attempt_one,
            )
            attempt_two = {**enquiry_input, "redraft_attempt": 2}
            _invoke_stage(
                run,
                catalogue,
                clock,
                sequence_cursor,
                correlation_id=correlation_id,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                subject_id=subject_id,
                subject_ref=subject_ref,
                agent_role=agent_role,
                task_kind=task_kind,
                enquiry_input=attempt_two,
            )
            continue

        if scenario == Scenario.DEEPER_CONTEXT and task_kind == "enquiry_classification":
            attempt_one = {**enquiry_input, "classification_attempt": 1}
            _invoke_stage(
                run,
                catalogue,
                clock,
                sequence_cursor,
                correlation_id=correlation_id,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                subject_id=subject_id,
                subject_ref=subject_ref,
                agent_role=agent_role,
                task_kind=task_kind,
                enquiry_input=attempt_one,
            )
            attempt_two = {**enquiry_input, "classification_attempt": 2}
            _invoke_stage(
                run,
                catalogue,
                clock,
                sequence_cursor,
                correlation_id=correlation_id,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                subject_id=subject_id,
                subject_ref=subject_ref,
                agent_role=agent_role,
                task_kind=task_kind,
                enquiry_input=attempt_two,
            )
            continue

        _invoke_stage(
            run,
            catalogue,
            clock,
            sequence_cursor,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            subject_id=subject_id,
            subject_ref=subject_ref,
            agent_role=agent_role,
            task_kind=task_kind,
            enquiry_input=enquiry_input,
        )

    _emit_connector_send(
        run,
        clock,
        sequence_cursor,
        correlation_id=correlation_id,
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        subject_id=subject_id,
        subject_ref=subject_ref,
    )
    _emit(
        run,
        clock,
        sequence_cursor,
        correlation_id=correlation_id,
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        subject_id=subject_id,
        subject_ref=subject_ref,
        event_type="workflow.completed",
        step="complete",
        payload={"subject_summary": "complete", "outcome": "completed"},
    )
    run.terminal_outcome = "completed"
    return run


def _enquiry_input_for(scenario: Scenario) -> dict[str, Any]:
    if scenario == Scenario.DEEPER_CONTEXT:
        return {
            "enquiry_subject": "Motor cover enquiry (deeper-context fixture)",
            "enquiry_body_text": (
                "Hi, I would like a quote for my car. Deeper-context fixture marker."
            ),
        }
    if scenario == Scenario.VALIDATOR_REDRAFT:
        return {
            "enquiry_subject": "Motor cover enquiry (validator-redraft fixture)",
            "enquiry_body_text": (
                "Hi, I would like a quote for my car. Validator-redraft fixture marker."
            ),
            "validator_reason": {
                "code": "scope_mismatch",
                "missing_elements": ["cover_scope", "claims_history"],
            },
        }
    return {
        "enquiry_subject": "Motor cover enquiry",
        "enquiry_body_text": (
            "Hi, please could you quote me for third-party fire and theft on a 2018 hatchback."
        ),
    }


def _invoke_stage(
    run: CapturedRun,
    catalogue: RouteCatalogue,
    clock: _Clock,
    sequence_cursor: _SequenceCursor,
    *,
    correlation_id: str,
    workflow_id: str,
    tenant_id: str,
    subject_id: UUID,
    subject_ref: str,
    agent_role: str,
    task_kind: str,
    enquiry_input: dict[str, Any],
) -> None:
    started = clock.tick(milliseconds=20)
    args = InvocationArgs(
        route_id=RECORDED_REPLAY_ROUTE,
        messages=(InvocationMessage(role="user", content=f"{task_kind} input"),),
        metadata={
            "task_kind": task_kind,
            "input": enquiry_input,
            "agent_role": agent_role,
            "tenant_id": tenant_id,
        },
    )
    result = catalogue.invoke(args)
    completed = clock.tick(milliseconds=50)

    _emit(
        run,
        clock,
        sequence_cursor,
        correlation_id=correlation_id,
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        subject_id=subject_id,
        subject_ref=subject_ref,
        event_type="workflow.step.started",
        step=task_kind,
        payload={"subject_summary": task_kind},
    )
    _emit(
        run,
        clock,
        sequence_cursor,
        correlation_id=correlation_id,
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        subject_id=subject_id,
        subject_ref=subject_ref,
        event_type="workflow.step.completed",
        step=task_kind,
        payload={"subject_summary": task_kind},
    )

    invocation_id = uuid4()
    transcript_id = uuid4()
    structured = dict(result.structured_data)
    route_entry = catalogue.get(RECORDED_REPLAY_ROUTE)

    run.decisions.append(
        DecisionTrailRecord(
            invocation_id=invocation_id,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            agent_id=f"uc1.{agent_role}",
            agent_role=agent_role,
            agent_version="v1",
            prompt_reference=f"prompts/uc1/{agent_role}/v1.md",
            prompt_hash="sha256:" + "0" * 64,
            provider=route_entry.provider_id,
            model=route_entry.model_id,
            task_kind=task_kind,
            input_summary=_summarise(enquiry_input),
            output_summary=result.summary,
            justification=result.rationale,
            outcome="succeeded",
            cost_amount_usd=result.cost_amount_usd,
            duration_ms=int((completed - started).total_seconds() * 1000),
            started_at=started,
            completed_at=completed,
            contract_refs=[
                UC1_AGENT_CONTRACT_REF,
                "contracts/audit/agent_invocation_record.schema.json",
            ],
            structured_data=structured,
        )
    )
    run.transcripts.append(
        TranscriptRecord(
            transcript_id=transcript_id,
            invocation_id=invocation_id,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            route_id=route_entry.route_id,
            provider_id=route_entry.provider_id,
            model_id=route_entry.model_id,
            adapter_version=route_entry.adapter_version,
            parameters=dict(route_entry.parameters),
            request_messages=[
                {"role": message.role, "content": message.content} for message in args.messages
            ],
            response_messages=[
                {"role": "assistant", "content": result.summary},
            ],
            structured_data=structured,
            started_at=started,
            completed_at=completed,
        )
    )


def _emit_connector_send(
    run: CapturedRun,
    clock: _Clock,
    sequence_cursor: _SequenceCursor,
    *,
    correlation_id: str,
    workflow_id: str,
    tenant_id: str,
    subject_id: UUID,
    subject_ref: str,
) -> None:
    _emit(
        run,
        clock,
        sequence_cursor,
        correlation_id=correlation_id,
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        subject_id=subject_id,
        subject_ref=subject_ref,
        event_type="workflow.step.started",
        step="missing_data_request_send",
        payload={"subject_summary": "missing_data_request_send"},
    )
    propose_id = uuid4()
    propose_at = clock.tick(milliseconds=10)
    run.tool_actions.append(
        ToolActionRecord(
            audit_event_id=propose_id,
            invocation_id=run.decisions[-1].invocation_id if run.decisions else None,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            actor_type="agent",
            actor_id="uc1.validator",
            category="tool_gateway",
            action="tool_call.decided",
            tool_name="outbound_comms.message",
            requested_mode="propose",
            enforced_mode="propose",
            verdict="propose",
            reason="adviser approval required before write",
            approval_required=True,
            approval_granted=None,
            occurred_at=propose_at,
        )
    )
    send_id = uuid4()
    send_at = clock.tick(milliseconds=50)
    run.tool_actions.append(
        ToolActionRecord(
            audit_event_id=send_id,
            invocation_id=None,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            actor_type="human",
            actor_id="adviser_demo",
            category="tool_gateway",
            action="approval.apply",
            tool_name="outbound_comms.message",
            requested_mode="write",
            enforced_mode="write",
            verdict="allow",
            reason="adviser approved the proposed missing-data request",
            approval_required=True,
            approval_granted=True,
            occurred_at=send_at,
        )
    )
    _emit(
        run,
        clock,
        sequence_cursor,
        correlation_id=correlation_id,
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        subject_id=subject_id,
        subject_ref=subject_ref,
        event_type="workflow.step.completed",
        step="missing_data_request_send",
        payload={"subject_summary": "missing_data_request_send"},
    )


def _play_retry_exhaustion(
    run: CapturedRun,
    catalogue: RouteCatalogue,
    clock: _Clock,
    sequence_cursor: _SequenceCursor,
    *,
    correlation_id: str,
    workflow_id: str,
    tenant_id: str,
    subject_id: UUID,
    subject_ref: str,
) -> None:
    enquiry_input = {
        "enquiry_subject": "Motor cover enquiry (retry-exhaustion fixture)",
        "enquiry_body_text": "Retry-exhaustion fixture marker.",
    }
    started = clock.tick(milliseconds=20)
    args = InvocationArgs(
        route_id=RECORDED_REPLAY_ROUTE,
        messages=(InvocationMessage(role="user", content="enquiry_classification input"),),
        metadata={
            "task_kind": "enquiry_classification",
            "input": enquiry_input,
            "agent_role": "classifier",
            "tenant_id": tenant_id,
        },
    )
    try:
        catalogue.invoke(args)
    except LLMProviderInvocationError as exc:
        completed = clock.tick(milliseconds=50)
        route_entry = catalogue.get(RECORDED_REPLAY_ROUTE)
        invocation_id = uuid4()
        run.decisions.append(
            DecisionTrailRecord(
                invocation_id=invocation_id,
                correlation_id=correlation_id,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                agent_id="uc1.classifier",
                agent_role="classifier",
                agent_version="v1",
                prompt_reference="prompts/uc1/classifier/v1.md",
                prompt_hash="sha256:" + "0" * 64,
                provider=route_entry.provider_id,
                model=route_entry.model_id,
                task_kind="enquiry_classification",
                input_summary=_summarise(enquiry_input),
                output_summary=f"Agent runtime failed: {exc}",
                justification=str(exc),
                outcome="failed",
                cost_amount_usd=Decimal("0.000000"),
                duration_ms=int((completed - started).total_seconds() * 1000),
                started_at=started,
                completed_at=completed,
                contract_refs=[UC1_AGENT_CONTRACT_REF],
                structured_data={},
            )
        )
        run.tool_actions.append(
            ToolActionRecord(
                audit_event_id=uuid4(),
                invocation_id=invocation_id,
                correlation_id=correlation_id,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                actor_type="system",
                actor_id="chorus.workflows.activities.record_retry_exhaustion_dlq",
                category="tool_gateway",
                action="workflow.retry_exhausted.dlq_recorded",
                tool_name=None,
                requested_mode=None,
                enforced_mode=None,
                verdict="dlq",
                reason="classifier retries exhausted",
                approval_required=False,
                approval_granted=None,
                occurred_at=completed,
            )
        )
        _emit(
            run,
            clock,
            sequence_cursor,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            subject_id=subject_id,
            subject_ref=subject_ref,
            event_type="workflow.failed",
            step="classification",
            payload={"subject_summary": "retry exhausted", "outcome": "failed"},
        )
        run.terminal_outcome = "failed"


def _emit(
    run: CapturedRun,
    clock: _Clock,
    sequence_cursor: _SequenceCursor,
    *,
    correlation_id: str,
    workflow_id: str,
    tenant_id: str,
    subject_id: UUID,
    subject_ref: str,
    event_type: str,
    step: str | None,
    payload: dict[str, Any],
) -> None:
    sequence = sequence_cursor.next()
    run.projection_events.append(
        ProjectionEvent(
            event_id=uuid4(),
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            workflow_type="uc1_enquiry_qualification",
            subject_id=subject_id,
            subject_ref=subject_ref,
            sequence=sequence,
            event_type=event_type,
            step=step,
            occurred_at=clock.tick(milliseconds=1),
            payload=payload,
        )
    )


def _summarise(payload: dict[str, Any]) -> str:
    return ", ".join(f"{key}={payload[key]}" for key in sorted(payload))


class _SequenceCursor:
    def __init__(self) -> None:
        self._cursor = 0

    def next(self) -> int:
        self._cursor += 1
        return self._cursor


class _Clock:
    def __init__(self, start: datetime) -> None:
        self._now = start

    def tick(self, *, milliseconds: int) -> datetime:
        self._now = self._now + timedelta(milliseconds=milliseconds)
        return self._now


__all__ = [
    "PIPELINE_STAGES",
    "PIPELINE_VERSION",
    "RECORDED_REPLAY_ADAPTER_VERSION",
    "RECORDED_REPLAY_BUDGET_USD",
    "RECORDED_REPLAY_MODEL",
    "RECORDED_REPLAY_PROVIDER",
    "RECORDED_REPLAY_ROUTE",
    "CapturedRun",
    "DecisionTrailRecord",
    "ProjectionEvent",
    "ToolActionRecord",
    "TranscriptRecord",
    "play_scenario",
]

RECORDED_REPLAY_ADAPTER_VERSION = REPLAY_ADAPTER_VERSION

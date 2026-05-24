"""Invariant assertions over a captured UC1 run.

ADR 0019 retires the path-enumeration eval era. In its place, every UC1
enquiry run, regardless of which branch the agents took, must satisfy a
small set of invariants. The invariants live here as pure functions over
the :class:`CapturedRun` shape :mod:`chorus.eval.scenario_player` produces
(and the equivalent shape a live run persists).

Each invariant returns a :class:`EvalCheck` list - one or more checks per
invariant - so the runner can report which invariants passed and which
failed without coupling them to the runner's loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from chorus.contracts.generated.eval.eval_fixture import OutcomeCategory
from chorus.eval.scenario_player import (
    PIPELINE_STAGES,
    CapturedRun,
    DecisionTrailRecord,
    TranscriptRecord,
)

EvalStatus = Literal["pass", "fail", "skip"]


@dataclass(frozen=True)
class EvalCheck:
    name: str
    status: EvalStatus
    detail: str


_REQUIRED_DECISION_FIELDS: tuple[str, ...] = (
    "correlation_id",
    "workflow_id",
    "tenant_id",
    "agent_id",
    "agent_role",
    "agent_version",
    "prompt_reference",
    "prompt_hash",
    "provider",
    "model",
    "task_kind",
    "started_at",
    "completed_at",
)


def assert_cross_port_payload_validity(run: CapturedRun) -> list[EvalCheck]:
    """Every captured payload at every port boundary carries its contract refs."""

    failures: list[str] = []
    for record in run.decisions:
        if not record.contract_refs:
            failures.append(f"decision {record.invocation_id} has no contract_refs")
    if failures:
        return [EvalCheck("cross-port payload validity", "fail", "; ".join(failures))]
    return [
        EvalCheck(
            "cross-port payload validity",
            "pass",
            f"all {len(run.decisions)} decision-trail rows reference their contract",
        )
    ]


def assert_governed_decision_provenance(run: CapturedRun) -> list[EvalCheck]:
    """Every decision-trail row carries the compliance provenance fields."""

    failures: list[str] = []
    for record in run.decisions:
        missing = [field for field in _REQUIRED_DECISION_FIELDS if not getattr(record, field, None)]
        if missing:
            failures.append(f"decision {record.invocation_id} missing {sorted(missing)}")
    if failures:
        return [EvalCheck("governed-decision provenance", "fail", "; ".join(failures))]
    return [
        EvalCheck(
            "governed-decision provenance",
            "pass",
            f"all {len(run.decisions)} decision-trail rows carry the required provenance fields",
        )
    ]


def assert_audit_completeness(run: CapturedRun) -> list[EvalCheck]:
    """Every LLM invocation pairs a decision-trail row with a transcript row."""

    decision_ids = {record.invocation_id for record in run.decisions}
    transcript_ids = {record.invocation_id for record in run.transcripts}
    only_decisions = decision_ids - transcript_ids
    only_transcripts = transcript_ids - decision_ids
    if not only_decisions and not only_transcripts:
        return [
            EvalCheck(
                "audit completeness",
                "pass",
                (
                    f"{len(decision_ids)} decision-trail rows and "
                    f"{len(transcript_ids)} transcript rows pair on invocation_id"
                ),
            )
        ]

    detail: list[str] = []
    if only_decisions:
        detail.append(f"decision-only invocations: {sorted(map(str, only_decisions))}")
    if only_transcripts:
        detail.append(f"transcript-only invocations: {sorted(map(str, only_transcripts))}")
    return [EvalCheck("audit completeness", "fail", "; ".join(detail))]


def assert_observability_emission(run: CapturedRun) -> list[EvalCheck]:
    """Every captured transcript carries the route catalogue surface."""

    failures: list[str] = []
    for record in run.transcripts:
        if not record.route_id:
            failures.append(f"transcript {record.transcript_id} missing route_id")
        if not record.provider_id or not record.model_id:
            failures.append(f"transcript {record.transcript_id} missing provider/model identifiers")
        if not record.adapter_version:
            failures.append(f"transcript {record.transcript_id} missing adapter_version")
    if failures:
        return [EvalCheck("observability emission", "fail", "; ".join(failures))]
    return [
        EvalCheck(
            "observability emission",
            "pass",
            f"all {len(run.transcripts)} transcripts carry route catalogue metadata",
        )
    ]


def assert_uc1_qualification_invariants(run: CapturedRun) -> list[EvalCheck]:
    """The qualification decision carries the four UC1 conduct hooks and provenance."""

    qualifier = _decision_for_task(run, "enquiry_qualification")
    if qualifier is None:
        if run.terminal_outcome == "failed":
            return [
                EvalCheck(
                    "UC1 qualification invariants",
                    "skip",
                    "qualifier did not run (workflow failed before qualification step)",
                )
            ]
        return [
            EvalCheck(
                "UC1 qualification invariants",
                "fail",
                "no enquiry_qualification decision-trail row found",
            )
        ]

    checks: list[EvalCheck] = []
    data = qualifier.structured_data
    transcript = _transcript_for_invocation(run, qualifier.invocation_id)

    for hook in (
        "best_interests_check",
        "demands_and_needs_statement",
        "target_market_check",
        "foreseeable_harm_check",
    ):
        if not isinstance(data.get(hook), dict):
            checks.append(
                EvalCheck(
                    f"UC1 qualification hook: {hook}",
                    "fail",
                    f"missing or malformed {hook} in qualification structured_data",
                )
            )
        else:
            checks.append(
                EvalCheck(
                    f"UC1 qualification hook: {hook}",
                    "pass",
                    f"present with regulatory ref {data[hook].get('regulatory_ref')!r}",
                )
            )

    if not qualifier.justification:
        checks.append(
            EvalCheck(
                "UC1 qualification rationale",
                "fail",
                "qualification decision missing justification",
            )
        )
    else:
        checks.append(
            EvalCheck(
                "UC1 qualification rationale",
                "pass",
                "qualification decision carries an explicit rationale",
            )
        )

    if not data.get("policy_snapshot_ref"):
        checks.append(
            EvalCheck(
                "UC1 qualification policy_snapshot_ref",
                "fail",
                "qualification structured_data missing policy_snapshot_ref",
            )
        )
    else:
        checks.append(
            EvalCheck(
                "UC1 qualification policy_snapshot_ref",
                "pass",
                f"policy_snapshot_ref={data['policy_snapshot_ref']!r}",
            )
        )

    if transcript is None:
        checks.append(
            EvalCheck(
                "UC1 qualification transcript_ref",
                "fail",
                f"no transcript paired with invocation {qualifier.invocation_id}",
            )
        )
    else:
        checks.append(
            EvalCheck(
                "UC1 qualification transcript_ref",
                "pass",
                (
                    f"transcript {transcript.transcript_id} pairs with "
                    f"invocation {qualifier.invocation_id}"
                ),
            )
        )

    return checks


def assert_connector_authority_discipline(run: CapturedRun) -> list[EvalCheck]:
    """Every connector call went through the gateway with mode + verdict captured."""

    if run.terminal_outcome == "failed" and not run.tool_actions:
        return [
            EvalCheck(
                "connector authority discipline",
                "fail",
                "no tool-action audit row for the failed workflow",
            )
        ]
    if not run.tool_actions:
        return [
            EvalCheck(
                "connector authority discipline",
                "skip",
                "no connector calls captured in this run",
            )
        ]

    checks: list[EvalCheck] = []
    write_actions = [
        action
        for action in run.tool_actions
        if action.enforced_mode == "write" and action.tool_name is not None
    ]
    if not write_actions and run.terminal_outcome != "failed":
        checks.append(
            EvalCheck(
                "connector authority discipline (writes through approval)",
                "fail",
                "no write-mode tool-action audit row recorded",
            )
        )
    else:
        for action in write_actions:
            if not action.approval_required or action.approval_granted is not True:
                checks.append(
                    EvalCheck(
                        f"connector write authority: {action.tool_name}",
                        "fail",
                        (
                            f"write at {action.audit_event_id} did not record adviser approval "
                            f"(approval_required={action.approval_required}, "
                            f"approval_granted={action.approval_granted})"
                        ),
                    )
                )
            else:
                checks.append(
                    EvalCheck(
                        f"connector write authority: {action.tool_name}",
                        "pass",
                        f"write at {action.audit_event_id} carries adviser approval",
                    )
                )

    for action in run.tool_actions:
        if not action.verdict:
            checks.append(
                EvalCheck(
                    f"connector verdict captured: {action.audit_event_id}",
                    "fail",
                    "tool-action audit row missing verdict",
                )
            )
    return checks


def assert_projection_convergence(run: CapturedRun) -> list[EvalCheck]:
    """The workflow event sequence reaches the expected terminal state."""

    expected = run.fixture.expected.outcome_category
    terminal = next(
        (
            event
            for event in reversed(run.projection_events)
            if event.event_type in {"workflow.completed", "workflow.escalated", "workflow.failed"}
        ),
        None,
    )
    if terminal is None:
        return [
            EvalCheck(
                "projection convergence",
                "fail",
                "no terminal workflow event captured",
            )
        ]

    expected_event = _expected_terminal_event(expected)
    if terminal.event_type != expected_event:
        return [
            EvalCheck(
                "projection convergence",
                "fail",
                (
                    f"expected terminal event {expected_event!r} for outcome "
                    f"{expected.value!r}, got {terminal.event_type!r}"
                ),
            )
        ]

    sequences = [event.sequence for event in run.projection_events]
    if sequences != sorted(sequences):
        return [
            EvalCheck(
                "projection convergence",
                "fail",
                f"projection event sequence is not monotonic: {sequences}",
            )
        ]

    return [
        EvalCheck(
            "projection convergence",
            "pass",
            (
                f"terminal event {terminal.event_type!r} matches outcome "
                f"{expected.value!r} after {len(run.projection_events)} events"
            ),
        )
    ]


UC1_INVARIANTS = (
    assert_cross_port_payload_validity,
    assert_governed_decision_provenance,
    assert_audit_completeness,
    assert_observability_emission,
    assert_uc1_qualification_invariants,
    assert_connector_authority_discipline,
    assert_projection_convergence,
)


def run_invariants(run: CapturedRun) -> list[EvalCheck]:
    checks: list[EvalCheck] = []
    for invariant in UC1_INVARIANTS:
        checks.extend(invariant(run))
    return checks


def _expected_terminal_event(category: OutcomeCategory) -> str:
    if category == OutcomeCategory.ESCALATE:
        return "workflow.escalated"
    if category == OutcomeCategory.DLQ:
        return "workflow.failed"
    return "workflow.completed"


def _decision_for_task(run: CapturedRun, task_kind: str) -> DecisionTrailRecord | None:
    matches = [record for record in run.decisions if record.task_kind == task_kind]
    return matches[-1] if matches else None


def _transcript_for_invocation(run: CapturedRun, invocation_id: object) -> TranscriptRecord | None:
    return next(
        (record for record in run.transcripts if record.invocation_id == invocation_id),
        None,
    )


_ = PIPELINE_STAGES  # re-export anchor; pipeline ordering lives with the scenario player

__all__ = [
    "UC1_INVARIANTS",
    "EvalCheck",
    "EvalStatus",
    "assert_audit_completeness",
    "assert_connector_authority_discipline",
    "assert_cross_port_payload_validity",
    "assert_governed_decision_provenance",
    "assert_observability_emission",
    "assert_projection_convergence",
    "assert_uc1_qualification_invariants",
    "run_invariants",
]

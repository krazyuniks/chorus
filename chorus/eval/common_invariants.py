"""Architecture-wide invariant assertions over captured eval runs.

These checks apply to every use case: they assert named-port payload
validity, decision provenance, audit / transcript pairing, route metadata,
connector authority, and projection convergence. Business conduct rules live
in per-use-case modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chorus.eval.types import EvalCheck

if TYPE_CHECKING:
    from chorus.eval.scenario_player import CapturedRun


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
                "connector authority discipline (writes captured)",
                "fail",
                "no write-mode tool-action audit row recorded",
            )
        )
    else:
        for action in write_actions:
            if action.approval_required and action.approval_granted is not True:
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
            elif action.approval_required:
                checks.append(
                    EvalCheck(
                        f"connector write authority: {action.tool_name}",
                        "pass",
                        f"write at {action.audit_event_id} carries adviser approval",
                    )
                )
            elif action.verdict == "allow":
                checks.append(
                    EvalCheck(
                        f"connector write authority: {action.tool_name}",
                        "pass",
                        (
                            f"write at {action.audit_event_id} records Tool Gateway "
                            "authority without an approval requirement"
                        ),
                    )
                )
            else:
                checks.append(
                    EvalCheck(
                        f"connector write authority: {action.tool_name}",
                        "fail",
                        (
                            f"write at {action.audit_event_id} had no approval requirement "
                            f"but verdict={action.verdict!r}"
                        ),
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
    expected_value = _enum_value(expected)
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

    expected_event = _expected_terminal_event(expected_value)
    if terminal.event_type != expected_event:
        return [
            EvalCheck(
                "projection convergence",
                "fail",
                (
                    f"expected terminal event {expected_event!r} for outcome "
                    f"{expected_value!r}, got {terminal.event_type!r}"
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
                f"{expected_value!r} after {len(run.projection_events)} events"
            ),
        )
    ]


COMMON_INVARIANTS = (
    assert_cross_port_payload_validity,
    assert_governed_decision_provenance,
    assert_audit_completeness,
    assert_observability_emission,
    assert_connector_authority_discipline,
    assert_projection_convergence,
)


def _expected_terminal_event(category: str) -> str:
    if category == "escalate":
        return "workflow.escalated"
    if category == "dlq":
        return "workflow.failed"
    return "workflow.completed"


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


__all__ = [
    "COMMON_INVARIANTS",
    "assert_audit_completeness",
    "assert_connector_authority_discipline",
    "assert_cross_port_payload_validity",
    "assert_governed_decision_provenance",
    "assert_observability_emission",
    "assert_projection_convergence",
]

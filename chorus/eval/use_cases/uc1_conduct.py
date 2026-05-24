"""UC1 conduct invariant assertions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from chorus.eval.types import EvalCheck

if TYPE_CHECKING:
    from chorus.eval.scenario_player import CapturedRun, DecisionTrailRecord, TranscriptRecord


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


UC1_CONDUCT_INVARIANTS = (assert_uc1_qualification_invariants,)


def _decision_for_task(run: CapturedRun, task_kind: str) -> DecisionTrailRecord | None:
    matches = [record for record in run.decisions if record.task_kind == task_kind]
    return matches[-1] if matches else None


def _transcript_for_invocation(run: CapturedRun, invocation_id: object) -> TranscriptRecord | None:
    return next(
        (record for record in run.transcripts if record.invocation_id == invocation_id),
        None,
    )


__all__ = [
    "UC1_CONDUCT_INVARIANTS",
    "assert_uc1_qualification_invariants",
]

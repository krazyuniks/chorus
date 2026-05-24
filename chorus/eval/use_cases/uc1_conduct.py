"""UC1 conduct invariant assertions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from chorus.eval.types import EvalCheck

if TYPE_CHECKING:
    from chorus.eval.scenario_player import (
        CapturedRun,
        DecisionTrailRecord,
        ProjectionEvent,
        ToolActionRecord,
        TranscriptRecord,
    )


_TERMINAL_CONNECTOR_ROUTES = {
    "accepted_routed": {
        "category": "accept",
        "tool_name": "crm.route_to_quoting_queue",
        "step": "route_verdict_accept",
        "route_ref_key": "queued_route_ref",
        "route_ref_prefix": "qroute_",
        "route_status": "queued",
    },
    "referred_routed": {
        "category": "refer",
        "tool_name": "referral_inbox.route",
        "step": "route_verdict_refer",
        "route_ref_key": "referral_route_ref",
        "route_ref_prefix": "rroute_",
        "route_status": "routed",
    },
    "declined_routed": {
        "category": "decline",
        "tool_name": "decline_ledger.route",
        "step": "route_verdict_decline",
        "route_ref_key": "decline_route_ref",
        "route_ref_prefix": "droute_",
        "route_status": "recorded",
    },
}


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


def assert_uc1_terminal_connector_routing(run: CapturedRun) -> list[EvalCheck]:
    """Terminal UC1 verdict fixtures route through the expected connector path."""

    expected = _expected_terminal_connector_route(run)
    if expected is None:
        return []

    checks: list[EvalCheck] = []
    qualifier = _decision_for_task(run, "enquiry_qualification")
    category = expected["category"]
    if qualifier is None:
        checks.append(
            EvalCheck(
                f"UC1 terminal connector route: {category}",
                "fail",
                "no enquiry_qualification decision-trail row found",
            )
        )
    else:
        actual_category = qualifier.structured_data.get("qualification_verdict_category")
        if actual_category != category:
            checks.append(
                EvalCheck(
                    f"UC1 terminal connector route: {category}",
                    "fail",
                    (f"qualification_verdict_category={actual_category!r}, expected {category!r}"),
                )
            )
        else:
            checks.append(
                EvalCheck(
                    f"UC1 terminal connector route: {category}",
                    "pass",
                    f"qualification verdict category {category!r} selected",
                )
            )

    action = _tool_action_for(run, expected["tool_name"])
    if action is None:
        checks.append(
            EvalCheck(
                f"UC1 terminal connector tool: {expected['tool_name']}",
                "fail",
                "no matching Tool Gateway audit row found",
            )
        )
        return checks

    mode_failures: list[str] = []
    if action.actor_id != "uc1.qualifier":
        mode_failures.append(f"actor_id={action.actor_id!r}")
    if action.action != "tool_call.decided":
        mode_failures.append(f"action={action.action!r}")
    if action.requested_mode != "write" or action.enforced_mode != "write":
        mode_failures.append(
            f"requested/enforced mode={action.requested_mode!r}/{action.enforced_mode!r}"
        )
    if action.verdict != "allow":
        mode_failures.append(f"verdict={action.verdict!r}")
    if action.approval_required:
        mode_failures.append("approval_required=True")
    if mode_failures:
        checks.append(
            EvalCheck(
                f"UC1 terminal connector authority: {expected['tool_name']}",
                "fail",
                "; ".join(mode_failures),
            )
        )
    else:
        checks.append(
            EvalCheck(
                f"UC1 terminal connector authority: {expected['tool_name']}",
                "pass",
                "qualifier write was allowed by the Tool Gateway without human approval",
            )
        )

    route_ref = action.output.get(expected["route_ref_key"])
    route_status = action.output.get("route_status")
    if not isinstance(route_ref, str) or not route_ref.startswith(expected["route_ref_prefix"]):
        checks.append(
            EvalCheck(
                f"UC1 terminal connector ref: {expected['route_ref_key']}",
                "fail",
                f"connector output route ref was {route_ref!r}",
            )
        )
    elif route_status != expected["route_status"]:
        checks.append(
            EvalCheck(
                f"UC1 terminal connector ref: {expected['route_ref_key']}",
                "fail",
                f"route_status={route_status!r}, expected {expected['route_status']!r}",
            )
        )
    else:
        checks.append(
            EvalCheck(
                f"UC1 terminal connector ref: {expected['route_ref_key']}",
                "pass",
                f"{expected['route_ref_key']}={route_ref!r} status={route_status!r}",
            )
        )

    projection = _projection_for_step(run, expected["step"])
    if projection is None:
        checks.append(
            EvalCheck(
                f"UC1 terminal route projection: {expected['step']}",
                "fail",
                "no completed projection event found for the route step",
            )
        )
    elif projection.payload.get("routing_ref") != route_ref:
        checks.append(
            EvalCheck(
                f"UC1 terminal route projection: {expected['step']}",
                "fail",
                (
                    f"projection routing_ref={projection.payload.get('routing_ref')!r}, "
                    f"connector route_ref={route_ref!r}"
                ),
            )
        )
    else:
        checks.append(
            EvalCheck(
                f"UC1 terminal route projection: {expected['step']}",
                "pass",
                f"projection carries routing_ref={route_ref!r}",
            )
        )

    return checks


UC1_CONDUCT_INVARIANTS = (
    assert_uc1_qualification_invariants,
    assert_uc1_terminal_connector_routing,
)


def _decision_for_task(run: CapturedRun, task_kind: str) -> DecisionTrailRecord | None:
    matches = [record for record in run.decisions if record.task_kind == task_kind]
    return matches[-1] if matches else None


def _transcript_for_invocation(run: CapturedRun, invocation_id: object) -> TranscriptRecord | None:
    return next(
        (record for record in run.transcripts if record.invocation_id == invocation_id),
        None,
    )


def _expected_terminal_connector_route(run: CapturedRun) -> dict[str, str] | None:
    outcome = run.fixture.expected.use_case_outcome
    if outcome is None:
        return None
    return _TERMINAL_CONNECTOR_ROUTES.get(str(getattr(outcome, "value", outcome)))


def _tool_action_for(run: CapturedRun, tool_name: str) -> ToolActionRecord | None:
    matches = [record for record in run.tool_actions if record.tool_name == tool_name]
    return matches[-1] if matches else None


def _projection_for_step(run: CapturedRun, step: str) -> ProjectionEvent | None:
    matches = [
        record
        for record in run.projection_events
        if record.step == step and record.event_type == "workflow.step.completed"
    ]
    return matches[-1] if matches else None


__all__ = [
    "UC1_CONDUCT_INVARIANTS",
    "assert_uc1_qualification_invariants",
    "assert_uc1_terminal_connector_routing",
]

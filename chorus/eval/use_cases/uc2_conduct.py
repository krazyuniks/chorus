"""UC2 conduct invariant assertions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from chorus.eval.types import EvalCheck

if TYPE_CHECKING:
    from uuid import UUID

    from chorus.eval.scenario_player import (
        CapturedRun,
        DecisionTrailRecord,
        ToolActionRecord,
        TranscriptRecord,
    )


_REQUIRED_ENGAGEMENT_FIELDS = (
    "engagement_outcome",
    "engagement_decision_ref",
    "policy_snapshot_ref",
    "prospective_client_ref",
    "instructing_contact_ref",
    "authority_status",
    "matter_scope_ref",
    "conflict_status",
    "confidentiality_safeguard_status",
    "cdd_status",
    "beneficial_ownership_status",
    "aml_risk_rating",
    "conduct_hook_refs",
)

_REQUIRED_CONDUCT_REFS = frozenset(
    {
        "conduct_sra_identify_client_8_1",
        "conduct_sra_conflict_6_1_6_2",
        "conduct_sra_confidentiality_6_3_6_5",
        "conduct_mlr_cdd_reg_27_28",
        "conduct_sra_accountability_7_1_7_2",
    }
)

_BLOCKING_CONFLICT_STATUSES = frozenset(
    {
        "own_interest_conflict",
        "client_conflict_blocked",
        "permitted_exception_candidate",
        "confidentiality_risk",
        "unknown_manual_review",
    }
)

_ACCEPTANCE_OUTCOMES = frozenset(
    {
        "accept_for_engagement",
        "accepted_engagement_letter_sent",
        "completed",
    }
)

_APPROVAL_WAITING_OUTCOMES = frozenset(
    {
        "accept_subject_to_approval",
        "approval_required",
    }
)

_RAW_CONTENT_KEYS = frozenset(
    {
        "body_text",
        "email_body",
        "engagement_letter_text",
        "identity_document",
        "raw_conflict_detail",
        "raw_party_name",
        "source_of_funds_detail",
        "source_of_wealth_detail",
    }
)


_BASE_WORKFLOW_STEPS = (
    "intake",
    "matter_classification",
    "party_extraction",
    "conflict_check",
    "conflict_determination",
)

_ACCEPTANCE_WORKFLOW_STEPS = (
    "kyc_beneficial_ownership",
    "aml_assessment",
    "engagement_decision",
    "engagement_letter_draft",
    "engagement_letter_send",
    "close",
)

_CONFLICT_EXCEPTION_WORKFLOW_STEPS = (
    "conflict_exception_approval",
    "manual_review",
    "close",
)

_BASE_AGENT_TASKS = (
    "uc2_matter_classification",
    "uc2_party_extraction",
    "uc2_conflict_determination",
)

_ACCEPTANCE_AGENT_TASKS = ("uc2_engagement_decision",)


def assert_uc2_workflow_progress_evidence(run: CapturedRun) -> list[EvalCheck]:
    """UC2 fixtures must carry the workflow step evidence for their branch."""

    if not run.projection_events:
        return [
            EvalCheck(
                "UC2 workflow progress evidence",
                "fail",
                "no workflow progress events captured",
            )
        ]

    required_steps: list[str] = list(_BASE_WORKFLOW_STEPS)
    if _is_conflict_exception_branch(run):
        required_steps.extend(_CONFLICT_EXCEPTION_WORKFLOW_STEPS)
    elif _is_acceptance_path(run):
        required_steps.extend(_ACCEPTANCE_WORKFLOW_STEPS)
    else:
        required_steps.append("close")

    completed_steps = _completed_step_set(run)
    failures: list[str] = []
    missing_steps = [step for step in required_steps if step not in completed_steps]
    if missing_steps:
        failures.append(f"missing workflow step completions: {missing_steps}")

    terminal = _terminal_event_type(run)
    if terminal is None:
        failures.append("missing terminal workflow event")

    if failures:
        return [EvalCheck("UC2 workflow progress evidence", "fail", "; ".join(failures))]
    return [
        EvalCheck(
            "UC2 workflow progress evidence",
            "pass",
            f"captured UC2 workflow progress through {required_steps[-1]!r}",
        )
    ]


def assert_uc2_agent_decision_and_transcript_evidence(run: CapturedRun) -> list[EvalCheck]:
    """Required UC2 agent stages must have decision-trail and transcript rows."""

    if not run.decisions:
        return [
            EvalCheck(
                "UC2 agent decision and transcript evidence",
                "fail",
                "no decision-trail rows captured",
            )
        ]

    required_tasks: list[str] = list(_BASE_AGENT_TASKS)
    if _is_acceptance_path(run):
        required_tasks.extend(_ACCEPTANCE_AGENT_TASKS)

    failures: list[str] = []
    for task_kind in required_tasks:
        decision = _decision_for_task(run, task_kind)
        if decision is None:
            failures.append(f"missing decision-trail row for {task_kind}")
            continue
        transcript = _transcript_for_invocation(run, decision.invocation_id)
        if transcript is None:
            failures.append(f"missing transcript row for {task_kind}")
        elif not transcript.structured_data:
            failures.append(f"transcript row for {task_kind} missing response structured_data")
        if decision.outcome != "succeeded":
            failures.append(f"{task_kind} decision outcome={decision.outcome!r}")
        if not decision.structured_data:
            failures.append(f"{task_kind} decision missing structured_data evidence")

    if failures:
        return [
            EvalCheck(
                "UC2 agent decision and transcript evidence",
                "fail",
                "; ".join(failures),
            )
        ]
    return [
        EvalCheck(
            "UC2 agent decision and transcript evidence",
            "pass",
            f"captured decision and transcript evidence for {required_tasks}",
        )
    ]


def assert_uc2_engagement_decision_conduct(run: CapturedRun) -> list[EvalCheck]:
    """UC2 engagement decisions carry SRA / AML conduct evidence and safe refs."""

    if _is_conflict_exception_branch(run) and not _is_acceptance_path(run):
        return [
            EvalCheck(
                "UC2 engagement decision conduct",
                "pass",
                "engagement decision correctly not reached before conflict-exception approval",
            )
        ]

    decision = _decision_for_task(run, "uc2_engagement_decision")
    if decision is None:
        return [
            EvalCheck(
                "UC2 engagement decision conduct",
                "fail",
                "no uc2_engagement_decision decision-trail row found",
            )
        ]

    data = decision.structured_data
    failures: list[str] = []
    missing = [field for field in _REQUIRED_ENGAGEMENT_FIELDS if not _present(data.get(field))]
    if missing:
        failures.append(f"missing required fields: {missing}")

    conduct_refs = _string_set(data.get("conduct_hook_refs"))
    missing_refs = sorted(_REQUIRED_CONDUCT_REFS - conduct_refs)
    if missing_refs:
        failures.append(f"missing conduct refs: {missing_refs}")

    outcome = _string_value(data.get("engagement_outcome"))
    if outcome in _ACCEPTANCE_OUTCOMES:
        failures.extend(_acceptance_boundary_failures(data))

    raw_fields = sorted(key for key in data if key in _RAW_CONTENT_KEYS)
    if raw_fields:
        failures.append(f"raw content fields present: {raw_fields}")

    if failures:
        return [
            EvalCheck(
                "UC2 engagement decision conduct",
                "fail",
                "; ".join(failures),
            )
        ]
    return [
        EvalCheck(
            "UC2 engagement decision conduct",
            "pass",
            f"engagement decision {outcome!r} carries safe SRA / AML conduct evidence",
        )
    ]


def assert_uc2_conflict_exception_approval_branch(run: CapturedRun) -> list[EvalCheck]:
    """Conflict-exception branches must stop before engagement and route review."""

    if not _is_conflict_exception_branch(run):
        return []

    failures: list[str] = []
    conflict = _decision_for_task(run, "uc2_conflict_determination")
    if conflict is None:
        failures.append("missing uc2_conflict_determination decision-trail row")
    else:
        status = _string_value(conflict.structured_data.get("conflict_status"))
        if status not in {"permitted_exception_candidate", "confidentiality_risk"}:
            failures.append(f"conflict exception branch has conflict_status={status!r}")
        confidentiality = _string_value(
            conflict.structured_data.get("confidentiality_safeguard_status")
        )
        if not confidentiality:
            failures.append("conflict exception branch missing confidentiality safeguard status")

    completed_steps = _completed_step_set(run)
    for step in _CONFLICT_EXCEPTION_WORKFLOW_STEPS:
        if step not in completed_steps:
            failures.append(f"missing workflow step completion for {step}")

    handoff = _last_tool_action_for(
        run,
        "engagement_letter.route_manual_review",
        mode="write",
    )
    if handoff is None:
        failures.append("missing engagement_letter.route_manual_review write audit row")
    else:
        if handoff.verdict != "allow":
            failures.append(f"manual review handoff verdict={handoff.verdict!r}")
        if not _string_value(handoff.output.get("handoff_ref")):
            failures.append("manual review handoff output missing handoff_ref")
        if not _string_value(handoff.output.get("review_reason_category")):
            failures.append("manual review handoff output missing review_reason_category")

    if _tool_actions_for(run, "engagement_letter.send"):
        failures.append("conflict exception branch reached engagement_letter.send")

    if failures:
        return [
            EvalCheck(
                "UC2 conflict-exception approval branch",
                "fail",
                "; ".join(failures),
            )
        ]
    return [
        EvalCheck(
            "UC2 conflict-exception approval branch",
            "pass",
            "conflict exception is approval-gated and routed to manual review before send",
        )
    ]


def assert_uc2_engagement_letter_send_approval_gate(run: CapturedRun) -> list[EvalCheck]:
    """UC2 engagement-letter send is always approval-gated before effect."""

    decision = _decision_for_task(run, "uc2_engagement_decision")
    decision_outcome = (
        _string_value(decision.structured_data.get("engagement_outcome"))
        if decision is not None
        else ""
    )
    use_case_outcome = _use_case_outcome(run)
    terminal = run.terminal_outcome
    send_relevant = (
        _is_acceptance_path(run)
        or decision_outcome in (_ACCEPTANCE_OUTCOMES | _APPROVAL_WAITING_OUTCOMES)
        or use_case_outcome in (_ACCEPTANCE_OUTCOMES | _APPROVAL_WAITING_OUTCOMES)
        or "engagement_letter" in use_case_outcome
        or "accepted" in use_case_outcome
    )
    if not send_relevant:
        return []

    send_actions = _tool_actions_for(run, "engagement_letter.send")
    package_requests = [
        action
        for action in send_actions
        if action.requested_mode == "write"
        and action.enforced_mode == "write"
        and action.verdict == "approval_required"
        and action.approval_required
        and action.approval_granted is None
    ]
    approved_applies = [
        action
        for action in send_actions
        if action.requested_mode == "write"
        and action.enforced_mode == "write"
        and action.verdict == "allow"
        and action.approval_required
        and action.approval_granted is True
    ]

    failures: list[str] = []
    if not package_requests:
        failures.append("no approval_required package request for engagement_letter.send")
    else:
        package_request = package_requests[-1]
        request_output = package_request.output
        if request_output.get("requested_action") != "engagement_letter.send.write":
            failures.append("send approval package missing requested_action ref")
        if not _string_value(request_output.get("approval_id")):
            failures.append("send approval package missing approval_id")
        if not package_request.approval_package:
            failures.append("send approval package table evidence missing")
        elif package_request.approval_package.get("requested_action") != (
            "engagement_letter.send.write"
        ):
            failures.append("send approval package table row has wrong requested_action")

    waiting = (
        terminal in _APPROVAL_WAITING_OUTCOMES
        or decision_outcome in _APPROVAL_WAITING_OUTCOMES
        or use_case_outcome in _APPROVAL_WAITING_OUTCOMES
        or "approval_gated" in use_case_outcome
        or "approval_required" in use_case_outcome
    )
    completed_acceptance = (
        terminal in _ACCEPTANCE_OUTCOMES or use_case_outcome in _ACCEPTANCE_OUTCOMES
    )
    if completed_acceptance and not approved_applies:
        failures.append("completed acceptance lacks approved engagement_letter.send apply")
    if waiting and approved_applies:
        failures.append("approval-waiting outcome already contains send apply")

    for action in send_actions:
        raw_output_keys = sorted(key for key in action.output if key in _RAW_CONTENT_KEYS)
        if raw_output_keys:
            failures.append(f"send action output carried raw content fields: {raw_output_keys}")

    if failures:
        return [
            EvalCheck(
                "UC2 engagement-letter send approval gate",
                "fail",
                "; ".join(failures),
            )
        ]
    return [
        EvalCheck(
            "UC2 engagement-letter send approval gate",
            "pass",
            "engagement_letter.send has an approval package request and required apply state",
        )
    ]


def assert_uc2_connector_ref_evidence(run: CapturedRun) -> list[EvalCheck]:
    """UC2 connector actions expose safe refs for conflict, AML, and engagement records."""

    if not run.tool_actions:
        return [
            EvalCheck(
                "UC2 connector ref evidence",
                "fail",
                "no tool-action audit rows captured",
            )
        ]

    expected: dict[str, tuple[str, tuple[str, ...]]] = {
        "conflict_check.search": ("read", ("conflict_check_ref",)),
    }
    if _is_conflict_exception_branch(run):
        expected["engagement_letter.route_manual_review"] = ("write", ("handoff_ref",))
    elif _is_acceptance_path(run):
        expected.update(
            {
                "kyc_bo.lookup": ("read", ("cdd_record_ref", "beneficial_ownership_snapshot_ref")),
                "aml_record_store.record_assessment": ("write", ("aml_risk_assessment_ref",)),
                "engagement_letter.draft": ("write", ("engagement_letter_ref", "draft_ref")),
            }
        )

    failures: list[str] = []
    for tool_name, (mode, ref_keys) in expected.items():
        action = _last_tool_action_for(run, tool_name, mode=mode)
        if action is None:
            failures.append(f"missing {tool_name} {mode} action")
            continue
        if action.verdict not in {"allow", "approval_required"}:
            failures.append(f"{tool_name} verdict={action.verdict!r}")
        for key in ref_keys:
            if not _string_value(action.output.get(key)):
                failures.append(f"{tool_name} output missing {key}")

    if _is_acceptance_path(run):
        send = _last_tool_action_for(run, "engagement_letter.send", mode="write")
        if send is None:
            failures.append("missing engagement_letter.send write action")
        elif send.verdict == "approval_required":
            if not _string_value(send.output.get("approval_id")):
                failures.append("engagement_letter.send approval output missing approval_id")
        elif send.verdict == "allow":
            if not _string_value(send.output.get("send_record_ref")):
                failures.append("engagement_letter.send output missing send_record_ref")
        else:
            failures.append(f"engagement_letter.send verdict={send.verdict!r}")

    if failures:
        return [EvalCheck("UC2 connector ref evidence", "fail", "; ".join(failures))]
    return [
        EvalCheck(
            "UC2 connector ref evidence",
            "pass",
            "UC2 connector actions carry safe conflict, AML, draft, send, or handoff refs",
        )
    ]


UC2_CONDUCT_INVARIANTS = (
    assert_uc2_workflow_progress_evidence,
    assert_uc2_agent_decision_and_transcript_evidence,
    assert_uc2_engagement_decision_conduct,
    assert_uc2_conflict_exception_approval_branch,
    assert_uc2_engagement_letter_send_approval_gate,
    assert_uc2_connector_ref_evidence,
)


def _acceptance_boundary_failures(data: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if _string_value(data.get("authority_status")) != "confirmed":
        failures.append("acceptance requires confirmed authority")
    conflict_status = _string_value(data.get("conflict_status"))
    if conflict_status in _BLOCKING_CONFLICT_STATUSES:
        failures.append(f"acceptance blocked by conflict_status={conflict_status!r}")
    if conflict_status != "no_conflict":
        failures.append("this slice only accepts no_conflict UC2 evidence")
    confidentiality = _string_value(data.get("confidentiality_safeguard_status"))
    if confidentiality not in {"not_required", "no_real_risk_evidenced"}:
        failures.append(
            "acceptance requires not_required or no_real_risk_evidenced confidentiality state"
        )
    if _string_value(data.get("cdd_status")) != "complete_standard":
        failures.append("acceptance requires complete_standard CDD")
    if _string_value(data.get("beneficial_ownership_status")) not in {
        "complete",
        "not_applicable",
    }:
        failures.append("acceptance requires complete or not_applicable beneficial ownership")
    if _string_value(data.get("aml_risk_rating")) not in {"low", "standard"}:
        failures.append("this slice routes high or EDD AML risk away from acceptance")
    return failures


def _decision_for_task(run: CapturedRun, task_kind: str) -> DecisionTrailRecord | None:
    matches = [record for record in run.decisions if record.task_kind == task_kind]
    return matches[-1] if matches else None


def _transcript_for_invocation(
    run: CapturedRun,
    invocation_id: UUID,
) -> TranscriptRecord | None:
    matches = [record for record in run.transcripts if record.invocation_id == invocation_id]
    return matches[-1] if matches else None


def _tool_actions_for(run: CapturedRun, tool_name: str) -> list[ToolActionRecord]:
    return [record for record in run.tool_actions if record.tool_name == tool_name]


def _last_tool_action_for(
    run: CapturedRun,
    tool_name: str,
    *,
    mode: str,
) -> ToolActionRecord | None:
    matches = [
        record
        for record in run.tool_actions
        if record.tool_name == tool_name and record.enforced_mode == mode
    ]
    return matches[-1] if matches else None


def _completed_step_set(run: CapturedRun) -> set[str]:
    return {
        event.step
        for event in run.projection_events
        if event.event_type == "workflow.step.completed" and event.step is not None
    }


def _terminal_event_type(run: CapturedRun) -> str | None:
    terminal = next(
        (
            event.event_type
            for event in reversed(run.projection_events)
            if event.event_type in {"workflow.completed", "workflow.escalated", "workflow.failed"}
        ),
        None,
    )
    return terminal


def _is_acceptance_path(run: CapturedRun) -> bool:
    steps = _completed_step_set(run)
    if steps.intersection({"engagement_decision", "engagement_letter_send"}):
        return True
    decision = _decision_for_task(run, "uc2_engagement_decision")
    if decision is not None:
        return True
    use_case_outcome = _use_case_outcome(run)
    return "engagement_letter" in use_case_outcome or "accepted" in use_case_outcome


def _is_conflict_exception_branch(run: CapturedRun) -> bool:
    if "conflict_exception_approval" in _completed_step_set(run):
        return True
    conflict = _decision_for_task(run, "uc2_conflict_determination")
    if conflict is not None and _string_value(conflict.structured_data.get("conflict_status")) in {
        "permitted_exception_candidate",
        "confidentiality_risk",
    }:
        return True
    use_case_outcome = _use_case_outcome(run)
    return "conflict_exception" in use_case_outcome


def _use_case_outcome(run: CapturedRun) -> str:
    value = run.fixture.expected.use_case_outcome
    return str(getattr(value, "value", value)) if value is not None else ""


def _present(value: object) -> bool:
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, list):
        return bool(cast(list[Any], value))
    return value is not None


def _string_value(value: object) -> str:
    return value if isinstance(value, str) else ""


def _string_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    items = cast(list[Any], value)
    return {item for item in items if isinstance(item, str)}


__all__ = [
    "UC2_CONDUCT_INVARIANTS",
    "assert_uc2_agent_decision_and_transcript_evidence",
    "assert_uc2_conflict_exception_approval_branch",
    "assert_uc2_connector_ref_evidence",
    "assert_uc2_engagement_decision_conduct",
    "assert_uc2_engagement_letter_send_approval_gate",
    "assert_uc2_workflow_progress_evidence",
]

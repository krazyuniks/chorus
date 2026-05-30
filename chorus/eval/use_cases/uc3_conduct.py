"""UC3 conduct invariant assertions."""

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


_REQUIRED_SUITABILITY_FIELDS = (
    "suitability_outcome",
    "suitability_conclusion_ref",
    "policy_snapshot_ref",
    "advice_enquiry_ref",
    "prospective_retail_client_ref",
    "fact_find_summary_ref",
    "risk_profile_ref",
    "risk_profile_status",
    "capacity_for_loss_ref",
    "capacity_for_loss_status",
    "platform_research_ref",
    "product_universe_coverage",
    "target_market_status",
    "support_assessment_ref",
    "support_status",
    "consumer_understanding_check_ref",
    "conduct_hook_refs",
)

_REQUIRED_CONDUCT_REFS = frozenset(
    {
        "conduct_fca_cobs_2_1_client_best_interests",
        "conduct_fca_cobs_6_2b_independent_advice",
        "conduct_fca_cobs_9_suitability",
        "conduct_fca_prod_3_target_market",
        "conduct_fca_prin_2a_consumer_duty",
        "conduct_fca_vulnerability_fg21_1",
        "conduct_fca_cobs_9_recordkeeping",
    }
)

_SUITABILITY_REPORT_RELEVANT_OUTCOMES = frozenset(
    {
        "suitable_subject_to_adviser_approval",
        "suitability_report_issued",
        "completed",
        "approval_required",
    }
)

_COMPLETED_OUTCOMES = frozenset({"suitability_report_issued", "completed"})
_APPROVAL_WAITING_OUTCOMES = frozenset(
    {
        "approval_required",
        "suitability_report_issue_approval_gated",
        "suitable_subject_to_adviser_approval",
    }
)

_RISK_APPROVAL_STATUSES = frozenset(
    {
        "mismatch_requires_approval",
        "client_overstates_risk",
        "client_understates_loss_concern",
    }
)

_SUPPORT_APPROVAL_STATUSES = frozenset(
    {
        "approval_required",
        "requires_handoff",
        "support_adjustment_required",
        "vulnerability_support_required",
        "third_party_authority_review",
    }
)

_PRE_RISK_WORKFLOW_STEPS = (
    "intake",
    "advice_scope_classification",
    "fact_find_summary",
    "attitude_to_risk_profile",
    "risk_profile_assessment",
)
_POST_RISK_BASE_WORKFLOW_STEPS = (
    "capacity_for_loss_assessment",
    "consumer_duty_support_assessment",
)
_SUITABILITY_REPORT_WORKFLOW_STEPS = (
    "platform_research",
    "suitability_conclusion",
    "suitability_report_draft",
    "suitability_report_approval",
    "suitability_report_issue",
    "close",
)
_RISK_HANDOFF_WORKFLOW_STEPS = (
    "risk_profile_approval",
    "manual_review",
    "close",
)
_VULNERABILITY_HANDOFF_WORKFLOW_STEPS = (
    "vulnerability_handoff_approval",
    "manual_review",
    "close",
)

_PRE_SUPPORT_AGENT_TASKS = (
    "uc3_advice_scope_classification",
    "uc3_fact_find_summary",
    "uc3_risk_profile_assessment",
)
_SUPPORT_AGENT_TASK = "uc3_consumer_duty_support_assessment"
_SUITABILITY_AGENT_TASK = "uc3_suitability_conclusion"

_RAW_CONTENT_KEYS = frozenset(
    {
        "adviser_note_text",
        "client_name",
        "email_body",
        "health_detail",
        "national_insurance_number",
        "platform_account_number",
        "raw_client_financial_details",
        "raw_suitability_report_text",
        "vulnerability_narrative",
    }
)


def assert_uc3_workflow_progress_evidence(run: CapturedRun) -> list[EvalCheck]:
    """UC3 fixtures must carry workflow step evidence for their branch."""

    if not run.projection_events:
        return [
            EvalCheck(
                "UC3 workflow progress evidence",
                "fail",
                "no workflow progress events captured",
            )
        ]

    required_steps = list(_required_workflow_steps(run))
    completed_steps = _completed_step_set(run)
    failures: list[str] = []
    missing_steps = [step for step in required_steps if step not in completed_steps]
    if missing_steps:
        failures.append(f"missing workflow step completions: {missing_steps}")

    terminal = _terminal_event_type(run)
    if terminal is None:
        failures.append("missing terminal workflow event")

    if failures:
        return [EvalCheck("UC3 workflow progress evidence", "fail", "; ".join(failures))]
    return [
        EvalCheck(
            "UC3 workflow progress evidence",
            "pass",
            f"captured UC3 workflow progress through {required_steps[-1]!r}",
        )
    ]


def assert_uc3_agent_decision_and_transcript_evidence(run: CapturedRun) -> list[EvalCheck]:
    """Required UC3 agent stages must have decision-trail and transcript rows."""

    if not run.decisions:
        return [
            EvalCheck(
                "UC3 agent decision and transcript evidence",
                "fail",
                "no decision-trail rows captured",
            )
        ]

    required_tasks = list(_required_agent_tasks(run))
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
                "UC3 agent decision and transcript evidence",
                "fail",
                "; ".join(failures),
            )
        ]
    return [
        EvalCheck(
            "UC3 agent decision and transcript evidence",
            "pass",
            f"captured decision and transcript evidence for {required_tasks}",
        )
    ]


def assert_uc3_suitability_decision_conduct(run: CapturedRun) -> list[EvalCheck]:
    """UC3 suitability conclusions carry FCA conduct evidence and safe refs."""

    decision = _decision_for_task(run, _SUITABILITY_AGENT_TASK)
    if decision is None:
        if _manual_handoff_required(run):
            return [
                EvalCheck(
                    "UC3 suitability decision conduct",
                    "pass",
                    "suitability decision correctly not reached before manual handoff",
                )
            ]
        if run.terminal_outcome == "failed":
            return [
                EvalCheck(
                    "UC3 suitability decision conduct",
                    "skip",
                    "suitability conclusion did not run because the workflow failed earlier",
                )
            ]
        return [
            EvalCheck(
                "UC3 suitability decision conduct",
                "fail",
                "no uc3_suitability_conclusion decision-trail row found",
            )
        ]

    data = decision.structured_data
    failures: list[str] = []
    missing = [field for field in _REQUIRED_SUITABILITY_FIELDS if not _present(data.get(field))]
    if missing:
        failures.append(f"missing required fields: {missing}")

    conduct_refs = _string_set(data.get("conduct_hook_refs"))
    missing_refs = sorted(_REQUIRED_CONDUCT_REFS - conduct_refs)
    if missing_refs:
        failures.append(f"missing conduct refs: {missing_refs}")

    outcome = _string_value(data.get("suitability_outcome"))
    if outcome == "suitable_subject_to_adviser_approval":
        failures.extend(_positive_suitability_boundary_failures(data))

    raw_fields = sorted(key for key in data if key in _RAW_CONTENT_KEYS)
    if raw_fields:
        failures.append(f"raw content fields present: {raw_fields}")

    if failures:
        return [
            EvalCheck(
                "UC3 suitability decision conduct",
                "fail",
                "; ".join(failures),
            )
        ]
    return [
        EvalCheck(
            "UC3 suitability decision conduct",
            "pass",
            f"suitability decision {outcome!r} carries safe FCA conduct evidence",
        )
    ]


def assert_uc3_manual_handoff_boundaries(run: CapturedRun) -> list[EvalCheck]:
    """Risk-profile and vulnerability approval points route to manual evidence."""

    if not _manual_handoff_required(run):
        return []

    failures: list[str] = []
    if _tool_actions_for(run, "suitability_report.issue"):
        failures.append("manual-handoff run reached suitability_report.issue")

    manual_review = [
        action
        for action in _tool_actions_for(run, "suitability_report.route_manual_review")
        if action.enforced_mode == "write" and action.verdict == "allow"
    ]
    if not manual_review:
        failures.append("manual-handoff run lacks suitability_report.route_manual_review evidence")

    terminal_markers = {run.terminal_outcome, _use_case_outcome(run)}
    if not terminal_markers.intersection({"approval_required", "manual_review"}):
        failures.append("manual-handoff run did not finish as approval_required or manual_review")

    if failures:
        return [EvalCheck("UC3 manual handoff boundaries", "fail", "; ".join(failures))]
    return [
        EvalCheck(
            "UC3 manual handoff boundaries",
            "pass",
            "risk-profile or vulnerability approval point routes to manual-review evidence",
        )
    ]


def assert_uc3_suitability_report_issue_approval_gate(run: CapturedRun) -> list[EvalCheck]:
    """UC3 suitability-report issue is always approval-gated before effect."""

    if _manual_handoff_required(run):
        return []

    decision = _decision_for_task(run, _SUITABILITY_AGENT_TASK)
    decision_outcome = (
        _string_value(decision.structured_data.get("suitability_outcome"))
        if decision is not None
        else ""
    )
    use_case_outcome = _use_case_outcome(run)
    terminal = run.terminal_outcome
    issue_relevant = (
        _is_suitability_report_path(run)
        or decision_outcome in _SUITABILITY_REPORT_RELEVANT_OUTCOMES
        or use_case_outcome in (_SUITABILITY_REPORT_RELEVANT_OUTCOMES | _COMPLETED_OUTCOMES)
        or terminal in (_SUITABILITY_REPORT_RELEVANT_OUTCOMES | _COMPLETED_OUTCOMES)
    )
    if not issue_relevant:
        return []

    issue_actions = _tool_actions_for(run, "suitability_report.issue")
    package_requests = [
        action
        for action in issue_actions
        if action.requested_mode == "write"
        and action.enforced_mode == "write"
        and action.verdict == "approval_required"
        and action.approval_required
        and action.approval_granted is None
    ]
    approved_applies = [
        action
        for action in issue_actions
        if action.requested_mode == "write"
        and action.enforced_mode == "write"
        and action.verdict == "allow"
        and action.approval_required
        and action.approval_granted is True
    ]

    failures: list[str] = []
    if not package_requests:
        failures.append("no approval_required package request for suitability_report.issue")
    else:
        package_request = package_requests[-1]
        request_output = package_request.output
        if request_output.get("requested_action") != "suitability_report.issue.write":
            failures.append("issue approval package missing requested_action ref")
        if not _string_value(request_output.get("approval_id")):
            failures.append("issue approval package missing approval_id")
        if not package_request.approval_package:
            failures.append("issue approval package table evidence missing")
        elif package_request.approval_package.get("requested_action") != (
            "suitability_report.issue.write"
        ):
            failures.append("issue approval package table row has wrong requested_action")

    waiting = (
        terminal in _APPROVAL_WAITING_OUTCOMES
        or use_case_outcome in _APPROVAL_WAITING_OUTCOMES
        or decision_outcome == "approval_required"
        or "approval_gated" in use_case_outcome
        or "approval_required" in use_case_outcome
    )
    completed = terminal in _COMPLETED_OUTCOMES or use_case_outcome in _COMPLETED_OUTCOMES
    if completed and not approved_applies:
        failures.append("completed suitability run lacks approved suitability_report.issue apply")
    if waiting and approved_applies:
        failures.append("approval-waiting outcome already contains issue apply")

    for action in issue_actions:
        raw_output_keys = sorted(key for key in action.output if key in _RAW_CONTENT_KEYS)
        if raw_output_keys:
            failures.append(f"issue action output carried raw content fields: {raw_output_keys}")

    if failures:
        return [
            EvalCheck(
                "UC3 suitability-report issue approval gate",
                "fail",
                "; ".join(failures),
            )
        ]
    return [
        EvalCheck(
            "UC3 suitability-report issue approval gate",
            "pass",
            "suitability_report.issue has an approval package request and required apply state",
        )
    ]


def assert_uc3_connector_ref_evidence(run: CapturedRun) -> list[EvalCheck]:
    """UC3 connector actions expose safe refs for risk, research, report, and handoff."""

    if not run.tool_actions:
        return [
            EvalCheck(
                "UC3 connector ref evidence",
                "fail",
                "no tool-action audit rows captured",
            )
        ]

    expected: dict[str, tuple[str, tuple[str, ...]]] = {
        "attitude_to_risk.profile": ("read", ("risk_profile_ref",)),
    }
    if not _is_risk_profile_handoff_branch(run):
        expected["capacity_for_loss.assess"] = ("read", ("capacity_for_loss_ref",))
    if _manual_handoff_required(run):
        expected["suitability_report.route_manual_review"] = ("write", ("handoff_ref",))
    elif _is_suitability_report_path(run):
        expected.update(
            {
                "platform_research.run": ("read", ("platform_research_ref",)),
                "suitability_report.draft": (
                    "write",
                    ("suitability_report_ref", "draft_ref"),
                ),
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

    if _manual_handoff_required(run):
        if _tool_actions_for(run, "suitability_report.draft"):
            failures.append("manual-handoff run reached suitability_report.draft")
    elif _is_suitability_report_path(run):
        issue = _last_tool_action_for(run, "suitability_report.issue", mode="write")
        if issue is None:
            failures.append("missing suitability_report.issue write action")
        elif issue.verdict == "approval_required":
            if not _string_value(issue.output.get("approval_id")):
                failures.append("suitability_report.issue approval output missing approval_id")
        elif issue.verdict == "allow":
            if not _string_value(issue.output.get("issue_record_ref")):
                failures.append("suitability_report.issue output missing issue_record_ref")
        else:
            failures.append(f"suitability_report.issue verdict={issue.verdict!r}")

    if failures:
        return [EvalCheck("UC3 connector ref evidence", "fail", "; ".join(failures))]
    return [
        EvalCheck(
            "UC3 connector ref evidence",
            "pass",
            "UC3 connector actions carry safe risk, research, draft, issue, or handoff refs",
        )
    ]


UC3_CONDUCT_INVARIANTS = (
    assert_uc3_workflow_progress_evidence,
    assert_uc3_agent_decision_and_transcript_evidence,
    assert_uc3_suitability_decision_conduct,
    assert_uc3_manual_handoff_boundaries,
    assert_uc3_suitability_report_issue_approval_gate,
    assert_uc3_connector_ref_evidence,
)


def _required_workflow_steps(run: CapturedRun) -> tuple[str, ...]:
    if _is_risk_profile_handoff_branch(run):
        return _PRE_RISK_WORKFLOW_STEPS + _RISK_HANDOFF_WORKFLOW_STEPS
    if _is_vulnerability_handoff_branch(run):
        return (
            _PRE_RISK_WORKFLOW_STEPS
            + _POST_RISK_BASE_WORKFLOW_STEPS
            + _VULNERABILITY_HANDOFF_WORKFLOW_STEPS
        )
    if _is_suitability_report_path(run):
        return (
            _PRE_RISK_WORKFLOW_STEPS
            + _POST_RISK_BASE_WORKFLOW_STEPS
            + _SUITABILITY_REPORT_WORKFLOW_STEPS
        )
    return (*_PRE_RISK_WORKFLOW_STEPS, "close")


def _required_agent_tasks(run: CapturedRun) -> tuple[str, ...]:
    if _is_risk_profile_handoff_branch(run):
        return _PRE_SUPPORT_AGENT_TASKS
    if _is_vulnerability_handoff_branch(run):
        return (*_PRE_SUPPORT_AGENT_TASKS, _SUPPORT_AGENT_TASK)
    if _is_suitability_report_path(run):
        return (*_PRE_SUPPORT_AGENT_TASKS, _SUPPORT_AGENT_TASK, _SUITABILITY_AGENT_TASK)
    return _PRE_SUPPORT_AGENT_TASKS


def _positive_suitability_boundary_failures(data: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if _string_value(data.get("risk_profile_status")) != "aligned":
        failures.append("positive suitability requires aligned risk profile")
    if _string_value(data.get("capacity_for_loss_status")) != "adequate":
        failures.append("positive suitability requires adequate capacity for loss")
    if _string_value(data.get("product_universe_coverage")) != "sufficient_independent_range":
        failures.append("positive suitability requires sufficient independent-advice range")
    if _string_value(data.get("target_market_status")) != "in_target_market":
        failures.append("positive suitability requires in-target-market evidence")
    if _string_value(data.get("support_status")) != "clear":
        failures.append("positive suitability requires clear support / vulnerability state")
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
    return next(
        (
            event.event_type
            for event in reversed(run.projection_events)
            if event.event_type in {"workflow.completed", "workflow.escalated", "workflow.failed"}
        ),
        None,
    )


def _manual_handoff_required(run: CapturedRun) -> bool:
    return _is_risk_profile_handoff_branch(run) or _is_vulnerability_handoff_branch(run)


def _is_risk_profile_handoff_branch(run: CapturedRun) -> bool:
    if "risk_profile_approval" in _completed_step_set(run):
        return True
    decision = _decision_for_task(run, "uc3_risk_profile_assessment")
    if (
        decision is not None
        and _string_value(decision.structured_data.get("risk_profile_status"))
        in _RISK_APPROVAL_STATUSES
    ):
        return True
    return "risk_profile" in _use_case_outcome(run) and "approval" in _use_case_outcome(run)


def _is_vulnerability_handoff_branch(run: CapturedRun) -> bool:
    if "vulnerability_handoff_approval" in _completed_step_set(run):
        return True
    decision = _decision_for_task(run, _SUPPORT_AGENT_TASK)
    if (
        decision is not None
        and _string_value(decision.structured_data.get("support_status"))
        in _SUPPORT_APPROVAL_STATUSES
    ):
        return True
    outcome = _use_case_outcome(run)
    return "vulnerability" in outcome or "support_handoff" in outcome


def _is_suitability_report_path(run: CapturedRun) -> bool:
    steps = _completed_step_set(run)
    if steps.intersection({"suitability_report_approval", "suitability_report_issue"}):
        return True
    decision = _decision_for_task(run, _SUITABILITY_AGENT_TASK)
    if (
        decision is not None
        and _string_value(decision.structured_data.get("suitability_outcome"))
        in _SUITABILITY_REPORT_RELEVANT_OUTCOMES
    ):
        return True
    outcome = _use_case_outcome(run)
    return "suitability_report" in outcome or "suitable" in outcome


def _use_case_outcome(run: CapturedRun) -> str:
    value = run.fixture.expected.use_case_outcome
    return str(getattr(value, "value", value)) if value is not None else ""


def _string_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    items = cast(list[Any], value)
    return {item for item in items if isinstance(item, str)}


def _string_value(value: object) -> str:
    return value if isinstance(value, str) else ""


def _present(value: object) -> bool:
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, list):
        return bool(cast(list[Any], value))
    return value is not None


__all__ = [
    "UC3_CONDUCT_INVARIANTS",
    "assert_uc3_agent_decision_and_transcript_evidence",
    "assert_uc3_connector_ref_evidence",
    "assert_uc3_manual_handoff_boundaries",
    "assert_uc3_suitability_decision_conduct",
    "assert_uc3_suitability_report_issue_approval_gate",
    "assert_uc3_workflow_progress_evidence",
]

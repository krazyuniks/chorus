"""UC2 conduct invariant assertions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from chorus.eval.types import EvalCheck

if TYPE_CHECKING:
    from chorus.eval.scenario_player import CapturedRun, DecisionTrailRecord, ToolActionRecord


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


def assert_uc2_engagement_decision_conduct(run: CapturedRun) -> list[EvalCheck]:
    """UC2 engagement decisions carry SRA / AML conduct evidence and safe refs."""

    decision = _decision_for_task(run, "uc2_engagement_decision")
    if decision is None:
        if run.terminal_outcome == "failed":
            return [
                EvalCheck(
                    "UC2 engagement decision conduct",
                    "skip",
                    "engagement decision did not run because the workflow failed earlier",
                )
            ]
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
        decision_outcome in (_ACCEPTANCE_OUTCOMES | _APPROVAL_WAITING_OUTCOMES)
        or use_case_outcome in (_ACCEPTANCE_OUTCOMES | _APPROVAL_WAITING_OUTCOMES)
        or terminal in (_ACCEPTANCE_OUTCOMES | _APPROVAL_WAITING_OUTCOMES)
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
        request_output = package_requests[-1].output
        if request_output.get("requested_action") != "engagement_letter.send.write":
            failures.append("send approval package missing requested_action ref")
        if not _string_value(request_output.get("approval_id")):
            failures.append("send approval package missing approval_id")

    waiting = (
        terminal in _APPROVAL_WAITING_OUTCOMES
        or decision_outcome in _APPROVAL_WAITING_OUTCOMES
        or use_case_outcome in _APPROVAL_WAITING_OUTCOMES
    )
    completed_acceptance = (
        terminal in _ACCEPTANCE_OUTCOMES
        or use_case_outcome in _ACCEPTANCE_OUTCOMES
        or decision_outcome == "accept_for_engagement"
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

    decision = _decision_for_task(run, "uc2_engagement_decision")
    if decision is None:
        return []
    outcome = _string_value(decision.structured_data.get("engagement_outcome"))
    if outcome not in _ACCEPTANCE_OUTCOMES:
        return []

    expected = {
        "conflict_check.search": ("read", ("conflict_check_ref",)),
        "kyc_bo.lookup": ("read", ("cdd_record_ref", "beneficial_ownership_snapshot_ref")),
        "aml_record_store.record_assessment": ("write", ("aml_risk_assessment_ref",)),
        "engagement_letter.draft": ("write", ("engagement_letter_ref", "draft_ref")),
        "engagement_letter.send": ("write", ("send_record_ref",)),
    }
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

    if failures:
        return [EvalCheck("UC2 connector ref evidence", "fail", "; ".join(failures))]
    return [
        EvalCheck(
            "UC2 connector ref evidence",
            "pass",
            "UC2 connector actions carry safe conflict, AML, draft, and send refs",
        )
    ]


UC2_CONDUCT_INVARIANTS = (
    assert_uc2_engagement_decision_conduct,
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
    "assert_uc2_connector_ref_evidence",
    "assert_uc2_engagement_decision_conduct",
    "assert_uc2_engagement_letter_send_approval_gate",
]

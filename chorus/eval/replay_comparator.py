"""Tiered replay-eval comparator classification helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

from jsonschema import Draft202012Validator

from chorus.llm_provider import InvocationResult

ComparatorStatus = Literal["pass", "fail", "skipped", "error"]

HARD_FAIL_TIER = "hard_fail"
DECISION_FAIL_TIER = "decision_fail"
REQUIRED_UC1_CONDUCT_HOOKS: tuple[str, ...] = (
    "best_interests_check",
    "demands_and_needs_statement",
    "target_market_check",
    "foreseeable_harm_check",
)
_UC1_ROUTE_CATEGORY_FIELDS: tuple[str, ...] = (
    "qualification_verdict_category",
    "verdict_category",
    "routing_category",
    "route_category",
)
_UC1_REGULATED_OUTCOME_FIELDS: tuple[tuple[str, ...], ...] = (
    ("conduct_hooks_pass",),
    ("best_interests_check", "status"),
    ("demands_and_needs_statement", "captured"),
    ("target_market_check", "status"),
    ("foreseeable_harm_check", "status"),
)
_APPROVAL_DECISION_FIELDS: tuple[tuple[str, ...], ...] = (
    ("approval_required",),
    ("approval_granted",),
    ("approval_decision",),
    ("required_approval_decision",),
    ("human_approval_required",),
    ("gateway_verdict",),
)
_CONNECTOR_ACTION_CATEGORY_FIELDS: tuple[tuple[str, ...], ...] = (
    ("connector_action_category",),
    ("tool_action_category",),
    ("tool_name",),
    ("requested_mode",),
    ("enforced_mode",),
)
_UC1_CONNECTOR_ACTION_BY_ROUTE_CATEGORY = {
    "accept": "crm.route_to_quoting_queue.write",
    "refer": "referral_inbox.route.write",
    "decline": "decline_ledger.route.write",
    "missing_data": "outbound_comms.message.propose",
}


@dataclass(frozen=True)
class HardFailClassification:
    """Safe hard-fail outcome details for a replay-run comparator record."""

    reason_code: str
    field_names: tuple[str, ...]
    status: Literal["fail", "error"] = "fail"
    safe_error_reason: str | None = None
    provider_error_reason: str | None = None
    error_count: int | None = None

    def result_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tier": HARD_FAIL_TIER,
            "reason_code": self.reason_code,
            "field_names": list(self.field_names),
            "changed_field_names": [],
        }
        if self.provider_error_reason is not None:
            payload["provider_error_reason"] = self.provider_error_reason
        if self.error_count is not None:
            payload["error_count"] = self.error_count
        return payload


@dataclass(frozen=True)
class DecisionFailClassification:
    """Safe decision-fail outcome details for a replay-run comparator record."""

    reason_code: str
    field_names: tuple[str, ...]
    reason_codes: tuple[str, ...] = ()

    def result_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tier": DECISION_FAIL_TIER,
            "reason_code": self.reason_code,
            "field_names": list(self.field_names),
            "changed_field_names": list(self.field_names),
        }
        if self.reason_codes:
            payload["reason_codes"] = list(self.reason_codes)
        return payload


def classify_replay_input_hard_failure(
    *,
    policy_snapshot_ref: str | None,
    evidence_missing_fields: tuple[str, ...],
) -> HardFailClassification | None:
    """Classify missing replay lineage before invoking an alternate route."""

    if evidence_missing_fields:
        return HardFailClassification(
            reason_code="missing_audit_transcript_evidence",
            field_names=tuple(sorted(set(evidence_missing_fields))),
        )
    if not _non_empty_string(policy_snapshot_ref):
        return HardFailClassification(
            reason_code="missing_policy_snapshot_evidence",
            field_names=("lineage.policy_snapshot_ref",),
        )
    return None


def classify_replay_result_hard_failure(
    *,
    task_kind: str,
    result: InvocationResult,
    response_shape: dict[str, Any],
) -> HardFailClassification | None:
    """Classify replay output defects that are hard failures, not review findings."""

    if result.tool_calls:
        return HardFailClassification(
            reason_code="unsafe_action_proposal",
            field_names=("tool_calls",),
        )

    structured_data = result.structured_data
    if task_kind == "enquiry_qualification":
        policy_snapshot_ref = structured_data.get("policy_snapshot_ref")
        if not _non_empty_string(policy_snapshot_ref):
            return HardFailClassification(
                reason_code="missing_policy_snapshot_evidence",
                field_names=("structured_data.policy_snapshot_ref",),
            )

        missing_hooks = tuple(
            f"structured_data.{hook}"
            for hook in REQUIRED_UC1_CONDUCT_HOOKS
            if not isinstance(structured_data.get(hook), dict)
        )
        if missing_hooks:
            return HardFailClassification(
                reason_code="missing_conduct_hooks",
                field_names=missing_hooks,
            )

    schema_errors = _schema_error_field_names(
        schema=_response_schema(response_shape),
        value=_result_envelope(result),
    )
    if schema_errors:
        return HardFailClassification(
            reason_code="schema_invalid_replay_output",
            field_names=schema_errors,
            error_count=len(schema_errors),
        )
    return None


def classify_replay_decision_failure(
    *,
    task_kind: str,
    policy_snapshot_ref: str | None,
    expected_structured_data: dict[str, Any],
    actual_structured_data: dict[str, Any],
) -> DecisionFailClassification | None:
    """Classify bounded business-decision divergence after hard-fail checks."""

    if task_kind != "enquiry_qualification":
        return None
    if not _same_policy_snapshot(
        policy_snapshot_ref=policy_snapshot_ref,
        expected_structured_data=expected_structured_data,
        actual_structured_data=actual_structured_data,
    ):
        return None

    mismatch_groups: list[tuple[str, tuple[str, ...]]] = []

    expected_route = _uc1_route_category(expected_structured_data)
    actual_route = _uc1_route_category(actual_structured_data)
    if (
        expected_route.category is not None
        and actual_route.category is not None
        and expected_route.category != actual_route.category
    ):
        field_names = tuple(sorted(set(expected_route.field_names + actual_route.field_names)))
        connector_field_names = _derived_connector_action_field_names(
            expected_route.category,
            actual_route.category,
        )
        mismatch_groups.append(
            (
                _route_category_reason_code(field_names),
                tuple(sorted(set(field_names + connector_field_names))),
            )
        )

    regulated_fields = _changed_field_names(
        expected_structured_data,
        actual_structured_data,
        _UC1_REGULATED_OUTCOME_FIELDS,
        require_both_present=True,
    )
    if regulated_fields:
        mismatch_groups.append(("regulated_outcome_mismatch", regulated_fields))

    approval_fields = _changed_field_names(
        expected_structured_data,
        actual_structured_data,
        _APPROVAL_DECISION_FIELDS,
        require_both_present=True,
    )
    if approval_fields:
        mismatch_groups.append(("required_approval_decision_mismatch", approval_fields))

    connector_fields = _changed_field_names(
        expected_structured_data,
        actual_structured_data,
        _CONNECTOR_ACTION_CATEGORY_FIELDS,
        require_both_present=True,
    )
    if connector_fields:
        mismatch_groups.append(("connector_action_category_mismatch", connector_fields))

    if not mismatch_groups:
        return None

    reason_codes = tuple(reason for reason, _fields in mismatch_groups)
    field_names = tuple(sorted({field for _reason, fields in mismatch_groups for field in fields}))
    return DecisionFailClassification(
        reason_code=reason_codes[0],
        reason_codes=reason_codes,
        field_names=field_names,
    )


def provider_port_error_hard_failure(reason: str) -> HardFailClassification:
    """Classify an LLM-provider replay error without leaking provider content."""

    safe_reason = safe_reason_code(reason)
    return HardFailClassification(
        reason_code="provider_port_replay_error",
        field_names=(),
        status="error",
        safe_error_reason=safe_reason,
        provider_error_reason=safe_reason,
    )


def safe_reason_code(reason: str) -> str:
    """Bound provider reasons to the replay-run safe reason alphabet."""

    return "".join(character for character in reason if character.isalnum() or character in ":_.-")


def _result_envelope(result: InvocationResult) -> dict[str, Any]:
    return {
        "summary": result.summary,
        "confidence": result.confidence,
        "structured_data": result.structured_data,
        "recommended_next_step": result.recommended_next_step,
        "rationale": result.rationale,
    }


def _response_schema(response_shape: dict[str, Any]) -> dict[str, Any]:
    schema = response_shape.get("schema")
    if not isinstance(schema, dict):
        return {}
    return cast(dict[str, Any], schema)


def _schema_error_field_names(*, schema: dict[str, Any], value: dict[str, Any]) -> tuple[str, ...]:
    raw_errors = cast(Any, Draft202012Validator(schema)).iter_errors(value)
    errors = sorted(
        raw_errors,
        key=lambda error: tuple(str(part) for part in getattr(error, "path", ())),
    )
    fields: list[str] = []
    for error in errors:
        fields.extend(_field_names_for_error(error))
    return tuple(sorted(set(fields)))


def _field_names_for_error(error: Any) -> tuple[str, ...]:
    path = tuple(str(part) for part in getattr(error, "path", ()))
    validator = getattr(error, "validator", None)
    instance = getattr(error, "instance", None)
    schema = getattr(error, "schema", {})

    if validator == "required" and isinstance(instance, dict):
        required = getattr(error, "validator_value", ())
        if isinstance(required, list | tuple):
            required_values = cast(list[object] | tuple[object, ...], required)
            required_fields = [str(field) for field in required_values]
            instance_fields = cast(dict[str, Any], instance)
            missing = sorted(field for field in required_fields if field not in instance_fields)
            return tuple(_join_path(path, field) for field in missing)

    if (
        validator == "additionalProperties"
        and isinstance(instance, dict)
        and isinstance(schema, dict)
    ):
        schema_fields = cast(dict[str, Any], schema)
        properties = schema_fields.get("properties")
        if isinstance(properties, dict):
            allowed_fields = cast(dict[str, Any], properties)
            instance_fields = cast(dict[str, Any], instance)
            extra = sorted(str(field) for field in instance_fields if field not in allowed_fields)
            return tuple(_join_path(path, field) for field in extra)

    return (_join_path(path, None),)


def _join_path(path: tuple[str, ...], field: str | None) -> str:
    parts = (*path, field) if field is not None else path
    return ".".join(part for part in parts if part) or "root"


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


@dataclass(frozen=True)
class _RouteCategory:
    category: str | None
    field_names: tuple[str, ...]


def _same_policy_snapshot(
    *,
    policy_snapshot_ref: str | None,
    expected_structured_data: dict[str, Any],
    actual_structured_data: dict[str, Any],
) -> bool:
    expected_ref = _optional_string(expected_structured_data.get("policy_snapshot_ref"))
    actual_ref = _optional_string(actual_structured_data.get("policy_snapshot_ref"))
    reference_ref = _optional_string(policy_snapshot_ref) or expected_ref
    if reference_ref is None or actual_ref is None:
        return False
    if expected_ref is not None and expected_ref != reference_ref:
        return False
    return actual_ref == reference_ref


def _uc1_route_category(data: dict[str, Any]) -> _RouteCategory:
    observed_fields: list[str] = []
    for field_name in _UC1_ROUTE_CATEGORY_FIELDS:
        if field_name in data:
            observed_fields.append(f"structured_data.{field_name}")
            category = _normalise_route_category(data.get(field_name))
            if category is not None:
                return _RouteCategory(category=category, field_names=tuple(observed_fields))
    if _has_missing_data_signal(data):
        return _RouteCategory(
            category="missing_data",
            field_names=("structured_data.missing_data_request_required",),
        )
    return _RouteCategory(category=None, field_names=tuple(observed_fields))


def _normalise_route_category(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalised = value.strip().lower().replace("-", "_").replace(" ", "_")
    match normalised:
        case "accept" | "accepted" | "accepted_for_quoting" | "quote":
            return "accept"
        case "refer" | "referred" | "referral" | "refer_to_underwriter":
            return "refer"
        case "decline" | "declined" | "declined_to_quote":
            return "decline"
        case (
            "missing_data"
            | "missingdata"
            | "missing_data_request"
            | "request_missing_data"
            | "needs_missing_data"
        ):
            return "missing_data"
        case _:
            return None


def _has_missing_data_signal(data: dict[str, Any]) -> bool:
    required = data.get("missing_data_request_required")
    if isinstance(required, bool) and required:
        return True
    fields = data.get("missing_data_fields")
    if not isinstance(fields, list):
        return False
    fields_list = cast(list[object], fields)
    return len(fields_list) > 0


def _route_category_reason_code(field_names: tuple[str, ...]) -> str:
    if "structured_data.qualification_verdict_category" in field_names:
        return "terminal_verdict_mismatch"
    return "route_category_mismatch"


def _derived_connector_action_field_names(
    expected_category: str,
    actual_category: str,
) -> tuple[str, ...]:
    expected_action = _UC1_CONNECTOR_ACTION_BY_ROUTE_CATEGORY.get(expected_category)
    actual_action = _UC1_CONNECTOR_ACTION_BY_ROUTE_CATEGORY.get(actual_category)
    if expected_action is None or actual_action is None or expected_action == actual_action:
        return ()
    return ("derived.connector_action_category",)


def _changed_field_names(
    expected: dict[str, Any],
    actual: dict[str, Any],
    field_paths: tuple[tuple[str, ...], ...],
    *,
    require_both_present: bool,
) -> tuple[str, ...]:
    changed: list[str] = []
    for path in field_paths:
        expected_present, expected_value = _path_value(expected, path)
        actual_present, actual_value = _path_value(actual, path)
        if require_both_present and not (expected_present and actual_present):
            continue
        if not require_both_present and not (expected_present or actual_present):
            continue
        if expected_value != actual_value:
            changed.append(_field_name(path))
    return tuple(sorted(set(changed)))


def _path_value(data: dict[str, Any], path: tuple[str, ...]) -> tuple[bool, object]:
    current: object = data
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return False, None
        current_mapping = cast(dict[str, object], current)
        current = current_mapping[part]
    return True, current


def _field_name(path: tuple[str, ...]) -> str:
    return "structured_data." + ".".join(path)


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


__all__ = [
    "DECISION_FAIL_TIER",
    "HARD_FAIL_TIER",
    "REQUIRED_UC1_CONDUCT_HOOKS",
    "ComparatorStatus",
    "DecisionFailClassification",
    "HardFailClassification",
    "classify_replay_decision_failure",
    "classify_replay_input_hard_failure",
    "classify_replay_result_hard_failure",
    "provider_port_error_hard_failure",
    "safe_reason_code",
]

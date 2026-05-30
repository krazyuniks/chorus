"""Tiered replay-eval comparator classification helpers."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, cast

from jsonschema import Draft202012Validator

from chorus.llm_provider import InvocationResult

ComparatorStatus = Literal["pass", "fail", "skipped", "error"]

HARD_FAIL_TIER = "hard_fail"
DECISION_FAIL_TIER = "decision_fail"
REVIEW_FINDING_TIER = "review_finding"
METRICS_ONLY_TIER = "metrics_only"


def _provider_metadata_field_name(path: tuple[str, ...]) -> str:
    return "provider_metadata." + ".".join(path)


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
_UC1_OPTIONAL_REVIEW_FIELDS: tuple[tuple[str, ...], ...] = (
    ("customer_ref",),
    ("verdict_ref",),
    ("routing_policy_ref",),
    ("product_family_category",),
    ("qualification_summary_ref",),
    ("referral_destination_category",),
    ("referral_reason_category",),
    ("decline_reason_category",),
)
_UC1_EVIDENCE_SELECTION_FIELDS: tuple[tuple[str, ...], ...] = (
    ("best_interests_check", "regulatory_ref"),
    ("demands_and_needs_statement", "regulatory_ref"),
    ("target_market_check", "regulatory_ref"),
    ("foreseeable_harm_check", "regulatory_ref"),
)
_UC1_CONNECTOR_ACTION_BY_ROUTE_CATEGORY = {
    "accept": "crm.route_to_quoting_queue.write",
    "refer": "referral_inbox.route.write",
    "decline": "decline_ledger.route.write",
    "missing_data": "outbound_comms.message.propose",
}
_CONFIDENCE_DELTA_THRESHOLD = 0.15
_TOKEN_USAGE_FIELDS: tuple[str, ...] = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
)
_PROVIDER_RETRY_METADATA_PATHS: tuple[tuple[str, ...], ...] = (
    ("retry_count",),
    ("retry_attempts",),
    ("attempt_count",),
    ("retries",),
)
_SAFE_PROVIDER_METADATA_PATHS: tuple[tuple[str, ...], ...] = (
    ("adapter",),
    ("model",),
    ("finish_reason",),
    ("response_format_type",),
    ("response_schema", "name"),
    ("response_schema", "contract_ref"),
    ("response_schema", "task_kind"),
    ("response_schema", "strict"),
    ("response_schema", "source"),
    ("response_schema", "hash"),
    ("response_schema", "response_format_type"),
)
_METRICS_COMPARED_FIELD_NAMES: tuple[str, ...] = (
    "metrics.cost_amount_usd",
    "metrics.latency_ms",
    *tuple(f"metrics.token_usage.{field_name}" for field_name in _TOKEN_USAGE_FIELDS),
    *tuple(_provider_metadata_field_name(path) for path in _PROVIDER_RETRY_METADATA_PATHS),
    *tuple(_provider_metadata_field_name(path) for path in _SAFE_PROVIDER_METADATA_PATHS),
)


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


@dataclass(frozen=True)
class ReviewFindingClassification:
    """Safe non-terminal review-finding details for a replay-run comparator record."""

    reason_code: str
    field_names: tuple[str, ...]
    reason_codes: tuple[str, ...] = ()

    def result_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tier": REVIEW_FINDING_TIER,
            "reason_code": self.reason_code,
            "field_names": list(self.field_names),
            "changed_field_names": list(self.field_names),
            "non_terminal": True,
        }
        if self.reason_codes:
            payload["reason_codes"] = list(self.reason_codes)
        return payload


@dataclass(frozen=True)
class MetricsOnlyClassification:
    """Safe metrics-only replay details after semantic replay tiers pass."""

    reason_code: str
    field_names: tuple[str, ...]
    reason_codes: tuple[str, ...] = ()
    compared_field_names: tuple[str, ...] = _METRICS_COMPARED_FIELD_NAMES

    def result_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tier": METRICS_ONLY_TIER,
            "reason_code": self.reason_code,
            "field_names": list(self.field_names),
            "changed_field_names": list(self.field_names),
            "compared_field_names": list(self.compared_field_names),
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

    regulated_fields = _changed_uc1_regulated_outcome_field_names(
        expected_structured_data,
        actual_structured_data,
    )
    if regulated_fields and not _same_non_terminal_missing_data_route(
        expected_route,
        actual_route,
    ):
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


def classify_replay_review_finding(
    *,
    task_kind: str,
    policy_snapshot_ref: str | None,
    expected_structured_data: dict[str, Any],
    actual_structured_data: dict[str, Any],
    expected_recommended_next_step: str | None,
    actual_recommended_next_step: str,
    expected_confidence: float | None,
    actual_confidence: float,
    expected_rationale: str | None,
    actual_rationale: str,
) -> ReviewFindingClassification | None:
    """Classify non-terminal UC1 replay divergence for reviewer attention."""

    if task_kind != "enquiry_qualification":
        return None
    if not _same_policy_snapshot(
        policy_snapshot_ref=policy_snapshot_ref,
        expected_structured_data=expected_structured_data,
        actual_structured_data=actual_structured_data,
    ):
        return None
    if not _same_uc1_route_category(expected_structured_data, actual_structured_data):
        return None
    if _changed_uc1_regulated_outcome_field_names(
        expected_structured_data,
        actual_structured_data,
    ):
        return None
    if _changed_field_names(
        expected_structured_data,
        actual_structured_data,
        _APPROVAL_DECISION_FIELDS,
        require_both_present=True,
    ):
        return None
    if _changed_field_names(
        expected_structured_data,
        actual_structured_data,
        _CONNECTOR_ACTION_CATEGORY_FIELDS,
        require_both_present=True,
    ):
        return None

    mismatch_groups: list[tuple[str, tuple[str, ...]]] = []
    if (
        expected_recommended_next_step is not None
        and expected_recommended_next_step != actual_recommended_next_step
    ):
        mismatch_groups.append(("recommended_next_step_mismatch", ("recommended_next_step",)))

    confidence_reason = _confidence_review_reason(expected_confidence, actual_confidence)
    if confidence_reason is not None:
        mismatch_groups.append((confidence_reason, ("confidence",)))

    rationale_reason = _rationale_review_reason(expected_rationale, actual_rationale)
    if rationale_reason is not None:
        mismatch_groups.append((rationale_reason, ("rationale",)))

    optional_fields = _changed_field_names(
        expected_structured_data,
        actual_structured_data,
        _UC1_OPTIONAL_REVIEW_FIELDS,
        require_both_present=False,
    )
    if optional_fields:
        mismatch_groups.append(("optional_structured_field_mismatch", optional_fields))

    evidence_fields = _changed_field_names(
        expected_structured_data,
        actual_structured_data,
        _UC1_EVIDENCE_SELECTION_FIELDS,
        require_both_present=True,
    )
    if evidence_fields:
        mismatch_groups.append(("evidence_selection_mismatch", evidence_fields))

    if not mismatch_groups:
        return None

    reason_codes = tuple(reason for reason, _fields in mismatch_groups)
    field_names = tuple(sorted({field for _reason, fields in mismatch_groups for field in fields}))
    return ReviewFindingClassification(
        reason_code=reason_codes[0],
        reason_codes=reason_codes,
        field_names=field_names,
    )


def classify_replay_metrics_only(
    *,
    original_cost_amount_usd: Decimal,
    alternate_cost_amount_usd: Decimal,
    original_latency_ms: int,
    alternate_latency_ms: int,
    original_token_usage: dict[str, int],
    alternate_token_usage: dict[str, int],
    original_provider_metadata: dict[str, Any],
    alternate_provider_metadata: dict[str, Any],
) -> MetricsOnlyClassification:
    """Classify safe metric/provider-metadata deltas after semantics agree."""

    mismatch_groups: list[tuple[str, tuple[str, ...]]] = []

    if alternate_cost_amount_usd != original_cost_amount_usd:
        mismatch_groups.append(("cost_amount_delta", ("metrics.cost_amount_usd",)))

    if alternate_latency_ms != original_latency_ms:
        mismatch_groups.append(("latency_delta", ("metrics.latency_ms",)))

    token_fields = _changed_token_usage_field_names(
        original_token_usage,
        alternate_token_usage,
    )
    if token_fields:
        mismatch_groups.append(("token_usage_delta", token_fields))

    retry_fields = _changed_provider_metadata_field_names(
        original_provider_metadata,
        alternate_provider_metadata,
        _PROVIDER_RETRY_METADATA_PATHS,
    )
    if retry_fields:
        mismatch_groups.append(("retry_count_delta", retry_fields))

    safe_metadata_fields = _changed_provider_metadata_field_names(
        original_provider_metadata,
        alternate_provider_metadata,
        _SAFE_PROVIDER_METADATA_PATHS,
    )
    if safe_metadata_fields:
        mismatch_groups.append(("provider_metadata_delta", safe_metadata_fields))

    if not mismatch_groups:
        return MetricsOnlyClassification(
            reason_code="metrics_only_no_delta",
            field_names=(),
        )

    reason_codes = tuple(reason for reason, _fields in mismatch_groups)
    field_names = tuple(sorted({field for _reason, fields in mismatch_groups for field in fields}))
    return MetricsOnlyClassification(
        reason_code="metrics_only_delta",
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


def _same_uc1_route_category(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    expected_route = _uc1_route_category(expected)
    actual_route = _uc1_route_category(actual)
    return (
        expected_route.category is not None
        and actual_route.category is not None
        and expected_route.category == actual_route.category
    )


def _same_non_terminal_missing_data_route(
    expected_route: _RouteCategory,
    actual_route: _RouteCategory,
) -> bool:
    return expected_route.category == "missing_data" and actual_route.category == "missing_data"


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


def _changed_uc1_regulated_outcome_field_names(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> tuple[str, ...]:
    changed: list[str] = []
    for path in _UC1_REGULATED_OUTCOME_FIELDS:
        expected_present, expected_value = _path_value(expected, path)
        actual_present, actual_value = _path_value(actual, path)
        if not (expected_present and actual_present):
            continue
        if _normalise_uc1_regulated_outcome_value(path, expected_value) != (
            _normalise_uc1_regulated_outcome_value(path, actual_value)
        ):
            changed.append(_field_name(path))
    return tuple(sorted(set(changed)))


def _normalise_uc1_regulated_outcome_value(
    path: tuple[str, ...],
    value: object,
) -> object:
    if path[-1:] != ("status",) or not isinstance(value, str):
        return value
    normalised = value.strip().lower().replace("-", "_").replace(" ", "_")
    if path[0] == "foreseeable_harm_check" and normalised in {
        "pass",
        "passed",
        "ok",
        "no_harm",
        "no_harm_identified",
        "no_foreseeable_harm",
        "no_foreseeable_harm_identified",
    }:
        return "pass"
    if path[0] in {"best_interests_check", "target_market_check"} and normalised in {
        "pass",
        "passed",
        "ok",
        "aligned",
        "in_scope",
        "partial",
        "pending",
        "pending_data",
        "pending_missing_data",
        "within_target_market",
    }:
        return "pass"
    return normalised


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


def _changed_token_usage_field_names(
    original: dict[str, int],
    alternate: dict[str, int],
) -> tuple[str, ...]:
    changed = [
        f"metrics.token_usage.{field_name}"
        for field_name in _TOKEN_USAGE_FIELDS
        if _token_count(original.get(field_name)) != _token_count(alternate.get(field_name))
    ]
    return tuple(changed)


def _token_count(value: object) -> int:
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _changed_provider_metadata_field_names(
    original: dict[str, Any],
    alternate: dict[str, Any],
    field_paths: tuple[tuple[str, ...], ...],
) -> tuple[str, ...]:
    changed: list[str] = []
    for path in field_paths:
        original_present, original_value = _path_value(original, path)
        alternate_present, alternate_value = _path_value(alternate, path)
        if not (original_present or alternate_present):
            continue
        if _safe_metadata_value(original_value) != _safe_metadata_value(alternate_value):
            changed.append(_provider_metadata_field_name(path))
    return tuple(sorted(set(changed)))


def _safe_metadata_value(value: object) -> object:
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return type(value).__name__


def _confidence_review_reason(
    expected_confidence: float | None,
    actual_confidence: float,
) -> str | None:
    if expected_confidence is None:
        return None
    if _confidence_band(expected_confidence) != _confidence_band(actual_confidence):
        return "confidence_band_mismatch"
    if abs(actual_confidence - expected_confidence) >= _CONFIDENCE_DELTA_THRESHOLD:
        return "confidence_delta_mismatch"
    return None


def _confidence_band(value: float) -> str:
    if value < 0.5:
        return "low"
    if value < 0.8:
        return "medium"
    return "high"


def _rationale_review_reason(
    expected_rationale: str | None,
    actual_rationale: str,
) -> str | None:
    if expected_rationale is None:
        return None
    expected_present = _non_empty_string(expected_rationale)
    actual_present = _non_empty_string(actual_rationale)
    if expected_present != actual_present:
        return "rationale_presence_mismatch"
    if expected_present and actual_present and expected_rationale != actual_rationale:
        return "rationale_text_mismatch"
    return None


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


__all__ = [
    "DECISION_FAIL_TIER",
    "HARD_FAIL_TIER",
    "METRICS_ONLY_TIER",
    "REQUIRED_UC1_CONDUCT_HOOKS",
    "REVIEW_FINDING_TIER",
    "ComparatorStatus",
    "DecisionFailClassification",
    "HardFailClassification",
    "MetricsOnlyClassification",
    "ReviewFindingClassification",
    "classify_replay_decision_failure",
    "classify_replay_input_hard_failure",
    "classify_replay_metrics_only",
    "classify_replay_result_hard_failure",
    "classify_replay_review_finding",
    "provider_port_error_hard_failure",
    "safe_reason_code",
]

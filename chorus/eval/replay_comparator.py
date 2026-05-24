"""Hard-fail tier classification for replay-eval comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

from jsonschema import Draft202012Validator

from chorus.llm_provider import InvocationResult

ComparatorStatus = Literal["pass", "fail", "skipped", "error"]

HARD_FAIL_TIER = "hard_fail"
REQUIRED_UC1_CONDUCT_HOOKS: tuple[str, ...] = (
    "best_interests_check",
    "demands_and_needs_statement",
    "target_market_check",
    "foreseeable_harm_check",
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


__all__ = [
    "HARD_FAIL_TIER",
    "REQUIRED_UC1_CONDUCT_HOOKS",
    "ComparatorStatus",
    "HardFailClassification",
    "classify_replay_input_hard_failure",
    "classify_replay_result_hard_failure",
    "provider_port_error_hard_failure",
    "safe_reason_code",
]

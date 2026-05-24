"""`eval replay` subcommand: re-execute a captured transcript through the
recorded-replay route and verify the structured output matches the original.

ADR 0019 names replay-as-eval-substrate as the cross-provider comparison
mode. R3 ships the deterministic recorded-replay route only; cross-provider
replay (against the OpenAI-compatible adapter) is on the R4 entry list. The
subcommand shape carries the route id so R4 can plug it through without a
CLI rewrite.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any, Literal, cast
from uuid import NAMESPACE_URL, uuid5

from chorus.agent_runtime.response_schemas import (
    response_shape_metadata,
    uc1_response_shape_for_task,
)
from chorus.contracts.generated.eval.replay_run_record import ReplayRunRecord
from chorus.eval.replay_comparator import (
    DecisionFailClassification,
    HardFailClassification,
    classify_replay_decision_failure,
    classify_replay_input_hard_failure,
    classify_replay_result_hard_failure,
    provider_port_error_hard_failure,
    safe_reason_code,
)
from chorus.eval.types import EvalCheck
from chorus.llm_provider import (
    InvocationArgs,
    InvocationMessage,
    InvocationResult,
    LLMProviderInvocationError,
    RouteCatalogue,
    RouteCatalogueEntry,
    default_route_catalogue,
)

_VALID_ROLES = ("system", "user", "assistant", "tool")
_COMPARATOR_NAME = "tiered_replay_comparator"
_COMPARATOR_VERSION = "v0.2-decision-fail"
_UC1_PROMPT_REFERENCES = {
    "classifier": "prompts/uc1/classifier/v1.md",
    "context_gatherer": "prompts/uc1/context-gatherer/v1.md",
    "qualifier": "prompts/uc1/qualifier/v1.md",
    "request_drafter": "prompts/uc1/request-drafter/v1.md",
    "validator": "prompts/uc1/validator/v1.md",
}
_UC1_PROMPT_HASHES = {
    "classifier": "sha256:6e25aca95c76a38b089fedbcac94316a47e18a9d2575089363f5c35f1cbcd67e",
    "context_gatherer": "sha256:ebbbcc8091838ce2962642f3436b1188bef35fe0dc8ab67ededd475aaa683e20",
    "qualifier": "sha256:2877d857fba0d2dc974e73968977dfd5072568b03aca9ed8adb73fab01d17f5f",
    "request_drafter": "sha256:e25a62fe7137f6f88a0987cb9897417532a7a5dc807eb954a48c3b770923bcbd",
    "validator": "sha256:157b1c9e3b0916bed7814bd01e912c62d38b87d4ceee9af25807f7b062fc0743",
}

ComparatorStatus = Literal["pass", "fail", "skipped", "error"]


def _invocation_message(message: dict[str, Any]) -> InvocationMessage:
    role = str(message["role"])
    if role not in _VALID_ROLES:
        raise ValueError(
            f"Captured transcript carries unsupported role {role!r}; expected one of {_VALID_ROLES}"
        )
    return InvocationMessage(role=role, content=str(message["content"]))


@dataclass(frozen=True)
class CapturedTranscript:
    """Captured transcript surface the replay subcommand needs.

    Aligns with :class:`AgentInvocationTranscript` (the audit-port transcript
    contract) but only carries the fields a replay re-execution needs.
    """

    invocation_id: str
    transcript_id: str
    correlation_id: str
    workflow_id: str
    route_id: str
    provider_id: str
    model_id: str
    adapter_version: str
    parameters: dict[str, Any]
    request_messages: list[dict[str, Any]]
    expected_structured_data: dict[str, Any]
    task_kind: str
    agent_role: str
    tenant_id: str
    enquiry_input: dict[str, Any]
    prompt_reference: str
    prompt_hash: str
    policy_snapshot_ref: str | None
    route_version_ref: str | None
    provider_catalogue_id: str | None
    eval_fixture_ref: str | None
    transcript_source_ref: str | None
    original_cost_amount_usd: Decimal
    original_latency_ms: int
    token_usage: dict[str, int]
    evidence_missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReplayRunResult:
    """Replay checks plus the safe evidence record that can be persisted."""

    checks: list[EvalCheck]
    record: ReplayRunRecord


@dataclass(frozen=True)
class _Comparison:
    checks: list[EvalCheck]
    status: ComparatorStatus
    result: dict[str, Any]
    safe_error_reason: str | None = None
    safe_skipped_reason: str | None = None


def load_transcript(path: Path) -> CapturedTranscript:
    """Load a captured transcript JSON fixture."""

    data = json.loads(path.read_text(encoding="utf-8"))
    invocation_id = str(data["invocation_id"])
    agent_role = str(data["agent_role"])
    evidence_missing_fields = _evidence_missing_fields(data)
    return CapturedTranscript(
        invocation_id=invocation_id,
        transcript_id=str(
            data.get("transcript_id")
            or uuid5(NAMESPACE_URL, f"chorus.eval.transcript:{invocation_id}")
        ),
        correlation_id=str(
            data.get("correlation_id") or f"cor_replay_{invocation_id.replace('-', '_')}"
        ),
        workflow_id=str(data.get("workflow_id") or f"eval-replay-{invocation_id}"),
        route_id=str(data["route_id"]),
        provider_id=str(data["provider_id"]),
        model_id=str(data["model_id"]),
        adapter_version=str(data["adapter_version"]),
        parameters=dict(data.get("parameters", {})),
        request_messages=list(data["request_messages"]),
        expected_structured_data=dict(data["expected_structured_data"]),
        task_kind=str(data["task_kind"]),
        agent_role=agent_role,
        tenant_id=str(data["tenant_id"]),
        enquiry_input=dict(data["enquiry_input"]),
        prompt_reference=str(data.get("prompt_reference") or _UC1_PROMPT_REFERENCES[agent_role]),
        prompt_hash=str(data.get("prompt_hash") or _UC1_PROMPT_HASHES[agent_role]),
        policy_snapshot_ref=_optional_str(data.get("policy_snapshot_ref")),
        route_version_ref=_optional_str(data.get("route_version_ref")),
        provider_catalogue_id=_optional_str(data.get("provider_catalogue_id")),
        eval_fixture_ref=_optional_str(data.get("eval_fixture_ref")),
        transcript_source_ref=_optional_str(data.get("transcript_source_ref")),
        original_cost_amount_usd=Decimal(str(data.get("original_cost_amount_usd", "0"))),
        original_latency_ms=int(data.get("original_latency_ms", 0)),
        token_usage=_token_usage(data.get("token_usage")),
        evidence_missing_fields=evidence_missing_fields,
    )


def replay_transcript(
    transcript: CapturedTranscript,
    *,
    route_id: str | None = None,
    route_catalogue: RouteCatalogue | None = None,
) -> list[EvalCheck]:
    """Re-execute a captured transcript through the route catalogue."""

    return replay_transcript_with_record(
        transcript,
        route_id=route_id,
        route_catalogue=route_catalogue,
    ).checks


def replay_transcript_with_record(
    transcript: CapturedTranscript,
    *,
    route_id: str | None = None,
    route_catalogue: RouteCatalogue | None = None,
) -> ReplayRunResult:
    """Replay a transcript and return the checks plus a persistable evidence record."""

    catalogue = route_catalogue or default_route_catalogue()
    target_route = route_id or transcript.route_id
    target_entry = catalogue.get(target_route)
    started_at = datetime.now(UTC)
    input_hard_fail = classify_replay_input_hard_failure(
        policy_snapshot_ref=transcript.policy_snapshot_ref,
        evidence_missing_fields=transcript.evidence_missing_fields,
    )
    if input_hard_fail is not None:
        completed_at = datetime.now(UTC)
        comparison = _hard_fail_comparison(
            transcript=transcript,
            target_route=target_route,
            classification=input_hard_fail,
        )
        return ReplayRunResult(
            checks=comparison.checks,
            record=_replay_run_record(
                transcript=transcript,
                target_entry=target_entry,
                comparison=comparison,
                replay_result=None,
                replay_latency_ms=0,
                started_at=started_at,
                completed_at=completed_at,
            ),
        )
    if target_route == transcript.route_id and (
        target_entry.provider_id != transcript.provider_id
        or target_entry.model_id != transcript.model_id
    ):
        completed_at = datetime.now(UTC)
        comparison = _route_mismatch_comparison(transcript, target_entry)
        return ReplayRunResult(
            checks=comparison.checks,
            record=_replay_run_record(
                transcript=transcript,
                target_entry=target_entry,
                comparison=comparison,
                replay_result=None,
                replay_latency_ms=0,
                started_at=started_at,
                completed_at=completed_at,
            ),
        )
    args = InvocationArgs(
        route_id=target_route,
        messages=tuple(_invocation_message(message) for message in transcript.request_messages),
        response_shape=uc1_response_shape_for_task(transcript.task_kind),
        metadata={
            "task_kind": transcript.task_kind,
            "input": transcript.enquiry_input,
            "agent_role": transcript.agent_role,
            "tenant_id": transcript.tenant_id,
            "model_id": target_entry.model_id,
            "parameters": {
                **target_entry.parameters,
                **transcript.parameters,
            },
        },
    )
    replay_started = perf_counter()
    try:
        replay_result = catalogue.invoke(args)
    except LLMProviderInvocationError as exc:
        completed_at = datetime.now(UTC)
        comparison = _provider_error_comparison(transcript, target_route, exc)
        return ReplayRunResult(
            checks=comparison.checks,
            record=_replay_run_record(
                transcript=transcript,
                target_entry=target_entry,
                comparison=comparison,
                replay_result=None,
                replay_latency_ms=_duration_ms(replay_started),
                started_at=started_at,
                completed_at=completed_at,
            ),
        )

    replay_latency_ms = _duration_ms(replay_started)
    completed_at = datetime.now(UTC)
    comparison = _compare_structured_data(
        transcript=transcript,
        invocation_id=transcript.invocation_id,
        route_id=target_route,
        expected=transcript.expected_structured_data,
        actual=replay_result,
    )
    return ReplayRunResult(
        checks=comparison.checks,
        record=_replay_run_record(
            transcript=transcript,
            target_entry=target_entry,
            comparison=comparison,
            replay_result=replay_result,
            replay_latency_ms=replay_latency_ms,
            started_at=started_at,
            completed_at=completed_at,
        ),
    )


def _compare_structured_data(
    *,
    transcript: CapturedTranscript,
    invocation_id: str,
    route_id: str,
    expected: dict[str, Any],
    actual: InvocationResult,
) -> _Comparison:
    hard_fail = classify_replay_result_hard_failure(
        task_kind=transcript.task_kind,
        result=actual,
        response_shape=uc1_response_shape_for_task(transcript.task_kind),
    )
    if hard_fail is not None:
        return _hard_fail_comparison(
            transcript=transcript,
            target_route=route_id,
            classification=hard_fail,
        )

    actual_data = dict(actual.structured_data)
    # The route_catalogue stamp is added by the runtime normaliser, not by the
    # adapter; the transcript expected_structured_data should not require it
    # because it captures the adapter's output before normalisation.
    actual_data.pop("route_catalogue", None)

    decision_fail = classify_replay_decision_failure(
        task_kind=transcript.task_kind,
        policy_snapshot_ref=transcript.policy_snapshot_ref,
        expected_structured_data=expected,
        actual_structured_data=actual_data,
    )
    if decision_fail is not None:
        return _decision_fail_comparison(
            transcript=transcript,
            target_route=route_id,
            classification=decision_fail,
        )

    if actual_data == expected:
        return _Comparison(
            checks=[
                EvalCheck(
                    "replay stability",
                    "pass",
                    (
                        f"replay through route {route_id!r} for invocation {invocation_id!r} "
                        "produced the same structured output"
                    ),
                )
            ],
            status="pass",
            result={
                "tier": "metrics_only",
                "reason_code": "structured_data_matched",
                "changed_field_names": [],
                "tier_placeholder": "metrics_only",
            },
        )

    missing = sorted(expected.keys() - actual_data.keys())
    extra = sorted(actual_data.keys() - expected.keys())
    changed = sorted(
        key for key in expected.keys() & actual_data.keys() if expected[key] != actual_data[key]
    )
    diff_summary: list[str] = []
    if missing:
        diff_summary.append(f"missing fields: {missing}")
    if extra:
        diff_summary.append(f"extra fields: {extra}")
    if changed:
        diff_summary.append(f"changed fields: {changed}")
    return _Comparison(
        checks=[
            EvalCheck(
                "replay stability",
                "fail",
                (
                    f"replay through route {route_id!r} for invocation {invocation_id!r} "
                    f"diverged from the captured transcript: {'; '.join(diff_summary)}"
                ),
            )
        ],
        status="fail",
        result={
            "tier": "decision_comparator_pending",
            "reason_code": "structured_data_diverged",
            "missing_field_names": missing,
            "extra_field_names": extra,
            "changed_field_names": changed,
            "tier_placeholder": "decision_comparator_pending",
        },
    )


def _decision_fail_comparison(
    *,
    transcript: CapturedTranscript,
    target_route: str,
    classification: DecisionFailClassification,
) -> _Comparison:
    fields = ", ".join(classification.field_names) if classification.field_names else "none"
    return _Comparison(
        checks=[
            EvalCheck(
                "replay decision-fail tier",
                "fail",
                (
                    f"replay through route {target_route!r} for invocation "
                    f"{transcript.invocation_id!r} classified {classification.reason_code!r} "
                    f"on fields: {fields}"
                ),
            )
        ],
        status="fail",
        result=classification.result_payload(),
    )


def _route_mismatch_comparison(
    transcript: CapturedTranscript,
    target_entry: RouteCatalogueEntry,
) -> _Comparison:
    return _Comparison(
        checks=[
            EvalCheck(
                "route governance alignment",
                "fail",
                (
                    f"captured route {target_entry.route_id!r} records "
                    f"{transcript.provider_id!r}/{transcript.model_id!r}, but the executable "
                    f"route catalogue registers {target_entry.provider_id!r}/"
                    f"{target_entry.model_id!r}"
                ),
            )
        ],
        status="fail",
        result={
            "tier": "hard_fail",
            "reason_code": "route_governance_mismatch",
            "field_names": ["provider_id", "model_id"],
            "changed_field_names": ["provider_id", "model_id"],
        },
        safe_error_reason="route_governance_mismatch",
    )


def _provider_error_comparison(
    transcript: CapturedTranscript,
    target_route: str,
    exc: LLMProviderInvocationError,
) -> _Comparison:
    reason = safe_reason_code(exc.reason)
    if reason.startswith("missing_api_key:"):
        return _Comparison(
            checks=[
                EvalCheck(
                    "replay stability",
                    "skip",
                    (
                        f"replay through route {target_route!r} for invocation "
                        f"{transcript.invocation_id!r} skipped: {reason}"
                    ),
                )
            ],
            status="skipped",
            result={
                "tier": "live_provider_gate",
                "reason_code": reason,
                "changed_field_names": [],
                "tier_placeholder": "live_provider_gate_skipped",
            },
            safe_skipped_reason=reason,
        )
    classification = provider_port_error_hard_failure(reason)
    return _hard_fail_comparison(
        transcript=transcript,
        target_route=target_route,
        classification=classification,
    )


def _hard_fail_comparison(
    *,
    transcript: CapturedTranscript,
    target_route: str,
    classification: HardFailClassification,
) -> _Comparison:
    fields = ", ".join(classification.field_names) if classification.field_names else "none"
    return _Comparison(
        checks=[
            EvalCheck(
                "replay hard-fail tier",
                "fail",
                (
                    f"replay through route {target_route!r} for invocation "
                    f"{transcript.invocation_id!r} classified {classification.reason_code!r} "
                    f"on fields: {fields}"
                ),
            )
        ],
        status=classification.status,
        result=classification.result_payload(),
        safe_error_reason=classification.safe_error_reason,
    )


def _replay_run_record(
    *,
    transcript: CapturedTranscript,
    target_entry: RouteCatalogueEntry,
    comparison: _Comparison,
    replay_result: InvocationResult | None,
    replay_latency_ms: int,
    started_at: datetime,
    completed_at: datetime,
) -> ReplayRunRecord:
    schema_metadata = response_shape_metadata(uc1_response_shape_for_task(transcript.task_kind))
    alternate_cost = replay_result.cost_amount_usd if replay_result else Decimal("0")
    alternate_token_usage = replay_result.token_usage if replay_result else {}
    original_metrics = _run_metrics(
        cost_amount_usd=transcript.original_cost_amount_usd,
        latency_ms=transcript.original_latency_ms,
        token_usage=transcript.token_usage,
    )
    alternate_metrics = _run_metrics(
        cost_amount_usd=alternate_cost,
        latency_ms=replay_latency_ms,
        token_usage=alternate_token_usage,
    )
    record = {
        "schema_version": "1.0.0",
        "replay_run_id": str(
            uuid5(
                NAMESPACE_URL,
                (
                    "chorus.eval.replay-run:"
                    f"{transcript.tenant_id}:{transcript.invocation_id}:"
                    f"{transcript.transcript_id}:{target_entry.route_id}"
                ),
            )
        ),
        "tenant_id": transcript.tenant_id,
        "correlation_id": transcript.correlation_id,
        "workflow_id": transcript.workflow_id,
        "original": {
            "invocation_id": transcript.invocation_id,
            "transcript_id": transcript.transcript_id,
            "runtime_route_id": transcript.route_id,
            "provider_id": transcript.provider_id,
            "model_id": transcript.model_id,
            "adapter_version": transcript.adapter_version,
            "parameters": transcript.parameters,
        },
        "alternate": {
            "runtime_route_id": target_entry.route_id,
            "provider_id": target_entry.provider_id,
            "model_id": target_entry.model_id,
            "adapter_version": target_entry.adapter_version,
            "parameters": target_entry.parameters,
        },
        "lineage": {
            "agent_role": transcript.agent_role,
            "task_kind": transcript.task_kind,
            "policy_snapshot_ref": transcript.policy_snapshot_ref,
            "prompt_reference": transcript.prompt_reference,
            "prompt_hash": transcript.prompt_hash,
            "response_schema_name": schema_metadata["response_schema.name"],
            "response_schema_contract_ref": schema_metadata["response_schema.contract_ref"],
            "response_schema_hash": schema_metadata["response_schema.hash"],
            "route_version_ref": transcript.route_version_ref,
            "provider_catalogue_id": transcript.provider_catalogue_id,
            "eval_fixture_ref": transcript.eval_fixture_ref,
            "transcript_source_ref": transcript.transcript_source_ref,
        },
        "comparator": {
            "name": _COMPARATOR_NAME,
            "version": _COMPARATOR_VERSION,
            "status": comparison.status,
            "result": comparison.result,
            "safe_error_reason": comparison.safe_error_reason,
            "safe_skipped_reason": comparison.safe_skipped_reason,
        },
        "metrics": {
            "original": original_metrics,
            "alternate": alternate_metrics,
            "delta": {
                "cost_amount_usd": float(alternate_cost - transcript.original_cost_amount_usd),
                "latency_ms": replay_latency_ms - transcript.original_latency_ms,
                "token_usage": _token_usage_delta(
                    original=transcript.token_usage,
                    alternate=alternate_token_usage,
                ),
            },
        },
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
    }
    return ReplayRunRecord.model_validate(record)


def _run_metrics(
    *,
    cost_amount_usd: Decimal,
    latency_ms: int,
    token_usage: dict[str, int],
) -> dict[str, Any]:
    return {
        "cost_amount_usd": float(cost_amount_usd),
        "cost_currency": "USD",
        "latency_ms": latency_ms,
        "token_usage": _token_usage(token_usage),
    }


def _token_usage(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    raw_usage = cast(dict[str, object], value)
    usage: dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        token_value = raw_usage.get(key)
        if isinstance(token_value, int) and token_value >= 0:
            usage[key] = token_value
    return usage


def _token_usage_delta(
    *,
    original: dict[str, int],
    alternate: dict[str, int],
) -> dict[str, int]:
    keys = sorted(set(original) | set(alternate))
    return {key: alternate.get(key, 0) - original.get(key, 0) for key in keys}


def _duration_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _evidence_missing_fields(data: dict[str, Any]) -> tuple[str, ...]:
    missing: list[str] = []
    if not _optional_str(data.get("transcript_id")):
        missing.append("original.transcript_id")
    return tuple(missing)


__all__ = [
    "CapturedTranscript",
    "ReplayRunResult",
    "load_transcript",
    "replay_transcript",
    "replay_transcript_with_record",
]

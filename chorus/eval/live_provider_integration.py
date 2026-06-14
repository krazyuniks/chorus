"""Helpers for explicit credential-gated live-provider replay checks."""

from __future__ import annotations

import json
import os
from typing import Any, cast

from psycopg import Connection
from psycopg.types.json import Jsonb

from chorus.contracts.generated.eval.replay_run_record import ReplayRunRecord
from chorus.eval.replay import CapturedTranscript
from chorus.eval.scenario_player import CapturedRun, DecisionTrailRecord, TranscriptRecord
from chorus.llm_provider import RouteCatalogue, default_route_catalogue

LIVE_OPENAI_ROUTE_ID = "demo-eval-canonical"
LIVE_DEEPSEEK_ROUTE_ID = "dev"
ALLOWED_LIVE_COMPARATOR_OUTCOMES = frozenset({"success", "review-finding", "metrics-only"})


class LiveProviderCredentialError(RuntimeError):
    """Raised when an explicitly requested live route lacks its credential."""


def require_live_route_credential(
    route_id: str = LIVE_OPENAI_ROUTE_ID,
    *,
    route_catalogue: RouteCatalogue | None = None,
) -> None:
    """Fail loudly before an explicit live-provider integration run starts."""

    catalogue = route_catalogue or default_route_catalogue()
    route = catalogue.get(route_id)
    credential_env = route.required_credential_env
    if credential_env is None:
        return
    if os.environ.get(credential_env, "").strip():
        return
    raise LiveProviderCredentialError(
        f"Live provider integration test for route {route_id!r} requires "
        f"{credential_env} to be set and non-empty."
    )


def captured_transcripts_for_replay(run: CapturedRun) -> tuple[CapturedTranscript, ...]:
    """Convert captured-run transcript rows into replay comparator inputs."""

    decisions_by_invocation = {str(decision.invocation_id): decision for decision in run.decisions}
    transcripts: list[CapturedTranscript] = []
    for transcript in run.transcripts:
        decision = decisions_by_invocation.get(str(transcript.invocation_id))
        if decision is None:
            raise ValueError(
                "Captured run transcript lacks matching decision-trail row for "
                f"invocation {transcript.invocation_id}."
            )
        expected_structured_data = dict(transcript.structured_data)
        expected_structured_data.pop("route_catalogue", None)
        policy_snapshot_ref = _optional_string(
            expected_structured_data.get("policy_snapshot_ref")
        ) or _default_policy_snapshot_ref(run)
        transcripts.append(
            CapturedTranscript(
                invocation_id=str(transcript.invocation_id),
                transcript_id=str(transcript.transcript_id),
                correlation_id=transcript.correlation_id,
                workflow_id=transcript.workflow_id,
                route_id=transcript.route_id,
                provider_id=transcript.provider_id,
                model_id=transcript.model_id,
                adapter_version=transcript.adapter_version,
                parameters=dict(transcript.parameters),
                request_messages=[dict(message) for message in transcript.request_messages],
                expected_structured_data=expected_structured_data,
                task_kind=decision.task_kind,
                agent_role=decision.agent_role,
                tenant_id=transcript.tenant_id,
                enquiry_input=_input_from_summary(decision.input_summary),
                prompt_reference=decision.prompt_reference,
                prompt_hash=decision.prompt_hash,
                policy_snapshot_ref=policy_snapshot_ref,
                route_version_ref=None,
                provider_catalogue_id=None,
                eval_fixture_ref=run.fixture.fixture_id,
                transcript_source_ref=(
                    f"captured-run:{run.fixture.fixture_id}:{transcript.transcript_id}"
                ),
                original_cost_amount_usd=decision.cost_amount_usd,
                original_latency_ms=decision.duration_ms,
                token_usage={},
                provider_metadata={},
            )
        )
    return tuple(transcripts)


def persist_captured_run_audit_refs(
    conn: Connection[Any],
    run: CapturedRun,
) -> None:
    """Persist captured-run source refs required by replay-run FK checks.

    UC2 and UC3 workflow playback already write these rows through the real
    runtime path. UC1 live replay uses the offline captured-run path, so the
    live integration tests seed only the original recorded-replay audit and
    transcript refs before `ReplayRunStore` writes comparator evidence.
    """

    for decision in run.decisions:
        _persist_decision_ref(conn, decision, run.fixture.fixture_id)
    for transcript in run.transcripts:
        _persist_transcript_ref(conn, transcript, run.fixture.fixture_id)


def replay_comparator_outcome(record: ReplayRunRecord) -> str:
    """Return the bounded outcome label used by live integration tests."""

    status = record.comparator.status.value
    tier = str(record.comparator.result.get("tier", "")).replace("_", "-")
    reason_code = str(record.comparator.result.get("reason_code", ""))
    if status == "pass" and tier == "metrics-only" and reason_code == "metrics_only_no_delta":
        return "success"
    if tier in {"review-finding", "metrics-only", "hard-fail", "decision-fail"}:
        return tier
    if status == "pass":
        return "success"
    if status == "error":
        return "hard-fail"
    return tier or status


def _persist_decision_ref(
    conn: Connection[Any],
    decision: DecisionTrailRecord,
    fixture_id: str,
) -> None:
    conn.execute(
        """
        INSERT INTO decision_trail_entries (
            tenant_id,
            invocation_id,
            correlation_id,
            workflow_id,
            agent_id,
            agent_role,
            agent_version,
            lifecycle_state,
            prompt_reference,
            prompt_hash,
            provider,
            model,
            task_kind,
            budget_cap_usd,
            input_summary,
            output_summary,
            justification,
            outcome,
            tool_call_ids,
            cost_amount,
            cost_currency,
            duration_ms,
            started_at,
            completed_at,
            contract_refs,
            raw_record,
            metadata
        )
        VALUES (
            %(tenant_id)s,
            %(invocation_id)s,
            %(correlation_id)s,
            %(workflow_id)s,
            %(agent_id)s,
            %(agent_role)s,
            %(agent_version)s,
            'approved',
            %(prompt_reference)s,
            %(prompt_hash)s,
            %(provider)s,
            %(model)s,
            %(task_kind)s,
            0.0500,
            %(input_summary)s,
            %(output_summary)s,
            %(justification)s,
            %(outcome)s,
            ARRAY[]::uuid[],
            %(cost_amount)s,
            'USD',
            %(duration_ms)s,
            %(started_at)s,
            %(completed_at)s,
            %(contract_refs)s,
            %(raw_record)s,
            %(metadata)s
        )
        ON CONFLICT (tenant_id, invocation_id) DO NOTHING
        """,
        {
            "tenant_id": decision.tenant_id,
            "invocation_id": decision.invocation_id,
            "correlation_id": decision.correlation_id,
            "workflow_id": decision.workflow_id,
            "agent_id": decision.agent_id,
            "agent_role": decision.agent_role,
            "agent_version": decision.agent_version,
            "prompt_reference": decision.prompt_reference,
            "prompt_hash": decision.prompt_hash,
            "provider": decision.provider,
            "model": decision.model,
            "task_kind": decision.task_kind,
            "input_summary": decision.input_summary,
            "output_summary": decision.output_summary,
            "justification": decision.justification,
            "outcome": decision.outcome,
            "cost_amount": decision.cost_amount_usd,
            "duration_ms": decision.duration_ms,
            "started_at": decision.started_at,
            "completed_at": decision.completed_at,
            "contract_refs": decision.contract_refs,
            "raw_record": Jsonb(
                {
                    "source": "captured_run",
                    "fixture_id": fixture_id,
                    "invocation_id": str(decision.invocation_id),
                    "structured_data": decision.structured_data,
                }
            ),
            "metadata": Jsonb(
                {
                    "eval_fixture_ref": fixture_id,
                    "source": "live_provider_integration.captured_run",
                }
            ),
        },
    )


def _persist_transcript_ref(
    conn: Connection[Any],
    transcript: TranscriptRecord,
    fixture_id: str,
) -> None:
    response_body = {
        "summary": _last_assistant_content(transcript),
        "confidence": 1.0,
        "structured_data": transcript.structured_data,
        "recommended_next_step": "continue",
        "rationale": "",
    }
    conn.execute(
        """
        INSERT INTO agent_invocation_transcripts (
            tenant_id,
            transcript_id,
            invocation_id,
            correlation_id,
            workflow_id,
            route_id,
            provider_id,
            model_id,
            adapter_version,
            parameters,
            messages,
            tool_calls,
            response_body,
            token_usage,
            provider_metadata,
            started_at,
            completed_at,
            raw_record
        )
        VALUES (
            %(tenant_id)s,
            %(transcript_id)s,
            %(invocation_id)s,
            %(correlation_id)s,
            %(workflow_id)s,
            %(route_id)s,
            %(provider_id)s,
            %(model_id)s,
            %(adapter_version)s,
            %(parameters)s,
            %(messages)s,
            '[]'::jsonb,
            %(response_body)s,
            '{}'::jsonb,
            %(provider_metadata)s,
            %(started_at)s,
            %(completed_at)s,
            %(raw_record)s
        )
        ON CONFLICT (tenant_id, transcript_id) DO NOTHING
        """,
        {
            "tenant_id": transcript.tenant_id,
            "transcript_id": transcript.transcript_id,
            "invocation_id": transcript.invocation_id,
            "correlation_id": transcript.correlation_id,
            "workflow_id": transcript.workflow_id,
            "route_id": transcript.route_id,
            "provider_id": transcript.provider_id,
            "model_id": transcript.model_id,
            "adapter_version": transcript.adapter_version,
            "parameters": Jsonb(transcript.parameters),
            "messages": Jsonb(transcript.request_messages + transcript.response_messages),
            "response_body": Jsonb(response_body),
            "provider_metadata": Jsonb(
                {
                    "adapter": transcript.adapter_version,
                    "source": "captured_run",
                }
            ),
            "started_at": transcript.started_at,
            "completed_at": transcript.completed_at,
            "raw_record": Jsonb(
                {
                    "source": "captured_run",
                    "fixture_id": fixture_id,
                    "transcript_id": str(transcript.transcript_id),
                    "structured_data": transcript.structured_data,
                }
            ),
        },
    )


def _last_assistant_content(transcript: TranscriptRecord) -> str:
    for message in reversed(transcript.response_messages):
        content = message.get("content")
        if isinstance(content, str):
            return content
    return ""


def _input_from_summary(input_summary: str) -> dict[str, Any]:
    try:
        value = json.loads(input_summary)
    except json.JSONDecodeError:
        return {"input_summary_ref": "unparseable"}
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {"input_summary_ref": "non_object"}


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _default_policy_snapshot_ref(run: CapturedRun) -> str | None:
    workflow_type = str(getattr(run.fixture.workflow_type, "value", run.fixture.workflow_type))
    match workflow_type:
        case "uc1_enquiry_qualification":
            return "policy_snapshot:uc1:default:v1"
        case "uc2_legal_services_intake_conflict_check":
            return "policy_snapshot:uc2:default:v1"
        case "uc3_ifa_suitability_intake":
            return "policy_snapshot:uc3:default:v1"
        case _:
            return None


__all__ = [
    "ALLOWED_LIVE_COMPARATOR_OUTCOMES",
    "LIVE_DEEPSEEK_ROUTE_ID",
    "LIVE_OPENAI_ROUTE_ID",
    "LiveProviderCredentialError",
    "captured_transcripts_for_replay",
    "persist_captured_run_audit_refs",
    "replay_comparator_outcome",
    "require_live_route_credential",
]

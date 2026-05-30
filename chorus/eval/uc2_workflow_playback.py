"""UC2 eval playback through the real workflow and runtime activities."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from chorus.contracts.generated.eval.eval_fixture import EvalFixture
from chorus.eval.scenario_player import (
    CapturedRun,
    DecisionTrailRecord,
    ProjectionEvent,
    ToolActionRecord,
    TranscriptRecord,
)
from chorus.workflows.activities import (
    invoke_agent_runtime_activity,
    invoke_tool_gateway_activity,
    record_retry_exhaustion_dlq_activity,
    record_tool_failure_compensation_activity,
    record_workflow_event_activity,
)
from chorus.workflows.types import Uc2WorkflowResult
from chorus.workflows.uc2 import UC2_WORKFLOW_TYPE, Uc2LegalServicesIntakeConflictCheckWorkflow
from chorus.workflows.uc2_synthetic_intake import workflow_start_request_from_email_fixture

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUPPORTED_SCENARIOS = {
    "synthetic_acceptance_conduct",
    "conflict_exception_approval",
}


@dataclass(frozen=True)
class Uc2WorkflowPlaybackResult:
    workflow_result: Uc2WorkflowResult
    captured_run: CapturedRun


def play_uc2_workflow_fixture(
    fixture: EvalFixture,
    *,
    database_url: str | None = None,
    playback_ref: str | None = None,
) -> CapturedRun:
    """Synchronously play a UC2 fixture through the real workflow path."""

    return asyncio.run(
        play_uc2_workflow_fixture_async(
            fixture,
            database_url=database_url,
            playback_ref=playback_ref,
        )
    ).captured_run


async def play_uc2_workflow_fixture_async(
    fixture: EvalFixture,
    *,
    database_url: str | None = None,
    playback_ref: str | None = None,
) -> Uc2WorkflowPlaybackResult:
    """Run a UC2 eval fixture through Temporal, Agent Runtime, and Tool Gateway."""

    _validate_fixture(fixture)
    source_fixture_path = _source_fixture_path(fixture)
    request = workflow_start_request_from_email_fixture(source_fixture_path)
    run_ref = _safe_playback_ref(playback_ref or uuid4().hex[:12])
    intake = replace(
        request.intake,
        correlation_id=f"{request.intake.correlation_id}_{run_ref}",
        legal_intake_ref=f"{request.intake.legal_intake_ref}_{run_ref}",
        idempotency_key_ref=(
            f"{request.intake.idempotency_key_ref}_{run_ref}"
            if request.intake.idempotency_key_ref is not None
            else None
        ),
    )
    workflow_id = f"{request.workflow_id}-{run_ref}"

    with (
        _database_url_override(database_url),
        ThreadPoolExecutor(max_workers=4) as activity_executor,
    ):
        async with (
            await WorkflowEnvironment.start_time_skipping() as env,
            Worker(
                env.client,
                task_queue=f"eval-uc2-{fixture.fixture_id}",
                workflows=[Uc2LegalServicesIntakeConflictCheckWorkflow],
                activities=[
                    record_workflow_event_activity,
                    invoke_agent_runtime_activity,
                    invoke_tool_gateway_activity,
                    record_tool_failure_compensation_activity,
                    record_retry_exhaustion_dlq_activity,
                ],
                activity_executor=activity_executor,
            ),
        ):
            result = await env.client.execute_workflow(
                "Uc2LegalServicesIntakeConflictCheckWorkflow",
                intake,
                id=workflow_id,
                task_queue=f"eval-uc2-{fixture.fixture_id}",
                result_type=Uc2WorkflowResult,
            )

        captured = _captured_run_from_database(
            fixture=fixture,
            tenant_id=intake.tenant_id,
            workflow_id=result.workflow_id,
        )
        captured.terminal_outcome = result.outcome
        return Uc2WorkflowPlaybackResult(workflow_result=result, captured_run=captured)


def _validate_fixture(fixture: EvalFixture) -> None:
    workflow_type = str(getattr(fixture.workflow_type, "value", fixture.workflow_type))
    if workflow_type != UC2_WORKFLOW_TYPE:
        raise ValueError(f"UC2 playback received unsupported workflow_type {workflow_type!r}")
    if fixture.scenario not in _SUPPORTED_SCENARIOS:
        raise ValueError(f"UC2 workflow playback does not support scenario {fixture.scenario!r}")


def _source_fixture_path(fixture: EvalFixture) -> Path:
    source_path = fixture.input.source_fixture_path
    if source_path is None:
        raise ValueError("UC2 workflow playback requires input.source_fixture_path")
    path = Path(source_path)
    return path if path.is_absolute() else _REPO_ROOT / path


def _safe_playback_ref(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)
    return safe[:32] or "run"


@contextmanager
def _database_url_override(database_url: str | None) -> Generator[None]:
    if database_url is None:
        yield
        return
    original = os.environ.get("CHORUS_DATABASE_URL")
    os.environ["CHORUS_DATABASE_URL"] = database_url
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("CHORUS_DATABASE_URL", None)
        else:
            os.environ["CHORUS_DATABASE_URL"] = original


def _database_url() -> str:
    database_url = os.environ.get("CHORUS_DATABASE_URL")
    if database_url is None or database_url.strip() == "":
        raise RuntimeError("CHORUS_DATABASE_URL is required for UC2 workflow playback")
    return database_url


def _captured_run_from_database(
    *,
    fixture: EvalFixture,
    tenant_id: str,
    workflow_id: str,
) -> CapturedRun:
    with cast(
        psycopg.Connection[dict[str, Any]],
        psycopg.connect(_database_url(), row_factory=cast(Any, dict_row)),
    ) as conn:
        return CapturedRun(
            fixture=fixture,
            decisions=_decision_records(conn, tenant_id=tenant_id, workflow_id=workflow_id),
            transcripts=_transcript_records(conn, tenant_id=tenant_id, workflow_id=workflow_id),
            tool_actions=_tool_action_records(conn, tenant_id=tenant_id, workflow_id=workflow_id),
            projection_events=_projection_events(
                conn,
                tenant_id=tenant_id,
                workflow_id=workflow_id,
            ),
        )


def _decision_records(
    conn: psycopg.Connection[dict[str, Any]],
    *,
    tenant_id: str,
    workflow_id: str,
) -> list[DecisionTrailRecord]:
    rows = conn.execute(
        """
        SELECT
            d.invocation_id,
            d.correlation_id,
            d.workflow_id,
            d.tenant_id,
            d.agent_id,
            d.agent_role,
            d.agent_version,
            d.prompt_reference,
            d.prompt_hash,
            d.provider,
            d.model,
            d.task_kind,
            d.input_summary,
            d.output_summary,
            d.justification,
            d.outcome,
            d.cost_amount,
            d.duration_ms,
            d.started_at,
            d.completed_at,
            d.contract_refs,
            t.response_body
        FROM decision_trail_entries d
        LEFT JOIN agent_invocation_transcripts t
          ON t.tenant_id = d.tenant_id
         AND t.invocation_id = d.invocation_id
        WHERE d.tenant_id = %s
          AND d.workflow_id = %s
        ORDER BY d.started_at, d.invocation_id
        """,
        (tenant_id, workflow_id),
    ).fetchall()
    return [
        DecisionTrailRecord(
            invocation_id=row["invocation_id"],
            correlation_id=row["correlation_id"],
            workflow_id=row["workflow_id"],
            tenant_id=row["tenant_id"],
            agent_id=row["agent_id"],
            agent_role=row["agent_role"],
            agent_version=row["agent_version"],
            prompt_reference=row["prompt_reference"],
            prompt_hash=row["prompt_hash"],
            provider=row["provider"],
            model=row["model"],
            task_kind=row["task_kind"],
            input_summary=row["input_summary"],
            output_summary=row["output_summary"],
            justification=row["justification"],
            outcome=row["outcome"],
            cost_amount_usd=Decimal(str(row["cost_amount"])),
            duration_ms=row["duration_ms"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            contract_refs=list(row["contract_refs"]),
            structured_data=_response_structured_data(row["response_body"]),
        )
        for row in rows
    ]


def _transcript_records(
    conn: psycopg.Connection[dict[str, Any]],
    *,
    tenant_id: str,
    workflow_id: str,
) -> list[TranscriptRecord]:
    rows = conn.execute(
        """
        SELECT
            transcript_id,
            invocation_id,
            correlation_id,
            workflow_id,
            tenant_id,
            route_id,
            provider_id,
            model_id,
            adapter_version,
            parameters,
            messages,
            response_body,
            started_at,
            completed_at
        FROM agent_invocation_transcripts
        WHERE tenant_id = %s
          AND workflow_id = %s
        ORDER BY started_at, invocation_id
        """,
        (tenant_id, workflow_id),
    ).fetchall()
    records: list[TranscriptRecord] = []
    for row in rows:
        messages = _json_list(row["messages"])
        records.append(
            TranscriptRecord(
                transcript_id=row["transcript_id"],
                invocation_id=row["invocation_id"],
                correlation_id=row["correlation_id"],
                workflow_id=row["workflow_id"],
                tenant_id=row["tenant_id"],
                route_id=row["route_id"],
                provider_id=row["provider_id"],
                model_id=row["model_id"],
                adapter_version=row["adapter_version"],
                parameters=dict(row["parameters"] or {}),
                request_messages=[
                    message for message in messages if message.get("role") != "assistant"
                ],
                response_messages=[
                    message for message in messages if message.get("role") == "assistant"
                ],
                structured_data=_response_structured_data(row["response_body"]),
                started_at=row["started_at"],
                completed_at=row["completed_at"],
            )
        )
    return records


def _tool_action_records(
    conn: psycopg.Connection[dict[str, Any]],
    *,
    tenant_id: str,
    workflow_id: str,
) -> list[ToolActionRecord]:
    approval_packages = _approval_packages_by_source_audit_id(
        conn,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
    )
    rows = conn.execute(
        """
        SELECT
            audit_event_id,
            invocation_id,
            correlation_id,
            workflow_id,
            tenant_id,
            actor_type,
            actor_id,
            category,
            action,
            tool_name,
            requested_mode,
            enforced_mode,
            verdict,
            reason,
            occurred_at,
            raw_event
        FROM tool_action_audit
        WHERE tenant_id = %s
          AND workflow_id = %s
        ORDER BY occurred_at, audit_event_id
        """,
        (tenant_id, workflow_id),
    ).fetchall()
    records: list[ToolActionRecord] = []
    for row in rows:
        raw_event = _json_dict(row["raw_event"])
        details = _json_dict(raw_event.get("details"))
        verdict_details = _json_dict(details.get("gateway_verdict"))
        response = _json_dict(details.get("gateway_response"))
        records.append(
            ToolActionRecord(
                audit_event_id=row["audit_event_id"],
                invocation_id=row["invocation_id"],
                correlation_id=row["correlation_id"],
                workflow_id=row["workflow_id"],
                tenant_id=row["tenant_id"],
                actor_type=row["actor_type"],
                actor_id=row["actor_id"],
                category=row["category"],
                action=row["action"],
                tool_name=row["tool_name"],
                requested_mode=row["requested_mode"],
                enforced_mode=row["enforced_mode"],
                verdict=row["verdict"],
                reason=row["reason"],
                approval_required=bool(verdict_details.get("approval_required")),
                approval_granted=_approval_granted(row["action"], row["verdict"]),
                occurred_at=row["occurred_at"],
                output=_json_dict(response.get("output")),
                approval_package=approval_packages.get(row["audit_event_id"], {}),
            )
        )
    return records


def _approval_packages_by_source_audit_id(
    conn: psycopg.Connection[dict[str, Any]],
    *,
    tenant_id: str,
    workflow_id: str,
) -> dict[UUID, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            source_audit_event_id,
            approval_id,
            approval_package_version,
            approval_state,
            requested_action,
            tool_name,
            requested_mode,
            enforced_mode,
            idempotency_key_ref,
            policy_version_refs,
            metadata
        FROM approval_packages
        WHERE tenant_id = %s
          AND workflow_id = %s
        """,
        (tenant_id, workflow_id),
    ).fetchall()
    return {
        row["source_audit_event_id"]: {
            "approval_id": str(row["approval_id"]),
            "approval_package_version": row["approval_package_version"],
            "approval_state": row["approval_state"],
            "requested_action": row["requested_action"],
            "tool_name": row["tool_name"],
            "requested_mode": row["requested_mode"],
            "enforced_mode": row["enforced_mode"],
            "idempotency_key_ref": row["idempotency_key_ref"],
            "policy_version_refs": _json_dict(row["policy_version_refs"]),
            "metadata": _json_dict(row["metadata"]),
        }
        for row in rows
    }


def _projection_events(
    conn: psycopg.Connection[dict[str, Any]],
    *,
    tenant_id: str,
    workflow_id: str,
) -> list[ProjectionEvent]:
    rows = conn.execute(
        """
        SELECT
            event_id,
            correlation_id,
            workflow_id,
            tenant_id,
            workflow_type,
            subject_id,
            subject_ref,
            sequence,
            event_type,
            step,
            occurred_at,
            payload
        FROM outbox_events
        WHERE tenant_id = %s
          AND workflow_id = %s
        ORDER BY sequence, occurred_at
        """,
        (tenant_id, workflow_id),
    ).fetchall()
    return [
        ProjectionEvent(
            event_id=row["event_id"],
            correlation_id=row["correlation_id"],
            workflow_id=row["workflow_id"],
            tenant_id=row["tenant_id"],
            workflow_type=row["workflow_type"],
            subject_id=row["subject_id"],
            subject_ref=row["subject_ref"],
            sequence=row["sequence"],
            event_type=row["event_type"],
            step=row["step"],
            occurred_at=_datetime_value(row["occurred_at"]),
            payload=_json_dict(row["payload"]),
        )
        for row in rows
    ]


def _response_structured_data(response_body: object) -> dict[str, Any]:
    body = _json_dict(response_body)
    return _json_dict(body.get("structured_data"))


def _approval_granted(action: str, verdict: str) -> bool | None:
    if action == "approval.apply" and verdict == "allow":
        return True
    return None


def _json_dict(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _json_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        cast(dict[str, Any], item) for item in cast(list[object], value) if isinstance(item, dict)
    ]


def _datetime_value(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    raise TypeError(f"expected datetime from Postgres row, got {type(value)!r}")


__all__ = [
    "Uc2WorkflowPlaybackResult",
    "play_uc2_workflow_fixture",
    "play_uc2_workflow_fixture_async",
]

"""Persistence surface for replay-eval run evidence records."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict

from chorus.contracts.generated.eval.replay_run_record import ReplayRunRecord
from chorus.persistence._query import (
    clear_tenant_context,
    fetch_models,
    set_tenant_context,
)


class ReplayRunRecordReadModel(BaseModel):
    """Read model for persisted replay-eval run evidence."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    replay_run_id: UUID
    correlation_id: str
    workflow_id: str
    original_invocation_id: UUID
    original_transcript_id: UUID
    original_runtime_route_id: str
    original_provider_id: str
    original_model_id: str
    original_adapter_version: str
    original_parameters: dict[str, Any]
    alternate_runtime_route_id: str
    alternate_provider_id: str
    alternate_model_id: str
    alternate_adapter_version: str
    alternate_parameters: dict[str, Any]
    agent_role: str
    task_kind: str
    policy_snapshot_ref: str | None
    prompt_reference: str
    prompt_hash: str
    response_schema_name: str
    response_schema_contract_ref: str
    response_schema_hash: str
    route_version_ref: str | None
    provider_catalogue_id: str | None
    eval_fixture_ref: str | None
    transcript_source_ref: str | None
    comparator_name: str
    comparator_version: str
    comparator_status: str
    comparator_result: dict[str, Any]
    safe_error_reason: str | None
    safe_skipped_reason: str | None
    original_cost_amount: Decimal
    original_cost_currency: str
    original_latency_ms: int
    original_token_usage: dict[str, Any]
    alternate_cost_amount: Decimal
    alternate_cost_currency: str
    alternate_latency_ms: int
    alternate_token_usage: dict[str, Any]
    metric_deltas: dict[str, Any]
    started_at: datetime
    completed_at: datetime
    raw_record: dict[str, Any]
    created_at: datetime


class ReplayRunStore:
    """Write and read replay-run evidence records."""

    def __init__(self, conn: Connection[Any]) -> None:
        self._conn = conn

    def set_tenant_context(self, tenant_id: str) -> None:
        set_tenant_context(self._conn, tenant_id)

    def clear_tenant_context(self) -> None:
        clear_tenant_context(self._conn)

    def record_replay_run(self, record: ReplayRunRecord) -> None:
        data = record.model_dump(mode="json", exclude_none=True)
        original = data["original"]
        alternate = data["alternate"]
        lineage = data["lineage"]
        comparator = data["comparator"]
        metrics = data["metrics"]
        original_metrics = metrics["original"]
        alternate_metrics = metrics["alternate"]

        self._conn.execute(
            """
            INSERT INTO replay_run_records (
                tenant_id,
                replay_run_id,
                correlation_id,
                workflow_id,
                original_invocation_id,
                original_transcript_id,
                original_runtime_route_id,
                original_provider_id,
                original_model_id,
                original_adapter_version,
                original_parameters,
                alternate_runtime_route_id,
                alternate_provider_id,
                alternate_model_id,
                alternate_adapter_version,
                alternate_parameters,
                agent_role,
                task_kind,
                policy_snapshot_ref,
                prompt_reference,
                prompt_hash,
                response_schema_name,
                response_schema_contract_ref,
                response_schema_hash,
                route_version_ref,
                provider_catalogue_id,
                eval_fixture_ref,
                transcript_source_ref,
                comparator_name,
                comparator_version,
                comparator_status,
                comparator_result,
                safe_error_reason,
                safe_skipped_reason,
                original_cost_amount,
                original_cost_currency,
                original_latency_ms,
                original_token_usage,
                alternate_cost_amount,
                alternate_cost_currency,
                alternate_latency_ms,
                alternate_token_usage,
                metric_deltas,
                started_at,
                completed_at,
                raw_record
            )
            VALUES (
                %(tenant_id)s,
                %(replay_run_id)s,
                %(correlation_id)s,
                %(workflow_id)s,
                %(original_invocation_id)s,
                %(original_transcript_id)s,
                %(original_runtime_route_id)s,
                %(original_provider_id)s,
                %(original_model_id)s,
                %(original_adapter_version)s,
                %(original_parameters)s,
                %(alternate_runtime_route_id)s,
                %(alternate_provider_id)s,
                %(alternate_model_id)s,
                %(alternate_adapter_version)s,
                %(alternate_parameters)s,
                %(agent_role)s,
                %(task_kind)s,
                %(policy_snapshot_ref)s,
                %(prompt_reference)s,
                %(prompt_hash)s,
                %(response_schema_name)s,
                %(response_schema_contract_ref)s,
                %(response_schema_hash)s,
                %(route_version_ref)s,
                %(provider_catalogue_id)s,
                %(eval_fixture_ref)s,
                %(transcript_source_ref)s,
                %(comparator_name)s,
                %(comparator_version)s,
                %(comparator_status)s,
                %(comparator_result)s,
                %(safe_error_reason)s,
                %(safe_skipped_reason)s,
                %(original_cost_amount)s,
                %(original_cost_currency)s,
                %(original_latency_ms)s,
                %(original_token_usage)s,
                %(alternate_cost_amount)s,
                %(alternate_cost_currency)s,
                %(alternate_latency_ms)s,
                %(alternate_token_usage)s,
                %(metric_deltas)s,
                %(started_at)s,
                %(completed_at)s,
                %(raw_record)s
            )
            ON CONFLICT (tenant_id, replay_run_id) DO UPDATE
            SET
                comparator_status = EXCLUDED.comparator_status,
                comparator_result = EXCLUDED.comparator_result,
                safe_error_reason = EXCLUDED.safe_error_reason,
                safe_skipped_reason = EXCLUDED.safe_skipped_reason,
                alternate_cost_amount = EXCLUDED.alternate_cost_amount,
                alternate_cost_currency = EXCLUDED.alternate_cost_currency,
                alternate_latency_ms = EXCLUDED.alternate_latency_ms,
                alternate_token_usage = EXCLUDED.alternate_token_usage,
                metric_deltas = EXCLUDED.metric_deltas,
                completed_at = EXCLUDED.completed_at,
                raw_record = EXCLUDED.raw_record
            """,
            {
                "tenant_id": data["tenant_id"],
                "replay_run_id": data["replay_run_id"],
                "correlation_id": data["correlation_id"],
                "workflow_id": data["workflow_id"],
                "original_invocation_id": original["invocation_id"],
                "original_transcript_id": original["transcript_id"],
                "original_runtime_route_id": original["runtime_route_id"],
                "original_provider_id": original["provider_id"],
                "original_model_id": original["model_id"],
                "original_adapter_version": original["adapter_version"],
                "original_parameters": Jsonb(original["parameters"]),
                "alternate_runtime_route_id": alternate["runtime_route_id"],
                "alternate_provider_id": alternate["provider_id"],
                "alternate_model_id": alternate["model_id"],
                "alternate_adapter_version": alternate["adapter_version"],
                "alternate_parameters": Jsonb(alternate["parameters"]),
                "agent_role": lineage["agent_role"],
                "task_kind": lineage["task_kind"],
                "policy_snapshot_ref": lineage.get("policy_snapshot_ref"),
                "prompt_reference": lineage["prompt_reference"],
                "prompt_hash": lineage["prompt_hash"],
                "response_schema_name": lineage["response_schema_name"],
                "response_schema_contract_ref": lineage["response_schema_contract_ref"],
                "response_schema_hash": lineage["response_schema_hash"],
                "route_version_ref": lineage.get("route_version_ref"),
                "provider_catalogue_id": lineage.get("provider_catalogue_id"),
                "eval_fixture_ref": lineage.get("eval_fixture_ref"),
                "transcript_source_ref": lineage.get("transcript_source_ref"),
                "comparator_name": comparator["name"],
                "comparator_version": comparator["version"],
                "comparator_status": comparator["status"],
                "comparator_result": Jsonb(comparator["result"]),
                "safe_error_reason": comparator.get("safe_error_reason"),
                "safe_skipped_reason": comparator.get("safe_skipped_reason"),
                "original_cost_amount": original_metrics["cost_amount_usd"],
                "original_cost_currency": original_metrics["cost_currency"],
                "original_latency_ms": original_metrics["latency_ms"],
                "original_token_usage": Jsonb(original_metrics["token_usage"]),
                "alternate_cost_amount": alternate_metrics["cost_amount_usd"],
                "alternate_cost_currency": alternate_metrics["cost_currency"],
                "alternate_latency_ms": alternate_metrics["latency_ms"],
                "alternate_token_usage": Jsonb(alternate_metrics["token_usage"]),
                "metric_deltas": Jsonb(metrics["delta"]),
                "started_at": data["started_at"],
                "completed_at": data["completed_at"],
                "raw_record": Jsonb(data),
            },
        )

    def list_replay_runs(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        limit: int = 500,
    ) -> list[ReplayRunRecordReadModel]:
        if workflow_id is not None:
            return fetch_models(
                self._conn,
                ReplayRunRecordReadModel,
                """
                SELECT *
                FROM replay_run_records
                WHERE tenant_id = %s AND workflow_id = %s
                ORDER BY completed_at DESC, replay_run_id ASC
                LIMIT %s
                """,
                (tenant_id, workflow_id, limit),
            )

        return fetch_models(
            self._conn,
            ReplayRunRecordReadModel,
            """
            SELECT *
            FROM replay_run_records
            WHERE tenant_id = %s
            ORDER BY completed_at DESC, replay_run_id ASC
            LIMIT %s
            """,
            (tenant_id, limit),
        )


__all__ = [
    "ReplayRunRecordReadModel",
    "ReplayRunStore",
]

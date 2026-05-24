# pyright: reportUnusedFunction=false
"""Projection-backed FastAPI BFF for Chorus local POC inspection surfaces."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator, Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Any

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from chorus.observability import set_current_span_attributes
from chorus.persistence import (
    ApprovalPackageReadModel,
    CalendarProjectionReadModel,
    ProjectionStore,
    WorkflowHistoryEventReadModel,
    WorkflowRunReadModel,
)
from chorus.persistence._query import set_tenant_context
from chorus.persistence.audit_port import (
    AuditPortStore,
    DecisionTrailEntryReadModel,
    ToolActionAuditReadModel,
)
from chorus.persistence.migrate import database_url_from_env
from chorus.persistence.provider_governance import (
    ModelRouteVersion,
    ProviderCatalogueModel,
    ProviderCatalogueProvider,
    ProviderGovernanceStore,
)
from chorus.persistence.replay_runs import ReplayRunRecordReadModel, ReplayRunStore
from chorus.persistence.runtime_policy import PolicySnapshotStore

DEFAULT_TENANT_ID = "tenant_demo"


def _tenant_id_from_env() -> str:
    return os.environ.get(
        "CHORUS_TENANT_ID",
        os.environ.get("CHORUS_BFF_DEFAULT_TENANT", DEFAULT_TENANT_ID),
    )


def _sse_poll_interval_from_env() -> float:
    raw = os.environ.get("CHORUS_BFF_SSE_POLL_INTERVAL_SECONDS")
    if raw is None or not raw.strip():
        return 1.0
    try:
        return float(raw)
    except ValueError:
        return 1.0


class BffSettings(BaseModel):
    """Environment-derived BFF runtime settings."""

    model_config = ConfigDict(extra="forbid")

    database_url: str = Field(
        default_factory=lambda: os.environ.get("CHORUS_DATABASE_URL", database_url_from_env())
    )
    tenant_id: str = Field(default_factory=_tenant_id_from_env)
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            f"http://localhost:{os.environ.get('FRONTEND_PORT', '5173')}",
        ]
    )
    sse_poll_interval_seconds: float = Field(default_factory=_sse_poll_interval_from_env, gt=0)


@dataclass(frozen=True)
class PortReaders:
    """Per-port read stores bound to a single request-scoped connection."""

    projection: ProjectionStore
    audit: AuditPortStore
    policy: PolicySnapshotStore
    governance: ProviderGovernanceStore
    replay: ReplayRunStore


class HealthResponse(BaseModel):
    status: str
    tenant_id: str


class WorkflowRunSummary(BaseModel):
    workflow_id: str
    run_id: str | None
    workflow_type: str
    status: str
    current_step: str | None
    started_at: str | None
    closed_at: str | None
    updated_at: str
    correlation_id: str
    subject_id: str
    subject_ref: str | None
    subject_summary: str | None
    subject_from: str | None
    metadata: dict[str, Any]


class WorkflowEventView(BaseModel):
    id: str
    workflow_id: str
    event_type: str
    sequence: int
    step: str | None
    occurred_at: str
    correlation_id: str
    payload: dict[str, Any]


class DecisionTrailEntryView(BaseModel):
    id: str
    workflow_id: str
    agent_id: str
    agent_role: str
    invocation_id: str
    prompt_ref: str
    prompt_hash: str
    model_route: str
    route_id: str | None
    route_version: int | None
    provider: str
    model: str
    fallback_reason: str | None
    fallback_applied: bool | None
    task_kind: str
    outcome: str
    reasoning_summary: str | None
    cost_usd: float | None
    latency_ms: int | None
    occurred_at: str
    correlation_id: str
    contract_refs: list[str]


class ToolVerdictEntryView(BaseModel):
    id: str
    workflow_id: str
    tool_name: str | None
    requested_mode: str | None
    enforced_mode: str | None
    verdict: str
    reason: str | None
    redactions: list[str]
    caller_agent_id: str
    correlation_id: str
    occurred_at: str


class CalendarStatusEntryView(BaseModel):
    id: str
    workflow_id: str
    correlation_id: str
    tool_name: str
    requested_action: str
    requested_mode: str
    enforced_mode: str
    approval_state: str
    idempotency_key_ref: str
    calendar_refs: dict[str, Any]
    projection_status: str
    source_audit_event_id: str
    latest_audit_event_id: str | None
    latest_verdict: str | None
    latest_reason: str | None
    connector_invocation_id: str | None
    retry_category: str | None
    compensation_category: str | None
    failure_category: str | None
    grant_ref: str | None
    policy_version_refs: dict[str, Any]
    trace_join: dict[str, Any]
    updated_at: str


class ApprovalPackageEntryView(BaseModel):
    id: str
    workflow_id: str
    workflow_type: str
    correlation_id: str
    approval_package_version: int
    approval_state: str
    decision: str | None
    reason_category: str
    agent_id: str
    agent_version: str
    requested_action: str
    tool_name: str
    requested_mode: str
    enforced_mode: str
    idempotency_key_ref: str
    redaction_summary: dict[str, Any]
    subject_refs: dict[str, Any]
    action_refs: dict[str, Any]
    requested_at: str
    decision_due_at: str
    expires_at: str
    decision_at: str | None
    source_audit_event_id: str
    latest_audit_event_id: str | None
    latest_verdict: str | None
    latest_reason: str | None
    connector_invocation_id: str | None
    grant_ref: str | None
    policy_version_refs: dict[str, Any]
    trace_join: dict[str, Any]
    updated_at: str


class RegistryEntryView(BaseModel):
    agent_id: str
    role: str
    version: str
    lifecycle_state: str
    owner: str
    prompt_ref: str
    prompt_hash: str
    capability_tags: list[str]
    updated_at: str


class GrantEntryView(BaseModel):
    grant_id: str
    agent_id: str
    agent_version: str
    tool_name: str
    mode: str
    allowed: bool
    approval_required: bool
    redaction_policy: dict[str, Any]


class RoutingEntryView(BaseModel):
    route_id: str
    agent_role: str
    task_kind: str
    tenant_tier: str
    runtime_route_id: str
    provider: str
    model: str
    parameters: dict[str, Any]
    budget_usd: float
    fallback_policy: dict[str, Any]
    lifecycle_state: str


class ProviderEntryView(BaseModel):
    catalogue_id: str
    provider_id: str
    display_name: str
    provider_kind: str
    lifecycle_state: str
    credential_required: bool
    secret_ref_names: list[str]
    missing_credentials_behaviour: str
    data_boundary: dict[str, Any]
    operational_limits: dict[str, Any]
    audit: dict[str, Any]


class ProviderModelEntryView(BaseModel):
    catalogue_id: str
    provider_id: str
    model_id: str
    display_name: str
    lifecycle_state: str
    supported_task_kinds: list[str]
    supports_structured_output: bool
    context_window_tokens: int | None
    cost_policy: dict[str, Any]


class RouteVersionEntryView(BaseModel):
    route_id: str
    route_version: int
    lifecycle_state: str
    agent_role: str
    task_kind: str
    tenant_tier: str
    runtime_route_id: str
    provider_catalogue_id: str
    provider_id: str
    model_id: str
    parameters: dict[str, Any]
    budget_usd: float
    max_latency_ms: int
    fallback_policy: dict[str, Any]
    eval_required: bool
    eval_fixture_refs: list[str]
    promotion: dict[str, Any]
    created_at: str


class ReplayRunEntryView(BaseModel):
    id: str
    workflow_id: str
    correlation_id: str
    original_invocation_id: str
    original_transcript_id: str
    original_route: str
    alternate_route: str
    comparator_status: str
    comparator_result: dict[str, Any]
    safe_error_reason: str | None
    safe_skipped_reason: str | None
    agent_role: str
    task_kind: str
    policy_snapshot_ref: str | None
    prompt_ref: str
    prompt_hash: str
    response_schema_ref: str
    response_schema_hash: str
    original_cost_usd: float
    alternate_cost_usd: float
    cost_delta_usd: float | None
    original_latency_ms: int
    alternate_latency_ms: int
    latency_delta_ms: int | None
    token_delta: dict[str, Any]
    started_at: str
    completed_at: str


class ProgressEvent(BaseModel):
    id: str
    workflow_id: str
    event_type: str
    sequence: int
    step: str | None
    payload: dict[str, Any]
    occurred_at: str
    correlation_id: str


def create_app(settings: BffSettings | None = None) -> FastAPI:
    resolved = settings or BffSettings()
    app = FastAPI(title="Chorus BFF", version="0.1.0")
    app.state.settings = resolved

    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(set(resolved.cors_origins)),
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", tenant_id=resolved.tenant_id)

    @app.get("/api/workflows", response_model=list[WorkflowRunSummary])
    def list_workflows(
        readers: Annotated[PortReaders, Depends(readers_dependency)],
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[WorkflowRunSummary]:
        rows = readers.projection.list_workflows(resolved.tenant_id, limit=limit)
        return [_workflow_view(row) for row in rows]

    @app.get("/api/workflows/{workflow_id}", response_model=WorkflowRunSummary)
    def get_workflow(
        workflow_id: str,
        readers: Annotated[PortReaders, Depends(readers_dependency)],
    ) -> WorkflowRunSummary:
        row = readers.projection.get_workflow(resolved.tenant_id, workflow_id)
        if row is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        return _workflow_view(row)

    @app.get("/api/workflows/{workflow_id}/events", response_model=list[WorkflowEventView])
    def list_workflow_events(
        workflow_id: str,
        readers: Annotated[PortReaders, Depends(readers_dependency)],
        after_sequence: Annotated[int | None, Query(ge=0)] = None,
        limit: Annotated[int, Query(ge=1, le=1_000)] = 500,
    ) -> list[WorkflowEventView]:
        events = readers.projection.list_workflow_history(
            resolved.tenant_id,
            workflow_id,
            after_sequence=after_sequence,
            limit=limit,
        )
        return [_workflow_event_view(row) for row in events]

    @app.get(
        "/api/workflows/{workflow_id}/decision-trail",
        response_model=list[DecisionTrailEntryView],
    )
    def list_workflow_decisions(
        workflow_id: str,
        readers: Annotated[PortReaders, Depends(readers_dependency)],
    ) -> list[DecisionTrailEntryView]:
        entries = readers.audit.list_decision_trail(resolved.tenant_id, workflow_id=workflow_id)
        return [_decision_view(row) for row in entries]

    @app.get(
        "/api/workflows/{workflow_id}/tool-verdicts",
        response_model=list[ToolVerdictEntryView],
    )
    def list_workflow_tool_verdicts(
        workflow_id: str,
        readers: Annotated[PortReaders, Depends(readers_dependency)],
    ) -> list[ToolVerdictEntryView]:
        entries = readers.audit.list_tool_action_audit(resolved.tenant_id, workflow_id=workflow_id)
        return [_tool_verdict_view(row) for row in entries]

    @app.get("/api/decision-trail", response_model=list[DecisionTrailEntryView])
    def list_decision_trail(
        readers: Annotated[PortReaders, Depends(readers_dependency)],
        limit: Annotated[int, Query(ge=1, le=1_000)] = 500,
    ) -> list[DecisionTrailEntryView]:
        entries = readers.audit.list_decision_trail(resolved.tenant_id, limit=limit)
        return [_decision_view(row) for row in entries]

    @app.get("/api/tool-verdicts", response_model=list[ToolVerdictEntryView])
    def list_tool_verdicts(
        readers: Annotated[PortReaders, Depends(readers_dependency)],
        limit: Annotated[int, Query(ge=1, le=1_000)] = 500,
    ) -> list[ToolVerdictEntryView]:
        entries = readers.audit.list_tool_action_audit(resolved.tenant_id, limit=limit)
        return [_tool_verdict_view(row) for row in entries]

    @app.get("/api/calendar/status", response_model=list[CalendarStatusEntryView])
    def list_calendar_status(
        readers: Annotated[PortReaders, Depends(readers_dependency)],
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[CalendarStatusEntryView]:
        entries = readers.projection.list_calendar_projections(resolved.tenant_id, limit=limit)
        return [_calendar_status_view(row) for row in entries]

    @app.get(
        "/api/workflows/{workflow_id}/calendar/status",
        response_model=list[CalendarStatusEntryView],
    )
    def list_workflow_calendar_status(
        workflow_id: str,
        readers: Annotated[PortReaders, Depends(readers_dependency)],
    ) -> list[CalendarStatusEntryView]:
        entries = readers.projection.list_calendar_projections(
            resolved.tenant_id, workflow_id=workflow_id
        )
        return [_calendar_status_view(row) for row in entries]

    @app.get("/api/approval-packages", response_model=list[ApprovalPackageEntryView])
    def list_approval_packages(
        readers: Annotated[PortReaders, Depends(readers_dependency)],
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[ApprovalPackageEntryView]:
        entries = readers.projection.list_approval_packages(resolved.tenant_id, limit=limit)
        return [_approval_package_view(row) for row in entries]

    @app.get(
        "/api/workflows/{workflow_id}/approval-packages",
        response_model=list[ApprovalPackageEntryView],
    )
    def list_workflow_approval_packages(
        workflow_id: str,
        readers: Annotated[PortReaders, Depends(readers_dependency)],
    ) -> list[ApprovalPackageEntryView]:
        entries = readers.projection.list_approval_packages(
            resolved.tenant_id, workflow_id=workflow_id
        )
        return [_approval_package_view(row) for row in entries]

    @app.get("/api/runtime/registry", response_model=list[RegistryEntryView])
    def list_registry(
        readers: Annotated[PortReaders, Depends(readers_dependency)],
    ) -> list[RegistryEntryView]:
        snapshot = readers.policy.snapshot(resolved.tenant_id)
        return [
            RegistryEntryView(
                agent_id=row.agent_id,
                role=row.role,
                version=row.version,
                lifecycle_state=row.lifecycle_state,
                owner=row.owner,
                prompt_ref=row.prompt_reference,
                prompt_hash=row.prompt_hash,
                capability_tags=row.capability_tags,
                updated_at=row.updated_at.isoformat(),
            )
            for row in snapshot.agents
        ]

    @app.get("/api/runtime/grants", response_model=list[GrantEntryView])
    def list_grants(
        readers: Annotated[PortReaders, Depends(readers_dependency)],
    ) -> list[GrantEntryView]:
        snapshot = readers.policy.snapshot(resolved.tenant_id)
        return [
            GrantEntryView(
                grant_id=str(row.grant_id),
                agent_id=row.agent_id,
                agent_version=row.agent_version,
                tool_name=row.tool_name,
                mode=row.mode,
                allowed=row.allowed,
                approval_required=row.approval_required,
                redaction_policy=row.redaction_policy,
            )
            for row in snapshot.tool_grants
        ]

    @app.get("/api/runtime/routing", response_model=list[RoutingEntryView])
    def list_routing(
        readers: Annotated[PortReaders, Depends(readers_dependency)],
    ) -> list[RoutingEntryView]:
        snapshot = readers.policy.snapshot(resolved.tenant_id)
        return [
            RoutingEntryView(
                route_id=str(row.policy_id),
                agent_role=row.agent_role,
                task_kind=row.task_kind,
                tenant_tier=row.tenant_tier,
                runtime_route_id=row.runtime_route_id,
                provider=row.provider,
                model=row.model,
                parameters=row.parameters,
                budget_usd=_decimal_to_float(row.budget_cap_usd),
                fallback_policy=row.fallback_policy,
                lifecycle_state=row.lifecycle_state,
            )
            for row in snapshot.model_routes
        ]

    @app.get("/api/runtime/providers", response_model=list[ProviderEntryView])
    def list_providers(
        readers: Annotated[PortReaders, Depends(readers_dependency)],
    ) -> list[ProviderEntryView]:
        snapshot = readers.governance.snapshot(resolved.tenant_id)
        return [_provider_view(row) for row in snapshot.providers]

    @app.get("/api/runtime/provider-models", response_model=list[ProviderModelEntryView])
    def list_provider_models(
        readers: Annotated[PortReaders, Depends(readers_dependency)],
    ) -> list[ProviderModelEntryView]:
        snapshot = readers.governance.snapshot(resolved.tenant_id)
        return [_provider_model_view(row) for row in snapshot.provider_models]

    @app.get("/api/runtime/route-versions", response_model=list[RouteVersionEntryView])
    def list_route_versions(
        readers: Annotated[PortReaders, Depends(readers_dependency)],
    ) -> list[RouteVersionEntryView]:
        snapshot = readers.governance.snapshot(resolved.tenant_id)
        return [_route_version_view(row) for row in snapshot.route_versions]

    @app.get("/api/eval/replay-runs", response_model=list[ReplayRunEntryView])
    def list_replay_runs(
        readers: Annotated[PortReaders, Depends(readers_dependency)],
        limit: Annotated[int, Query(ge=1, le=1_000)] = 500,
    ) -> list[ReplayRunEntryView]:
        rows = readers.replay.list_replay_runs(resolved.tenant_id, limit=limit)
        return [_replay_run_view(row) for row in rows]

    @app.get(
        "/api/workflows/{workflow_id}/replay-runs",
        response_model=list[ReplayRunEntryView],
    )
    def list_workflow_replay_runs(
        workflow_id: str,
        readers: Annotated[PortReaders, Depends(readers_dependency)],
    ) -> list[ReplayRunEntryView]:
        rows = readers.replay.list_replay_runs(resolved.tenant_id, workflow_id=workflow_id)
        return [_replay_run_view(row) for row in rows]

    @app.get("/api/progress")
    async def progress(
        request: Request,
        snapshot_store: Annotated[ProjectionStore | None, Depends(progress_projection_dependency)],
        workflow_id: Annotated[str | None, Query()] = None,
        correlation_id: Annotated[str | None, Query()] = None,
        once: Annotated[bool, Query()] = False,
    ) -> StreamingResponse:
        set_current_span_attributes(
            tenant_id=resolved.tenant_id,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
        )
        return StreamingResponse(
            _progress_events(
                request,
                resolved,
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                once=once,
                snapshot_store=snapshot_store,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


def readers_dependency(request: Request) -> Iterator[PortReaders]:
    settings = request.app.state.settings
    if not isinstance(settings, BffSettings):
        raise RuntimeError("BFF settings are not configured")

    with _port_readers(settings) as readers:
        yield readers


def progress_projection_dependency(
    request: Request,
    once: Annotated[bool, Query()] = False,
) -> Iterator[ProjectionStore | None]:
    if not once:
        yield None
        return

    settings = request.app.state.settings
    if not isinstance(settings, BffSettings):
        raise RuntimeError("BFF settings are not configured")

    with _projection_store(settings) as store:
        yield store


@contextmanager
def _port_readers(settings: BffSettings) -> Generator[PortReaders]:
    with psycopg.connect(settings.database_url) as conn:
        set_tenant_context(conn, settings.tenant_id)
        yield PortReaders(
            projection=ProjectionStore(conn),
            audit=AuditPortStore(conn),
            policy=PolicySnapshotStore(conn),
            governance=ProviderGovernanceStore(conn),
            replay=ReplayRunStore(conn),
        )


@contextmanager
def _projection_store(settings: BffSettings) -> Generator[ProjectionStore]:
    with psycopg.connect(settings.database_url) as conn:
        set_tenant_context(conn, settings.tenant_id)
        yield ProjectionStore(conn)


async def _progress_events(
    request: Request,
    settings: BffSettings,
    *,
    workflow_id: str | None,
    correlation_id: str | None,
    once: bool,
    snapshot_store: ProjectionStore | None,
) -> AsyncIterator[str]:
    emitted: set[str] = set()
    yield ": chorus-bff progress stream open\n\n"
    while True:
        if await request.is_disconnected():
            break

        if snapshot_store is not None:
            recent = snapshot_store.list_recent_workflow_history(settings.tenant_id, limit=100)
        else:
            with _projection_store(settings) as store:
                recent = store.list_recent_workflow_history(settings.tenant_id, limit=100)

        events = [
            event
            for event in reversed(recent)
            if (workflow_id is None or event.workflow_id == workflow_id)
            and (correlation_id is None or event.correlation_id == correlation_id)
        ]

        for event in events:
            event_id = str(event.source_event_id)
            if event_id in emitted:
                continue
            emitted.add(event_id)
            yield _sse_payload(event_id, _progress_view(event))

        if once:
            break
        await asyncio.sleep(settings.sse_poll_interval_seconds)


def _sse_payload(event_id: str, event: ProgressEvent) -> str:
    payload = json.dumps(event.model_dump(mode="json"), separators=(",", ":"))
    return f"id: {event_id}\nevent: progress\ndata: {payload}\n\n"


def _workflow_view(row: WorkflowRunReadModel) -> WorkflowRunSummary:
    subject_from = row.metadata.get("subject_from")
    if not isinstance(subject_from, str):
        subject_from = row.metadata.get("sender")
    return WorkflowRunSummary(
        workflow_id=row.workflow_id,
        run_id=None,
        workflow_type=row.workflow_type,
        status=row.status,
        current_step=row.current_step,
        started_at=row.started_at.isoformat() if row.started_at is not None else None,
        closed_at=row.completed_at.isoformat() if row.completed_at is not None else None,
        updated_at=row.updated_at.isoformat(),
        correlation_id=row.correlation_id,
        subject_id=str(row.subject_id),
        subject_ref=row.subject_ref,
        subject_summary=row.subject_summary or None,
        subject_from=subject_from if isinstance(subject_from, str) else None,
        metadata=row.metadata,
    )


def _workflow_event_view(row: WorkflowHistoryEventReadModel) -> WorkflowEventView:
    return WorkflowEventView(
        id=str(row.source_event_id),
        workflow_id=row.workflow_id,
        event_type=row.event_type,
        sequence=row.sequence,
        step=row.step,
        occurred_at=row.occurred_at.isoformat(),
        correlation_id=row.correlation_id,
        payload=row.payload,
    )


def _progress_view(row: WorkflowHistoryEventReadModel) -> ProgressEvent:
    return ProgressEvent(
        id=str(row.source_event_id),
        workflow_id=row.workflow_id,
        event_type=row.event_type,
        sequence=row.sequence,
        step=row.step,
        payload=row.payload,
        occurred_at=row.occurred_at.isoformat(),
        correlation_id=row.correlation_id,
    )


def _metadata_str(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None


def _metadata_int(metadata: dict[str, Any], key: str) -> int | None:
    value = metadata.get(key)
    return value if isinstance(value, int) else None


def _metadata_bool(metadata: dict[str, Any], key: str) -> bool | None:
    value = metadata.get(key)
    return value if isinstance(value, bool) else None


def _decision_view(row: DecisionTrailEntryReadModel) -> DecisionTrailEntryView:
    return DecisionTrailEntryView(
        id=str(row.invocation_id),
        workflow_id=row.workflow_id,
        agent_id=row.agent_id,
        agent_role=row.agent_role,
        invocation_id=str(row.invocation_id),
        prompt_ref=row.prompt_reference,
        prompt_hash=row.prompt_hash,
        model_route=f"{row.provider}/{row.model}",
        route_id=_metadata_str(row.metadata, "model_route.route_id"),
        route_version=_metadata_int(row.metadata, "model_route.route_version"),
        provider=row.provider,
        model=row.model,
        fallback_reason=_metadata_str(row.metadata, "model_route.fallback_reason"),
        fallback_applied=_metadata_bool(row.metadata, "provider_fallback.applied"),
        task_kind=row.task_kind,
        outcome=row.outcome,
        reasoning_summary=row.justification or row.output_summary or None,
        cost_usd=_decimal_to_float(row.cost_amount),
        latency_ms=row.duration_ms,
        occurred_at=row.completed_at.isoformat(),
        correlation_id=row.correlation_id,
        contract_refs=row.contract_refs,
    )


def _tool_verdict_view(row: ToolActionAuditReadModel) -> ToolVerdictEntryView:
    return ToolVerdictEntryView(
        id=str(row.audit_event_id),
        workflow_id=row.workflow_id,
        tool_name=row.tool_name,
        requested_mode=row.requested_mode,
        enforced_mode=row.enforced_mode,
        verdict=row.verdict,
        reason=row.reason,
        redactions=_redacted_fields(row.arguments_redacted),
        caller_agent_id=row.actor_id,
        correlation_id=row.correlation_id,
        occurred_at=row.occurred_at.isoformat(),
    )


def _calendar_status_view(row: CalendarProjectionReadModel) -> CalendarStatusEntryView:
    return CalendarStatusEntryView(
        id=str(row.approval_id),
        workflow_id=row.workflow_id,
        correlation_id=row.correlation_id,
        tool_name=row.tool_name,
        requested_action=row.requested_action,
        requested_mode=row.requested_mode,
        enforced_mode=row.enforced_mode,
        approval_state=row.approval_state,
        idempotency_key_ref=row.idempotency_key_ref,
        calendar_refs=row.calendar_refs,
        projection_status=row.projection_status,
        source_audit_event_id=str(row.source_audit_event_id),
        latest_audit_event_id=(
            str(row.latest_audit_event_id) if row.latest_audit_event_id is not None else None
        ),
        latest_verdict=row.latest_verdict,
        latest_reason=row.latest_reason,
        connector_invocation_id=(
            str(row.connector_invocation_id) if row.connector_invocation_id is not None else None
        ),
        retry_category=row.retry_category,
        compensation_category=row.compensation_category,
        failure_category=row.failure_category,
        grant_ref=row.grant_ref,
        policy_version_refs=row.policy_version_refs,
        trace_join=row.trace_join,
        updated_at=row.updated_at.isoformat(),
    )


def _approval_package_view(row: ApprovalPackageReadModel) -> ApprovalPackageEntryView:
    return ApprovalPackageEntryView(
        id=str(row.approval_id),
        workflow_id=row.workflow_id,
        workflow_type=row.workflow_type,
        correlation_id=row.correlation_id,
        approval_package_version=row.approval_package_version,
        approval_state=row.approval_state,
        decision=row.decision,
        reason_category=row.reason_category,
        agent_id=row.agent_id,
        agent_version=row.agent_version,
        requested_action=row.requested_action,
        tool_name=row.tool_name,
        requested_mode=row.requested_mode,
        enforced_mode=row.enforced_mode,
        idempotency_key_ref=row.idempotency_key_ref,
        redaction_summary=row.redaction_summary,
        subject_refs=row.subject_refs,
        action_refs=row.action_refs,
        requested_at=row.requested_at.isoformat(),
        decision_due_at=row.decision_due_at.isoformat(),
        expires_at=row.expires_at.isoformat(),
        decision_at=row.decision_at.isoformat() if row.decision_at is not None else None,
        source_audit_event_id=str(row.source_audit_event_id),
        latest_audit_event_id=(
            str(row.latest_audit_event_id) if row.latest_audit_event_id is not None else None
        ),
        latest_verdict=row.latest_verdict,
        latest_reason=row.latest_reason,
        connector_invocation_id=(
            str(row.connector_invocation_id) if row.connector_invocation_id is not None else None
        ),
        grant_ref=row.grant_ref,
        policy_version_refs=row.policy_version_refs,
        trace_join=row.trace_join,
        updated_at=row.updated_at.isoformat(),
    )


def _redacted_fields(arguments: dict[str, Any]) -> list[str]:
    return sorted(key for key, value in arguments.items() if value == "[redacted]")


def _provider_view(row: ProviderCatalogueProvider) -> ProviderEntryView:
    return ProviderEntryView(
        catalogue_id=row.catalogue_id,
        provider_id=row.provider_id,
        display_name=row.display_name,
        provider_kind=row.provider_kind,
        lifecycle_state=row.lifecycle_state,
        credential_required=row.credential_required,
        secret_ref_names=row.secret_ref_names,
        missing_credentials_behaviour=row.missing_credentials_behaviour,
        data_boundary=row.data_boundary,
        operational_limits=row.operational_limits,
        audit=row.audit,
    )


def _provider_model_view(row: ProviderCatalogueModel) -> ProviderModelEntryView:
    return ProviderModelEntryView(
        catalogue_id=row.catalogue_id,
        provider_id=row.provider_id,
        model_id=row.model_id,
        display_name=row.display_name,
        lifecycle_state=row.lifecycle_state,
        supported_task_kinds=row.supported_task_kinds,
        supports_structured_output=row.supports_structured_output,
        context_window_tokens=row.context_window_tokens,
        cost_policy=row.cost_policy,
    )


def _route_version_view(row: ModelRouteVersion) -> RouteVersionEntryView:
    return RouteVersionEntryView(
        route_id=str(row.route_id),
        route_version=row.route_version,
        lifecycle_state=row.lifecycle_state,
        agent_role=row.agent_role,
        task_kind=row.task_kind,
        tenant_tier=row.tenant_tier,
        runtime_route_id=row.runtime_route_id,
        provider_catalogue_id=row.provider_catalogue_id,
        provider_id=row.provider_id,
        model_id=row.model_id,
        parameters=row.parameters,
        budget_usd=_decimal_to_float(row.budget_cap_usd),
        max_latency_ms=row.max_latency_ms,
        fallback_policy=row.fallback_policy,
        eval_required=row.eval_required,
        eval_fixture_refs=row.eval_fixture_refs,
        promotion=row.promotion,
        created_at=row.created_at.isoformat(),
    )


def _replay_run_view(row: ReplayRunRecordReadModel) -> ReplayRunEntryView:
    return ReplayRunEntryView(
        id=str(row.replay_run_id),
        workflow_id=row.workflow_id,
        correlation_id=row.correlation_id,
        original_invocation_id=str(row.original_invocation_id),
        original_transcript_id=str(row.original_transcript_id),
        original_route=(
            f"{row.original_runtime_route_id} ({row.original_provider_id}/{row.original_model_id})"
        ),
        alternate_route=(
            f"{row.alternate_runtime_route_id} "
            f"({row.alternate_provider_id}/{row.alternate_model_id})"
        ),
        comparator_status=row.comparator_status,
        comparator_result=row.comparator_result,
        safe_error_reason=row.safe_error_reason,
        safe_skipped_reason=row.safe_skipped_reason,
        agent_role=row.agent_role,
        task_kind=row.task_kind,
        policy_snapshot_ref=row.policy_snapshot_ref,
        prompt_ref=row.prompt_reference,
        prompt_hash=row.prompt_hash,
        response_schema_ref=row.response_schema_contract_ref,
        response_schema_hash=row.response_schema_hash,
        original_cost_usd=_decimal_to_float(row.original_cost_amount),
        alternate_cost_usd=_decimal_to_float(row.alternate_cost_amount),
        cost_delta_usd=_numeric_delta(row.metric_deltas, "cost_amount_usd"),
        original_latency_ms=row.original_latency_ms,
        alternate_latency_ms=row.alternate_latency_ms,
        latency_delta_ms=_integer_delta(row.metric_deltas, "latency_ms"),
        token_delta=row.metric_deltas.get("token_usage", {}),
        started_at=row.started_at.isoformat(),
        completed_at=row.completed_at.isoformat(),
    )


def _numeric_delta(metadata: dict[str, Any], key: str) -> float | None:
    value = metadata.get(key)
    if isinstance(value, int | float):
        return float(value)
    return None


def _integer_delta(metadata: dict[str, Any], key: str) -> int | None:
    value = metadata.get(key)
    return value if isinstance(value, int) else None


def _decimal_to_float(value: Decimal) -> float:
    return float(value)


app = create_app()

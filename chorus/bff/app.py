# pyright: reportUnusedFunction=false
"""Projection-backed FastAPI BFF for the Phase 1A Lighthouse UI."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator, Generator, Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Annotated, Any

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from chorus.observability import set_current_span_attributes
from chorus.persistence import (
    CalendarProjectionReadModel,
    DecisionTrailEntryReadModel,
    ModelRouteVersion,
    ProjectionStore,
    ProviderCatalogueModel,
    ProviderCatalogueProvider,
    SupportAgentDecisionReadModel,
    SupportCaseUpdateProposalReadModel,
    SupportInspectionReadModel,
    SupportStatusWriteBoundaryReadModel,
    SupportTicketVerdictReadModel,
    SupportWorkflowEventReadModel,
    ToolActionAuditReadModel,
    WorkflowHistoryEventReadModel,
    WorkflowRunReadModel,
)
from chorus.persistence.migrate import database_url_from_env

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
    lead_id: str
    lead_subject: str | None
    lead_from: str | None
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


class SupportWorkflowEventSummaryView(BaseModel):
    id: str
    workflow_id: str
    correlation_id: str
    workflow_type: str
    request_ref: str | None
    event_type: str
    sequence: int
    step: str | None
    case_ref: str | None
    account_ref: str | None
    product_ref: str | None
    severity_category: str | None
    case_status_category: str | None
    verdict_category: str | None
    gateway_verdict: str | None
    enforced_mode: str | None
    case_update_ref: str | None
    outcome: str | None
    trace_join: dict[str, Any]
    occurred_at: str


class SupportAgentDecisionSummaryView(BaseModel):
    id: str
    workflow_id: str
    correlation_id: str
    invocation_id: str
    agent_id: str
    agent_role: str
    agent_version: str
    task_kind: str
    provider: str
    model: str
    route_id: str | None
    route_version: int | None
    outcome: str
    cost_usd: float
    latency_ms: int
    contract_refs: list[str]
    trace_join: dict[str, Any]
    occurred_at: str


class SupportTicketVerdictSummaryView(BaseModel):
    id: str
    workflow_id: str
    correlation_id: str
    invocation_id: str | None
    tool_call_id: str | None
    verdict_id: str | None
    agent_id: str
    tool_name: str
    requested_mode: str | None
    enforced_mode: str | None
    verdict: str
    reason_category: str
    idempotency_key_ref: str | None
    connector_invocation_id: str | None
    output_refs: dict[str, Any]
    trace_join: dict[str, Any]
    occurred_at: str


class SupportCaseUpdateProposalSummaryView(BaseModel):
    id: str
    workflow_id: str
    correlation_id: str
    source_audit_event_id: str
    connector_invocation_id: str
    request_ref: str
    case_ref: str
    account_ref: str
    product_ref: str
    severity_category: str
    target_status_category: str
    update_reason_category: str
    proposal_status: str
    policy_ref: str | None
    case_status_mutated: bool
    trace_join: dict[str, Any]
    updated_at: str


class SupportStatusWriteBoundaryView(BaseModel):
    grant_ref: str
    agent_id: str
    agent_version: str
    tool_name: str
    mode: str
    allowed: bool
    approval_required: bool


class SupportInspectionEntryView(BaseModel):
    tenant_id: str
    workflow_id: str
    correlation_id: str
    workflow_type: str
    request_refs: list[str]
    case_refs: list[str]
    account_refs: list[str]
    product_refs: list[str]
    proposed_case_update_refs: list[str]
    latest_event_sequence: int | None
    workflow_events: list[SupportWorkflowEventSummaryView]
    agent_decisions: list[SupportAgentDecisionSummaryView]
    ticket_verdicts: list[SupportTicketVerdictSummaryView]
    proposed_case_updates: list[SupportCaseUpdateProposalSummaryView]
    status_write_boundary: list[SupportStatusWriteBoundaryView]
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
    app = FastAPI(title="Chorus Lighthouse BFF", version="0.1.0")
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
        store: Annotated[ProjectionStore, Depends(store_dependency)],
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[WorkflowRunSummary]:
        rows = store.list_workflows(resolved.tenant_id, limit=limit)
        return [_workflow_view(row) for row in rows]

    @app.get("/api/workflows/{workflow_id}", response_model=WorkflowRunSummary)
    def get_workflow(
        workflow_id: str,
        store: Annotated[ProjectionStore, Depends(store_dependency)],
    ) -> WorkflowRunSummary:
        row = store.get_workflow(resolved.tenant_id, workflow_id)
        if row is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        return _workflow_view(row)

    @app.get("/api/workflows/{workflow_id}/events", response_model=list[WorkflowEventView])
    def list_workflow_events(
        workflow_id: str,
        store: Annotated[ProjectionStore, Depends(store_dependency)],
        after_sequence: Annotated[int | None, Query(ge=0)] = None,
        limit: Annotated[int, Query(ge=1, le=1_000)] = 500,
    ) -> list[WorkflowEventView]:
        events = store.list_workflow_history(
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
        store: Annotated[ProjectionStore, Depends(store_dependency)],
    ) -> list[DecisionTrailEntryView]:
        entries = store.list_decision_trail(resolved.tenant_id, workflow_id=workflow_id)
        return [_decision_view(row) for row in entries]

    @app.get(
        "/api/workflows/{workflow_id}/tool-verdicts",
        response_model=list[ToolVerdictEntryView],
    )
    def list_workflow_tool_verdicts(
        workflow_id: str,
        store: Annotated[ProjectionStore, Depends(store_dependency)],
    ) -> list[ToolVerdictEntryView]:
        entries = store.list_tool_action_audit(resolved.tenant_id, workflow_id=workflow_id)
        return [_tool_verdict_view(row) for row in entries]

    @app.get("/api/decision-trail", response_model=list[DecisionTrailEntryView])
    def list_decision_trail(
        store: Annotated[ProjectionStore, Depends(store_dependency)],
        limit: Annotated[int, Query(ge=1, le=1_000)] = 500,
    ) -> list[DecisionTrailEntryView]:
        entries = store.list_decision_trail(resolved.tenant_id, limit=limit)
        return [_decision_view(row) for row in entries]

    @app.get("/api/tool-verdicts", response_model=list[ToolVerdictEntryView])
    def list_tool_verdicts(
        store: Annotated[ProjectionStore, Depends(store_dependency)],
        limit: Annotated[int, Query(ge=1, le=1_000)] = 500,
    ) -> list[ToolVerdictEntryView]:
        entries = store.list_tool_action_audit(resolved.tenant_id, limit=limit)
        return [_tool_verdict_view(row) for row in entries]

    @app.get("/api/calendar/status", response_model=list[CalendarStatusEntryView])
    def list_calendar_status(
        store: Annotated[ProjectionStore, Depends(store_dependency)],
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[CalendarStatusEntryView]:
        entries = store.list_calendar_projections(resolved.tenant_id, limit=limit)
        return [_calendar_status_view(row) for row in entries]

    @app.get(
        "/api/workflows/{workflow_id}/calendar/status",
        response_model=list[CalendarStatusEntryView],
    )
    def list_workflow_calendar_status(
        workflow_id: str,
        store: Annotated[ProjectionStore, Depends(store_dependency)],
    ) -> list[CalendarStatusEntryView]:
        entries = store.list_calendar_projections(resolved.tenant_id, workflow_id=workflow_id)
        return [_calendar_status_view(row) for row in entries]

    @app.get("/api/support/inspections", response_model=list[SupportInspectionEntryView])
    def list_support_inspections(
        store: Annotated[ProjectionStore, Depends(store_dependency)],
        workflow_id: Annotated[str | None, Query()] = None,
        correlation_id: Annotated[str | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> list[SupportInspectionEntryView]:
        entries = store.list_support_inspections(
            resolved.tenant_id,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
            limit=limit,
        )
        return [_support_inspection_view(row) for row in entries]

    @app.get(
        "/api/workflows/{workflow_id}/support/inspection",
        response_model=SupportInspectionEntryView,
    )
    def get_workflow_support_inspection(
        workflow_id: str,
        store: Annotated[ProjectionStore, Depends(store_dependency)],
    ) -> SupportInspectionEntryView:
        entries = store.list_support_inspections(
            resolved.tenant_id,
            workflow_id=workflow_id,
            limit=1,
        )
        if not entries:
            raise HTTPException(status_code=404, detail="support inspection not found")
        return _support_inspection_view(entries[0])

    @app.get("/api/runtime/registry", response_model=list[RegistryEntryView])
    def list_registry(
        store: Annotated[ProjectionStore, Depends(store_dependency)],
    ) -> list[RegistryEntryView]:
        snapshot = store.runtime_policy_snapshot(resolved.tenant_id)
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
        store: Annotated[ProjectionStore, Depends(store_dependency)],
    ) -> list[GrantEntryView]:
        snapshot = store.runtime_policy_snapshot(resolved.tenant_id)
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
        store: Annotated[ProjectionStore, Depends(store_dependency)],
    ) -> list[RoutingEntryView]:
        snapshot = store.runtime_policy_snapshot(resolved.tenant_id)
        return [
            RoutingEntryView(
                route_id=str(row.policy_id),
                agent_role=row.agent_role,
                task_kind=row.task_kind,
                tenant_tier=row.tenant_tier,
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
        store: Annotated[ProjectionStore, Depends(store_dependency)],
    ) -> list[ProviderEntryView]:
        snapshot = store.provider_governance_snapshot(resolved.tenant_id)
        return [_provider_view(row) for row in snapshot.providers]

    @app.get("/api/runtime/provider-models", response_model=list[ProviderModelEntryView])
    def list_provider_models(
        store: Annotated[ProjectionStore, Depends(store_dependency)],
    ) -> list[ProviderModelEntryView]:
        snapshot = store.provider_governance_snapshot(resolved.tenant_id)
        return [_provider_model_view(row) for row in snapshot.provider_models]

    @app.get("/api/runtime/route-versions", response_model=list[RouteVersionEntryView])
    def list_route_versions(
        store: Annotated[ProjectionStore, Depends(store_dependency)],
    ) -> list[RouteVersionEntryView]:
        snapshot = store.provider_governance_snapshot(resolved.tenant_id)
        return [_route_version_view(row) for row in snapshot.route_versions]

    @app.get("/api/progress")
    async def progress(
        request: Request,
        snapshot_store: Annotated[
            ProjectionStore | None, Depends(progress_snapshot_store_dependency)
        ],
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


def store_dependency(request: Request) -> Iterator[ProjectionStore]:
    settings = request.app.state.settings
    if not isinstance(settings, BffSettings):
        raise RuntimeError("BFF settings are not configured")

    with _projection_store(settings) as store:
        yield store


def progress_snapshot_store_dependency(
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
def _projection_store(settings: BffSettings) -> Generator[ProjectionStore]:
    with psycopg.connect(settings.database_url) as conn:
        store = ProjectionStore(conn)
        store.set_tenant_context(settings.tenant_id)
        yield store


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
    lead_from = row.metadata.get("sender")
    return WorkflowRunSummary(
        workflow_id=row.workflow_id,
        run_id=None,
        workflow_type="Lighthouse",
        status=row.status,
        current_step=row.current_step,
        started_at=row.started_at.isoformat() if row.started_at is not None else None,
        closed_at=row.completed_at.isoformat() if row.completed_at is not None else None,
        updated_at=row.updated_at.isoformat(),
        correlation_id=row.correlation_id,
        lead_id=str(row.lead_id),
        lead_subject=row.lead_summary or None,
        lead_from=lead_from if isinstance(lead_from, str) else None,
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


def _support_inspection_view(row: SupportInspectionReadModel) -> SupportInspectionEntryView:
    return SupportInspectionEntryView(
        tenant_id=row.tenant_id,
        workflow_id=row.workflow_id,
        correlation_id=row.correlation_id,
        workflow_type=row.workflow_type,
        request_refs=row.request_refs,
        case_refs=row.case_refs,
        account_refs=row.account_refs,
        product_refs=row.product_refs,
        proposed_case_update_refs=row.proposed_case_update_refs,
        latest_event_sequence=row.latest_event_sequence,
        workflow_events=[_support_event_view(event) for event in row.workflow_events],
        agent_decisions=[_support_decision_view(decision) for decision in row.agent_decisions],
        ticket_verdicts=[_support_ticket_verdict_view(verdict) for verdict in row.ticket_verdicts],
        proposed_case_updates=[
            _support_case_update_view(proposal) for proposal in row.proposed_case_updates
        ],
        status_write_boundary=[
            _support_status_write_boundary_view(boundary) for boundary in row.status_write_boundary
        ],
        updated_at=row.updated_at.isoformat(),
    )


def _support_event_view(row: SupportWorkflowEventReadModel) -> SupportWorkflowEventSummaryView:
    return SupportWorkflowEventSummaryView(
        id=str(row.source_event_id),
        workflow_id=row.workflow_id,
        correlation_id=row.correlation_id,
        workflow_type=row.workflow_type,
        request_ref=row.request_ref,
        event_type=row.event_type,
        sequence=row.sequence,
        step=row.step,
        case_ref=row.case_ref,
        account_ref=row.account_ref,
        product_ref=row.product_ref,
        severity_category=row.severity_category,
        case_status_category=row.case_status_category,
        verdict_category=row.verdict_category,
        gateway_verdict=row.gateway_verdict,
        enforced_mode=row.enforced_mode,
        case_update_ref=row.case_update_ref,
        outcome=row.outcome,
        trace_join=row.trace_join,
        occurred_at=row.occurred_at.isoformat(),
    )


def _support_decision_view(row: SupportAgentDecisionReadModel) -> SupportAgentDecisionSummaryView:
    return SupportAgentDecisionSummaryView(
        id=str(row.invocation_id),
        workflow_id=row.workflow_id,
        correlation_id=row.correlation_id,
        invocation_id=str(row.invocation_id),
        agent_id=row.agent_id,
        agent_role=row.agent_role,
        agent_version=row.agent_version,
        task_kind=row.task_kind,
        provider=row.provider,
        model=row.model,
        route_id=row.route_id,
        route_version=row.route_version,
        outcome=row.outcome,
        cost_usd=_decimal_to_float(row.cost_amount),
        latency_ms=row.duration_ms,
        contract_refs=row.contract_refs,
        trace_join=row.trace_join,
        occurred_at=row.occurred_at.isoformat(),
    )


def _support_ticket_verdict_view(
    row: SupportTicketVerdictReadModel,
) -> SupportTicketVerdictSummaryView:
    return SupportTicketVerdictSummaryView(
        id=str(row.audit_event_id),
        workflow_id=row.workflow_id,
        correlation_id=row.correlation_id,
        invocation_id=str(row.invocation_id) if row.invocation_id is not None else None,
        tool_call_id=str(row.tool_call_id) if row.tool_call_id is not None else None,
        verdict_id=str(row.verdict_id) if row.verdict_id is not None else None,
        agent_id=row.agent_id,
        tool_name=row.tool_name,
        requested_mode=row.requested_mode,
        enforced_mode=row.enforced_mode,
        verdict=row.verdict,
        reason_category=row.reason_category,
        idempotency_key_ref=row.idempotency_key_ref,
        connector_invocation_id=(
            str(row.connector_invocation_id) if row.connector_invocation_id is not None else None
        ),
        output_refs=row.output_refs,
        trace_join=row.trace_join,
        occurred_at=row.occurred_at.isoformat(),
    )


def _support_case_update_view(
    row: SupportCaseUpdateProposalReadModel,
) -> SupportCaseUpdateProposalSummaryView:
    return SupportCaseUpdateProposalSummaryView(
        id=row.case_update_ref,
        workflow_id=row.workflow_id,
        correlation_id=row.correlation_id,
        source_audit_event_id=str(row.source_audit_event_id),
        connector_invocation_id=str(row.connector_invocation_id),
        request_ref=row.request_ref,
        case_ref=row.case_ref,
        account_ref=row.account_ref,
        product_ref=row.product_ref,
        severity_category=row.severity_category,
        target_status_category=row.target_status_category,
        update_reason_category=row.update_reason_category,
        proposal_status=row.proposal_status,
        policy_ref=row.policy_ref,
        case_status_mutated=row.case_status_mutated,
        trace_join=row.trace_join,
        updated_at=row.updated_at.isoformat(),
    )


def _support_status_write_boundary_view(
    row: SupportStatusWriteBoundaryReadModel,
) -> SupportStatusWriteBoundaryView:
    return SupportStatusWriteBoundaryView(
        grant_ref=row.grant_ref,
        agent_id=row.agent_id,
        agent_version=row.agent_version,
        tool_name=row.tool_name,
        mode=row.mode,
        allowed=row.allowed,
        approval_required=row.approval_required,
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


def _decimal_to_float(value: Decimal) -> float:
    return float(value)


app = create_app()

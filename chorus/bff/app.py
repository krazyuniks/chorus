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
    DecisionTrailEntryReadModel,
    ProjectionStore,
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

    @app.get("/api/progress")
    async def progress(
        request: Request,
        store: Annotated[ProjectionStore, Depends(store_dependency)],
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
                snapshot_store=store if once else None,
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


def _redacted_fields(arguments: dict[str, Any]) -> list[str]:
    return sorted(key for key, value in arguments.items() if value == "[redacted]")


def _decimal_to_float(value: Decimal) -> float:
    return float(value)


app = create_app()

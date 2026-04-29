"""Agent Runtime policy resolution, model boundary, and decision trail."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any, Protocol
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from chorus.contracts.generated.agents.lighthouse_agent_io import LighthouseAgentIO
from chorus.contracts.generated.events.agent_invocation_record import AgentInvocationRecord
from chorus.observability import current_otel_ids
from chorus.workflows.types import AgentCitation, AgentInvocationRequest, AgentInvocationResponse


class AgentRuntimeError(RuntimeError):
    """Raised when runtime policy resolution or provider invocation fails."""


class TenantPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    tenant_tier: str
    status: str


class ResolvedAgent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    role: str
    version: str
    lifecycle_state: str
    owner: str
    prompt_reference: str
    prompt_hash: str
    capability_tags: list[str]


class ResolvedModelRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    task_kind: str
    parameters: dict[str, Any]
    budget_cap_usd: Decimal = Field(ge=0)
    fallback_policy: dict[str, Any]


class RuntimeResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant: TenantPolicy
    agent: ResolvedAgent
    model_route: ResolvedModelRoute


@dataclass(frozen=True)
class ModelBoundaryResult:
    summary: str
    confidence: float
    structured_data: dict[str, Any]
    recommended_next_step: str
    rationale: str
    citations: list[AgentCitation]
    cost_amount_usd: Decimal


class ModelBoundary(Protocol):
    def invoke(
        self,
        request: AgentInvocationRequest,
        resolution: RuntimeResolution,
        invocation_id: UUID,
    ) -> ModelBoundaryResult: ...


class AgentRuntimeStore:
    """Postgres-backed runtime policy and decision-trail adapter."""

    def __init__(self, conn: Connection[Any]) -> None:
        self._conn = conn

    def set_tenant_context(self, tenant_id: str) -> None:
        self._conn.execute("SELECT set_config('app.tenant_id', %s, false)", (tenant_id,))

    def resolve(self, request: AgentInvocationRequest) -> RuntimeResolution:
        self.set_tenant_context(request.tenant_id)
        tenant = self._fetch_tenant(request.tenant_id)
        if tenant.status != "active":
            raise AgentRuntimeError(f"Tenant {request.tenant_id!r} is not active: {tenant.status}")

        agent = self._fetch_agent(request.tenant_id, request.agent_role)
        if agent.lifecycle_state != "approved":
            raise AgentRuntimeError(
                f"Agent {agent.agent_id!r} {agent.version} is not approved: {agent.lifecycle_state}"
            )

        route = self._fetch_model_route(
            request.tenant_id,
            request.agent_role,
            request.task_kind,
            tenant.tenant_tier,
        )
        return RuntimeResolution(tenant=tenant, agent=agent, model_route=route)

    def record_decision(self, record: AgentInvocationRecord) -> None:
        raw_record = record.model_dump(mode="json")
        agent = record.agent
        model_route = record.model_route
        self.set_tenant_context(record.tenant_id)
        with self._conn.transaction():
            self._conn.execute(
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
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s
                )
                ON CONFLICT (tenant_id, invocation_id) DO NOTHING
                """,
                (
                    record.tenant_id,
                    record.invocation_id,
                    record.correlation_id,
                    record.workflow_id,
                    agent.agent_id,
                    agent.role.value,
                    agent.version,
                    agent.lifecycle_state.value,
                    agent.prompt_reference,
                    agent.prompt_hash,
                    model_route.provider,
                    model_route.model,
                    model_route.task_kind,
                    Decimal(str(model_route.budget_cap_usd)),
                    record.input_summary,
                    record.output_summary,
                    record.justification,
                    record.outcome.value,
                    list(record.tool_call_ids),
                    Decimal(str(record.cost.amount)),
                    record.cost.currency,
                    record.duration_ms,
                    record.started_at,
                    record.completed_at,
                    [contract_ref.root for contract_ref in record.contract_refs],
                    Jsonb(raw_record),
                    Jsonb(current_otel_ids()),
                ),
            )

    def _fetch_tenant(self, tenant_id: str) -> TenantPolicy:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT tenant_id, tenant_tier, status
                FROM tenants
                WHERE tenant_id = %s
                """,
                (tenant_id,),
            )
            row = cur.fetchone()
        if row is None:
            raise AgentRuntimeError(f"No tenant policy found for {tenant_id!r}")
        return TenantPolicy.model_validate(row)

    def _fetch_agent(self, tenant_id: str, agent_role: str) -> ResolvedAgent:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    agent_id,
                    role,
                    version,
                    lifecycle_state,
                    owner,
                    prompt_reference,
                    prompt_hash,
                    capability_tags
                FROM agent_registry
                WHERE tenant_id = %s
                  AND role = %s
                  AND lifecycle_state = 'approved'
                ORDER BY substring(version from 2)::integer DESC, agent_id
                LIMIT 1
                """,
                (tenant_id, agent_role),
            )
            row = cur.fetchone()
        if row is None:
            raise AgentRuntimeError(
                f"No approved agent registered for tenant {tenant_id!r} role {agent_role!r}"
            )
        return ResolvedAgent.model_validate(row)

    def _fetch_model_route(
        self,
        tenant_id: str,
        agent_role: str,
        task_kind: str,
        tenant_tier: str,
    ) -> ResolvedModelRoute:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    provider,
                    model,
                    task_kind,
                    parameters,
                    budget_cap_usd,
                    fallback_policy
                FROM model_routing_policies
                WHERE tenant_id = %s
                  AND agent_role = %s
                  AND task_kind = %s
                  AND tenant_tier = %s
                  AND lifecycle_state = 'approved'
                """,
                (tenant_id, agent_role, task_kind, tenant_tier),
            )
            row = cur.fetchone()
        if row is None:
            raise AgentRuntimeError(
                "No approved model route for "
                f"tenant={tenant_id!r}, role={agent_role!r}, "
                f"task={task_kind!r}, tier={tenant_tier!r}"
            )
        return ResolvedModelRoute.model_validate(row)


class LocalLighthouseModelBoundary:
    """Local structured provider boundary for the Phase 1A happy path."""

    def invoke(
        self,
        request: AgentInvocationRequest,
        resolution: RuntimeResolution,
        invocation_id: UUID,
    ) -> ModelBoundaryResult:
        _ = invocation_id
        provider = resolution.model_route.provider
        if provider != "local":
            raise AgentRuntimeError(
                f"Provider {provider!r} is not available in the local Phase 1A runtime"
            )

        summary, next_step, structured_data = _lighthouse_result_for(request)
        return ModelBoundaryResult(
            summary=summary,
            confidence=0.88,
            structured_data={
                **structured_data,
                "model_boundary": {
                    "provider": resolution.model_route.provider,
                    "model": resolution.model_route.model,
                },
            },
            recommended_next_step=next_step,
            rationale=(
                "Local Phase 1A model boundary returned a governed structured decision; "
                "external actions remain behind the Tool Gateway."
            ),
            citations=[],
            cost_amount_usd=Decimal("0.000000"),
        )


class AgentRuntime:
    def __init__(self, store: AgentRuntimeStore, model_boundary: ModelBoundary) -> None:
        self._store = store
        self._model_boundary = model_boundary

    def invoke(self, request: AgentInvocationRequest) -> AgentInvocationResponse:
        invocation_id = uuid4()
        started_at = datetime.now(UTC)
        started_monotonic = perf_counter()
        resolution = self._store.resolve(request)

        try:
            result = self._model_boundary.invoke(request, resolution, invocation_id)
            outcome = "succeeded"
        except Exception as exc:
            completed_at = datetime.now(UTC)
            duration_ms = _duration_ms(started_monotonic)
            self._store.record_decision(
                _decision_record(
                    request=request,
                    resolution=resolution,
                    invocation_id=invocation_id,
                    input_summary=_summarise_mapping(request.input),
                    output_summary=f"Agent runtime failed: {exc}",
                    justification=str(exc),
                    outcome="failed",
                    cost_amount_usd=Decimal("0.000000"),
                    duration_ms=duration_ms,
                    started_at=started_at,
                    completed_at=completed_at,
                    contract_refs=[request.expected_output_contract],
                )
            )
            raise

        completed_at = datetime.now(UTC)
        duration_ms = _duration_ms(started_monotonic)
        contract = _lighthouse_contract(
            request=request,
            invocation_id=invocation_id,
            result=result,
        )
        self._store.record_decision(
            _decision_record(
                request=request,
                resolution=resolution,
                invocation_id=invocation_id,
                input_summary=_summarise_mapping(request.input),
                output_summary=contract.result.summary,
                justification=contract.result.rationale,
                outcome=outcome,
                cost_amount_usd=result.cost_amount_usd,
                duration_ms=duration_ms,
                started_at=started_at,
                completed_at=completed_at,
                contract_refs=[
                    request.expected_output_contract,
                    "contracts/events/agent_invocation_record.schema.json",
                ],
            )
        )
        return AgentInvocationResponse(
            invocation_id=str(invocation_id),
            summary=contract.result.summary,
            confidence=contract.result.confidence,
            structured_data=contract.result.structured_data,
            recommended_next_step=contract.result.recommended_next_step.value,
            rationale=contract.result.rationale,
            citations=[
                AgentCitation(source=citation.source, reference=citation.reference)
                for citation in contract.result.citations
            ],
        )


def _decision_record(
    *,
    request: AgentInvocationRequest,
    resolution: RuntimeResolution,
    invocation_id: UUID,
    input_summary: str,
    output_summary: str,
    justification: str,
    outcome: str,
    cost_amount_usd: Decimal,
    duration_ms: int,
    started_at: datetime,
    completed_at: datetime,
    contract_refs: list[str],
) -> AgentInvocationRecord:
    return AgentInvocationRecord.model_validate(
        {
            "schema_version": "1.0.0",
            "invocation_id": str(invocation_id),
            "correlation_id": request.correlation_id,
            "workflow_id": request.workflow_id,
            "tenant_id": request.tenant_id,
            "agent": {
                "agent_id": resolution.agent.agent_id,
                "role": resolution.agent.role,
                "version": resolution.agent.version,
                "lifecycle_state": resolution.agent.lifecycle_state,
                "prompt_reference": resolution.agent.prompt_reference,
                "prompt_hash": resolution.agent.prompt_hash,
            },
            "model_route": {
                "provider": resolution.model_route.provider,
                "model": resolution.model_route.model,
                "task_kind": resolution.model_route.task_kind,
                "budget_cap_usd": float(resolution.model_route.budget_cap_usd),
                "parameters": resolution.model_route.parameters,
            },
            "input_summary": input_summary,
            "output_summary": output_summary,
            "justification": justification,
            "outcome": outcome,
            "tool_call_ids": [],
            "cost": {"amount": float(cost_amount_usd), "currency": "USD"},
            "duration_ms": duration_ms,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "contract_refs": contract_refs,
        }
    )


def _lighthouse_contract(
    *,
    request: AgentInvocationRequest,
    invocation_id: UUID,
    result: ModelBoundaryResult,
) -> LighthouseAgentIO:
    return LighthouseAgentIO.model_validate(
        {
            "schema_version": "1.0.0",
            "task_id": str(invocation_id),
            "tenant_id": request.tenant_id,
            "correlation_id": request.correlation_id,
            "workflow_id": request.workflow_id,
            "agent_role": request.agent_role,
            "task_kind": request.task_kind,
            "input": request.input,
            "expected_output_contract": request.expected_output_contract,
            "result": {
                "summary": result.summary,
                "confidence": result.confidence,
                "structured_data": result.structured_data,
                "recommended_next_step": result.recommended_next_step,
                "rationale": result.rationale,
                "citations": [
                    {"source": citation.source, "reference": citation.reference}
                    for citation in result.citations
                ],
            },
        }
    )


def _duration_ms(started_monotonic: float) -> int:
    return max(0, round((perf_counter() - started_monotonic) * 1000))


def _summarise_mapping(payload: dict[str, Any]) -> str:
    summary = json.dumps(payload, sort_keys=True, default=str)
    if len(summary) <= 400:
        return summary
    return f"{summary[:397]}..."


def _lighthouse_result_for(
    request: AgentInvocationRequest,
) -> tuple[str, str, dict[str, Any]]:
    match request.task_kind:
        case "company_research":
            return (
                "Identified a small operations-led services business from the lead email.",
                "continue",
                {"company_name": "Acme Field Services", "fit": "operations automation"},
            )
        case "lead_qualification":
            return (
                "Lead qualifies for a lightweight Lighthouse pilot conversation.",
                "continue",
                {"qualification": "qualified", "priority": "normal"},
            )
        case "response_draft":
            return (
                "Drafted a concise response proposing a discovery call and pilot outline.",
                "continue",
                {
                    "draft_response": (
                        "Thanks for getting in touch. A lightweight pilot could qualify "
                        "new enquiries, research company context, and prepare response "
                        "drafts for your account team to review."
                    )
                },
            )
        case "response_validation":
            return (
                "Draft is suitable for proposal mode in the local sandbox.",
                "send",
                {"validation": "approved"},
            )
        case _:
            return (
                "Input accepted for Lighthouse processing.",
                "continue",
                {"classification": "lead"},
            )

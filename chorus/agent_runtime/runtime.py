"""Agent Runtime policy resolution, model boundary, and decision trail."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any, Protocol, TypedDict, cast
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph  # type: ignore[reportMissingTypeStubs]
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from chorus.contracts.generated.agents.lighthouse_agent_io import LighthouseAgentIO
from chorus.contracts.generated.events.agent_invocation_record import AgentInvocationRecord
from chorus.observability import current_otel_ids
from chorus.workflows.types import AgentCitation, AgentInvocationRequest, AgentInvocationResponse

LANGGRAPH_EXECUTION_ENGINE = "langgraph"
LIGHTHOUSE_AGENT_GRAPH_VERSION = "lighthouse-agent-runtime-graph-v1"
LIGHTHOUSE_AGENT_GRAPH_STEPS = (
    "prepare_context",
    "invoke_model_adapter",
    "normalise_result",
    "validate_contract",
    "final_response",
)


class AgentRuntimeError(RuntimeError):
    """Raised when runtime policy resolution or provider invocation fails."""

    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        self.agent_execution_graph_path: tuple[str, ...] = ()


class ProviderInvocationError(AgentRuntimeError):
    """Raised when a selected provider boundary fails during invocation."""

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        reason: str = "provider_error",
        retryable: bool = True,
        message: str | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.fallback_reason = reason
        self.retryable = retryable
        super().__init__(message or f"Provider {provider!r} model {model!r} failed: {reason}")

    @property
    def decision_metadata(self) -> dict[str, Any]:
        return {
            "provider_failure.provider": self.provider,
            "provider_failure.model": self.model,
            "provider_failure.reason": self.fallback_reason,
            "provider_failure.retryable": self.retryable,
        }


class CommercialProviderDisabledError(AgentRuntimeError):
    """Raised when a commercial provider route resolves to a disabled boundary."""

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        reason: str,
        credential_required: bool,
        secret_ref_names: Sequence[str],
        missing_credentials_behaviour: str,
    ) -> None:
        self.provider = provider
        self.model = model
        self.reason = reason
        self.credential_required = credential_required
        self.secret_ref_names = tuple(secret_ref_names)
        self.missing_credentials_behaviour = missing_credentials_behaviour
        message = (
            f"Commercial provider {provider!r} model {model!r} is disabled "
            f"by Agent Runtime policy: {reason}; "
            f"missing_credentials_behaviour={missing_credentials_behaviour}"
        )
        super().__init__(message)

    @property
    def fallback_reason(self) -> str:
        if self.reason == "missing_credentials":
            return "credentials_missing"
        return "provider_disabled"

    @property
    def decision_metadata(self) -> dict[str, Any]:
        return {
            "provider_boundary.provider": self.provider,
            "provider_boundary.model": self.model,
            "provider_boundary.state": "disabled",
            "provider_boundary.reason": self.reason,
            "provider_boundary.credential_required": self.credential_required,
            "provider_boundary.secret_ref_names": list(self.secret_ref_names),
            "provider_boundary.missing_credentials_behaviour": (self.missing_credentials_behaviour),
        }


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

    route_id: UUID | None = None
    route_version: int | None = Field(default=None, ge=1)
    provider_catalogue_id: str | None = None
    selection_source: str = "model_routing_policies"
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


class AgentExecutionGraphState(TypedDict, total=False):
    request: AgentInvocationRequest
    resolution: RuntimeResolution
    invocation_id: UUID
    input_summary: str
    result: ModelAdapterResult
    contract: LighthouseAgentIO
    response: AgentInvocationResponse
    path: list[str]


@dataclass(frozen=True)
class ModelAdapterResult:
    summary: str
    confidence: float
    structured_data: dict[str, Any]
    recommended_next_step: str
    rationale: str
    citations: list[AgentCitation]
    cost_amount_usd: Decimal


class ModelAdapter(Protocol):
    """Provider-specific model invocation boundary selected by runtime policy."""

    provider_id: str

    def invoke(
        self,
        request: AgentInvocationRequest,
        resolution: RuntimeResolution,
        invocation_id: UUID,
    ) -> ModelAdapterResult: ...


class ModelAdapterRegistry:
    """Provider adapter registry used after model-route policy resolution."""

    def __init__(self, adapters: Sequence[ModelAdapter]) -> None:
        self._adapters: dict[str, ModelAdapter] = {}
        for adapter in adapters:
            if adapter.provider_id in self._adapters:
                raise AgentRuntimeError(
                    f"Duplicate model adapter registered for provider {adapter.provider_id!r}"
                )
            self._adapters[adapter.provider_id] = adapter

    @property
    def provider_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

    def invoke(
        self,
        request: AgentInvocationRequest,
        resolution: RuntimeResolution,
        invocation_id: UUID,
    ) -> ModelAdapterResult:
        provider = resolution.model_route.provider
        adapter = self._adapters.get(provider)
        if adapter is None:
            raise AgentRuntimeError(
                f"No model adapter registered for provider {provider!r}; "
                "provider execution must be added behind Agent Runtime policy"
            )
        return adapter.invoke(request, resolution, invocation_id)


def default_model_adapter_registry() -> ModelAdapterRegistry:
    """Return the Phase 2A runnable adapter registry.

    The commercial placeholder adapter is registered as a boundary but remains
    disabled by default. The local Lighthouse adapter is still the only
    runnable model path for local evidence.
    """

    return ModelAdapterRegistry([LocalLighthouseModelAdapter(), CommercialExampleModelAdapter()])


@dataclass(frozen=True)
class AgentExecutionResult:
    result: ModelAdapterResult
    contract: LighthouseAgentIO
    response: AgentInvocationResponse
    input_summary: str
    graph_path: tuple[str, ...]
    decision_metadata: dict[str, Any]


@dataclass(frozen=True)
class RuntimeFallback:
    reason: str
    primary_provider: str
    primary_model: str
    resolution: RuntimeResolution

    @property
    def fallback_provider(self) -> str:
        return self.resolution.model_route.provider

    @property
    def fallback_model(self) -> str:
        return self.resolution.model_route.model


class AgentExecutionEngine(Protocol):
    execution_engine: str
    graph_version: str

    def invoke(
        self,
        request: AgentInvocationRequest,
        resolution: RuntimeResolution,
        invocation_id: UUID,
    ) -> AgentExecutionResult: ...


class LangGraphAgentExecutionEngine:
    """LangGraph-backed per-invocation agent execution engine.

    Temporal remains the durable workflow owner. This graph is compiled without
    checkpointer persistence and is invoked synchronously inside the Agent
    Runtime activity boundary.
    """

    execution_engine = LANGGRAPH_EXECUTION_ENGINE
    graph_version = LIGHTHOUSE_AGENT_GRAPH_VERSION

    def __init__(self, model_adapters: ModelAdapterRegistry) -> None:
        self._model_adapters = model_adapters
        self._graph = self._build_graph()

    def invoke(
        self,
        request: AgentInvocationRequest,
        resolution: RuntimeResolution,
        invocation_id: UUID,
    ) -> AgentExecutionResult:
        state = self._graph.invoke(
            {
                "request": request,
                "resolution": resolution,
                "invocation_id": invocation_id,
            }
        )
        result = state["result"]
        contract = state["contract"]
        response = state["response"]
        input_summary = state["input_summary"]
        path = tuple(state["path"])
        return AgentExecutionResult(
            result=result,
            contract=contract,
            response=response,
            input_summary=input_summary,
            graph_path=path,
            decision_metadata=_agent_execution_metadata(
                engine=self.execution_engine,
                graph_version=self.graph_version,
                graph_path=path,
            ),
        )

    def _build_graph(self) -> Any:
        graph: Any = StateGraph(AgentExecutionGraphState)
        graph.add_node("prepare_context", self._prepare_context)
        graph.add_node("invoke_model_adapter", self._invoke_model_adapter)
        graph.add_node("normalise_result", self._normalise_result)
        graph.add_node("validate_contract", self._validate_contract)
        graph.add_node("final_response", self._final_response)
        graph.add_edge(START, "prepare_context")
        graph.add_edge("prepare_context", "invoke_model_adapter")
        graph.add_edge("invoke_model_adapter", "normalise_result")
        graph.add_edge("normalise_result", "validate_contract")
        graph.add_edge("validate_contract", "final_response")
        graph.add_edge("final_response", END)
        return graph.compile()

    def _prepare_context(self, state: AgentExecutionGraphState) -> AgentExecutionGraphState:
        request = _state_request(state)
        return {
            "input_summary": _summarise_mapping(request.input),
            "path": _append_graph_step(state, "prepare_context"),
        }

    def _invoke_model_adapter(self, state: AgentExecutionGraphState) -> AgentExecutionGraphState:
        graph_path = tuple(_append_graph_step(state, "invoke_model_adapter"))
        try:
            result = self._model_adapters.invoke(
                _state_request(state),
                _state_resolution(state),
                _state_invocation_id(state),
            )
        except AgentRuntimeError as exc:
            exc.agent_execution_graph_path = graph_path
            raise
        return {
            "result": result,
            "path": list(graph_path),
        }

    def _normalise_result(self, state: AgentExecutionGraphState) -> AgentExecutionGraphState:
        result = _state_result(state)
        structured_data = {
            **result.structured_data,
            "agent_execution": {
                "engine": self.execution_engine,
                "graph_version": self.graph_version,
                "graph_steps": list(LIGHTHOUSE_AGENT_GRAPH_STEPS),
            },
        }
        normalised_result = ModelAdapterResult(
            summary=result.summary,
            confidence=result.confidence,
            structured_data=structured_data,
            recommended_next_step=result.recommended_next_step,
            rationale=result.rationale,
            citations=result.citations,
            cost_amount_usd=result.cost_amount_usd,
        )
        return {
            "result": normalised_result,
            "path": _append_graph_step(state, "normalise_result"),
        }

    def _validate_contract(self, state: AgentExecutionGraphState) -> AgentExecutionGraphState:
        contract = _lighthouse_contract(
            request=_state_request(state),
            invocation_id=_state_invocation_id(state),
            result=_state_result(state),
        )
        return {
            "contract": contract,
            "path": _append_graph_step(state, "validate_contract"),
        }

    def _final_response(self, state: AgentExecutionGraphState) -> AgentExecutionGraphState:
        contract = _state_contract(state)
        response = AgentInvocationResponse(
            invocation_id=str(_state_invocation_id(state)),
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
        return {
            "response": response,
            "path": _append_graph_step(state, "final_response"),
        }


class RuntimePolicyStore(Protocol):
    def resolve(self, request: AgentInvocationRequest) -> RuntimeResolution: ...

    def record_decision(
        self,
        record: AgentInvocationRecord,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...


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

    def record_decision(
        self,
        record: AgentInvocationRecord,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        raw_record = record.model_dump(mode="json")
        decision_metadata = {**current_otel_ids(), **(metadata or {})}
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
                    Jsonb(decision_metadata),
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
                    policy.policy_id AS route_id,
                    version.route_version,
                    version.provider_catalogue_id,
                    CASE
                        WHEN version.route_version IS NULL
                        THEN 'model_routing_policies'
                        ELSE 'model_routing_policies+model_route_versions'
                    END AS selection_source,
                    policy.provider,
                    policy.model,
                    policy.task_kind,
                    policy.parameters,
                    policy.budget_cap_usd,
                    policy.fallback_policy
                FROM model_routing_policies AS policy
                LEFT JOIN model_route_versions AS version
                  ON version.route_id = policy.policy_id
                 AND version.tenant_id = policy.tenant_id
                 AND version.agent_role = policy.agent_role
                 AND version.task_kind = policy.task_kind
                 AND version.tenant_tier = policy.tenant_tier
                 AND version.provider_id = policy.provider
                 AND version.model_id = policy.model
                 AND version.lifecycle_state = 'approved'
                WHERE policy.tenant_id = %s
                  AND policy.agent_role = %s
                  AND policy.task_kind = %s
                  AND policy.tenant_tier = %s
                  AND policy.lifecycle_state = 'approved'
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


class LocalLighthouseModelAdapter:
    """Local structured provider boundary for the Phase 1A happy path."""

    provider_id = "local"

    def invoke(
        self,
        request: AgentInvocationRequest,
        resolution: RuntimeResolution,
        invocation_id: UUID,
    ) -> ModelAdapterResult:
        _ = invocation_id
        if resolution.model_route.provider != self.provider_id:
            raise AgentRuntimeError(
                f"Provider {resolution.model_route.provider!r} cannot be handled by "
                f"{self.__class__.__name__}"
            )
        if resolution.model_route.model != "lighthouse-happy-path-v1":
            raise AgentRuntimeError(
                f"Model {resolution.model_route.model!r} is not available in the local "
                "Lighthouse adapter"
            )

        summary, next_step, structured_data, confidence = _lighthouse_result_for(request)
        return ModelAdapterResult(
            summary=summary,
            confidence=confidence,
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


class CommercialExampleModelAdapter:
    """Disabled commercial provider boundary for Phase 2A adapter evidence.

    This class deliberately performs no production provider calls. It exists so
    governed routing to the commercial placeholder reaches an explicit adapter
    boundary and records provider-disabled evidence through the Agent Runtime
    decision trail.
    """

    provider_id = "commercial.example"
    model_id = "commercial-reasoner-v1"
    secret_ref_names = ("CHORUS_COMMERCIAL_LLM_API_KEY",)
    missing_credentials_behaviour = "disable_provider"

    def __init__(self, *, enabled: bool = False) -> None:
        self._enabled = enabled

    def invoke(
        self,
        request: AgentInvocationRequest,
        resolution: RuntimeResolution,
        invocation_id: UUID,
    ) -> ModelAdapterResult:
        _ = request, invocation_id
        if resolution.model_route.provider != self.provider_id:
            raise AgentRuntimeError(
                f"Provider {resolution.model_route.provider!r} cannot be handled by "
                f"{self.__class__.__name__}"
            )
        if resolution.model_route.model != self.model_id:
            raise AgentRuntimeError(
                f"Model {resolution.model_route.model!r} is not available in the "
                "commercial example adapter boundary"
            )

        missing_secret_refs = [name for name in self.secret_ref_names if not os.environ.get(name)]
        if missing_secret_refs:
            reason = "missing_credentials"
        elif not self._enabled:
            reason = "adapter_disabled_by_default"
        else:
            reason = "production_provider_calls_not_implemented"

        raise CommercialProviderDisabledError(
            provider=self.provider_id,
            model=self.model_id,
            reason=reason,
            credential_required=True,
            secret_ref_names=self.secret_ref_names,
            missing_credentials_behaviour=self.missing_credentials_behaviour,
        )


ModelBoundaryResult = ModelAdapterResult
ModelBoundary = ModelAdapter
LocalLighthouseModelBoundary = LocalLighthouseModelAdapter


class AgentRuntime:
    def __init__(self, store: RuntimePolicyStore, model_adapters: ModelAdapterRegistry) -> None:
        self._store = store
        self._execution_engine: AgentExecutionEngine = LangGraphAgentExecutionEngine(model_adapters)

    def invoke(self, request: AgentInvocationRequest) -> AgentInvocationResponse:
        invocation_id = uuid4()
        started_at = datetime.now(UTC)
        started_monotonic = perf_counter()
        resolution = self._store.resolve(request)

        try:
            execution = self._execution_engine.invoke(request, resolution, invocation_id)
            outcome = "succeeded"
        except Exception as exc:
            completed_at = datetime.now(UTC)
            duration_ms = _duration_ms(started_monotonic)
            fallback = _runtime_fallback_for(resolution, exc)
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
                ),
                metadata=_failure_decision_metadata(
                    engine=self._execution_engine.execution_engine,
                    graph_version=self._execution_engine.graph_version,
                    exc=exc,
                )
                | _route_selection_metadata(
                    resolution=resolution,
                    fallback_reason=(
                        fallback.reason if fallback is not None else _provider_fallback_reason(exc)
                    ),
                    cost_amount_usd=Decimal("0.000000"),
                    duration_ms=duration_ms,
                )
                | (_provider_fallback_metadata(fallback, applied=False) if fallback else {}),
            )
            if fallback is not None:
                return self._invoke_fallback(request, fallback, primary_exc=exc)
            raise

        completed_at = datetime.now(UTC)
        duration_ms = _duration_ms(started_monotonic)
        self._store.record_decision(
            _decision_record(
                request=request,
                resolution=resolution,
                invocation_id=invocation_id,
                input_summary=execution.input_summary,
                output_summary=execution.contract.result.summary,
                justification=execution.contract.result.rationale,
                outcome=outcome,
                cost_amount_usd=execution.result.cost_amount_usd,
                duration_ms=duration_ms,
                started_at=started_at,
                completed_at=completed_at,
                contract_refs=[
                    request.expected_output_contract,
                    "contracts/events/agent_invocation_record.schema.json",
                ],
            ),
            metadata=execution.decision_metadata
            | _route_selection_metadata(
                resolution=resolution,
                fallback_reason=None,
                cost_amount_usd=execution.result.cost_amount_usd,
                duration_ms=duration_ms,
            ),
        )
        return execution.response

    def _invoke_fallback(
        self,
        request: AgentInvocationRequest,
        fallback: RuntimeFallback,
        *,
        primary_exc: Exception,
    ) -> AgentInvocationResponse:
        invocation_id = uuid4()
        started_at = datetime.now(UTC)
        started_monotonic = perf_counter()

        try:
            execution = self._execution_engine.invoke(
                request,
                fallback.resolution,
                invocation_id,
            )
        except Exception as exc:
            completed_at = datetime.now(UTC)
            duration_ms = _duration_ms(started_monotonic)
            self._store.record_decision(
                _decision_record(
                    request=request,
                    resolution=fallback.resolution,
                    invocation_id=invocation_id,
                    input_summary=_summarise_mapping(request.input),
                    output_summary=f"Agent runtime fallback failed: {exc}",
                    justification=str(exc),
                    outcome="failed",
                    cost_amount_usd=Decimal("0.000000"),
                    duration_ms=duration_ms,
                    started_at=started_at,
                    completed_at=completed_at,
                    contract_refs=[request.expected_output_contract],
                ),
                metadata=_failure_decision_metadata(
                    engine=self._execution_engine.execution_engine,
                    graph_version=self._execution_engine.graph_version,
                    exc=exc,
                )
                | _route_selection_metadata(
                    resolution=fallback.resolution,
                    fallback_reason=fallback.reason,
                    cost_amount_usd=Decimal("0.000000"),
                    duration_ms=duration_ms,
                )
                | _provider_fallback_metadata(fallback, applied=False),
            )
            raise exc from primary_exc

        completed_at = datetime.now(UTC)
        duration_ms = _duration_ms(started_monotonic)
        self._store.record_decision(
            _decision_record(
                request=request,
                resolution=fallback.resolution,
                invocation_id=invocation_id,
                input_summary=execution.input_summary,
                output_summary=execution.contract.result.summary,
                justification=execution.contract.result.rationale,
                outcome="succeeded",
                cost_amount_usd=execution.result.cost_amount_usd,
                duration_ms=duration_ms,
                started_at=started_at,
                completed_at=completed_at,
                contract_refs=[
                    request.expected_output_contract,
                    "contracts/events/agent_invocation_record.schema.json",
                ],
            ),
            metadata=execution.decision_metadata
            | _route_selection_metadata(
                resolution=fallback.resolution,
                fallback_reason=fallback.reason,
                cost_amount_usd=execution.result.cost_amount_usd,
                duration_ms=duration_ms,
            )
            | _provider_fallback_metadata(fallback, applied=True),
        )
        return execution.response


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
    result: ModelAdapterResult,
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


def _append_graph_step(state: AgentExecutionGraphState, step: str) -> list[str]:
    return [*state.get("path", []), step]


def _agent_execution_metadata(
    *,
    engine: str,
    graph_version: str,
    graph_path: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "agent_execution.engine": engine,
        "agent_execution.graph_version": graph_version,
        "agent_execution.graph_path": list(graph_path),
        "agent_execution.graph_path_summary": " -> ".join(graph_path),
    }


def _failure_decision_metadata(
    *,
    engine: str,
    graph_version: str,
    exc: Exception,
) -> dict[str, Any]:
    graph_path = getattr(exc, "agent_execution_graph_path", ())
    metadata = _agent_execution_metadata(
        engine=engine,
        graph_version=graph_version,
        graph_path=tuple(graph_path),
    )
    decision_metadata = getattr(exc, "decision_metadata", None)
    if decision_metadata is not None:
        metadata.update(decision_metadata)
    return metadata


def _runtime_fallback_for(
    resolution: RuntimeResolution,
    exc: Exception,
) -> RuntimeFallback | None:
    reason = _provider_fallback_reason(exc)
    if reason is None:
        return None

    policy = resolution.model_route.fallback_policy
    mode = policy.get("on_provider_error") or policy.get("mode")
    if mode != "fallback_route":
        return None

    reasons = policy.get("fallback_reasons")
    if isinstance(reasons, list) and reasons and reason not in reasons:
        return None

    fallback_route_value = policy.get("fallback_route")
    if not isinstance(fallback_route_value, dict):
        return None
    fallback_route = cast(dict[str, Any], fallback_route_value)

    provider_value = fallback_route.get("provider") or fallback_route.get("provider_id")
    model_value = fallback_route.get("model") or fallback_route.get("model_id")
    if not isinstance(provider_value, str) or not isinstance(model_value, str):
        return None
    provider = provider_value
    model = model_value

    parameters_value = fallback_route.get("parameters", resolution.model_route.parameters)
    parameters = (
        cast(dict[str, Any], parameters_value).copy()
        if isinstance(parameters_value, dict)
        else dict(resolution.model_route.parameters)
    )
    budget_value = fallback_route.get("budget_cap_usd", resolution.model_route.budget_cap_usd)
    budget_cap_usd = Decimal(str(budget_value))
    route_id_value = fallback_route.get("route_id")
    route_id = UUID(route_id_value) if isinstance(route_id_value, str) else None
    route_version_value = fallback_route.get("route_version")
    route_version = int(route_version_value) if route_version_value is not None else None
    provider_catalogue_id_value = fallback_route.get("provider_catalogue_id")
    provider_catalogue_id = (
        provider_catalogue_id_value if isinstance(provider_catalogue_id_value, str) else None
    )
    fallback_policy_value = fallback_route.get("fallback_policy", {"on_provider_error": "escalate"})
    fallback_policy = (
        cast(dict[str, Any], fallback_policy_value).copy()
        if isinstance(fallback_policy_value, dict)
        else {"on_provider_error": "escalate"}
    )
    fallback_resolution = resolution.model_copy(
        update={
            "model_route": ResolvedModelRoute(
                route_id=route_id,
                route_version=route_version,
                provider_catalogue_id=provider_catalogue_id,
                selection_source="fallback_policy",
                provider=provider,
                model=model,
                task_kind=resolution.model_route.task_kind,
                parameters=parameters,
                budget_cap_usd=budget_cap_usd,
                fallback_policy=fallback_policy,
            )
        }
    )
    return RuntimeFallback(
        reason=reason,
        primary_provider=resolution.model_route.provider,
        primary_model=resolution.model_route.model,
        resolution=fallback_resolution,
    )


def _provider_fallback_reason(exc: Exception) -> str | None:
    if isinstance(exc, ProviderInvocationError | CommercialProviderDisabledError):
        return exc.fallback_reason
    return None


def _provider_fallback_metadata(
    fallback: RuntimeFallback,
    *,
    applied: bool,
) -> dict[str, Any]:
    return {
        "provider_fallback.action": "fallback_route",
        "provider_fallback.applied": applied,
        "provider_fallback.reason": fallback.reason,
        "provider_fallback.primary_provider": fallback.primary_provider,
        "provider_fallback.primary_model": fallback.primary_model,
        "provider_fallback.fallback_provider": fallback.fallback_provider,
        "provider_fallback.fallback_model": fallback.fallback_model,
    }


def _route_selection_metadata(
    *,
    resolution: RuntimeResolution,
    fallback_reason: str | None,
    cost_amount_usd: Decimal,
    duration_ms: int,
) -> dict[str, Any]:
    route = resolution.model_route
    return {
        "model_route.route_id": str(route.route_id) if route.route_id is not None else None,
        "model_route.route_version": route.route_version,
        "model_route.provider_catalogue_id": route.provider_catalogue_id,
        "model_route.selection_source": route.selection_source,
        "model_route.provider": route.provider,
        "model_route.model": route.model,
        "model_route.task_kind": route.task_kind,
        "model_route.budget_cap_usd": str(route.budget_cap_usd),
        "model_route.fallback_reason": fallback_reason,
        "model_route.cost_amount_usd": str(cost_amount_usd),
        "model_route.latency_ms": duration_ms,
    }


def _state_request(state: AgentExecutionGraphState) -> AgentInvocationRequest:
    value = state.get("request")
    if value is None:
        raise AgentRuntimeError("LangGraph execution state missing request")
    return value


def _state_resolution(state: AgentExecutionGraphState) -> RuntimeResolution:
    value = state.get("resolution")
    if value is None:
        raise AgentRuntimeError("LangGraph execution state missing runtime resolution")
    return value


def _state_invocation_id(state: AgentExecutionGraphState) -> UUID:
    value = state.get("invocation_id")
    if value is None:
        raise AgentRuntimeError("LangGraph execution state missing invocation ID")
    return value


def _state_result(state: AgentExecutionGraphState) -> ModelAdapterResult:
    value = state.get("result")
    if value is None:
        raise AgentRuntimeError("LangGraph execution state missing model adapter result")
    return value


def _state_contract(state: AgentExecutionGraphState) -> LighthouseAgentIO:
    value = state.get("contract")
    if value is None:
        raise AgentRuntimeError("LangGraph execution state missing validated contract")
    return value


def _lighthouse_result_for(
    request: AgentInvocationRequest,
) -> tuple[str, str, dict[str, Any], float]:
    match request.task_kind:
        case "company_research":
            if _is_retry_exhaustion_fixture(request):
                raise AgentRuntimeError(
                    "retry-exhaustion fixture forced persistent agent-runtime failure"
                )
            if _is_low_confidence_research_fixture(request):
                attempt = int(request.input.get("research_attempt", 1))
                if attempt == 1:
                    return (
                        "Initial company research found ambiguous context and needs "
                        "deeper research.",
                        "deeper_research",
                        {
                            "company_name": "Unknown field services lead",
                            "fit": "requires_more_evidence",
                            "research_attempt": attempt,
                        },
                        0.42,
                    )
                return (
                    "Deeper research resolved the company context for the lead.",
                    "continue",
                    {
                        "company_name": "Acme Field Services",
                        "fit": "operations automation",
                        "research_attempt": attempt,
                        "deeper_research_completed": True,
                    },
                    0.86,
                )
            return (
                "Identified a small operations-led services business from the lead email.",
                "continue",
                {"company_name": "Acme Field Services", "fit": "operations automation"},
                0.88,
            )
        case "lead_qualification":
            return (
                "Lead qualifies for a lightweight Lighthouse pilot conversation.",
                "continue",
                {"qualification": "qualified", "priority": "normal"},
                0.88,
            )
        case "response_draft":
            if _is_validator_redraft_fixture(request):
                attempt = int(request.input.get("redraft_attempt", 1))
                if attempt == 1:
                    return (
                        "Initial draft offered a generic acknowledgement only.",
                        "continue",
                        {
                            "draft_response": (
                                "Thanks for getting in touch. We will be back in contact shortly."
                            ),
                            "redraft_attempt": attempt,
                        },
                        0.88,
                    )
                return (
                    "Redrafted response now offers an operations-led pilot and discovery call.",
                    "continue",
                    {
                        "draft_response": (
                            "Thanks for getting in touch. We would like to suggest "
                            "a lightweight operations-led pilot and a 30-minute "
                            "discovery call to scope your inbound enquiry handling."
                        ),
                        "redraft_attempt": attempt,
                        "applied_validator_reason": (
                            request.input.get("validator_reason", {}) or {}
                        ),
                    },
                    0.88,
                )
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
                0.88,
            )
        case "response_validation":
            if _is_validator_redraft_fixture(request):
                attempt = int(request.input.get("redraft_attempt", 1))
                if attempt == 1:
                    return (
                        "Draft missed the requested operations-pilot framing; "
                        "validator requested redraft.",
                        "redraft",
                        {
                            "validation": "redraft_requested",
                            "redraft_attempt": attempt,
                            "reason": {
                                "code": "tone_mismatch",
                                "missing_elements": ["pilot_framing", "discovery_call_offer"],
                                "guidance": (
                                    "Reframe around an operations-led pilot and offer a "
                                    "30-minute discovery call."
                                ),
                            },
                        },
                        0.88,
                    )
                return (
                    "Redrafted response addresses the validator's pilot-framing reason.",
                    "send",
                    {
                        "validation": "approved",
                        "redraft_attempt": attempt,
                        "redraft_completed": True,
                    },
                    0.88,
                )
            return (
                "Draft is suitable for proposal mode in the local sandbox.",
                "send",
                {"validation": "approved"},
                0.88,
            )
        case _:
            return (
                "Input accepted for Lighthouse processing.",
                "continue",
                {"classification": "lead"},
                0.88,
            )


def _is_low_confidence_research_fixture(request: AgentInvocationRequest) -> bool:
    if request.task_kind != "company_research":
        return False
    body = str(request.input.get("lead_body", "")).lower()
    subject = str(request.input.get("lead_subject", "")).lower()
    return "low-confidence research fixture" in body or "low-confidence research" in subject


def _is_validator_redraft_fixture(request: AgentInvocationRequest) -> bool:
    subject = str(request.input.get("lead_subject", "")).lower()
    body = str(request.input.get("lead_body", "")).lower()
    return "validator-redraft fixture" in subject or "validator-redraft fixture" in body


def _is_retry_exhaustion_fixture(request: AgentInvocationRequest) -> bool:
    if request.task_kind != "company_research":
        return False
    subject = str(request.input.get("lead_subject", "")).lower()
    body = str(request.input.get("lead_body", "")).lower()
    return "retry-exhaustion fixture" in subject or "retry-exhaustion fixture" in body

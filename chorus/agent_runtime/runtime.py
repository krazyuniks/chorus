"""Agent Runtime policy resolution, model boundary, and decision trail.

After R3 checkpoint B the runtime is the domain-side caller of the LLM
provider port (ADR 0018) and runs the invocation pipeline as plain
sequential Python: prepare context, invoke port, normalise result,
validate the agent IO contract, build the response. LangGraph leaves the
dependency set (ADR 0017).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any, ClassVar, Protocol, cast
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from chorus.contracts.generated.audit.agent_invocation_record import AgentInvocationRecord
from chorus.contracts.generated.audit.agent_invocation_transcript import (
    AgentInvocationTranscript,
)
from chorus.contracts.generated.llm_provider.uc1_agent_io import Uc1AgentIO
from chorus.llm_provider import (
    InvocationArgs,
    InvocationMessage,
    InvocationResult,
    LLMProviderInvocationError,
    RouteCatalogue,
    RouteCatalogueEntry,
    default_route_catalogue,
)
from chorus.observability import current_otel_ids
from chorus.workflows.types import AgentCitation, AgentInvocationRequest, AgentInvocationResponse

EXECUTION_PIPELINE_VERSION = "agent-runtime-pipeline-v1"
UC1_AGENT_CONTRACT_REF = "contracts/llm_provider/uc1_agent_io.schema.json"
EXECUTION_STEPS = (
    "prepare_context",
    "invoke_llm_provider_port",
    "normalise_result",
    "validate_contract",
    "final_response",
)

type AgentOutputContract = Uc1AgentIO


class AgentRuntimeError(RuntimeError):
    """Raised when runtime policy resolution or provider invocation fails."""

    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        self.execution_step_path: tuple[str, ...] = ()


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
        self.request_messages: tuple[InvocationMessage, ...] = ()
        self.route_entry: RouteCatalogueEntry | None = None
        super().__init__(message or f"Provider {provider!r} model {model!r} failed: {reason}")

    @property
    def decision_metadata(self) -> dict[str, Any]:
        return {
            "provider_failure.provider": self.provider,
            "provider_failure.model": self.model,
            "provider_failure.reason": self.fallback_reason,
            "provider_failure.retryable": self.retryable,
        }


class ProviderBudgetExceededError(AgentRuntimeError):
    """Raised when a selected provider result exceeds the resolved route budget."""

    fallback_reason = "budget_exceeded"

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        budget_cap_usd: Decimal,
        observed_cost_usd: Decimal,
    ) -> None:
        self.provider = provider
        self.model = model
        self.budget_cap_usd = budget_cap_usd
        self.observed_cost_usd = observed_cost_usd
        super().__init__(
            f"Provider {provider!r} model {model!r} exceeded budget cap "
            f"{budget_cap_usd} USD with observed cost {observed_cost_usd} USD"
        )

    @property
    def decision_metadata(self) -> dict[str, Any]:
        return {
            "provider_budget.provider": self.provider,
            "provider_budget.model": self.model,
            "provider_budget.reason": self.fallback_reason,
            "provider_budget.budget_cap_usd": str(self.budget_cap_usd),
            "provider_budget.observed_cost_usd": str(self.observed_cost_usd),
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


@dataclass(frozen=True)
class AgentExecutionResult:
    invocation_result: InvocationResult
    contract: AgentOutputContract
    response: AgentInvocationResponse
    input_summary: str
    step_path: tuple[str, ...]
    route_entry: RouteCatalogueEntry
    decision_metadata: dict[str, Any]
    request_messages: tuple[InvocationMessage, ...]


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


class SequentialAgentExecutionEngine:
    """Plain sequential execution pipeline for agent invocations.

    The pipeline prepares context, invokes the LLM provider port, normalises
    the result, validates the contract, and returns the final response. It is
    straight Python on a thread, with the LLM provider port as the only call
    out.
    """

    pipeline_version = EXECUTION_PIPELINE_VERSION

    def __init__(self, route_catalogue: RouteCatalogue, route_resolver: RouteResolver) -> None:
        self._route_catalogue = route_catalogue
        self._route_resolver = route_resolver

    def invoke(
        self,
        request: AgentInvocationRequest,
        resolution: RuntimeResolution,
        invocation_id: UUID,
    ) -> AgentExecutionResult:
        step_path: list[str] = []

        step_path.append("prepare_context")
        input_summary = _summarise_mapping(request.input)
        route_entry = self._route_resolver.resolve(resolution.model_route, self._route_catalogue)
        args = self._build_invocation_args(
            request=request,
            resolution=resolution,
            route_entry=route_entry,
        )

        step_path.append("invoke_llm_provider_port")
        try:
            invocation_result = self._route_catalogue.invoke(args)
        except LLMProviderInvocationError as exc:
            failure = ProviderInvocationError(
                provider=resolution.model_route.provider,
                model=resolution.model_route.model,
                reason=exc.reason,
                retryable=exc.retryable,
                message=str(exc),
            )
            failure.execution_step_path = tuple(step_path)
            failure.request_messages = args.messages
            failure.route_entry = route_entry
            raise failure from exc
        except AgentRuntimeError as exc:
            exc.execution_step_path = tuple(step_path)
            raise

        step_path.append("normalise_result")
        normalised = _normalise_invocation_result(invocation_result, route_entry)

        step_path.append("validate_contract")
        contract = _agent_output_contract(
            request=request,
            invocation_id=invocation_id,
            result=normalised,
        )

        step_path.append("final_response")
        response = _agent_response(
            contract=contract,
            result=normalised,
            invocation_id=invocation_id,
        )

        return AgentExecutionResult(
            invocation_result=normalised,
            contract=contract,
            response=response,
            input_summary=input_summary,
            step_path=tuple(step_path),
            route_entry=route_entry,
            decision_metadata=_execution_metadata(route_entry, tuple(step_path)),
            request_messages=args.messages,
        )

    def _build_invocation_args(
        self,
        *,
        request: AgentInvocationRequest,
        resolution: RuntimeResolution,
        route_entry: RouteCatalogueEntry,
    ) -> InvocationArgs:
        return InvocationArgs(
            route_id=route_entry.route_id,
            messages=(
                InvocationMessage(
                    role="user",
                    content=_summarise_mapping(request.input),
                ),
            ),
            metadata={
                "task_kind": request.task_kind,
                "input": dict(request.input),
                "agent_role": request.agent_role,
                "tenant_id": request.tenant_id,
                "model_id": route_entry.model_id,
                "parameters": {
                    **route_entry.parameters,
                    **resolution.model_route.parameters,
                },
            },
        )


class RouteResolver(Protocol):
    """Maps a resolved model route to a route catalogue entry."""

    def resolve(
        self, model_route: ResolvedModelRoute, catalogue: RouteCatalogue
    ) -> RouteCatalogueEntry: ...


class ProviderRouteResolver:
    """Default resolver: maps the provider id from the routing policy to a route id.

    Maps existing provider ids from routing policy rows to route catalogue ids.
    """

    _PROVIDER_TO_ROUTE: ClassVar[dict[str, str]] = {
        "local": "recorded-replay",
        "local-replay": "recorded-replay",
        "deepseek": "dev",
        "openai": "demo-eval-canonical",
    }

    def resolve(
        self, model_route: ResolvedModelRoute, catalogue: RouteCatalogue
    ) -> RouteCatalogueEntry:
        route_id = self._PROVIDER_TO_ROUTE.get(model_route.provider)
        if route_id is None:
            raise AgentRuntimeError(
                f"No LLM provider port route registered for provider {model_route.provider!r}; "
                "register it in the route catalogue first."
            )
        return catalogue.get(route_id)


class RuntimePolicyStore(Protocol):
    def resolve(self, request: AgentInvocationRequest) -> RuntimeResolution: ...

    def record_decision(
        self,
        record: AgentInvocationRecord,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...

    def record_transcript(self, record: AgentInvocationTranscript) -> None: ...


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

    def record_transcript(self, record: AgentInvocationTranscript) -> None:
        raw_record = record.model_dump(mode="json")
        route = record.route_catalogue
        self.set_tenant_context(record.tenant_id)
        with self._conn.transaction():
            self._conn.execute(
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
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                ON CONFLICT (tenant_id, invocation_id) DO NOTHING
                """,
                (
                    record.tenant_id,
                    record.transcript_id,
                    record.invocation_id,
                    record.correlation_id,
                    record.workflow_id,
                    route.route_id,
                    route.provider_id,
                    route.model_id,
                    route.adapter_version,
                    Jsonb(_as_jsonable(route.parameters)),
                    Jsonb([message.model_dump(mode="json") for message in record.messages]),
                    Jsonb([_as_jsonable(call) for call in record.tool_calls]),
                    Jsonb(_as_jsonable(record.response_body)) if record.response_body else None,
                    Jsonb(record.token_usage.model_dump(mode="json")),
                    Jsonb(_as_jsonable(record.provider_metadata) or {}),
                    record.started_at,
                    record.completed_at,
                    Jsonb(raw_record),
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


class AgentRuntime:
    def __init__(
        self,
        store: RuntimePolicyStore,
        route_catalogue: RouteCatalogue,
        route_resolver: RouteResolver | None = None,
    ) -> None:
        self._store = store
        self._execution_engine = SequentialAgentExecutionEngine(
            route_catalogue,
            route_resolver or ProviderRouteResolver(),
        )

    def invoke(self, request: AgentInvocationRequest) -> AgentInvocationResponse:
        invocation_id = uuid4()
        started_at = datetime.now(UTC)
        started_monotonic = perf_counter()
        resolution = self._store.resolve(request)
        failure_input_summary = _summarise_mapping(request.input)
        failure_cost_amount_usd = Decimal("0.000000")

        try:
            execution = self._execution_engine.invoke(request, resolution, invocation_id)
            failure_input_summary = execution.input_summary
            failure_cost_amount_usd = execution.invocation_result.cost_amount_usd
            _raise_if_budget_exceeded(
                execution=execution,
                resolution=resolution,
            )
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
                    input_summary=failure_input_summary,
                    output_summary=f"Agent runtime failed: {exc}",
                    justification=str(exc),
                    outcome="failed",
                    cost_amount_usd=failure_cost_amount_usd,
                    duration_ms=duration_ms,
                    started_at=started_at,
                    completed_at=completed_at,
                    contract_refs=[request.expected_output_contract],
                ),
                metadata=_failure_decision_metadata(exc)
                | _route_selection_metadata(
                    resolution=resolution,
                    fallback_reason=(
                        fallback.reason if fallback is not None else _provider_fallback_reason(exc)
                    ),
                    cost_amount_usd=failure_cost_amount_usd,
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
                output_summary=execution.response.summary,
                justification=execution.response.rationale,
                outcome=outcome,
                cost_amount_usd=execution.invocation_result.cost_amount_usd,
                duration_ms=duration_ms,
                started_at=started_at,
                completed_at=completed_at,
                contract_refs=[
                    request.expected_output_contract,
                    "contracts/audit/agent_invocation_record.schema.json",
                ],
            ),
            metadata=execution.decision_metadata
            | _route_selection_metadata(
                resolution=resolution,
                fallback_reason=None,
                cost_amount_usd=execution.invocation_result.cost_amount_usd,
                duration_ms=duration_ms,
            ),
        )
        self._store.record_transcript(
            _transcript_record(
                execution=execution,
                invocation_id=invocation_id,
                tenant_id=request.tenant_id,
                correlation_id=request.correlation_id,
                workflow_id=request.workflow_id,
                started_at=started_at,
                completed_at=completed_at,
            )
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
        failure_input_summary = _summarise_mapping(request.input)
        failure_cost_amount_usd = Decimal("0.000000")

        try:
            execution = self._execution_engine.invoke(
                request,
                fallback.resolution,
                invocation_id,
            )
            failure_input_summary = execution.input_summary
            failure_cost_amount_usd = execution.invocation_result.cost_amount_usd
            _raise_if_budget_exceeded(
                execution=execution,
                resolution=fallback.resolution,
            )
        except Exception as exc:
            completed_at = datetime.now(UTC)
            duration_ms = _duration_ms(started_monotonic)
            self._store.record_decision(
                _decision_record(
                    request=request,
                    resolution=fallback.resolution,
                    invocation_id=invocation_id,
                    input_summary=failure_input_summary,
                    output_summary=f"Agent runtime fallback failed: {exc}",
                    justification=str(exc),
                    outcome="failed",
                    cost_amount_usd=failure_cost_amount_usd,
                    duration_ms=duration_ms,
                    started_at=started_at,
                    completed_at=completed_at,
                    contract_refs=[request.expected_output_contract],
                ),
                metadata=_failure_decision_metadata(exc)
                | _route_selection_metadata(
                    resolution=fallback.resolution,
                    fallback_reason=fallback.reason,
                    cost_amount_usd=failure_cost_amount_usd,
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
                output_summary=execution.response.summary,
                justification=execution.response.rationale,
                outcome="succeeded",
                cost_amount_usd=execution.invocation_result.cost_amount_usd,
                duration_ms=duration_ms,
                started_at=started_at,
                completed_at=completed_at,
                contract_refs=[
                    request.expected_output_contract,
                    "contracts/audit/agent_invocation_record.schema.json",
                ],
            ),
            metadata=execution.decision_metadata
            | _route_selection_metadata(
                resolution=fallback.resolution,
                fallback_reason=fallback.reason,
                cost_amount_usd=execution.invocation_result.cost_amount_usd,
                duration_ms=duration_ms,
            )
            | _provider_fallback_metadata(fallback, applied=True),
        )
        self._store.record_transcript(
            _transcript_record(
                execution=execution,
                invocation_id=invocation_id,
                tenant_id=request.tenant_id,
                correlation_id=request.correlation_id,
                workflow_id=request.workflow_id,
                started_at=started_at,
                completed_at=completed_at,
            )
        )
        return execution.response


def _transcript_record(
    *,
    execution: AgentExecutionResult,
    invocation_id: UUID,
    tenant_id: str,
    correlation_id: str,
    workflow_id: str,
    started_at: datetime,
    completed_at: datetime,
) -> AgentInvocationTranscript:
    result = execution.invocation_result
    route_entry = execution.route_entry
    request_messages = [
        {"role": message.role, "content": message.content}
        | ({"tool_call_id": message.tool_call_id} if message.tool_call_id else {})
        | ({"name": message.name} if message.name else {})
        for message in execution.request_messages
    ]
    response_messages = [
        {"role": message.role, "content": message.content} for message in result.raw_messages
    ]
    if not response_messages:
        response_messages = [
            {"role": "assistant", "content": result.summary or ""},
        ]
    return AgentInvocationTranscript.model_validate(
        {
            "schema_version": "1.0.0",
            "transcript_id": str(uuid4()),
            "invocation_id": str(invocation_id),
            "tenant_id": tenant_id,
            "correlation_id": correlation_id,
            "workflow_id": workflow_id,
            "route_catalogue": {
                "route_id": route_entry.route_id,
                "provider_id": route_entry.provider_id,
                "model_id": route_entry.model_id,
                "adapter_version": route_entry.adapter_version,
                "parameters": route_entry.parameters,
            },
            "messages": request_messages + response_messages,
            "tool_calls": [_as_jsonable(call) for call in result.tool_calls],
            "token_usage": result.token_usage,
            "provider_metadata": _as_jsonable(result.provider_metadata) or None,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
        }
    )


def _as_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _as_jsonable(v) for k, v in cast(dict[Any, Any], value).items()}
    if isinstance(value, list | tuple):
        return [_as_jsonable(item) for item in cast(list[Any] | tuple[Any, ...], value)]
    return value


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


def _agent_output_contract(
    *,
    request: AgentInvocationRequest,
    invocation_id: UUID,
    result: InvocationResult,
) -> AgentOutputContract:
    if request.expected_output_contract == UC1_AGENT_CONTRACT_REF:
        return _uc1_contract(
            request=request,
            invocation_id=invocation_id,
            result=result,
        )
    raise AgentRuntimeError(
        f"Unsupported agent output contract {request.expected_output_contract!r}"
    )


def _uc1_contract(
    *,
    request: AgentInvocationRequest,
    invocation_id: UUID,
    result: InvocationResult,
) -> Uc1AgentIO:
    return Uc1AgentIO.model_validate(
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
                "citations": _result_citations(result),
            },
        }
    )


def _agent_response(
    *,
    contract: AgentOutputContract,
    result: InvocationResult,
    invocation_id: UUID,
) -> AgentInvocationResponse:
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
        ]
        if contract.result.citations
        else _result_invocation_citations(result),
    )


def _result_citations(result: InvocationResult) -> list[dict[str, Any]]:
    raw = result.structured_data.get("citations")
    if not isinstance(raw, list):
        return []
    citations: list[dict[str, Any]] = []
    for entry in cast(list[Any], raw):
        if isinstance(entry, dict):
            citations.append(
                {
                    "source": cast(dict[str, Any], entry).get("source"),
                    "reference": cast(dict[str, Any], entry).get("reference"),
                }
            )
    return citations


def _result_invocation_citations(_result: InvocationResult) -> list[AgentCitation]:
    return []


def _duration_ms(started_monotonic: float) -> int:
    return max(0, round((perf_counter() - started_monotonic) * 1000))


def _summarise_mapping(payload: dict[str, Any]) -> str:
    summary = json.dumps(payload, sort_keys=True, default=str)
    if len(summary) <= 400:
        return summary
    return f"{summary[:397]}..."


def _execution_metadata(
    route_entry: RouteCatalogueEntry, step_path: tuple[str, ...]
) -> dict[str, Any]:
    return {
        "execution.pipeline_version": EXECUTION_PIPELINE_VERSION,
        "execution.step_path": list(step_path),
        "execution.step_path_summary": " -> ".join(step_path),
        "route_catalogue.route_id": route_entry.route_id,
        "route_catalogue.provider_id": route_entry.provider_id,
        "route_catalogue.model_id": route_entry.model_id,
        "route_catalogue.adapter_version": route_entry.adapter_version,
    }


def _failure_decision_metadata(exc: Exception) -> dict[str, Any]:
    step_path = getattr(exc, "execution_step_path", ())
    metadata: dict[str, Any] = {
        "execution.pipeline_version": EXECUTION_PIPELINE_VERSION,
        "execution.step_path": list(step_path),
        "execution.step_path_summary": " -> ".join(step_path),
    }
    decision_metadata = getattr(exc, "decision_metadata", None)
    if decision_metadata is not None:
        metadata.update(decision_metadata)
    return metadata


def _normalise_invocation_result(
    result: InvocationResult, route_entry: RouteCatalogueEntry
) -> InvocationResult:
    structured = {
        **result.structured_data,
        "route_catalogue": {
            "route_id": route_entry.route_id,
            "provider_id": route_entry.provider_id,
            "model_id": route_entry.model_id,
            "adapter_version": route_entry.adapter_version,
        },
    }
    return InvocationResult(
        summary=result.summary,
        structured_data=structured,
        confidence=result.confidence,
        recommended_next_step=result.recommended_next_step,
        rationale=result.rationale,
        cost_amount_usd=result.cost_amount_usd,
        raw_messages=result.raw_messages,
        tool_calls=result.tool_calls,
        token_usage=result.token_usage,
        provider_metadata=result.provider_metadata,
    )


def _raise_if_budget_exceeded(
    *,
    execution: AgentExecutionResult,
    resolution: RuntimeResolution,
) -> None:
    route = resolution.model_route
    if execution.invocation_result.cost_amount_usd <= route.budget_cap_usd:
        return
    exc = ProviderBudgetExceededError(
        provider=route.provider,
        model=route.model,
        budget_cap_usd=route.budget_cap_usd,
        observed_cost_usd=execution.invocation_result.cost_amount_usd,
    )
    exc.execution_step_path = execution.step_path
    raise exc


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
    if isinstance(exc, ProviderInvocationError | ProviderBudgetExceededError):
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


__all__ = [
    "EXECUTION_PIPELINE_VERSION",
    "EXECUTION_STEPS",
    "UC1_AGENT_CONTRACT_REF",
    "AgentExecutionResult",
    "AgentOutputContract",
    "AgentRuntime",
    "AgentRuntimeError",
    "AgentRuntimeStore",
    "ProviderBudgetExceededError",
    "ProviderInvocationError",
    "ProviderRouteResolver",
    "ResolvedAgent",
    "ResolvedModelRoute",
    "RouteResolver",
    "RuntimeFallback",
    "RuntimePolicyStore",
    "RuntimeResolution",
    "SequentialAgentExecutionEngine",
    "TenantPolicy",
    "default_route_catalogue",
]

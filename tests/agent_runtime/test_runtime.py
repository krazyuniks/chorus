from __future__ import annotations

import json
import os
from collections.abc import Iterator
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from chorus.agent_runtime import (
    LANGGRAPH_EXECUTION_ENGINE,
    LIGHTHOUSE_AGENT_GRAPH_VERSION,
    SUPPORT_AGENT_CONTRACT_REF,
    AgentRuntime,
    AgentRuntimeError,
    AgentRuntimeStore,
    CommercialProviderDisabledError,
    LangGraphAgentExecutionEngine,
    LocalLighthouseModelAdapter,
    ModelAdapterRegistry,
    ModelAdapterResult,
    ProviderInvocationError,
    ResolvedAgent,
    ResolvedModelRoute,
    RuntimeResolution,
    TenantPolicy,
    default_model_adapter_registry,
)
from chorus.contracts.generated.audit.agent_invocation_record import AgentInvocationRecord
from chorus.contracts.generated.llm_provider.lighthouse_agent_io import LighthouseAgentIO
from chorus.contracts.generated.llm_provider.support_agent_io import SupportAgentIO
from chorus.persistence import apply_migrations
from chorus.workflows.activities import invoke_agent_runtime_activity
from chorus.workflows.types import AgentInvocationRequest

ADMIN_DATABASE_URL = os.environ.get(
    "CHORUS_TEST_ADMIN_DATABASE_URL",
    "postgresql://chorus:chorus@localhost:5432/postgres",
)


def _database_url(dbname: str) -> str:
    parts = urlsplit(ADMIN_DATABASE_URL)
    return urlunsplit((parts.scheme, parts.netloc, f"/{dbname}", parts.query, parts.fragment))


@pytest.fixture(scope="module")
def migrated_database_url() -> Iterator[str]:
    dbname = f"chorus_agent_runtime_test_{uuid4().hex}"

    try:
        with psycopg.connect(ADMIN_DATABASE_URL, autocommit=True, connect_timeout=2) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres is not available for agent runtime tests: {exc}")

    database_url = _database_url(dbname)
    try:
        apply_migrations(database_url)
        yield database_url
    finally:
        with psycopg.connect(ADMIN_DATABASE_URL, autocommit=True, connect_timeout=2) as admin:
            admin.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (dbname,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname)))


def _request(
    task_kind: str = "response_draft",
    role: str = "drafter",
    input_payload: dict[str, Any] | None = None,
) -> AgentInvocationRequest:
    return AgentInvocationRequest(
        tenant_id="tenant_demo",
        correlation_id=f"cor_agent_runtime_{uuid4().hex}",
        workflow_id=f"lighthouse-agent-runtime-{uuid4().hex}",
        lead_id=str(uuid4()),
        agent_role=role,
        task_kind=task_kind,
        input=input_payload or {"lead_subject": "Need help choosing a CRM automation partner"},
        expected_output_contract="contracts/llm_provider/lighthouse_agent_io.schema.json",
    )


def _resolution(
    *,
    provider: str = "local",
    model: str = "lighthouse-happy-path-v1",
    fallback_policy: dict[str, Any] | None = None,
) -> RuntimeResolution:
    return RuntimeResolution(
        tenant=TenantPolicy(tenant_id="tenant_demo", tenant_tier="demo", status="active"),
        agent=ResolvedAgent(
            agent_id="lighthouse.drafter",
            role="drafter",
            version="v1",
            lifecycle_state="approved",
            owner="agent-runtime",
            prompt_reference="prompts/lighthouse/drafter/v1.md",
            prompt_hash="sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
            capability_tags=["lighthouse", "drafting"],
        ),
        model_route=ResolvedModelRoute(
            provider=provider,
            model=model,
            task_kind="response_draft",
            parameters={"temperature": 0.3},
            budget_cap_usd=Decimal("0.01"),
            fallback_policy=fallback_policy or {"on_provider_error": "escalate"},
        ),
    )


def _support_request(
    task_kind: str = "support_resolution_plan",
    role: str = "support_resolution_planner",
) -> AgentInvocationRequest:
    return AgentInvocationRequest(
        tenant_id="tenant_demo",
        correlation_id=f"cor_support_runtime_{uuid4().hex}",
        workflow_id=f"support-runtime-{uuid4().hex}",
        lead_id="req_support_001",
        agent_role=role,
        task_kind=task_kind,
        input={
            "workflow_type": "support_triage",
            "input_refs": {
                "request_ref": "req_support_001",
                "case_ref": "case_existing_001",
                "account_ref": "acct_demo_001",
                "product_ref": "prod_core_platform",
                "redacted_summary_ref": "summary_support_001",
            },
            "severity_hint_category": "sev_high",
            "request_status_category": "open",
            "routing_policy_ref": "policy_support_triage_local_v1",
        },
        expected_output_contract=SUPPORT_AGENT_CONTRACT_REF,
    )


def _support_resolution(
    *,
    role: str = "support_resolution_planner",
    agent_id: str = "support.resolution_planner",
    task_kind: str = "support_resolution_plan",
) -> RuntimeResolution:
    return RuntimeResolution(
        tenant=TenantPolicy(tenant_id="tenant_demo", tenant_tier="demo", status="active"),
        agent=ResolvedAgent(
            agent_id=agent_id,
            role=role,
            version="v1",
            lifecycle_state="approved",
            owner="agent-runtime",
            prompt_reference="prompts/support/resolution-planner/v1.md",
            prompt_hash="sha256:5555555555555555555555555555555555555555555555555555555555555555",
            capability_tags=["support", "ticket_proposal"],
        ),
        model_route=ResolvedModelRoute(
            provider="local",
            model="lighthouse-happy-path-v1",
            task_kind=task_kind,
            parameters={"temperature": 0.1},
            budget_cap_usd=Decimal("0.01"),
            fallback_policy={"on_provider_error": "escalate"},
        ),
    )


class RecordingRuntimeStore:
    def __init__(self, resolution: RuntimeResolution) -> None:
        self._resolution = resolution
        self.records: list[AgentInvocationRecord] = []
        self.metadata: list[dict[str, Any]] = []

    def resolve(self, request: AgentInvocationRequest) -> RuntimeResolution:
        _ = request
        return self._resolution

    def record_decision(
        self,
        record: AgentInvocationRecord,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.records.append(record)
        self.metadata.append(metadata or {})


class FailingCommercialAdapter:
    provider_id = "commercial.example"

    def invoke(
        self,
        request: AgentInvocationRequest,
        resolution: RuntimeResolution,
        invocation_id: object,
    ) -> ModelAdapterResult:
        _ = request, invocation_id
        raise ProviderInvocationError(
            provider=resolution.model_route.provider,
            model=resolution.model_route.model,
            reason="provider_error",
            retryable=True,
            message="fixture commercial provider outage",
        )


class DegradingCommercialAdapter:
    provider_id = "commercial.example"

    def __init__(self, *, reason: str, retryable: bool) -> None:
        self._reason = reason
        self._retryable = retryable

    def invoke(
        self,
        request: AgentInvocationRequest,
        resolution: RuntimeResolution,
        invocation_id: object,
    ) -> ModelAdapterResult:
        _ = request, invocation_id
        raise ProviderInvocationError(
            provider=resolution.model_route.provider,
            model=resolution.model_route.model,
            reason=self._reason,
            retryable=self._retryable,
            message=f"fixture commercial provider {self._reason}",
        )


class ExpensiveCommercialAdapter:
    provider_id = "commercial.example"

    def invoke(
        self,
        request: AgentInvocationRequest,
        resolution: RuntimeResolution,
        invocation_id: object,
    ) -> ModelAdapterResult:
        _ = request, resolution, invocation_id
        return ModelAdapterResult(
            summary="Commercial provider returned a result over the route budget.",
            confidence=0.91,
            structured_data={"provider_fixture": "budget_exceeded"},
            recommended_next_step="continue",
            rationale="Fixture result intentionally exceeds the route budget cap.",
            citations=[],
            cost_amount_usd=Decimal("0.500000"),
        )


def _fallback_route_policy() -> dict[str, Any]:
    return {
        "on_provider_error": "fallback_route",
        "fallback_reasons": ["provider_error", "timeout", "rate_limited", "budget_exceeded"],
        "fallback_route": {
            "provider": "local",
            "model": "lighthouse-happy-path-v1",
            "route_version": 1,
            "provider_catalogue_id": "provider-catalogue.phase2a.seed",
            "parameters": {"temperature": 0.3},
        },
    }


def _assert_route_selection_metadata(
    metadata: dict[str, Any],
    *,
    provider: str,
    model: str,
    fallback_reason: str | None,
    route_version: int | None = None,
    selection_source: str = "model_routing_policies",
    task_kind: str = "response_draft",
    budget_cap_usd: str = "0.01",
) -> None:
    assert metadata["model_route.provider"] == provider
    assert metadata["model_route.model"] == model
    assert metadata["model_route.task_kind"] == task_kind
    assert Decimal(metadata["model_route.budget_cap_usd"]) == Decimal(budget_cap_usd)
    assert metadata["model_route.fallback_reason"] == fallback_reason
    assert metadata["model_route.route_version"] == route_version
    assert metadata["model_route.selection_source"] == selection_source
    assert Decimal(metadata["model_route.cost_amount_usd"]) >= Decimal("0")
    assert isinstance(metadata["model_route.latency_ms"], int)
    assert metadata["model_route.latency_ms"] >= 0


def _assert_metadata_subset(metadata: dict[str, Any], expected: dict[str, Any]) -> None:
    for key, value in expected.items():
        assert metadata[key] == value


def test_langgraph_execution_engine_invokes_adapter_through_expected_graph_path() -> None:
    class RecordingAdapter:
        provider_id = "local"

        def __init__(self) -> None:
            self.calls: list[tuple[AgentInvocationRequest, RuntimeResolution, object]] = []

        def invoke(
            self,
            request: AgentInvocationRequest,
            resolution: RuntimeResolution,
            invocation_id: object,
        ) -> ModelAdapterResult:
            self.calls.append((request, resolution, invocation_id))
            return ModelAdapterResult(
                summary="Adapter result passed through LangGraph.",
                confidence=0.91,
                structured_data={"adapter": "recording"},
                recommended_next_step="continue",
                rationale="Focused graph execution test.",
                citations=[],
                cost_amount_usd=Decimal("0.000001"),
            )

    request = _request()
    resolution = _resolution()
    invocation_id = uuid4()
    adapter = RecordingAdapter()

    execution = LangGraphAgentExecutionEngine(ModelAdapterRegistry([adapter])).invoke(
        request,
        resolution,
        invocation_id,
    )

    assert len(adapter.calls) == 1
    assert adapter.calls[0] == (request, resolution, invocation_id)
    assert execution.graph_path == (
        "prepare_context",
        "invoke_model_adapter",
        "normalise_result",
        "validate_contract",
        "final_response",
    )
    assert execution.response.invocation_id == str(invocation_id)
    assert execution.response.structured_data["adapter"] == "recording"
    assert execution.response.structured_data["agent_execution"] == {
        "engine": LANGGRAPH_EXECUTION_ENGINE,
        "graph_version": LIGHTHOUSE_AGENT_GRAPH_VERSION,
        "graph_steps": list(execution.graph_path),
    }
    assert isinstance(execution.contract, LighthouseAgentIO)
    assert execution.contract.result.structured_data == execution.response.structured_data
    assert execution.decision_metadata == {
        "agent_execution.engine": LANGGRAPH_EXECUTION_ENGINE,
        "agent_execution.graph_version": LIGHTHOUSE_AGENT_GRAPH_VERSION,
        "agent_execution.graph_path": list(execution.graph_path),
        "agent_execution.graph_path_summary": (
            "prepare_context -> invoke_model_adapter -> normalise_result -> "
            "validate_contract -> final_response"
        ),
    }


def test_policy_resolution_uses_registry_prompt_and_model_route(
    migrated_database_url: str,
) -> None:
    request = _request()

    with psycopg.connect(migrated_database_url) as conn:
        resolution = AgentRuntimeStore(conn).resolve(request)

    assert resolution.tenant.tenant_tier == "demo"
    assert resolution.agent.agent_id == "lighthouse.drafter"
    assert resolution.agent.version == "v1"
    assert resolution.agent.lifecycle_state == "approved"
    assert resolution.agent.prompt_reference == "prompts/lighthouse/drafter/v1.md"
    assert resolution.agent.prompt_hash.startswith("sha256:")
    assert resolution.model_route.provider == "local"
    assert resolution.model_route.model == "lighthouse-happy-path-v1"
    assert resolution.model_route.task_kind == "response_draft"
    assert resolution.model_route.route_id is not None
    assert resolution.model_route.route_version == 1
    assert resolution.model_route.provider_catalogue_id == "provider-catalogue.phase2a.seed"
    assert resolution.model_route.selection_source == (
        "model_routing_policies+model_route_versions"
    )


def test_support_policy_resolution_uses_local_runtime_route(
    migrated_database_url: str,
) -> None:
    request = _support_request()

    with psycopg.connect(migrated_database_url) as conn:
        resolution = AgentRuntimeStore(conn).resolve(request)

    assert resolution.agent.agent_id == "support.resolution_planner"
    assert resolution.agent.role == "support_resolution_planner"
    assert resolution.agent.prompt_reference == "prompts/support/resolution-planner/v1.md"
    assert resolution.model_route.provider == "local"
    assert resolution.model_route.model == "lighthouse-happy-path-v1"
    assert resolution.model_route.task_kind == "support_resolution_plan"
    assert resolution.model_route.route_version is None
    assert resolution.model_route.selection_source == "model_routing_policies"


def test_default_model_adapter_registry_registers_local_and_disabled_commercial_boundary() -> None:
    class DuplicateLocalAdapter:
        provider_id = "local"

        def invoke(
            self,
            request: AgentInvocationRequest,
            resolution: object,
            invocation_id: object,
        ) -> ModelAdapterResult:
            _ = request, resolution, invocation_id
            raise AssertionError("duplicate adapter should not be invoked")

    registry = default_model_adapter_registry()

    assert registry.provider_ids == ("commercial.example", "local")
    with pytest.raises(AgentRuntimeError, match="Duplicate model adapter"):
        ModelAdapterRegistry([DuplicateLocalAdapter(), DuplicateLocalAdapter()])


def test_langgraph_path_reports_disabled_commercial_provider_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    store = RecordingRuntimeStore(
        _resolution(provider="commercial.example", model="commercial-reasoner-v1")
    )
    monkeypatch.delenv("CHORUS_COMMERCIAL_LLM_API_KEY", raising=False)

    with pytest.raises(CommercialProviderDisabledError, match="missing_credentials"):
        AgentRuntime(store, default_model_adapter_registry()).invoke(request)

    assert len(store.records) == 1
    assert store.records[0].outcome.value == "failed"
    assert store.records[0].model_route.provider == "commercial.example"
    assert store.records[0].model_route.model == "commercial-reasoner-v1"
    assert "missing_credentials" in store.records[0].output_summary
    _assert_metadata_subset(
        store.metadata[0],
        {
            "agent_execution.engine": LANGGRAPH_EXECUTION_ENGINE,
            "agent_execution.graph_version": LIGHTHOUSE_AGENT_GRAPH_VERSION,
            "agent_execution.graph_path": [
                "prepare_context",
                "invoke_model_adapter",
            ],
            "agent_execution.graph_path_summary": "prepare_context -> invoke_model_adapter",
            "provider_boundary.provider": "commercial.example",
            "provider_boundary.model": "commercial-reasoner-v1",
            "provider_boundary.state": "disabled",
            "provider_boundary.reason": "missing_credentials",
            "provider_boundary.credential_required": True,
            "provider_boundary.secret_ref_names": ["CHORUS_COMMERCIAL_LLM_API_KEY"],
            "provider_boundary.missing_credentials_behaviour": "disable_provider",
        },
    )
    _assert_route_selection_metadata(
        store.metadata[0],
        provider="commercial.example",
        model="commercial-reasoner-v1",
        fallback_reason="credentials_missing",
    )


def test_runtime_records_provider_failure_then_invokes_policy_fallback() -> None:
    request = _request()
    store = RecordingRuntimeStore(
        _resolution(
            provider="commercial.example",
            model="commercial-reasoner-v1",
            fallback_policy=_fallback_route_policy(),
        )
    )

    response = AgentRuntime(
        store,
        ModelAdapterRegistry([FailingCommercialAdapter(), LocalLighthouseModelAdapter()]),
    ).invoke(request)

    assert response.recommended_next_step == "continue"
    assert response.structured_data["model_boundary"] == {
        "provider": "local",
        "model": "lighthouse-happy-path-v1",
    }
    assert [record.outcome.value for record in store.records] == ["failed", "succeeded"]
    assert [
        (record.model_route.provider, record.model_route.model) for record in store.records
    ] == [
        ("commercial.example", "commercial-reasoner-v1"),
        ("local", "lighthouse-happy-path-v1"),
    ]
    assert "fixture commercial provider outage" in store.records[0].output_summary
    assert store.records[0].invocation_id != store.records[1].invocation_id
    _assert_metadata_subset(
        store.metadata[0],
        {
            "agent_execution.engine": LANGGRAPH_EXECUTION_ENGINE,
            "agent_execution.graph_version": LIGHTHOUSE_AGENT_GRAPH_VERSION,
            "agent_execution.graph_path": [
                "prepare_context",
                "invoke_model_adapter",
            ],
            "agent_execution.graph_path_summary": "prepare_context -> invoke_model_adapter",
            "provider_failure.provider": "commercial.example",
            "provider_failure.model": "commercial-reasoner-v1",
            "provider_failure.reason": "provider_error",
            "provider_failure.retryable": True,
            "provider_fallback.action": "fallback_route",
            "provider_fallback.applied": False,
            "provider_fallback.reason": "provider_error",
            "provider_fallback.primary_provider": "commercial.example",
            "provider_fallback.primary_model": "commercial-reasoner-v1",
            "provider_fallback.fallback_provider": "local",
            "provider_fallback.fallback_model": "lighthouse-happy-path-v1",
        },
    )
    _assert_route_selection_metadata(
        store.metadata[0],
        provider="commercial.example",
        model="commercial-reasoner-v1",
        fallback_reason="provider_error",
    )
    _assert_metadata_subset(
        store.metadata[1],
        {
            "agent_execution.engine": LANGGRAPH_EXECUTION_ENGINE,
            "agent_execution.graph_version": LIGHTHOUSE_AGENT_GRAPH_VERSION,
            "agent_execution.graph_path": [
                "prepare_context",
                "invoke_model_adapter",
                "normalise_result",
                "validate_contract",
                "final_response",
            ],
            "agent_execution.graph_path_summary": (
                "prepare_context -> invoke_model_adapter -> normalise_result -> "
                "validate_contract -> final_response"
            ),
            "provider_fallback.action": "fallback_route",
            "provider_fallback.applied": True,
            "provider_fallback.reason": "provider_error",
            "provider_fallback.primary_provider": "commercial.example",
            "provider_fallback.primary_model": "commercial-reasoner-v1",
            "provider_fallback.fallback_provider": "local",
            "provider_fallback.fallback_model": "lighthouse-happy-path-v1",
        },
    )
    _assert_route_selection_metadata(
        store.metadata[1],
        provider="local",
        model="lighthouse-happy-path-v1",
        fallback_reason="provider_error",
        route_version=1,
        selection_source="fallback_policy",
    )


@pytest.mark.parametrize(
    ("reason", "retryable"),
    [
        ("timeout", True),
        ("rate_limited", True),
    ],
)
def test_runtime_records_provider_degradation_then_invokes_policy_fallback(
    reason: str,
    retryable: bool,
) -> None:
    request = _request()
    store = RecordingRuntimeStore(
        _resolution(
            provider="commercial.example",
            model="commercial-reasoner-v1",
            fallback_policy=_fallback_route_policy(),
        )
    )

    response = AgentRuntime(
        store,
        ModelAdapterRegistry(
            [
                DegradingCommercialAdapter(reason=reason, retryable=retryable),
                LocalLighthouseModelAdapter(),
            ]
        ),
    ).invoke(request)

    assert response.recommended_next_step == "continue"
    assert [record.outcome.value for record in store.records] == ["failed", "succeeded"]
    assert store.records[0].model_route.provider == "commercial.example"
    assert store.records[1].model_route.provider == "local"
    assert f"fixture commercial provider {reason}" in store.records[0].output_summary
    _assert_metadata_subset(
        store.metadata[0],
        {
            "provider_failure.provider": "commercial.example",
            "provider_failure.model": "commercial-reasoner-v1",
            "provider_failure.reason": reason,
            "provider_failure.retryable": retryable,
            "provider_fallback.applied": False,
            "provider_fallback.reason": reason,
        },
    )
    _assert_route_selection_metadata(
        store.metadata[0],
        provider="commercial.example",
        model="commercial-reasoner-v1",
        fallback_reason=reason,
    )
    _assert_metadata_subset(
        store.metadata[1],
        {
            "provider_fallback.applied": True,
            "provider_fallback.reason": reason,
            "provider_fallback.primary_provider": "commercial.example",
            "provider_fallback.fallback_provider": "local",
        },
    )
    _assert_route_selection_metadata(
        store.metadata[1],
        provider="local",
        model="lighthouse-happy-path-v1",
        fallback_reason=reason,
        route_version=1,
        selection_source="fallback_policy",
    )


def test_runtime_records_provider_budget_exceeded_then_invokes_policy_fallback() -> None:
    request = _request()
    store = RecordingRuntimeStore(
        _resolution(
            provider="commercial.example",
            model="commercial-reasoner-v1",
            fallback_policy=_fallback_route_policy(),
        )
    )

    response = AgentRuntime(
        store,
        ModelAdapterRegistry([ExpensiveCommercialAdapter(), LocalLighthouseModelAdapter()]),
    ).invoke(request)

    assert response.recommended_next_step == "continue"
    assert [record.outcome.value for record in store.records] == ["failed", "succeeded"]
    assert store.records[0].cost.amount == Decimal("0.5")
    assert Decimal(str(store.records[0].model_route.budget_cap_usd)) == Decimal("0.01")
    assert "exceeded budget cap" in store.records[0].output_summary
    _assert_metadata_subset(
        store.metadata[0],
        {
            "agent_execution.graph_path": [
                "prepare_context",
                "invoke_model_adapter",
                "normalise_result",
                "validate_contract",
                "final_response",
            ],
            "provider_budget.provider": "commercial.example",
            "provider_budget.model": "commercial-reasoner-v1",
            "provider_budget.reason": "budget_exceeded",
            "provider_budget.budget_cap_usd": "0.01",
            "provider_budget.observed_cost_usd": "0.500000",
            "provider_fallback.applied": False,
            "provider_fallback.reason": "budget_exceeded",
        },
    )
    _assert_route_selection_metadata(
        store.metadata[0],
        provider="commercial.example",
        model="commercial-reasoner-v1",
        fallback_reason="budget_exceeded",
    )
    assert store.metadata[0]["model_route.cost_amount_usd"] == "0.500000"
    _assert_metadata_subset(
        store.metadata[1],
        {
            "provider_fallback.applied": True,
            "provider_fallback.reason": "budget_exceeded",
            "provider_fallback.primary_provider": "commercial.example",
            "provider_fallback.fallback_provider": "local",
        },
    )
    _assert_route_selection_metadata(
        store.metadata[1],
        provider="local",
        model="lighthouse-happy-path-v1",
        fallback_reason="budget_exceeded",
        route_version=1,
        selection_source="fallback_policy",
    )


def test_runtime_invokes_selected_local_adapter_without_changing_activity_contract() -> None:
    request = _request()
    store = RecordingRuntimeStore(_resolution())

    response = AgentRuntime(store, default_model_adapter_registry()).invoke(request)

    assert response.recommended_next_step == "continue"
    assert response.structured_data["model_boundary"] == {
        "provider": "local",
        "model": "lighthouse-happy-path-v1",
    }
    assert response.structured_data["agent_execution"] == {
        "engine": LANGGRAPH_EXECUTION_ENGINE,
        "graph_version": LIGHTHOUSE_AGENT_GRAPH_VERSION,
        "graph_steps": [
            "prepare_context",
            "invoke_model_adapter",
            "normalise_result",
            "validate_contract",
            "final_response",
        ],
    }
    assert len(store.records) == 1
    assert store.records[0].model_route.provider == "local"
    assert store.records[0].model_route.model == "lighthouse-happy-path-v1"
    _assert_metadata_subset(
        store.metadata[0],
        {
            "agent_execution.engine": LANGGRAPH_EXECUTION_ENGINE,
            "agent_execution.graph_version": LIGHTHOUSE_AGENT_GRAPH_VERSION,
            "agent_execution.graph_path": [
                "prepare_context",
                "invoke_model_adapter",
                "normalise_result",
                "validate_contract",
                "final_response",
            ],
            "agent_execution.graph_path_summary": (
                "prepare_context -> invoke_model_adapter -> normalise_result -> "
                "validate_contract -> final_response"
            ),
        },
    )
    _assert_route_selection_metadata(
        store.metadata[0],
        provider="local",
        model="lighthouse-happy-path-v1",
        fallback_reason=None,
    )


def test_runtime_validates_support_agent_contract_with_safe_refs() -> None:
    request = _support_request()
    store = RecordingRuntimeStore(_support_resolution())

    response = AgentRuntime(store, default_model_adapter_registry()).invoke(request)

    assert response.recommended_next_step == "propose_only"
    assert response.structured_data["workflow_type"] == "support_triage"
    assert response.structured_data["agent_role"] == "support_resolution_planner"
    assert response.structured_data["task_kind"] == "support_resolution_plan"
    assert response.structured_data["verdict_category"] == "propose_case_update"
    assert response.structured_data["severity_category"] == "sev_high"
    assert response.structured_data["case_status_category"] == "pending_customer"
    assert response.structured_data["output_refs"] == {
        "request_ref": "req_support_001",
        "case_ref": "case_existing_001",
        "resolution_plan_ref": "plan_support_001",
        "response_draft_ref": "response_support_001",
        "case_update_ref": "caseupd_support_001",
    }
    assert response.structured_data["evidence_refs"] == ["evidence_support_local_runtime"]
    assert len(store.records) == 1
    record = store.records[0]
    assert record.agent.agent_id == "support.resolution_planner"
    assert record.agent.role == "support_resolution_planner"
    assert [contract.root for contract in record.contract_refs] == [
        SUPPORT_AGENT_CONTRACT_REF,
        "contracts/audit/agent_invocation_record.schema.json",
    ]


def test_langgraph_execution_engine_validates_support_agent_contract() -> None:
    request = _support_request(task_kind="support_validation", role="support_validator")
    resolution = _support_resolution(
        role="support_validator",
        agent_id="support.validator",
        task_kind="support_validation",
    )
    invocation_id = uuid4()

    execution = LangGraphAgentExecutionEngine(
        ModelAdapterRegistry([LocalLighthouseModelAdapter()])
    ).invoke(
        request,
        resolution,
        invocation_id,
    )

    assert isinstance(execution.contract, SupportAgentIO)
    assert execution.contract.workflow_type == "support_triage"
    assert execution.contract.agent_role == "support_validator"
    assert execution.contract.task_kind == "support_validation"
    assert execution.response.recommended_next_step == "complete"
    assert execution.response.structured_data["output_refs"] == {
        "request_ref": "req_support_001",
        "case_ref": "case_existing_001",
        "validation_ref": "validation_support_001",
    }


def test_runtime_records_failure_when_selected_provider_has_no_adapter() -> None:
    request = _request()
    store = RecordingRuntimeStore(
        _resolution(provider="unregistered.provider", model="unregistered-model-v1")
    )

    with pytest.raises(AgentRuntimeError, match="No model adapter registered"):
        AgentRuntime(store, default_model_adapter_registry()).invoke(request)

    assert len(store.records) == 1
    assert store.records[0].outcome.value == "failed"
    assert store.records[0].model_route.provider == "unregistered.provider"
    assert "No model adapter registered" in store.records[0].output_summary
    _assert_metadata_subset(
        store.metadata[0],
        {
            "agent_execution.engine": LANGGRAPH_EXECUTION_ENGINE,
            "agent_execution.graph_version": LIGHTHOUSE_AGENT_GRAPH_VERSION,
            "agent_execution.graph_path": [
                "prepare_context",
                "invoke_model_adapter",
            ],
            "agent_execution.graph_path_summary": "prepare_context -> invoke_model_adapter",
        },
    )
    _assert_route_selection_metadata(
        store.metadata[0],
        provider="unregistered.provider",
        model="unregistered-model-v1",
        fallback_reason=None,
    )


def test_runtime_validates_contracts_and_persists_decision_trail(
    migrated_database_url: str,
) -> None:
    request = _request()

    with psycopg.connect(migrated_database_url) as conn:
        response = AgentRuntime(
            AgentRuntimeStore(conn),
            default_model_adapter_registry(),
        ).invoke(request)

        row = conn.execute(
            """
            SELECT
                agent_id,
                agent_role,
                agent_version,
                prompt_reference,
                provider,
                model,
                task_kind,
                outcome,
                tool_call_ids,
                raw_record,
                metadata
            FROM decision_trail_entries
            WHERE tenant_id = %s AND invocation_id = %s
            """,
            (request.tenant_id, response.invocation_id),
        ).fetchone()

    assert response.recommended_next_step == "continue"
    assert "draft_response" in response.structured_data
    assert row is not None
    assert row[:8] == (
        "lighthouse.drafter",
        "drafter",
        "v1",
        "prompts/lighthouse/drafter/v1.md",
        "local",
        "lighthouse-happy-path-v1",
        "response_draft",
        "succeeded",
    )
    assert row[8] == []

    raw_record = AgentInvocationRecord.model_validate(row[9])
    assert str(raw_record.invocation_id) == response.invocation_id
    assert raw_record.tool_call_ids == []
    _assert_metadata_subset(
        row[10],
        {
            "agent_execution.engine": LANGGRAPH_EXECUTION_ENGINE,
            "agent_execution.graph_version": LIGHTHOUSE_AGENT_GRAPH_VERSION,
            "agent_execution.graph_path": [
                "prepare_context",
                "invoke_model_adapter",
                "normalise_result",
                "validate_contract",
                "final_response",
            ],
            "agent_execution.graph_path_summary": (
                "prepare_context -> invoke_model_adapter -> normalise_result -> "
                "validate_contract -> final_response"
            ),
        },
    )
    _assert_route_selection_metadata(
        row[10],
        provider="local",
        model="lighthouse-happy-path-v1",
        fallback_reason=None,
        route_version=1,
        selection_source="model_routing_policies+model_route_versions",
    )
    assert row[10]["model_route.route_id"] is not None
    assert row[10]["model_route.provider_catalogue_id"] == "provider-catalogue.phase2a.seed"

    LighthouseAgentIO.model_validate(
        {
            "schema_version": "1.0.0",
            "task_id": response.invocation_id,
            "tenant_id": request.tenant_id,
            "correlation_id": request.correlation_id,
            "workflow_id": request.workflow_id,
            "agent_role": request.agent_role,
            "task_kind": request.task_kind,
            "input": request.input,
            "expected_output_contract": request.expected_output_contract,
            "result": {
                "summary": response.summary,
                "confidence": response.confidence,
                "structured_data": response.structured_data,
                "recommended_next_step": response.recommended_next_step,
                "rationale": response.rationale,
                "citations": [
                    {"source": citation.source, "reference": citation.reference}
                    for citation in response.citations
                ],
            },
        }
    )


def test_runtime_low_confidence_fixture_requests_deeper_research_then_recovers(
    migrated_database_url: str,
) -> None:
    first_request = _request(
        task_kind="company_research",
        role="researcher",
        input_payload={
            "lead_subject": "Low-confidence research partner enquiry",
            "lead_body": "low-confidence research fixture",
            "sender": "alex.morgan@example.test",
            "research_attempt": 1,
        },
    )
    second_request = _request(
        task_kind="company_research",
        role="researcher",
        input_payload={
            "lead_subject": "Low-confidence research partner enquiry",
            "lead_body": "low-confidence research fixture",
            "sender": "alex.morgan@example.test",
            "research_attempt": 2,
            "deeper_research": True,
            "previous_research_summary": "Initial company research found ambiguous context.",
            "previous_research_confidence": 0.42,
            "previous_recommended_next_step": "deeper_research",
        },
    )

    with psycopg.connect(migrated_database_url) as conn:
        runtime = AgentRuntime(AgentRuntimeStore(conn), default_model_adapter_registry())
        first_response = runtime.invoke(first_request)
        second_response = runtime.invoke(second_request)

    assert first_response.recommended_next_step == "deeper_research"
    assert first_response.confidence == 0.42
    assert second_response.recommended_next_step == "continue"
    assert second_response.confidence == 0.86
    assert second_response.structured_data["deeper_research_completed"] is True


def test_runtime_records_disabled_commercial_provider_from_routing_policy(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    monkeypatch.delenv("CHORUS_COMMERCIAL_LLM_API_KEY", raising=False)

    with psycopg.connect(migrated_database_url) as conn:
        conn.execute(
            """
            UPDATE model_routing_policies
            SET provider = 'commercial.example',
                model = 'commercial-reasoner-v1'
            WHERE tenant_id = %s
              AND agent_role = %s
              AND task_kind = %s
            """,
            (request.tenant_id, request.agent_role, request.task_kind),
        )
        runtime = AgentRuntime(AgentRuntimeStore(conn), default_model_adapter_registry())

        with pytest.raises(CommercialProviderDisabledError, match="missing_credentials"):
            runtime.invoke(request)

        row = conn.execute(
            """
            SELECT provider, model, outcome, output_summary, metadata
            FROM decision_trail_entries
            WHERE tenant_id = %s
              AND correlation_id = %s
            """,
            (request.tenant_id, request.correlation_id),
        ).fetchone()

    assert row is not None
    assert row[:3] == ("commercial.example", "commercial-reasoner-v1", "failed")
    assert "missing_credentials" in row[3]
    _assert_metadata_subset(
        row[4],
        {
            "agent_execution.engine": LANGGRAPH_EXECUTION_ENGINE,
            "agent_execution.graph_version": LIGHTHOUSE_AGENT_GRAPH_VERSION,
            "agent_execution.graph_path": [
                "prepare_context",
                "invoke_model_adapter",
            ],
            "agent_execution.graph_path_summary": "prepare_context -> invoke_model_adapter",
            "provider_boundary.provider": "commercial.example",
            "provider_boundary.model": "commercial-reasoner-v1",
            "provider_boundary.state": "disabled",
            "provider_boundary.reason": "missing_credentials",
            "provider_boundary.credential_required": True,
            "provider_boundary.secret_ref_names": ["CHORUS_COMMERCIAL_LLM_API_KEY"],
            "provider_boundary.missing_credentials_behaviour": "disable_provider",
        },
    )
    _assert_route_selection_metadata(
        row[4],
        provider="commercial.example",
        model="commercial-reasoner-v1",
        fallback_reason="credentials_missing",
    )


def test_runtime_persists_provider_failure_and_local_fallback(
    migrated_database_url: str,
) -> None:
    request = _request()

    with psycopg.connect(migrated_database_url) as conn:
        conn.execute(
            """
            UPDATE model_routing_policies
            SET provider = 'commercial.example',
                model = 'commercial-reasoner-v1',
                fallback_policy = %s::jsonb
            WHERE tenant_id = %s
              AND agent_role = %s
              AND task_kind = %s
            """,
            (
                json.dumps(_fallback_route_policy()),
                request.tenant_id,
                request.agent_role,
                request.task_kind,
            ),
        )
        runtime = AgentRuntime(
            AgentRuntimeStore(conn),
            ModelAdapterRegistry([FailingCommercialAdapter(), LocalLighthouseModelAdapter()]),
        )

        response = runtime.invoke(request)

        rows = conn.execute(
            """
            SELECT provider, model, outcome, output_summary, metadata
            FROM decision_trail_entries
            WHERE tenant_id = %s
              AND correlation_id = %s
            ORDER BY started_at ASC
            """,
            (request.tenant_id, request.correlation_id),
        ).fetchall()

    assert response.recommended_next_step == "continue"
    assert len(rows) == 2
    assert rows[0][:3] == ("commercial.example", "commercial-reasoner-v1", "failed")
    assert rows[1][:3] == ("local", "lighthouse-happy-path-v1", "succeeded")
    assert "fixture commercial provider outage" in rows[0][3]
    assert rows[0][4]["provider_failure.reason"] == "provider_error"
    assert rows[0][4]["provider_fallback.applied"] is False
    assert rows[0][4]["model_route.provider"] == "commercial.example"
    assert rows[0][4]["model_route.model"] == "commercial-reasoner-v1"
    assert rows[0][4]["model_route.fallback_reason"] == "provider_error"
    assert rows[0][4]["model_route.latency_ms"] >= 0
    assert rows[1][4]["provider_fallback.applied"] is True
    assert rows[1][4]["provider_fallback.primary_provider"] == "commercial.example"
    assert rows[1][4]["model_route.provider"] == "local"
    assert rows[1][4]["model_route.model"] == "lighthouse-happy-path-v1"
    assert rows[1][4]["model_route.route_version"] == 1
    assert rows[1][4]["model_route.fallback_reason"] == "provider_error"
    assert rows[1][4]["model_route.cost_amount_usd"] == "0.000000"
    assert rows[1][4]["model_route.latency_ms"] >= 0
    assert rows[1][4]["agent_execution.graph_path"] == [
        "prepare_context",
        "invoke_model_adapter",
        "normalise_result",
        "validate_contract",
        "final_response",
    ]


def test_activity_integration_invokes_runtime_boundary(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(task_kind="response_validation", role="validator")
    monkeypatch.setenv("CHORUS_DATABASE_URL", migrated_database_url)

    response = invoke_agent_runtime_activity(request)

    with psycopg.connect(migrated_database_url) as conn:
        persisted = conn.execute(
            """
            SELECT agent_id, task_kind, outcome, metadata
            FROM decision_trail_entries
            WHERE tenant_id = %s AND invocation_id = %s
            """,
            (request.tenant_id, response.invocation_id),
        ).fetchone()

    assert response.recommended_next_step == "send"
    assert response.structured_data["validation"] == "approved"
    assert persisted is not None
    assert persisted[:3] == ("lighthouse.validator", "response_validation", "succeeded")
    _assert_metadata_subset(
        persisted[3],
        {
            "agent_execution.engine": LANGGRAPH_EXECUTION_ENGINE,
            "agent_execution.graph_version": LIGHTHOUSE_AGENT_GRAPH_VERSION,
            "agent_execution.graph_path": [
                "prepare_context",
                "invoke_model_adapter",
                "normalise_result",
                "validate_contract",
                "final_response",
            ],
            "agent_execution.graph_path_summary": (
                "prepare_context -> invoke_model_adapter -> normalise_result -> "
                "validate_contract -> final_response"
            ),
        },
    )
    _assert_route_selection_metadata(
        persisted[3],
        provider="local",
        model="lighthouse-happy-path-v1",
        fallback_reason=None,
        route_version=1,
        selection_source="model_routing_policies+model_route_versions",
        task_kind="response_validation",
        budget_cap_usd="0.01",
    )

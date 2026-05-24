from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from chorus.agent_runtime import (
    EXECUTION_PIPELINE_VERSION,
    AgentRuntime,
    AgentRuntimeError,
    AgentRuntimeStore,
    PromptLoadError,
    ProviderBudgetExceededError,
    ProviderRouteResolver,
    ResolvedAgent,
    ResolvedModelRoute,
    RuntimeResolution,
    SequentialAgentExecutionEngine,
    TenantPolicy,
    default_route_catalogue,
)
from chorus.contracts.generated.audit.agent_invocation_record import AgentInvocationRecord
from chorus.contracts.generated.audit.agent_invocation_transcript import (
    AgentInvocationTranscript,
)
from chorus.contracts.generated.llm_provider.uc1_agent_io import Uc1AgentIO
from chorus.llm_provider import (
    InvocationArgs,
    InvocationResult,
    OpenAICompatibleAdapter,
    RecordedReplayAdapter,
    RouteCatalogue,
    RouteCatalogueEntry,
)
from chorus.persistence import apply_migrations
from chorus.workflows.activities import invoke_agent_runtime_activity
from chorus.workflows.types import AgentInvocationRequest

ADMIN_DATABASE_URL = os.environ.get(
    "CHORUS_TEST_ADMIN_DATABASE_URL",
    "postgresql://chorus:chorus@localhost:5432/postgres",
)
PROMPT_HASHES = {
    "classifier": "sha256:6e25aca95c76a38b089fedbcac94316a47e18a9d2575089363f5c35f1cbcd67e",
    "context_gatherer": ("sha256:ebbbcc8091838ce2962642f3436b1188bef35fe0dc8ab67ededd475aaa683e20"),
    "qualifier": "sha256:2877d857fba0d2dc974e73968977dfd5072568b03aca9ed8adb73fab01d17f5f",
    "request_drafter": ("sha256:e25a62fe7137f6f88a0987cb9897417532a7a5dc807eb954a48c3b770923bcbd"),
    "validator": "sha256:157b1c9e3b0916bed7814bd01e912c62d38b87d4ceee9af25807f7b062fc0743",
}


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
    task_kind: str = "missing_data_request_draft",
    role: str = "request_drafter",
    input_payload: dict[str, Any] | None = None,
) -> AgentInvocationRequest:
    return AgentInvocationRequest(
        tenant_id="tenant_demo",
        correlation_id=f"cor_agent_runtime_{uuid4().hex}",
        workflow_id=f"uc1-agent-runtime-{uuid4().hex}",
        subject_id=str(uuid4()),
        agent_role=role,
        task_kind=task_kind,
        input=input_payload or {"enquiry_subject": "Motor cover enquiry"},
        expected_output_contract="contracts/llm_provider/uc1_agent_io.schema.json",
    )


def _resolution(
    *,
    role: str = "request_drafter",
    agent_id: str = "uc1.request_drafter",
    task_kind: str = "missing_data_request_draft",
    prompt_reference: str = "prompts/uc1/request-drafter/v1.md",
    prompt_hash: str = PROMPT_HASHES["request_drafter"],
    provider: str = "local",
    model: str = "uc1-happy-path-v1",
    fallback_policy: dict[str, Any] | None = None,
) -> RuntimeResolution:
    return RuntimeResolution(
        tenant=TenantPolicy(tenant_id="tenant_demo", tenant_tier="demo", status="active"),
        agent=ResolvedAgent(
            agent_id=agent_id,
            role=role,
            version="v1",
            lifecycle_state="approved",
            owner="agent-runtime",
            prompt_reference=prompt_reference,
            prompt_hash=prompt_hash,
            capability_tags=["uc1", "drafting"],
        ),
        model_route=ResolvedModelRoute(
            provider=provider,
            model=model,
            task_kind=task_kind,
            parameters={"temperature": 0.3},
            budget_cap_usd=Decimal("0.01"),
            fallback_policy=fallback_policy or {"on_provider_error": "escalate"},
        ),
    )


class RecordingRuntimeStore:
    def __init__(self, resolution: RuntimeResolution) -> None:
        self._resolution = resolution
        self.records: list[AgentInvocationRecord] = []
        self.metadata: list[dict[str, Any]] = []
        self.transcripts: list[AgentInvocationTranscript] = []

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

    def record_transcript(self, record: AgentInvocationTranscript) -> None:
        self.transcripts.append(record)


@dataclass
class _FailingAdapter:
    """Test adapter that always raises a provider error."""

    adapter_version: str = "failing-test-v1"

    def invoke(self, args: InvocationArgs) -> InvocationResult:
        from chorus.llm_provider import LLMProviderInvocationError

        raise LLMProviderInvocationError(
            route_id=args.route_id, reason="fixture_outage", retryable=True
        )


@dataclass
class _ExpensiveAdapter:
    """Test adapter that returns a result deliberately over budget."""

    adapter_version: str = "expensive-test-v1"

    def invoke(self, args: InvocationArgs) -> InvocationResult:
        _ = args
        return InvocationResult(
            summary="Expensive provider returned a result over the route budget.",
            structured_data={},
            confidence=0.9,
            recommended_next_step="continue",
            rationale="Fixture exceeds the route budget cap.",
            cost_amount_usd=Decimal("0.500000"),
        )


def _fallback_route_policy() -> dict[str, Any]:
    return {
        "on_provider_error": "fallback_route",
        "fallback_reasons": ["provider_error", "fixture_outage", "budget_exceeded"],
        "fallback_route": {
            "provider": "local",
            "model": "uc1-happy-path-v1",
            "parameters": {"temperature": 0.3},
        },
    }


def _replay_catalogue() -> RouteCatalogue:
    return RouteCatalogue(
        [
            RouteCatalogueEntry(
                route_id="recorded-replay",
                provider_id="local-replay",
                model_id="recorded-replay-v1",
                adapter=RecordedReplayAdapter(),
            )
        ]
    )


def test_sequential_engine_runs_pipeline_through_route_catalogue() -> None:
    """The post-B engine runs five steps as plain Python and emits route metadata."""

    request = _request()
    resolution = _resolution()
    engine = SequentialAgentExecutionEngine(_replay_catalogue(), ProviderRouteResolver())

    execution = engine.invoke(request, resolution, uuid4())

    assert execution.step_path == (
        "prepare_context",
        "invoke_llm_provider_port",
        "normalise_result",
        "validate_contract",
        "final_response",
    )
    assert isinstance(execution.contract, Uc1AgentIO)
    assert execution.decision_metadata["execution.pipeline_version"] == EXECUTION_PIPELINE_VERSION
    assert execution.decision_metadata["route_catalogue.route_id"] == "recorded-replay"
    assert execution.decision_metadata["route_catalogue.provider_id"] == "local-replay"
    assert execution.decision_metadata["route_catalogue.adapter_version"] == "recorded-replay-v1"
    assert execution.decision_metadata["prompt.reference"] == "prompts/uc1/request-drafter/v1.md"
    assert execution.decision_metadata["prompt.hash"] == PROMPT_HASHES["request_drafter"]
    assert execution.decision_metadata["prompt.hash_verified"] is True
    assert execution.request_messages[0].role == "system"
    assert execution.request_messages[0].content.startswith("# UC1 request drafter v1")
    assert execution.request_messages[1].role == "user"


def test_route_resolver_rejects_unregistered_provider() -> None:
    """A model-route provider with no catalogue entry must fail fast."""

    catalogue = _replay_catalogue()
    resolution = _resolution(provider="unknown.provider")
    resolver = ProviderRouteResolver()

    with pytest.raises(AgentRuntimeError, match="No LLM provider port route registered"):
        resolver.resolve(resolution.model_route, catalogue)


def test_runtime_invokes_recorded_replay_route_and_records_decision_trail() -> None:
    """Happy path: the runtime records a decision-trail entry with the new metadata shape."""

    store = RecordingRuntimeStore(_resolution())
    runtime = AgentRuntime(store, _replay_catalogue())

    response = runtime.invoke(_request())

    assert store.records, "decision-trail entry must be recorded"
    record = store.records[0]
    assert record.outcome.value == "succeeded"
    assert response.recommended_next_step == "continue"

    metadata = store.metadata[0]
    assert metadata["execution.pipeline_version"] == EXECUTION_PIPELINE_VERSION
    assert metadata["route_catalogue.route_id"] == "recorded-replay"
    assert metadata["model_route.provider"] == "local"
    assert metadata["model_route.cost_amount_usd"] == "0.000000"


def test_runtime_records_policy_snapshot_ref_metadata_for_qualification() -> None:
    """Qualifier outputs keep the policy snapshot ref visible on the decision trail."""

    store = RecordingRuntimeStore(
        _resolution(
            role="qualifier",
            agent_id="uc1.qualifier",
            task_kind="enquiry_qualification",
            prompt_reference="prompts/uc1/qualifier/v1.md",
            prompt_hash=PROMPT_HASHES["qualifier"],
        )
    )
    runtime = AgentRuntime(store, _replay_catalogue())

    response = runtime.invoke(_request(task_kind="enquiry_qualification", role="qualifier"))

    assert response.structured_data["policy_snapshot_ref"] == "policy_snapshot:uc1:default:v1"
    assert store.metadata[0]["policy_snapshot.ref"] == "policy_snapshot:uc1:default:v1"


def test_runtime_records_decision_trail_and_transcript_on_every_invocation() -> None:
    """Per ADR 0019, every invocation writes both audit-port records."""

    store = RecordingRuntimeStore(_resolution())
    runtime = AgentRuntime(store, _replay_catalogue())

    runtime.invoke(_request())

    assert len(store.records) == 1
    assert len(store.transcripts) == 1
    decision, transcript = store.records[0], store.transcripts[0]
    assert str(transcript.invocation_id) == str(decision.invocation_id)
    assert transcript.tenant_id == decision.tenant_id
    assert transcript.route_catalogue.route_id == "recorded-replay"
    assert transcript.route_catalogue.provider_id == "local-replay"
    assert transcript.route_catalogue.adapter_version == "recorded-replay-v1"
    assert transcript.messages[0].role.value == "system"
    assert transcript.messages[0].content.startswith("# UC1 request drafter v1")
    assert any(message.role.value == "user" for message in transcript.messages)
    assert any(message.role.value == "assistant" for message in transcript.messages)


def test_runtime_rejects_prompt_hash_mismatch_before_provider_call() -> None:
    """Registry prompt hashes are enforced before invoking the provider port."""

    store = RecordingRuntimeStore(_resolution(prompt_hash="sha256:" + "0" * 64))
    runtime = AgentRuntime(store, _replay_catalogue())

    with pytest.raises(PromptLoadError):
        runtime.invoke(_request())

    assert len(store.records) == 1
    assert store.records[0].outcome.value == "failed"
    assert store.metadata[0]["prompt.reference"] == "prompts/uc1/request-drafter/v1.md"
    assert store.metadata[0]["prompt.hash_verified"] is False
    assert store.metadata[0]["prompt.failure_reason"] == "prompt_hash_mismatch"
    assert store.metadata[0]["execution.step_path"] == ["prepare_context"]
    assert not store.transcripts


def test_runtime_records_provider_failure_then_invokes_policy_fallback() -> None:
    """Adapter failures must trigger the configured fallback route and be audited."""

    store = RecordingRuntimeStore(
        _resolution(provider="vendor.experimental", fallback_policy=_fallback_route_policy())
    )
    catalogue = RouteCatalogue(
        [
            RouteCatalogueEntry(
                route_id="recorded-replay",
                provider_id="local",
                model_id="uc1-happy-path-v1",
                adapter=RecordedReplayAdapter(),
            ),
            RouteCatalogueEntry(
                route_id="failing",
                provider_id="vendor.experimental",
                model_id="experimental-v1",
                adapter=_FailingAdapter(),
            ),
        ]
    )

    resolver = ProviderRouteResolver()
    # Map the experimental provider into the failing route for this test.
    resolver._PROVIDER_TO_ROUTE = {  # type: ignore[attr-defined]
        **resolver._PROVIDER_TO_ROUTE,  # type: ignore[attr-defined]
        "vendor.experimental": "failing",
    }

    runtime = AgentRuntime(store, catalogue, resolver)
    response = runtime.invoke(_request())

    assert response.recommended_next_step == "continue"
    assert len(store.records) == 2
    primary, fallback = store.records
    assert primary.outcome.value == "failed"
    assert fallback.outcome.value == "succeeded"
    assert store.metadata[0]["provider_fallback.reason"] == "fixture_outage"
    assert store.metadata[1]["provider_fallback.applied"] is True


def test_runtime_records_provider_budget_exceeded_then_invokes_policy_fallback() -> None:
    """Over-budget adapter results raise ProviderBudgetExceededError and trigger fallback."""

    store = RecordingRuntimeStore(
        _resolution(provider="vendor.experimental", fallback_policy=_fallback_route_policy())
    )
    catalogue = RouteCatalogue(
        [
            RouteCatalogueEntry(
                route_id="recorded-replay",
                provider_id="local",
                model_id="uc1-happy-path-v1",
                adapter=RecordedReplayAdapter(),
            ),
            RouteCatalogueEntry(
                route_id="expensive",
                provider_id="vendor.experimental",
                model_id="expensive-v1",
                adapter=_ExpensiveAdapter(),
            ),
        ]
    )

    resolver = ProviderRouteResolver()
    resolver._PROVIDER_TO_ROUTE = {  # type: ignore[attr-defined]
        **resolver._PROVIDER_TO_ROUTE,  # type: ignore[attr-defined]
        "vendor.experimental": "expensive",
    }

    runtime = AgentRuntime(store, catalogue, resolver)
    response = runtime.invoke(_request())

    assert response.recommended_next_step == "continue"
    assert len(store.records) == 2
    assert store.records[0].outcome.value == "failed"
    assert store.records[1].outcome.value == "succeeded"
    expected_reason = ProviderBudgetExceededError.fallback_reason
    assert store.metadata[0]["provider_fallback.reason"] == expected_reason


def test_default_route_catalogue_registers_three_routes() -> None:
    """Per ADR 0018 the catalogue ships dev, demo-eval-canonical, and recorded-replay."""

    catalogue = default_route_catalogue()
    assert catalogue.route_ids == ("demo-eval-canonical", "dev", "recorded-replay")
    replay = catalogue.get("recorded-replay")
    assert replay.provider_id == "local-replay"
    assert replay.adapter_version.startswith("recorded-replay")
    dev = catalogue.get("dev")
    assert dev.provider_id == "deepseek"
    assert dev.model_id == "deepseek-v4-flash"
    assert isinstance(dev.adapter, OpenAICompatibleAdapter)
    assert dev.adapter.api_key_env == "DEEPSEEK_API_KEY"
    assert dev.adapter.base_url == "https://api.deepseek.com"
    assert dev.parameters["extra_body"] == {"thinking": {"type": "enabled"}}
    canonical = catalogue.get("demo-eval-canonical")
    assert canonical.provider_id == "openai"
    assert canonical.model_id == "gpt-5.4-mini-2026-03-17"
    assert isinstance(canonical.adapter, OpenAICompatibleAdapter)
    assert canonical.adapter.api_key_env == "OPENAI_API_KEY"
    assert canonical.adapter.base_url == "https://api.openai.com/v1"


def test_runtime_validates_uc1_contract_for_missing_data_request_draft(
    migrated_database_url: str,
) -> None:
    """Integration: AgentRuntime invokes through the resolved model route in Postgres."""

    with psycopg.connect(migrated_database_url) as conn:
        store = AgentRuntimeStore(conn)
        store.set_tenant_context("tenant_demo")
        runtime = AgentRuntime(store, _replay_catalogue())

        response = runtime.invoke(_request())

        assert response.recommended_next_step == "continue"
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT outcome, contract_refs, metadata
                FROM decision_trail_entries
                WHERE invocation_id = %s
                """,
                (response.invocation_id,),
            )
            row = cur.fetchone()

    assert row is not None
    outcome, contract_refs, metadata = row
    assert outcome == "succeeded"
    assert "contracts/audit/agent_invocation_record.schema.json" in contract_refs
    assert metadata["route_catalogue.route_id"] == "recorded-replay"
    assert metadata["execution.pipeline_version"] == EXECUTION_PIPELINE_VERSION


def test_policy_resolution_uses_registry_prompt_and_model_route(
    migrated_database_url: str,
) -> None:
    """The runtime resolves tenant, agent, and model route from Postgres seeds."""

    with psycopg.connect(migrated_database_url) as conn:
        store = AgentRuntimeStore(conn)
        resolution = store.resolve(_request())

    assert resolution.tenant.tenant_id == "tenant_demo"
    assert resolution.agent.role == "request_drafter"
    assert resolution.agent.lifecycle_state == "approved"
    assert resolution.agent.prompt_reference == "prompts/uc1/request-drafter/v1.md"
    assert resolution.agent.prompt_hash == PROMPT_HASHES["request_drafter"]
    assert resolution.model_route.provider == "local"
    assert resolution.model_route.model == "uc1-happy-path-v1"


def test_activity_integration_invokes_runtime_boundary(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Temporal activity wires the route catalogue into the AgentRuntime path."""

    monkeypatch.setenv("CHORUS_DATABASE_URL", migrated_database_url)
    response = invoke_agent_runtime_activity(_request())
    assert response.recommended_next_step == "continue"
    assert response.summary

    with psycopg.connect(migrated_database_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT outcome FROM decision_trail_entries WHERE invocation_id = %s",
            (response.invocation_id,),
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == "succeeded"


def test_uc1_agent_contract_round_trip_through_runtime() -> None:
    """The Uc1AgentIO contract is produced and JSON-serialisable end-to-end."""

    store = RecordingRuntimeStore(_resolution())
    runtime = AgentRuntime(store, _replay_catalogue())

    runtime.invoke(_request())

    payload = json.loads(store.records[0].model_dump_json())
    assert payload["agent"]["role"] == "request_drafter"
    assert payload["model_route"]["provider"] == "local"

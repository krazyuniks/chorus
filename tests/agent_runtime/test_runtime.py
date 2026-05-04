from __future__ import annotations

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
    AgentRuntime,
    AgentRuntimeError,
    AgentRuntimeStore,
    ModelAdapterRegistry,
    ModelAdapterResult,
    ResolvedAgent,
    ResolvedModelRoute,
    RuntimeResolution,
    TenantPolicy,
    default_model_adapter_registry,
)
from chorus.contracts.generated.agents.lighthouse_agent_io import LighthouseAgentIO
from chorus.contracts.generated.events.agent_invocation_record import AgentInvocationRecord
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
        expected_output_contract="contracts/agents/lighthouse_agent_io.schema.json",
    )


def _resolution(
    *,
    provider: str = "local",
    model: str = "lighthouse-happy-path-v1",
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
            fallback_policy={"on_provider_error": "escalate"},
        ),
    )


class RecordingRuntimeStore:
    def __init__(self, resolution: RuntimeResolution) -> None:
        self._resolution = resolution
        self.records: list[AgentInvocationRecord] = []

    def resolve(self, request: AgentInvocationRequest) -> RuntimeResolution:
        _ = request
        return self._resolution

    def record_decision(self, record: AgentInvocationRecord) -> None:
        self.records.append(record)


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


def test_default_model_adapter_registry_registers_only_local_provider() -> None:
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

    assert registry.provider_ids == ("local",)
    with pytest.raises(AgentRuntimeError, match="Duplicate model adapter"):
        ModelAdapterRegistry([DuplicateLocalAdapter(), DuplicateLocalAdapter()])


def test_runtime_invokes_selected_local_adapter_without_changing_activity_contract() -> None:
    request = _request()
    store = RecordingRuntimeStore(_resolution())

    response = AgentRuntime(store, default_model_adapter_registry()).invoke(request)

    assert response.recommended_next_step == "continue"
    assert response.structured_data["model_boundary"] == {
        "provider": "local",
        "model": "lighthouse-happy-path-v1",
    }
    assert len(store.records) == 1
    assert store.records[0].model_route.provider == "local"
    assert store.records[0].model_route.model == "lighthouse-happy-path-v1"


def test_runtime_records_failure_when_selected_provider_has_no_adapter() -> None:
    request = _request()
    store = RecordingRuntimeStore(
        _resolution(provider="commercial.example", model="commercial-reasoner-v1")
    )

    with pytest.raises(AgentRuntimeError, match="No model adapter registered"):
        AgentRuntime(store, default_model_adapter_registry()).invoke(request)

    assert len(store.records) == 1
    assert store.records[0].outcome.value == "failed"
    assert store.records[0].model_route.provider == "commercial.example"
    assert "No model adapter registered" in store.records[0].output_summary


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
                raw_record
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


def test_runtime_records_failure_when_route_has_no_registered_adapter(
    migrated_database_url: str,
) -> None:
    request = _request()

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

        with pytest.raises(AgentRuntimeError, match="No model adapter registered"):
            runtime.invoke(request)

        row = conn.execute(
            """
            SELECT provider, model, outcome, output_summary
            FROM decision_trail_entries
            WHERE tenant_id = %s
              AND correlation_id = %s
            """,
            (request.tenant_id, request.correlation_id),
        ).fetchone()

    assert row is not None
    assert row[:3] == ("commercial.example", "commercial-reasoner-v1", "failed")
    assert "No model adapter registered" in row[3]


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
            SELECT agent_id, task_kind, outcome
            FROM decision_trail_entries
            WHERE tenant_id = %s AND invocation_id = %s
            """,
            (request.tenant_id, response.invocation_id),
        ).fetchone()

    assert response.recommended_next_step == "send"
    assert response.structured_data["validation"] == "approved"
    assert persisted == ("lighthouse.validator", "response_validation", "succeeded")

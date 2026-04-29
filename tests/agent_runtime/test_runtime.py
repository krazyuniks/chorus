from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from chorus.agent_runtime import AgentRuntime, AgentRuntimeStore, LocalLighthouseModelBoundary
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


def test_runtime_validates_contracts_and_persists_decision_trail(
    migrated_database_url: str,
) -> None:
    request = _request()

    with psycopg.connect(migrated_database_url) as conn:
        response = AgentRuntime(
            AgentRuntimeStore(conn),
            LocalLighthouseModelBoundary(),
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
        runtime = AgentRuntime(AgentRuntimeStore(conn), LocalLighthouseModelBoundary())
        first_response = runtime.invoke(first_request)
        second_response = runtime.invoke(second_request)

    assert first_response.recommended_next_step == "deeper_research"
    assert first_response.confidence == 0.42
    assert second_response.recommended_next_step == "continue"
    assert second_response.confidence == 0.86
    assert second_response.structured_data["deeper_research_completed"] is True


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

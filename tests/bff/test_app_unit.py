from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from chorus.bff.app import BffSettings, create_app, store_dependency
from chorus.persistence.projection import (
    AgentRegistryEntry,
    DecisionTrailEntryReadModel,
    ModelRoutingPolicy,
    RuntimePolicySnapshot,
    ToolActionAuditReadModel,
    ToolGrant,
    WorkflowHistoryEventReadModel,
    WorkflowRunReadModel,
)


class FakeProjectionStore:
    def __init__(self) -> None:
        self.workflow_id = "lighthouse-bff-unit"
        self.correlation_id = "cor_bff_unit"
        self.lead_id = uuid4()
        self.event_id = uuid4()
        self.invocation_id = uuid4()
        self.audit_event_id = uuid4()
        self.now = datetime(2026, 4, 29, 12, 0, tzinfo=UTC)

    def list_workflows(self, tenant_id: str, *, limit: int = 100) -> list[WorkflowRunReadModel]:
        _ = (tenant_id, limit)
        return [self._workflow()]

    def get_workflow(self, tenant_id: str, workflow_id: str) -> WorkflowRunReadModel | None:
        _ = tenant_id
        if workflow_id != self.workflow_id:
            return None
        return self._workflow()

    def list_workflow_history(
        self,
        tenant_id: str,
        workflow_id: str,
        *,
        after_sequence: int | None = None,
        limit: int = 500,
    ) -> list[WorkflowHistoryEventReadModel]:
        _ = (tenant_id, workflow_id, after_sequence, limit)
        return [self._event()]

    def list_recent_workflow_history(
        self,
        tenant_id: str,
        *,
        limit: int = 100,
    ) -> list[WorkflowHistoryEventReadModel]:
        _ = (tenant_id, limit)
        return [self._event()]

    def list_decision_trail(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        limit: int = 500,
    ) -> list[DecisionTrailEntryReadModel]:
        _ = (tenant_id, workflow_id, limit)
        return [self._decision()]

    def list_tool_action_audit(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        limit: int = 500,
    ) -> list[ToolActionAuditReadModel]:
        _ = (tenant_id, workflow_id, limit)
        return [self._audit()]

    def runtime_policy_snapshot(self, tenant_id: str) -> RuntimePolicySnapshot:
        return RuntimePolicySnapshot(
            tenant_id=tenant_id,
            agents=[
                AgentRegistryEntry(
                    tenant_id=tenant_id,
                    agent_id="lighthouse.drafter",
                    role="drafter",
                    version="v1",
                    lifecycle_state="approved",
                    owner="agent-runtime",
                    prompt_reference="prompts/lighthouse/drafter/v1.md",
                    prompt_hash="sha256:" + "d" * 64,
                    capability_tags=["lighthouse", "drafting"],
                    updated_at=self.now,
                )
            ],
            model_routes=[
                ModelRoutingPolicy(
                    policy_id=uuid4(),
                    tenant_id=tenant_id,
                    agent_role="drafter",
                    task_kind="response_draft",
                    tenant_tier="demo",
                    provider="local",
                    model="lighthouse-happy-path-v1",
                    parameters={"temperature": 0.3},
                    budget_cap_usd=Decimal("0.0100"),
                    fallback_policy={"on_provider_error": "escalate"},
                    lifecycle_state="approved",
                )
            ],
            tool_grants=[
                ToolGrant(
                    grant_id=uuid4(),
                    tenant_id=tenant_id,
                    agent_id="lighthouse.drafter",
                    agent_version="v1",
                    tool_name="email.propose_response",
                    mode="propose",
                    allowed=True,
                    approval_required=False,
                    redaction_policy={"redact_fields": ["body_text"]},
                )
            ],
        )

    def _workflow(self) -> WorkflowRunReadModel:
        return WorkflowRunReadModel(
            tenant_id="tenant_demo",
            workflow_id=self.workflow_id,
            correlation_id=self.correlation_id,
            lead_id=self.lead_id,
            status="running",
            current_step="propose_send",
            lead_summary="Unit fixture lead",
            last_event_id=self.event_id,
            last_event_sequence=1,
            started_at=self.now,
            completed_at=None,
            updated_at=self.now,
            metadata={"sender": "lead@example.com"},
        )

    def _event(self) -> WorkflowHistoryEventReadModel:
        return WorkflowHistoryEventReadModel(
            tenant_id="tenant_demo",
            history_event_id=uuid4(),
            workflow_id=self.workflow_id,
            correlation_id=self.correlation_id,
            source_event_id=self.event_id,
            event_type="lead.received",
            sequence=1,
            step="intake",
            payload={"lead_summary": "Unit fixture lead"},
            occurred_at=self.now,
            created_at=self.now,
        )

    def _decision(self) -> DecisionTrailEntryReadModel:
        return DecisionTrailEntryReadModel(
            tenant_id="tenant_demo",
            invocation_id=self.invocation_id,
            correlation_id=self.correlation_id,
            workflow_id=self.workflow_id,
            agent_id="lighthouse.drafter",
            agent_role="drafter",
            agent_version="v1",
            lifecycle_state="approved",
            prompt_reference="prompts/lighthouse/drafter/v1.md",
            prompt_hash="sha256:" + "d" * 64,
            provider="local",
            model="lighthouse-happy-path-v1",
            task_kind="response_draft",
            budget_cap_usd=Decimal("0.0100"),
            input_summary="input",
            output_summary="output",
            justification="unit route",
            outcome="succeeded",
            tool_call_ids=[],
            cost_amount=Decimal("0.0001"),
            cost_currency="USD",
            duration_ms=12,
            started_at=self.now,
            completed_at=self.now,
            contract_refs=["contracts/agents/lighthouse_agent_io.schema.json"],
            raw_record={"metadata": {"unit": True}},
            created_at=self.now,
        )

    def _audit(self) -> ToolActionAuditReadModel:
        return ToolActionAuditReadModel(
            tenant_id="tenant_demo",
            audit_event_id=self.audit_event_id,
            correlation_id=self.correlation_id,
            workflow_id=self.workflow_id,
            invocation_id=self.invocation_id,
            tool_call_id=uuid4(),
            verdict_id=uuid4(),
            actor_type="agent",
            actor_id="lighthouse.drafter",
            category="tool_gateway",
            action="email.propose_response",
            tool_name="email.propose_response",
            requested_mode="propose",
            enforced_mode="propose",
            verdict="propose",
            idempotency_key=f"{self.workflow_id}:email.propose_response",
            arguments_redacted={"body_text": "[redacted]"},
            rewritten_arguments=None,
            reason="Proposal captured by Mailpit",
            connector_invocation_id=uuid4(),
            occurred_at=self.now,
            raw_event={"details": {"gateway_verdict": {"verdict": "propose"}}},
            created_at=self.now,
        )


def _client() -> tuple[TestClient, FakeProjectionStore]:
    store = FakeProjectionStore()
    app = create_app(
        BffSettings(
            database_url="postgresql://unused:unused@localhost/unused",
            tenant_id="tenant_demo",
            sse_poll_interval_seconds=0.01,
        )
    )

    def override_store() -> Iterator[Any]:
        yield store

    app.dependency_overrides[store_dependency] = override_store
    return TestClient(app), store


def test_projection_endpoints_use_bff_response_contracts() -> None:
    client, store = _client()

    workflows = client.get("/api/workflows").json()
    detail = client.get(f"/api/workflows/{store.workflow_id}").json()
    events = client.get(f"/api/workflows/{store.workflow_id}/events").json()

    assert workflows[0]["workflow_id"] == store.workflow_id
    assert detail["lead_from"] == "lead@example.com"
    assert events[0]["event_type"] == "lead.received"


def test_audit_and_runtime_policy_endpoints_are_read_only_views() -> None:
    client, store = _client()

    decisions = client.get(f"/api/workflows/{store.workflow_id}/decision-trail").json()
    verdicts = client.get(f"/api/workflows/{store.workflow_id}/tool-verdicts").json()
    registry = client.get("/api/runtime/registry").json()
    grants = client.get("/api/runtime/grants").json()
    routing = client.get("/api/runtime/routing").json()

    assert decisions[0]["model_route"] == "local/lighthouse-happy-path-v1"
    assert verdicts[0]["redactions"] == ["body_text"]
    assert registry[0]["lifecycle_state"] == "approved"
    assert grants[0]["tool_name"] == "email.propose_response"
    assert routing[0]["budget_usd"] == 0.01


def test_progress_sse_is_projection_backed() -> None:
    client, _ = _client()

    response = client.get("/api/progress?once=true")

    assert response.status_code == 200
    assert "event: progress" in response.text
    assert "lead.received" in response.text

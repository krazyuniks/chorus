from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from chorus.bff.app import (
    BffSettings,
    create_app,
    progress_snapshot_store_dependency,
    store_dependency,
)
from chorus.persistence.projection import (
    AgentRegistryEntry,
    CalendarProjectionReadModel,
    DecisionTrailEntryReadModel,
    ModelRouteVersion,
    ModelRoutingPolicy,
    ProviderCatalogueEntry,
    ProviderCatalogueModel,
    ProviderCatalogueProvider,
    ProviderGovernanceSnapshot,
    RuntimePolicySnapshot,
    ToolActionAuditReadModel,
    ToolGrant,
    WorkflowHistoryEventReadModel,
    WorkflowRunReadModel,
)


class FakeProjectionStore:
    def __init__(self) -> None:
        self.workflow_id = "uc1-enq-bff-unit"
        self.correlation_id = "cor_bff_unit"
        self.subject_id = uuid4()
        self.event_id = uuid4()
        self.invocation_id = uuid4()
        self.audit_event_id = uuid4()
        self.approval_id = uuid4()
        self.calendar_apply_audit_event_id = uuid4()
        self.now = datetime(2026, 4, 29, 12, 0, tzinfo=UTC)

    def list_workflows(self, tenant_id: str, *, limit: int = 100) -> list[WorkflowRunReadModel]:
        del tenant_id, limit
        return [self._workflow()]

    def get_workflow(self, tenant_id: str, workflow_id: str) -> WorkflowRunReadModel | None:
        del tenant_id
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
        del tenant_id, workflow_id, after_sequence, limit
        return [self._event()]

    def list_recent_workflow_history(
        self,
        tenant_id: str,
        *,
        limit: int = 100,
    ) -> list[WorkflowHistoryEventReadModel]:
        del tenant_id, limit
        return [self._event()]

    def list_decision_trail(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        limit: int = 500,
    ) -> list[DecisionTrailEntryReadModel]:
        del tenant_id, workflow_id, limit
        return [self._decision()]

    def list_tool_action_audit(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        limit: int = 500,
    ) -> list[ToolActionAuditReadModel]:
        del tenant_id, workflow_id, limit
        return [self._audit()]

    def list_calendar_projections(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        limit: int = 100,
    ) -> list[CalendarProjectionReadModel]:
        del tenant_id, workflow_id, limit
        return [self._calendar_projection()]

    def runtime_policy_snapshot(self, tenant_id: str) -> RuntimePolicySnapshot:
        del tenant_id
        return RuntimePolicySnapshot(
            tenant_id="tenant_demo",
            agents=[self._agent()],
            model_routes=[self._route()],
            tool_grants=[self._grant()],
        )

    def provider_governance_snapshot(self, tenant_id: str) -> ProviderGovernanceSnapshot:
        del tenant_id
        return ProviderGovernanceSnapshot(
            tenant_id="tenant_demo",
            catalogues=[self._catalogue_entry()],
            providers=[self._provider(), self._commercial_provider()],
            provider_models=[self._provider_model()],
            route_versions=[self._route_version()],
        )

    def _workflow(self) -> WorkflowRunReadModel:
        return WorkflowRunReadModel(
            tenant_id="tenant_demo",
            workflow_id=self.workflow_id,
            workflow_type="uc1_enquiry_qualification",
            correlation_id=self.correlation_id,
            subject_id=self.subject_id,
            subject_ref="enq_motor_private_001",
            status="completed",
            current_step="complete",
            subject_summary="Motor cover enquiry",
            last_event_id=self.event_id,
            last_event_sequence=10,
            started_at=self.now,
            completed_at=self.now,
            updated_at=self.now,
            metadata={"sender": "enquiry@example.com"},
        )

    def _event(self) -> WorkflowHistoryEventReadModel:
        return WorkflowHistoryEventReadModel(
            tenant_id="tenant_demo",
            history_event_id=uuid4(),
            workflow_id=self.workflow_id,
            correlation_id=self.correlation_id,
            source_event_id=self.event_id,
            event_type="enquiry.received",
            sequence=1,
            step="intake",
            payload={"enquiry_summary": "Motor cover enquiry"},
            occurred_at=self.now,
            created_at=self.now,
        )

    def _decision(self) -> DecisionTrailEntryReadModel:
        return DecisionTrailEntryReadModel(
            tenant_id="tenant_demo",
            invocation_id=self.invocation_id,
            correlation_id=self.correlation_id,
            workflow_id=self.workflow_id,
            agent_id="uc1.request_drafter",
            agent_role="request_drafter",
            agent_version="v1",
            lifecycle_state="approved",
            prompt_reference="prompts/uc1/request-drafter/v1.md",
            prompt_hash="sha256:" + "0" * 64,
            provider="local",
            model="uc1-happy-path-v1",
            task_kind="missing_data_request_draft",
            budget_cap_usd=Decimal("0.01"),
            input_summary="Motor cover enquiry",
            output_summary="Drafted missing-data request",
            justification="test",
            outcome="succeeded",
            tool_call_ids=[],
            cost_amount=Decimal("0.001"),
            cost_currency="USD",
            duration_ms=120,
            started_at=self.now,
            completed_at=self.now,
            contract_refs=["contracts/llm_provider/uc1_agent_io.schema.json"],
            raw_record={},
            metadata={
                "model_route.route_id": "11000000-0000-4000-8000-000000000004",
                "model_route.route_version": 1,
            },
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
            actor_id="uc1.request_drafter",
            category="tool_gateway",
            action="tool_call.decided",
            tool_name="outbound_comms.message",
            requested_mode="propose",
            enforced_mode="propose",
            verdict="propose",
            idempotency_key="key",
            arguments_redacted={"body_text": "[redacted]"},
            rewritten_arguments=None,
            reason="propose mode",
            connector_invocation_id=None,
            occurred_at=self.now,
            raw_event={},
            created_at=self.now,
        )

    def _calendar_projection(self) -> CalendarProjectionReadModel:
        return CalendarProjectionReadModel(
            tenant_id="tenant_demo",
            approval_id=self.approval_id,
            workflow_id=self.workflow_id,
            correlation_id=self.correlation_id,
            tool_name="calendar.create_hold",
            requested_action="calendar.create_hold.write",
            requested_mode="write",
            enforced_mode="write",
            approval_state="approved",
            idempotency_key_ref="sha256:" + "0" * 64,
            calendar_refs={
                "calendar_ref": "cal_uc1_local_followup",
                "hold_ref": "hold_uc1_followup_001",
                "slot_ref": "slot_uc1_followup_001",
                "event_uid_ref": "evt_uc1_followup_001",
            },
            projection_status="calendar_hold_created",
            source_audit_event_id=self.audit_event_id,
            latest_audit_event_id=self.calendar_apply_audit_event_id,
            latest_verdict="allow",
            latest_reason="Approved local calendar package re-entered the Tool Gateway.",
            connector_invocation_id=uuid4(),
            retry_category=None,
            compensation_category=None,
            failure_category=None,
            grant_ref="tool_grant:" + str(uuid4()),
            policy_version_refs={},
            trace_join={},
            updated_at=self.now,
        )

    def _agent(self) -> AgentRegistryEntry:
        return AgentRegistryEntry(
            tenant_id="tenant_demo",
            agent_id="uc1.request_drafter",
            role="request_drafter",
            version="v1",
            lifecycle_state="approved",
            owner="agent-runtime",
            prompt_reference="prompts/uc1/request-drafter/v1.md",
            prompt_hash="sha256:" + "0" * 64,
            capability_tags=["uc1"],
            updated_at=self.now,
        )

    def _route(self) -> ModelRoutingPolicy:
        return ModelRoutingPolicy(
            policy_id=uuid4(),
            tenant_id="tenant_demo",
            agent_role="request_drafter",
            task_kind="missing_data_request_draft",
            tenant_tier="demo",
            provider="local",
            model="uc1-happy-path-v1",
            parameters={"temperature": 0.3},
            budget_cap_usd=Decimal("0.01"),
            fallback_policy={},
            lifecycle_state="approved",
        )

    def _grant(self) -> ToolGrant:
        return ToolGrant(
            grant_id=uuid4(),
            tenant_id="tenant_demo",
            agent_id="uc1.request_drafter",
            agent_version="v1",
            tool_name="outbound_comms.message",
            mode="propose",
            allowed=True,
            approval_required=False,
            redaction_policy={"redact_fields": ["body_text"]},
        )

    def _catalogue_entry(self) -> ProviderCatalogueEntry:
        return ProviderCatalogueEntry(
            catalogue_id="provider-catalogue.local.seed",
            schema_version="1.0.0",
            effective_from=self.now,
            created_at=self.now,
        )

    def _provider(self) -> ProviderCatalogueProvider:
        return ProviderCatalogueProvider(
            catalogue_id="provider-catalogue.local.seed",
            provider_id="local",
            display_name="Local structured boundary",
            provider_kind="local",
            lifecycle_state="approved",
            credential_required=False,
            secret_ref_names=[],
            missing_credentials_behaviour="allow",
            data_boundary={"mode": "local_only"},
            operational_limits={},
            audit={},
        )

    def _commercial_provider(self) -> ProviderCatalogueProvider:
        return ProviderCatalogueProvider(
            catalogue_id="provider-catalogue.local.seed",
            provider_id="commercial.example",
            display_name="Commercial",
            provider_kind="commercial",
            lifecycle_state="disabled",
            credential_required=True,
            secret_ref_names=["CHORUS_COMMERCIAL_LLM_API_KEY"],
            missing_credentials_behaviour="disable_provider",
            data_boundary={"mode": "external_api"},
            operational_limits={},
            audit={},
        )

    def _provider_model(self) -> ProviderCatalogueModel:
        return ProviderCatalogueModel(
            catalogue_id="provider-catalogue.local.seed",
            provider_id="local",
            model_id="uc1-happy-path-v1",
            display_name="UC1 local structured model",
            lifecycle_state="approved",
            supported_task_kinds=["enquiry_classification"],
            supports_structured_output=True,
            context_window_tokens=8192,
            cost_policy={"currency": "USD"},
        )

    def _route_version(self) -> ModelRouteVersion:
        return ModelRouteVersion(
            route_id=uuid4(),
            route_version=1,
            lifecycle_state="approved",
            tenant_id="tenant_demo",
            agent_role="request_drafter",
            task_kind="missing_data_request_draft",
            tenant_tier="demo",
            provider_catalogue_id="provider-catalogue.local.seed",
            provider_id="local",
            model_id="uc1-happy-path-v1",
            parameters={"temperature": 0.3},
            budget_cap_usd=Decimal("0.01"),
            max_latency_ms=5000,
            fallback_policy={"mode": "escalate"},
            eval_required=True,
            eval_fixture_refs=[],
            promotion={},
            created_at=self.now,
        )


def _client() -> tuple[TestClient, FakeProjectionStore]:
    store = FakeProjectionStore()
    settings = BffSettings(database_url="postgresql://invalid", tenant_id="tenant_demo")
    app = create_app(settings)

    def fake_store_dependency() -> Iterator[Any]:
        yield store

    def fake_progress_dependency(once: bool = False) -> Iterator[Any]:
        del once
        yield store

    app.dependency_overrides[store_dependency] = fake_store_dependency
    app.dependency_overrides[progress_snapshot_store_dependency] = fake_progress_dependency
    return TestClient(app), store


def test_projection_endpoints_use_bff_response_contracts() -> None:
    client, store = _client()

    workflows = client.get("/api/workflows").json()
    detail = client.get(f"/api/workflows/{store.workflow_id}").json()
    events = client.get(f"/api/workflows/{store.workflow_id}/events").json()

    assert workflows[0]["workflow_id"] == store.workflow_id
    assert workflows[0]["workflow_type"] == "uc1_enquiry_qualification"
    assert detail["subject_from"] == "enquiry@example.com"
    assert detail["subject_ref"] == "enq_motor_private_001"
    assert events[0]["event_type"] == "enquiry.received"


def test_audit_and_runtime_policy_endpoints_are_read_only_views() -> None:
    client, store = _client()

    decisions = client.get(f"/api/workflows/{store.workflow_id}/decision-trail").json()
    verdicts = client.get(f"/api/workflows/{store.workflow_id}/tool-verdicts").json()
    calendar_status = client.get(f"/api/workflows/{store.workflow_id}/calendar/status").json()
    registry = client.get("/api/runtime/registry").json()
    grants = client.get("/api/runtime/grants").json()
    routing = client.get("/api/runtime/routing").json()

    assert decisions[0]["model_route"] == "local/uc1-happy-path-v1"
    assert decisions[0]["provider"] == "local"
    assert verdicts[0]["redactions"] == ["body_text"]
    assert calendar_status[0]["projection_status"] == "calendar_hold_created"
    assert calendar_status[0]["calendar_refs"]["calendar_ref"] == "cal_uc1_local_followup"
    assert registry[0]["lifecycle_state"] == "approved"
    assert grants[0]["tool_name"] == "outbound_comms.message"
    assert routing[0]["budget_usd"] == 0.01


def test_provider_endpoints_are_read_only_views() -> None:
    client, _ = _client()

    providers = client.get("/api/runtime/providers").json()
    provider_models = client.get("/api/runtime/provider-models").json()
    route_versions = client.get("/api/runtime/route-versions").json()

    assert {row["provider_id"] for row in providers} == {"commercial.example", "local"}
    assert provider_models[0]["model_id"] == "uc1-happy-path-v1"
    assert route_versions[0]["route_version"] == 1
    assert route_versions[0]["provider_catalogue_id"] == "provider-catalogue.local.seed"


def test_progress_sse_is_projection_backed() -> None:
    client, _ = _client()

    with client.stream("GET", "/api/progress?once=true") as response:
        assert response.status_code == 200
        body = "".join(chunk for chunk in response.iter_text())
        assert "enquiry.received" in body

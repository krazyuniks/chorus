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
    SupportAgentDecisionReadModel,
    SupportCaseUpdateProposalReadModel,
    SupportInspectionReadModel,
    SupportStatusWriteBoundaryReadModel,
    SupportTicketVerdictReadModel,
    SupportWorkflowEventReadModel,
    ToolActionAuditReadModel,
    ToolGrant,
    WorkflowHistoryEventReadModel,
    WorkflowRunReadModel,
)


class FakeProjectionStore:
    def __init__(self) -> None:
        self.workflow_id = "lighthouse-bff-unit"
        self.correlation_id = "cor_bff_unit"
        self.support_workflow_id = "support-triage-bff-unit"
        self.support_correlation_id = "cor_support_bff_unit"
        self.lead_id = uuid4()
        self.event_id = uuid4()
        self.invocation_id = uuid4()
        self.audit_event_id = uuid4()
        self.approval_id = uuid4()
        self.calendar_apply_audit_event_id = uuid4()
        self.support_event_id = uuid4()
        self.support_invocation_id = uuid4()
        self.support_audit_event_id = uuid4()
        self.support_tool_call_id = uuid4()
        self.support_verdict_id = uuid4()
        self.support_connector_invocation_id = uuid4()
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

    def list_calendar_projections(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        limit: int = 100,
    ) -> list[CalendarProjectionReadModel]:
        _ = (tenant_id, workflow_id, limit)
        return [self._calendar_projection()]

    def list_support_inspections(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        correlation_id: str | None = None,
        limit: int = 100,
    ) -> list[SupportInspectionReadModel]:
        _ = (tenant_id, correlation_id, limit)
        if workflow_id is not None and workflow_id != self.support_workflow_id:
            return []
        return [self._support_inspection()]

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

    def provider_governance_snapshot(self, tenant_id: str) -> ProviderGovernanceSnapshot:
        return ProviderGovernanceSnapshot(
            tenant_id=tenant_id,
            catalogues=[
                ProviderCatalogueEntry(
                    catalogue_id="provider-catalogue.phase2a.seed",
                    schema_version="1.0.0",
                    effective_from=self.now,
                    created_at=self.now,
                )
            ],
            providers=[
                ProviderCatalogueProvider(
                    catalogue_id="provider-catalogue.phase2a.seed",
                    provider_id="local",
                    display_name="Local structured boundary",
                    provider_kind="local",
                    lifecycle_state="approved",
                    credential_required=False,
                    secret_ref_names=[],
                    missing_credentials_behaviour="allow",
                    data_boundary={"mode": "local_only"},
                    operational_limits={"default_timeout_ms": 1000},
                    audit={"owner": "agent-runtime"},
                ),
                ProviderCatalogueProvider(
                    catalogue_id="provider-catalogue.phase2a.seed",
                    provider_id="commercial.example",
                    display_name="Commercial provider placeholder",
                    provider_kind="commercial",
                    lifecycle_state="disabled",
                    credential_required=True,
                    secret_ref_names=["CHORUS_COMMERCIAL_LLM_API_KEY"],
                    missing_credentials_behaviour="disable_provider",
                    data_boundary={"mode": "external_api"},
                    operational_limits={"default_timeout_ms": 30000},
                    audit={"owner": "agent-runtime"},
                ),
            ],
            provider_models=[
                ProviderCatalogueModel(
                    catalogue_id="provider-catalogue.phase2a.seed",
                    provider_id="local",
                    model_id="lighthouse-happy-path-v1",
                    display_name="Lighthouse local structured model",
                    lifecycle_state="approved",
                    supported_task_kinds=["response_draft"],
                    supports_structured_output=True,
                    context_window_tokens=8192,
                    cost_policy={"currency": "USD"},
                )
            ],
            route_versions=[
                ModelRouteVersion(
                    route_id=uuid4(),
                    route_version=1,
                    lifecycle_state="approved",
                    tenant_id=tenant_id,
                    agent_role="drafter",
                    task_kind="response_draft",
                    tenant_tier="demo",
                    provider_catalogue_id="provider-catalogue.phase2a.seed",
                    provider_id="local",
                    model_id="lighthouse-happy-path-v1",
                    parameters={"temperature": 0.3},
                    budget_cap_usd=Decimal("0.0100"),
                    max_latency_ms=5000,
                    fallback_policy={"on_provider_error": "escalate"},
                    eval_required=True,
                    eval_fixture_refs=["chorus/eval/fixtures/lighthouse_happy_path.json"],
                    promotion={"change_ref": "2A-02"},
                    created_at=self.now,
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
            contract_refs=["contracts/llm_provider/lighthouse_agent_io.schema.json"],
            raw_record={"metadata": {"unit": True}},
            metadata={
                "execution.pipeline_version": "agent-runtime-pipeline-v1",
                "execution.step_path": [
                    "prepare_context",
                    "invoke_llm_provider_port",
                    "normalise_result",
                    "validate_contract",
                    "final_response",
                ],
                "execution.step_path_summary": (
                    "prepare_context -> invoke_llm_provider_port -> normalise_result -> "
                    "validate_contract -> final_response"
                ),
                "route_catalogue.route_id": "recorded-replay",
                "route_catalogue.provider_id": "local-replay",
                "route_catalogue.model_id": "recorded-replay-v1",
                "route_catalogue.adapter_version": "recorded-replay-v1",
                "model_route.route_id": str(uuid4()),
                "model_route.route_version": 1,
                "model_route.fallback_reason": None,
                "provider_fallback.applied": False,
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
            idempotency_key_ref="sha256:" + "a" * 64,
            calendar_refs={
                "calendar_ref": "cal_lighthouse_local_followup",
                "hold_ref": "hold_lighthouse_followup_001",
                "slot_ref": "slot_lighthouse_followup_001",
                "event_uid_ref": "evt_lighthouse_followup_001",
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
            grant_ref="tool_grant:12000000-0000-4000-8000-000000000011",
            policy_version_refs={"approval_policy_ref": "approval_policy.calendar_write.local.v1"},
            trace_join={},
            updated_at=self.now,
        )

    def _support_inspection(self) -> SupportInspectionReadModel:
        support_event = SupportWorkflowEventReadModel(
            tenant_id="tenant_demo",
            source_event_id=self.support_event_id,
            workflow_id=self.support_workflow_id,
            correlation_id=self.support_correlation_id,
            workflow_type="support_triage",
            request_ref="req_support_001",
            event_type="workflow.step.completed",
            sequence=4,
            step="support_propose",
            case_ref="case_existing_001",
            account_ref="acct_demo_001",
            product_ref="prod_core_platform",
            severity_category="sev_high",
            case_status_category="open",
            verdict_category="propose_case_update",
            gateway_verdict="propose",
            enforced_mode="propose",
            case_update_ref="caseupd_support_001",
            outcome=None,
            trace_join={},
            occurred_at=self.now,
        )
        support_decision = SupportAgentDecisionReadModel(
            tenant_id="tenant_demo",
            invocation_id=self.support_invocation_id,
            workflow_id=self.support_workflow_id,
            correlation_id=self.support_correlation_id,
            agent_id="support.resolution_planner",
            agent_role="support_resolution_planner",
            agent_version="v1",
            task_kind="support_resolution_plan",
            provider="local",
            model="lighthouse-happy-path-v1",
            route_id="route_support_resolution_plan_v1",
            route_version=1,
            outcome="succeeded",
            cost_amount=Decimal("0.0001"),
            duration_ms=10,
            contract_refs=["contracts/llm_provider/support_agent_io.schema.json"],
            trace_join={},
            occurred_at=self.now,
        )
        ticket_verdict = SupportTicketVerdictReadModel(
            tenant_id="tenant_demo",
            audit_event_id=self.support_audit_event_id,
            workflow_id=self.support_workflow_id,
            correlation_id=self.support_correlation_id,
            invocation_id=self.support_invocation_id,
            tool_call_id=self.support_tool_call_id,
            verdict_id=self.support_verdict_id,
            agent_id="support.resolution_planner",
            tool_name="ticket.propose_case_update",
            requested_mode="propose",
            enforced_mode="propose",
            verdict="propose",
            reason_category="proposal_mode",
            idempotency_key_ref=(
                f"{self.support_workflow_id}:ticket.propose_case_update:req_support_001"
            ),
            connector_invocation_id=self.support_connector_invocation_id,
            output_refs={
                "request_ref": "req_support_001",
                "case_ref": "case_existing_001",
                "case_update_ref": "caseupd_support_001",
                "case_status_mutated": False,
            },
            trace_join={},
            occurred_at=self.now,
        )
        case_update = SupportCaseUpdateProposalReadModel(
            tenant_id="tenant_demo",
            case_update_ref="caseupd_support_001",
            workflow_id=self.support_workflow_id,
            correlation_id=self.support_correlation_id,
            source_audit_event_id=self.support_audit_event_id,
            connector_invocation_id=self.support_connector_invocation_id,
            request_ref="req_support_001",
            case_ref="case_existing_001",
            account_ref="acct_demo_001",
            product_ref="prod_core_platform",
            severity_category="sev_high",
            target_status_category="pending_customer",
            update_reason_category="resolution_plan_ready",
            proposal_status="proposed",
            policy_ref="policy_support_triage_local_v1",
            case_status_mutated=False,
            trace_join={},
            updated_at=self.now,
        )
        status_boundary = SupportStatusWriteBoundaryReadModel(
            grant_ref="tool_grant:12000000-0000-4000-8000-000000000016",
            agent_id="support.resolution_planner",
            agent_version="v1",
            tool_name="ticket.update_status",
            mode="write",
            allowed=True,
            approval_required=True,
        )
        return SupportInspectionReadModel(
            tenant_id="tenant_demo",
            workflow_id=self.support_workflow_id,
            correlation_id=self.support_correlation_id,
            workflow_type="support_triage",
            request_refs=["req_support_001"],
            case_refs=["case_existing_001"],
            account_refs=["acct_demo_001"],
            product_refs=["prod_core_platform"],
            proposed_case_update_refs=["caseupd_support_001"],
            latest_event_sequence=4,
            workflow_events=[support_event],
            agent_decisions=[support_decision],
            ticket_verdicts=[ticket_verdict],
            proposed_case_updates=[case_update],
            status_write_boundary=[status_boundary],
            updated_at=self.now,
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
    app.dependency_overrides[progress_snapshot_store_dependency] = override_store
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
    calendar_status = client.get(f"/api/workflows/{store.workflow_id}/calendar/status").json()
    registry = client.get("/api/runtime/registry").json()
    grants = client.get("/api/runtime/grants").json()
    routing = client.get("/api/runtime/routing").json()

    assert decisions[0]["model_route"] == "local/lighthouse-happy-path-v1"
    assert decisions[0]["route_version"] == 1
    assert decisions[0]["provider"] == "local"
    assert decisions[0]["fallback_reason"] is None
    assert decisions[0]["fallback_applied"] is False
    assert verdicts[0]["redactions"] == ["body_text"]
    assert calendar_status[0]["projection_status"] == "calendar_hold_created"
    assert calendar_status[0]["calendar_refs"] == {
        "calendar_ref": "cal_lighthouse_local_followup",
        "hold_ref": "hold_lighthouse_followup_001",
        "slot_ref": "slot_lighthouse_followup_001",
        "event_uid_ref": "evt_lighthouse_followup_001",
    }
    assert calendar_status[0]["latest_audit_event_id"] == str(store.calendar_apply_audit_event_id)
    assert registry[0]["lifecycle_state"] == "approved"
    assert grants[0]["tool_name"] == "email.propose_response"
    assert routing[0]["budget_usd"] == 0.01


def test_support_inspection_endpoints_are_safe_read_only_views() -> None:
    client, store = _client()

    support_list = client.get(
        f"/api/support/inspections?correlation_id={store.support_correlation_id}"
    ).json()
    support_detail = client.get(
        f"/api/workflows/{store.support_workflow_id}/support/inspection"
    ).json()

    assert support_list == [support_detail]
    assert support_detail["workflow_type"] == "support_triage"
    assert support_detail["request_refs"] == ["req_support_001"]
    assert support_detail["case_refs"] == ["case_existing_001"]
    assert support_detail["proposed_case_update_refs"] == ["caseupd_support_001"]
    assert support_detail["workflow_events"][0]["step"] == "support_propose"
    assert support_detail["agent_decisions"][0]["agent_role"] == "support_resolution_planner"
    assert support_detail["agent_decisions"][0]["contract_refs"] == [
        "contracts/llm_provider/support_agent_io.schema.json"
    ]
    assert support_detail["ticket_verdicts"][0]["tool_name"] == "ticket.propose_case_update"
    assert support_detail["ticket_verdicts"][0]["reason_category"] == "proposal_mode"
    assert support_detail["ticket_verdicts"][0]["output_refs"] == {
        "request_ref": "req_support_001",
        "case_ref": "case_existing_001",
        "case_update_ref": "caseupd_support_001",
        "case_status_mutated": False,
    }
    assert support_detail["proposed_case_updates"][0]["case_status_mutated"] is False
    assert support_detail["status_write_boundary"][0]["tool_name"] == "ticket.update_status"
    assert support_detail["status_write_boundary"][0]["approval_required"] is True


def test_provider_endpoints_are_read_only_views() -> None:
    client, _ = _client()

    providers = client.get("/api/runtime/providers").json()
    provider_models = client.get("/api/runtime/provider-models").json()
    route_versions = client.get("/api/runtime/route-versions").json()

    assert {row["provider_id"] for row in providers} == {"commercial.example", "local"}
    assert providers[0]["catalogue_id"] == "provider-catalogue.phase2a.seed"
    assert provider_models[0]["model_id"] == "lighthouse-happy-path-v1"
    assert route_versions[0]["route_version"] == 1
    assert route_versions[0]["provider_catalogue_id"] == "provider-catalogue.phase2a.seed"


def test_progress_sse_is_projection_backed() -> None:
    client, _ = _client()

    response = client.get("/api/progress?once=true")

    assert response.status_code == 200
    assert "event: progress" in response.text
    assert "lead.received" in response.text

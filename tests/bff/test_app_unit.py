from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from chorus.bff.app import (
    BffSettings,
    PortReaders,
    create_app,
    progress_projection_dependency,
    readers_dependency,
)
from chorus.persistence.audit_port import (
    DecisionTrailEntryReadModel,
    ToolActionAuditReadModel,
)
from chorus.persistence.projection import (
    ApprovalPackageReadModel,
    CalendarProjectionReadModel,
    WorkflowHistoryEventReadModel,
    WorkflowRunReadModel,
)
from chorus.persistence.provider_governance import (
    ModelRouteVersion,
    ProviderCatalogueEntry,
    ProviderCatalogueModel,
    ProviderCatalogueProvider,
    ProviderGovernanceSnapshot,
)
from chorus.persistence.replay_runs import ReplayRunRecordReadModel
from chorus.persistence.runtime_policy import (
    AgentRegistryEntry,
    ModelRoutingPolicy,
    RuntimePolicySnapshot,
    ToolGrant,
)


class FakeProjectionStore:
    """Stand-in for the projection port's read + write surface."""

    def __init__(self, fixture: BffFixture) -> None:
        self._fixture = fixture

    def list_workflows(self, tenant_id: str, *, limit: int = 100) -> list[WorkflowRunReadModel]:
        del tenant_id, limit
        return [
            self._fixture.workflow(),
            self._fixture.uc2_workflow(),
            self._fixture.uc3_workflow(),
        ]

    def get_workflow(self, tenant_id: str, workflow_id: str) -> WorkflowRunReadModel | None:
        del tenant_id
        if workflow_id == self._fixture.workflow_id:
            return self._fixture.workflow()
        if workflow_id == self._fixture.uc2_workflow_id:
            return self._fixture.uc2_workflow()
        if workflow_id == self._fixture.uc3_workflow_id:
            return self._fixture.uc3_workflow()
        return None

    def list_workflow_history(
        self,
        tenant_id: str,
        workflow_id: str,
        *,
        after_sequence: int | None = None,
        limit: int = 500,
    ) -> list[WorkflowHistoryEventReadModel]:
        del tenant_id, workflow_id, after_sequence, limit
        return [self._fixture.event()]

    def list_recent_workflow_history(
        self,
        tenant_id: str,
        *,
        limit: int = 100,
    ) -> list[WorkflowHistoryEventReadModel]:
        del tenant_id, limit
        return [self._fixture.event()]

    def list_calendar_projections(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        limit: int = 100,
    ) -> list[CalendarProjectionReadModel]:
        del tenant_id, workflow_id, limit
        return [self._fixture.calendar_projection()]

    def list_approval_packages(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        limit: int = 100,
    ) -> list[ApprovalPackageReadModel]:
        del tenant_id, limit
        rows = [self._fixture.approval_package(), self._fixture.uc3_approval_package()]
        if workflow_id is not None:
            return [row for row in rows if row.workflow_id == workflow_id]
        return rows


class FakeAuditPortStore:
    """Stand-in for the audit ports' read surface."""

    def __init__(self, fixture: BffFixture) -> None:
        self._fixture = fixture

    def list_decision_trail(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        limit: int = 500,
    ) -> list[DecisionTrailEntryReadModel]:
        del tenant_id, workflow_id, limit
        return [self._fixture.decision()]

    def list_tool_action_audit(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        limit: int = 500,
    ) -> list[ToolActionAuditReadModel]:
        del tenant_id, workflow_id, limit
        return [self._fixture.audit()]


class FakePolicySnapshotStore:
    """Stand-in for the runtime-policy snapshot composition."""

    def __init__(self, fixture: BffFixture) -> None:
        self._fixture = fixture

    def snapshot(self, tenant_id: str) -> RuntimePolicySnapshot:
        del tenant_id
        return RuntimePolicySnapshot(
            tenant_id="tenant_demo",
            agents=[self._fixture.agent()],
            model_routes=[self._fixture.routing_policy()],
            tool_grants=[self._fixture.grant()],
            policy_snapshots=[],
        )


class FakeProviderGovernanceStore:
    """Stand-in for the provider-governance snapshot composition."""

    def __init__(self, fixture: BffFixture) -> None:
        self._fixture = fixture

    def snapshot(self, tenant_id: str) -> ProviderGovernanceSnapshot:
        del tenant_id
        return ProviderGovernanceSnapshot(
            tenant_id="tenant_demo",
            catalogues=[self._fixture.catalogue_entry()],
            providers=[
                self._fixture.provider(),
                self._fixture.deepseek_provider(),
                self._fixture.openai_provider(),
            ],
            provider_models=[
                self._fixture.provider_model(),
                self._fixture.deepseek_model(),
                self._fixture.openai_model(),
            ],
            route_versions=[self._fixture.route_version()],
        )


class FakeReplayRunStore:
    """Stand-in for the replay-eval evidence read surface."""

    def __init__(self, fixture: BffFixture) -> None:
        self._fixture = fixture

    def list_replay_runs(
        self,
        tenant_id: str,
        *,
        workflow_id: str | None = None,
        limit: int = 500,
    ) -> list[ReplayRunRecordReadModel]:
        del tenant_id, workflow_id, limit
        return [self._fixture.replay_run()]


class BffFixture:
    """Shared state and constructors for BFF unit-test stand-ins."""

    def __init__(self) -> None:
        self.workflow_id = "uc1-enq-bff-unit"
        self.uc2_workflow_id = "uc2-legal-bff-unit"
        self.uc3_workflow_id = "uc3-ifa-bff-unit"
        self.correlation_id = "cor_bff_unit"
        self.subject_id = uuid4()
        self.event_id = uuid4()
        self.invocation_id = uuid4()
        self.audit_event_id = uuid4()
        self.approval_id = uuid4()
        self.uc3_approval_id = uuid4()
        self.uc3_audit_event_id = uuid4()
        self.calendar_apply_audit_event_id = uuid4()
        self.transcript_id = uuid4()
        self.replay_run_id = uuid4()
        self.now = datetime(2026, 4, 29, 12, 0, tzinfo=UTC)

    def workflow(self) -> WorkflowRunReadModel:
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
            metadata={"subject_from": "enquiry@example.com", "sender": "enquiry@example.com"},
        )

    def uc2_workflow(self) -> WorkflowRunReadModel:
        return WorkflowRunReadModel(
            tenant_id="tenant_demo",
            workflow_id=self.uc2_workflow_id,
            workflow_type="uc2_legal_services_intake_conflict_check",
            correlation_id=self.correlation_id,
            subject_id=self.subject_id,
            subject_ref="legal_intake_bff_unit_001",
            status="completed",
            current_step="close",
            subject_summary="Commercial contract review enquiry",
            last_event_id=self.event_id,
            last_event_sequence=12,
            started_at=self.now,
            completed_at=self.now,
            updated_at=self.now,
            metadata={"subject_from": "legal-intake@example.test", "channel": "email"},
        )

    def uc3_workflow(self) -> WorkflowRunReadModel:
        return WorkflowRunReadModel(
            tenant_id="tenant_demo",
            workflow_id=self.uc3_workflow_id,
            workflow_type="uc3_ifa_suitability_intake",
            correlation_id=self.correlation_id,
            subject_id=self.subject_id,
            subject_ref="advice_enquiry_bff_unit_001",
            status="completed",
            current_step="close",
            subject_summary="ISA investment advice suitability enquiry",
            last_event_id=self.event_id,
            last_event_sequence=15,
            started_at=self.now,
            completed_at=self.now,
            updated_at=self.now,
            metadata={"subject_from": "web-advice@example.test", "channel": "web-form"},
        )

    def event(self) -> WorkflowHistoryEventReadModel:
        return WorkflowHistoryEventReadModel(
            tenant_id="tenant_demo",
            history_event_id=uuid4(),
            workflow_id=self.workflow_id,
            correlation_id=self.correlation_id,
            source_event_id=self.event_id,
            event_type="enquiry.received",
            sequence=1,
            step="intake",
            payload={"subject_summary": "Motor cover enquiry"},
            occurred_at=self.now,
            created_at=self.now,
        )

    def decision(self) -> DecisionTrailEntryReadModel:
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

    def audit(self) -> ToolActionAuditReadModel:
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

    def calendar_projection(self) -> CalendarProjectionReadModel:
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

    def approval_package(self) -> ApprovalPackageReadModel:
        return ApprovalPackageReadModel(
            tenant_id="tenant_demo",
            approval_id=self.approval_id,
            approval_package_version=1,
            workflow_id=self.uc2_workflow_id,
            workflow_type="uc2_legal_services_intake_conflict_check",
            correlation_id=self.correlation_id,
            approval_state="requested",
            decision=None,
            reason_category="tool_write_risk",
            agent_id="uc2.engagement_decider",
            agent_version="v1",
            requested_action="engagement_letter.send.write",
            tool_name="engagement_letter.send",
            requested_mode="write",
            enforced_mode="write",
            idempotency_key_ref="sha256:" + "2" * 64,
            redaction_summary={
                "redaction_policy_ref": "tool_grant:uc2:redaction_policy",
                "redacted_field_count": 0,
                "redacted_field_refs": [],
            },
            subject_refs={
                "subject_id": str(self.subject_id),
                "subject_ref": "legal_intake_bff_unit_001",
            },
            action_refs={
                "legal_intake_ref": "legal_intake_bff_unit_001",
                "engagement_letter_ref": "engagement_letter_bff_unit_001",
                "conduct_hook_refs": [
                    "conduct_sra_conflict_6_1_6_2",
                    "conduct_mlr_cdd_reg_27_28",
                ],
            },
            requested_at=self.now,
            decision_due_at=self.now,
            expires_at=self.now,
            decision_at=None,
            source_audit_event_id=self.audit_event_id,
            latest_audit_event_id=self.audit_event_id,
            latest_verdict="approval_required",
            latest_reason="Grant exists but requires approval before connector execution.",
            connector_invocation_id=None,
            grant_ref="tool_grant:" + str(uuid4()),
            policy_version_refs={
                "approval_policy_ref": "approval_policy.engagement_letter_send_write.local.v1"
            },
            trace_join={},
            updated_at=self.now,
        )

    def uc3_approval_package(self) -> ApprovalPackageReadModel:
        return ApprovalPackageReadModel(
            tenant_id="tenant_demo",
            approval_id=self.uc3_approval_id,
            approval_package_version=1,
            workflow_id=self.uc3_workflow_id,
            workflow_type="uc3_ifa_suitability_intake",
            correlation_id=self.correlation_id,
            approval_state="requested",
            decision=None,
            reason_category="tool_write_risk",
            agent_id="uc3.suitability_decider",
            agent_version="v1",
            requested_action="suitability_report.issue.write",
            tool_name="suitability_report.issue",
            requested_mode="write",
            enforced_mode="write",
            idempotency_key_ref="sha256:" + "3" * 64,
            redaction_summary={
                "redaction_policy_ref": "tool_grant:uc3:redaction_policy",
                "redacted_field_count": 0,
                "redacted_field_refs": [],
            },
            subject_refs={
                "subject_id": str(self.subject_id),
                "subject_ref": "advice_enquiry_bff_unit_001",
            },
            action_refs={
                "advice_enquiry_ref": "advice_enquiry_bff_unit_001",
                "suitability_report_ref": "suitability_report_bff_unit_001",
                "suitability_conclusion_ref": "suitability_conclusion_bff_unit_001",
                "consumer_understanding_check_ref": "consumer_understanding_bff_unit_001",
                "conduct_hook_refs": [
                    "conduct_fca_cobs_9_suitability",
                    "conduct_fca_prod_3_target_market",
                    "conduct_fca_prin_2a_consumer_duty",
                ],
            },
            requested_at=self.now,
            decision_due_at=self.now,
            expires_at=self.now,
            decision_at=None,
            source_audit_event_id=self.uc3_audit_event_id,
            latest_audit_event_id=self.uc3_audit_event_id,
            latest_verdict="approval_required",
            latest_reason="Grant exists but requires adviser approval before connector execution.",
            connector_invocation_id=None,
            grant_ref="tool_grant:" + str(uuid4()),
            policy_version_refs={
                "approval_policy_ref": "approval_policy.suitability_report_issue_write.local.v1"
            },
            trace_join={},
            updated_at=self.now,
        )

    def agent(self) -> AgentRegistryEntry:
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

    def routing_policy(self) -> ModelRoutingPolicy:
        return ModelRoutingPolicy(
            policy_id=uuid4(),
            tenant_id="tenant_demo",
            agent_role="request_drafter",
            task_kind="missing_data_request_draft",
            tenant_tier="demo",
            runtime_route_id="recorded-replay",
            provider="local",
            model="uc1-happy-path-v1",
            parameters={"temperature": 0.3},
            budget_cap_usd=Decimal("0.01"),
            fallback_policy={},
            lifecycle_state="approved",
        )

    def grant(self) -> ToolGrant:
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

    def catalogue_entry(self) -> ProviderCatalogueEntry:
        return ProviderCatalogueEntry(
            catalogue_id="provider-catalogue.local.seed",
            schema_version="1.0.0",
            effective_from=self.now,
            created_at=self.now,
        )

    def provider(self) -> ProviderCatalogueProvider:
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

    def deepseek_provider(self) -> ProviderCatalogueProvider:
        return ProviderCatalogueProvider(
            catalogue_id="provider-catalogue.local.seed",
            provider_id="deepseek",
            display_name="DeepSeek API",
            provider_kind="commercial",
            lifecycle_state="disabled",
            credential_required=True,
            secret_ref_names=["DEEPSEEK_API_KEY"],
            missing_credentials_behaviour="disable_provider",
            data_boundary={"mode": "external_api"},
            operational_limits={},
            audit={},
        )

    def openai_provider(self) -> ProviderCatalogueProvider:
        return ProviderCatalogueProvider(
            catalogue_id="provider-catalogue.local.seed",
            provider_id="openai",
            display_name="OpenAI API",
            provider_kind="commercial",
            lifecycle_state="disabled",
            credential_required=True,
            secret_ref_names=["OPENAI_API_KEY"],
            missing_credentials_behaviour="disable_provider",
            data_boundary={"mode": "external_api"},
            operational_limits={},
            audit={},
        )

    def provider_model(self) -> ProviderCatalogueModel:
        return ProviderCatalogueModel(
            catalogue_id="provider-catalogue.local.seed",
            provider_id="local",
            model_id="uc1-happy-path-v1",
            display_name="UC1 local structured model",
            lifecycle_state="approved",
            supported_task_kinds=[
                "enquiry_classification",
                "context_gathering",
                "enquiry_qualification",
                "missing_data_request_draft",
                "missing_data_request_validation",
            ],
            supports_structured_output=True,
            context_window_tokens=8192,
            cost_policy={"currency": "USD"},
        )

    def deepseek_model(self) -> ProviderCatalogueModel:
        return ProviderCatalogueModel(
            catalogue_id="provider-catalogue.local.seed",
            provider_id="deepseek",
            model_id="deepseek-v4-flash",
            display_name="DeepSeek V4 Flash",
            lifecycle_state="disabled",
            supported_task_kinds=[
                "enquiry_classification",
                "context_gathering",
                "enquiry_qualification",
                "missing_data_request_draft",
                "missing_data_request_validation",
            ],
            supports_structured_output=True,
            context_window_tokens=1000000,
            cost_policy={"currency": "USD"},
        )

    def openai_model(self) -> ProviderCatalogueModel:
        return ProviderCatalogueModel(
            catalogue_id="provider-catalogue.local.seed",
            provider_id="openai",
            model_id="gpt-5.4-mini-2026-03-17",
            display_name="GPT-5.4 mini pinned snapshot",
            lifecycle_state="disabled",
            supported_task_kinds=[
                "enquiry_classification",
                "context_gathering",
                "enquiry_qualification",
                "missing_data_request_draft",
                "missing_data_request_validation",
            ],
            supports_structured_output=True,
            context_window_tokens=400000,
            cost_policy={"currency": "USD"},
        )

    def route_version(self) -> ModelRouteVersion:
        return ModelRouteVersion(
            route_id=uuid4(),
            route_version=1,
            lifecycle_state="approved",
            tenant_id="tenant_demo",
            agent_role="request_drafter",
            task_kind="missing_data_request_draft",
            tenant_tier="demo",
            runtime_route_id="recorded-replay",
            provider_catalogue_id="provider-catalogue.local.seed",
            provider_id="local",
            model_id="uc1-happy-path-v1",
            parameters={"temperature": 0.3},
            budget_cap_usd=Decimal("0.01"),
            max_latency_ms=5000,
            fallback_policy={"mode": "escalate"},
            eval_required=True,
            eval_fixture_refs=[
                "chorus/eval/fixtures/uc1_happy_path.json",
                "chorus/eval/fixtures/uc1_validator_redraft.json",
                "chorus/eval/fixtures/uc1_accepted_routing.json",
                "chorus/eval/fixtures/uc1_referred_routing.json",
                "chorus/eval/fixtures/uc1_declined_routing.json",
            ],
            promotion={},
            created_at=self.now,
        )

    def replay_run(self) -> ReplayRunRecordReadModel:
        return ReplayRunRecordReadModel(
            tenant_id="tenant_demo",
            replay_run_id=self.replay_run_id,
            correlation_id=self.correlation_id,
            workflow_id=self.workflow_id,
            original_invocation_id=self.invocation_id,
            original_transcript_id=self.transcript_id,
            original_runtime_route_id="recorded-replay",
            original_provider_id="local",
            original_model_id="uc1-happy-path-v1",
            original_adapter_version="recorded-replay-v1",
            original_parameters={},
            alternate_runtime_route_id="recorded-replay",
            alternate_provider_id="local",
            alternate_model_id="uc1-happy-path-v1",
            alternate_adapter_version="recorded-replay-v1",
            alternate_parameters={},
            agent_role="request_drafter",
            task_kind="missing_data_request_draft",
            policy_snapshot_ref="policy_snapshot:uc1:default:v1",
            prompt_reference="prompts/uc1/request-drafter/v1.md",
            prompt_hash="sha256:" + "0" * 64,
            response_schema_name="uc1_missing_data_request_draft_response",
            response_schema_contract_ref="contracts/llm_provider/uc1_agent_io.schema.json",
            response_schema_hash="sha256:" + "1" * 64,
            route_version_ref="model_route_versions:11000000-0000-4000-8000-000000000004:1",
            provider_catalogue_id="provider-catalogue.local.seed",
            eval_fixture_ref="chorus/eval/fixtures/uc1_happy_path.json",
            transcript_source_ref="fixture:uc1_happy_path",
            comparator_name="tiered_replay_comparator",
            comparator_version="v0.4-metrics-only",
            comparator_status="pass",
            comparator_result={
                "tier": "metrics_only",
                "reason_code": "metrics_only_delta",
                "field_names": ["metrics.latency_ms"],
                "changed_field_names": ["metrics.latency_ms"],
                "compared_field_names": [
                    "metrics.cost_amount_usd",
                    "metrics.latency_ms",
                ],
                "reason_codes": ["latency_delta"],
            },
            safe_error_reason=None,
            safe_skipped_reason=None,
            original_cost_amount=Decimal("0.001"),
            original_cost_currency="USD",
            original_latency_ms=120,
            original_token_usage={"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            alternate_cost_amount=Decimal("0.000"),
            alternate_cost_currency="USD",
            alternate_latency_ms=40,
            alternate_token_usage={"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            metric_deltas={
                "cost_amount_usd": -0.001,
                "latency_ms": -80,
                "token_usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            },
            started_at=self.now,
            completed_at=self.now,
            raw_record={},
            created_at=self.now,
        )


def _client() -> tuple[TestClient, BffFixture]:
    fixture = BffFixture()
    settings = BffSettings(database_url="postgresql://invalid", tenant_id="tenant_demo")
    app = create_app(settings)

    readers = PortReaders(
        projection=FakeProjectionStore(fixture),  # type: ignore[arg-type]
        audit=FakeAuditPortStore(fixture),  # type: ignore[arg-type]
        policy=FakePolicySnapshotStore(fixture),  # type: ignore[arg-type]
        governance=FakeProviderGovernanceStore(fixture),  # type: ignore[arg-type]
        replay=FakeReplayRunStore(fixture),  # type: ignore[arg-type]
    )

    def fake_readers_dependency() -> Iterator[PortReaders]:
        yield readers

    def fake_progress_dependency(once: bool = False) -> Iterator[Any]:
        del once
        yield readers.projection

    app.dependency_overrides[readers_dependency] = fake_readers_dependency
    app.dependency_overrides[progress_projection_dependency] = fake_progress_dependency
    return TestClient(app), fixture


def test_projection_endpoints_use_bff_response_contracts() -> None:
    client, fixture = _client()

    workflows = client.get("/api/workflows").json()
    detail = client.get(f"/api/workflows/{fixture.workflow_id}").json()
    events = client.get(f"/api/workflows/{fixture.workflow_id}/events").json()

    assert workflows[0]["workflow_id"] == fixture.workflow_id
    assert workflows[0]["workflow_type"] == "uc1_enquiry_qualification"
    assert detail["subject_from"] == "enquiry@example.com"
    assert detail["subject_ref"] == "enq_motor_private_001"
    assert events[0]["event_type"] == "enquiry.received"


def test_audit_and_runtime_policy_endpoints_are_read_only_views() -> None:
    client, fixture = _client()

    decisions = client.get(f"/api/workflows/{fixture.workflow_id}/decision-trail").json()
    verdicts = client.get(f"/api/workflows/{fixture.workflow_id}/tool-verdicts").json()
    calendar_status = client.get(f"/api/workflows/{fixture.workflow_id}/calendar/status").json()
    approval_packages = client.get(
        f"/api/workflows/{fixture.uc2_workflow_id}/approval-packages"
    ).json()
    uc3_approval_packages = client.get(
        f"/api/workflows/{fixture.uc3_workflow_id}/approval-packages"
    ).json()
    all_approval_packages = client.get("/api/approval-packages").json()
    registry = client.get("/api/runtime/registry").json()
    grants = client.get("/api/runtime/grants").json()
    routing = client.get("/api/runtime/routing").json()

    assert decisions[0]["model_route"] == "local/uc1-happy-path-v1"
    assert decisions[0]["provider"] == "local"
    assert verdicts[0]["redactions"] == ["body_text"]
    assert calendar_status[0]["projection_status"] == "calendar_hold_created"
    assert calendar_status[0]["calendar_refs"]["calendar_ref"] == "cal_uc1_local_followup"
    assert approval_packages[0]["workflow_type"] == "uc2_legal_services_intake_conflict_check"
    assert approval_packages[0]["requested_action"] == "engagement_letter.send.write"
    assert approval_packages[0]["latest_verdict"] == "approval_required"
    assert approval_packages[0]["action_refs"]["conduct_hook_refs"] == [
        "conduct_sra_conflict_6_1_6_2",
        "conduct_mlr_cdd_reg_27_28",
    ]
    assert uc3_approval_packages[0]["workflow_type"] == "uc3_ifa_suitability_intake"
    assert uc3_approval_packages[0]["requested_action"] == "suitability_report.issue.write"
    assert uc3_approval_packages[0]["latest_verdict"] == "approval_required"
    assert uc3_approval_packages[0]["subject_refs"]["subject_ref"] == (
        "advice_enquiry_bff_unit_001"
    )
    assert uc3_approval_packages[0]["action_refs"]["conduct_hook_refs"] == [
        "conduct_fca_cobs_9_suitability",
        "conduct_fca_prod_3_target_market",
        "conduct_fca_prin_2a_consumer_duty",
    ]
    assert "raw_suitability_report_text" not in uc3_approval_packages[0]["action_refs"]
    assert "client_name" not in uc3_approval_packages[0]["action_refs"]
    assert {row["id"] for row in all_approval_packages} == {
        str(fixture.approval_id),
        str(fixture.uc3_approval_id),
    }
    assert registry[0]["lifecycle_state"] == "approved"
    assert grants[0]["tool_name"] == "outbound_comms.message"
    assert routing[0]["budget_usd"] == 0.01
    assert routing[0]["runtime_route_id"] == "recorded-replay"


def test_provider_endpoints_are_read_only_views() -> None:
    client, _ = _client()

    providers = client.get("/api/runtime/providers").json()
    provider_models = client.get("/api/runtime/provider-models").json()
    route_versions = client.get("/api/runtime/route-versions").json()

    assert {row["provider_id"] for row in providers} == {"deepseek", "local", "openai"}
    assert provider_models[0]["model_id"] == "uc1-happy-path-v1"
    assert route_versions[0]["route_version"] == 1
    assert route_versions[0]["runtime_route_id"] == "recorded-replay"
    assert route_versions[0]["provider_catalogue_id"] == "provider-catalogue.local.seed"


def test_replay_run_endpoints_are_read_only_views() -> None:
    client, fixture = _client()

    replay_runs = client.get("/api/eval/replay-runs").json()
    workflow_replay_runs = client.get(f"/api/workflows/{fixture.workflow_id}/replay-runs").json()

    assert replay_runs[0]["original_invocation_id"] == str(fixture.invocation_id)
    assert replay_runs[0]["original_transcript_id"] == str(fixture.transcript_id)
    assert replay_runs[0]["alternate_route"] == "recorded-replay (local/uc1-happy-path-v1)"
    assert replay_runs[0]["comparator_status"] == "pass"
    assert replay_runs[0]["cost_delta_usd"] == -0.001
    assert replay_runs[0]["latency_delta_ms"] == -80
    assert workflow_replay_runs[0]["id"] == str(fixture.replay_run_id)


def test_progress_sse_is_projection_backed() -> None:
    client, _ = _client()

    with client.stream("GET", "/api/progress?once=true") as response:
        assert response.status_code == 200
        body = "".join(chunk for chunk in response.iter_text())
        assert "enquiry.received" in body

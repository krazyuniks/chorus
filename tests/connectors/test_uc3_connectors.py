from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from psycopg import Connection

from chorus.connectors import ConnectorContext, default_registry
from chorus.connectors.uc3 import (
    SandboxAttitudeToRiskProfilerAdapter,
    SandboxCapacityForLossToolAdapter,
    SandboxPlatformResearchAdapter,
    SandboxSuitabilityReportStoreAdapter,
)
from chorus.contracts.generated.connector.uc3.attitude_to_risk_profile_args import (
    AttitudeToRiskProfileArgs,
)
from chorus.contracts.generated.connector.uc3.capacity_for_loss_assessment_args import (
    CapacityForLossAssessmentArgs,
)
from chorus.contracts.generated.connector.uc3.platform_research_args import PlatformResearchArgs
from chorus.contracts.generated.connector.uc3.suitability_report_decline_args import (
    SuitabilityReportDeclineArgs,
)
from chorus.contracts.generated.connector.uc3.suitability_report_draft_args import (
    SuitabilityReportDraftArgs,
)
from chorus.contracts.generated.connector.uc3.suitability_report_issue_args import (
    SuitabilityReportIssueArgs,
)
from chorus.contracts.generated.connector.uc3.suitability_report_manual_review_args import (
    SuitabilityReportManualReviewArgs,
)

ROOT = Path(__file__).resolve().parents[2]
UC3_SAMPLE_DIR = ROOT / "contracts" / "connector" / "uc3" / "samples"
FORBIDDEN_OUTPUT_KEYS = {
    "raw_client_financial_details",
    "vulnerability_narrative",
    "report_prose",
    "platform_credentials",
    "production_adviser_data",
    "production_customer_data",
}


def _sample(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((UC3_SAMPLE_DIR / name).read_text()))


def _context() -> ConnectorContext:
    return ConnectorContext(
        tenant_id="tenant_demo",
        correlation_id="cor_uc3_connector_sandbox",
        workflow_id="uc3-ifa-suitability-connector-sandbox",
    )


def _assert_safe_output(output: dict[str, Any]) -> None:
    assert FORBIDDEN_OUTPUT_KEYS.isdisjoint(output)


def test_default_registry_registers_uc3_tool_specs() -> None:
    registry = default_registry(cast(Connection[Any], object()))

    assert {
        "attitude_to_risk.profile",
        "capacity_for_loss.assess",
        "platform_research.run",
        "suitability_report.draft",
        "suitability_report.issue",
        "suitability_report.record_decline",
        "suitability_report.route_manual_review",
    }.issubset(set(registry.tool_names()))
    assert {
        "sandbox_attitude_to_risk_profiler",
        "sandbox_capacity_for_loss_tool",
        "sandbox_platform_research",
        "sandbox_suitability_report_store",
    }.issubset(set(registry.adapter_ids()))

    _adapter, risk_spec = registry.resolve("attitude_to_risk.profile")
    _adapter, capacity_spec = registry.resolve("capacity_for_loss.assess")
    _adapter, platform_spec = registry.resolve("platform_research.run")
    _adapter, draft_spec = registry.resolve("suitability_report.draft")
    _adapter, issue_spec = registry.resolve("suitability_report.issue")

    assert risk_spec.argument_contract is AttitudeToRiskProfileArgs
    assert capacity_spec.argument_contract is CapacityForLossAssessmentArgs
    assert platform_spec.argument_contract is PlatformResearchArgs
    assert draft_spec.argument_contract is SuitabilityReportDraftArgs
    assert issue_spec.argument_contract is SuitabilityReportIssueArgs


def test_attitude_to_risk_profiler_returns_deterministic_ref_only_profile() -> None:
    adapter = SandboxAttitudeToRiskProfilerAdapter()
    arguments = AttitudeToRiskProfileArgs.model_validate(
        _sample("attitude_to_risk_profile_args.sample.json")
    )

    first = adapter.invoke(
        tool_name="attitude_to_risk.profile",
        mode="read",
        context=_context(),
        arguments=arguments,
    )
    second = adapter.invoke(
        tool_name="attitude_to_risk.profile",
        mode="read",
        context=_context(),
        arguments=arguments,
    )

    assert first.output == second.output
    assert first.output["connector"] == "sandbox_attitude_to_risk_profiler.local"
    assert first.output["risk_profile_ref"].startswith("risk_profile_")
    assert first.output["profiler_band"] == "medium"
    assert first.output["risk_profile_status"] == "aligned"
    assert first.output["questionnaire_trace_ref"].startswith("risk_questionnaire_trace_")
    assert first.output["objective_refs"] == [
        "objective_capital_growth_001",
        "objective_tax_wrapper_001",
    ]
    assert first.output["evidence_status"] == "refs_only_synthetic"
    _assert_safe_output(first.output)


def test_attitude_to_risk_profiler_returns_bounded_mismatch_status() -> None:
    sample = _sample("attitude_to_risk_profile_args.sample.json")
    sample["risk_context_categories"] = ["objective_risk_mismatch"]
    arguments = AttitudeToRiskProfileArgs.model_validate(sample)

    result = SandboxAttitudeToRiskProfilerAdapter().invoke(
        tool_name="attitude_to_risk.profile",
        mode="read",
        context=_context(),
        arguments=arguments,
    )

    assert result.output["risk_profile_status"] == "mismatch_requires_approval"
    assert result.output["profiler_band"] == "medium"
    assert result.output["inconsistency_flags"] == ["objective_risk_mismatch"]


def test_capacity_for_loss_tool_returns_synthetic_stress_refs() -> None:
    arguments = CapacityForLossAssessmentArgs.model_validate(
        _sample("capacity_for_loss_assessment_args.sample.json")
    )

    result = SandboxCapacityForLossToolAdapter().invoke(
        tool_name="capacity_for_loss.assess",
        mode="read",
        context=_context(),
        arguments=arguments,
    )

    assert result.output["connector"] == "sandbox_capacity_for_loss_tool.local"
    assert result.output["capacity_for_loss_ref"].startswith("capacity_for_loss_")
    assert result.output["capacity_for_loss_status"] == "adequate"
    assert result.output["stress_test_ref"].startswith("capacity_stress_")
    assert result.output["stress_outcome"] == "pass"
    assert result.output["dependency_status"] == "dependencies_identified"
    assert result.output["affordability_evidence_ref"].startswith("affordability_evidence_")
    assert result.output["evidence_status"] == "refs_only_synthetic"
    _assert_safe_output(result.output)


def test_platform_research_returns_synthetic_independent_range_evidence() -> None:
    arguments = PlatformResearchArgs.model_validate(_sample("platform_research_args.sample.json"))

    result = SandboxPlatformResearchAdapter().invoke(
        tool_name="platform_research.run",
        mode="read",
        context=_context(),
        arguments=arguments,
    )

    assert result.output["connector"] == "sandbox_platform_research.local"
    assert result.output["platform_research_ref"].startswith("platform_research_")
    assert result.output["research_status"] == "complete"
    assert result.output["product_universe_coverage"] == "sufficient_independent_range"
    assert result.output["target_market_status"] == "in_target_market"
    assert result.output["product_candidate_refs"] == [
        "product_candidate_model_portfolio_001",
        "product_candidate_global_tracker_001",
    ]
    assert result.output["cost_charge_summary_ref"].startswith("cost_charge_summary_")
    assert result.output["due_diligence_ref"].startswith("due_diligence_")
    _assert_safe_output(result.output)


def test_suitability_report_store_drafts_and_issues_ref_only_metadata() -> None:
    adapter = SandboxSuitabilityReportStoreAdapter()
    draft_args = SuitabilityReportDraftArgs.model_validate(
        _sample("suitability_report_draft_args.sample.json")
    )
    issue_args = SuitabilityReportIssueArgs.model_validate(
        _sample("suitability_report_issue_args.sample.json")
    )

    draft = adapter.invoke(
        tool_name="suitability_report.draft",
        mode="write",
        context=_context(),
        arguments=draft_args,
    )
    issue = adapter.invoke(
        tool_name="suitability_report.issue",
        mode="write",
        context=_context(),
        arguments=issue_args,
    )

    assert draft.output["connector"] == "sandbox_suitability_report_store.local"
    assert draft.output["draft_ref"].startswith("suitability_report_draft_")
    assert draft.output["draft_status"] == "draft_recorded"
    assert draft.output["draft_storage"] == "local_ref_only"
    assert draft.output["draft_basis_categories"] == [
        "standard_independent_advice",
        "product_universe_review",
    ]
    assert issue.output["issue_record_ref"].startswith("suitability_report_issue_")
    assert issue.output["issue_status"] == "issue_recorded"
    assert issue.output["issue_channel_category"] == "portal"
    assert issue.output["delivery_surface"] == "local_record_only"
    _assert_safe_output(draft.output)
    _assert_safe_output(issue.output)


def test_suitability_report_store_records_decline_and_manual_review_refs() -> None:
    adapter = SandboxSuitabilityReportStoreAdapter()
    decline_args = SuitabilityReportDeclineArgs.model_validate(
        _sample("suitability_report_decline_args.sample.json")
    )
    review_args = SuitabilityReportManualReviewArgs.model_validate(
        _sample("suitability_report_manual_review_args.sample.json")
    )

    decline = adapter.invoke(
        tool_name="suitability_report.record_decline",
        mode="write",
        context=_context(),
        arguments=decline_args,
    )
    review = adapter.invoke(
        tool_name="suitability_report.route_manual_review",
        mode="write",
        context=_context(),
        arguments=review_args,
    )

    assert decline.output["decline_ref"] == "decline_unsuitable_demo_001"
    assert decline.output["decline_status"] == "recorded"
    assert decline.output["decline_reason_category"] == "capacity_for_loss_blocked"
    assert review.output["handoff_ref"] == "manual_review_vulnerability_demo_001"
    assert review.output["handoff_status"] == "routed"
    assert review.output["review_destination_category"] == "vulnerability_support_reviewer"
    _assert_safe_output(decline.output)
    _assert_safe_output(review.output)

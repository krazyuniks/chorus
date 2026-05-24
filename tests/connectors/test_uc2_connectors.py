from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from psycopg import Connection

from chorus.connectors import ConnectorContext, default_registry
from chorus.connectors.uc2 import (
    SandboxAmlRecordStoreAdapter,
    SandboxConflictCheckAdapter,
    SandboxEngagementLetterStoreAdapter,
    SandboxKycBeneficialOwnershipAdapter,
)
from chorus.contracts.generated.connector.uc2.aml_risk_assessment_record_args import (
    AmlRiskAssessmentRecordArgs,
)
from chorus.contracts.generated.connector.uc2.conflict_check_search_args import (
    ConflictCheckSearchArgs,
)
from chorus.contracts.generated.connector.uc2.engagement_letter_decline_args import (
    EngagementLetterDeclineArgs,
)
from chorus.contracts.generated.connector.uc2.engagement_letter_draft_args import (
    EngagementLetterDraftArgs,
)
from chorus.contracts.generated.connector.uc2.engagement_letter_manual_review_args import (
    EngagementLetterManualReviewArgs,
)
from chorus.contracts.generated.connector.uc2.engagement_letter_send_args import (
    EngagementLetterSendArgs,
)
from chorus.contracts.generated.connector.uc2.kyc_beneficial_ownership_lookup_args import (
    KycBeneficialOwnershipLookupArgs,
)

ROOT = Path(__file__).resolve().parents[2]
UC2_SAMPLE_DIR = ROOT / "contracts" / "connector" / "uc2" / "samples"


def _sample(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((UC2_SAMPLE_DIR / name).read_text()))


def _context() -> ConnectorContext:
    return ConnectorContext(
        tenant_id="tenant_demo",
        correlation_id="cor_uc2_connector_sandbox",
        workflow_id="uc2-legal-intake-connector-sandbox",
    )


def test_default_registry_registers_uc2_tool_specs() -> None:
    registry = default_registry(cast(Connection[Any], object()))

    assert {
        "conflict_check.search",
        "kyc_bo.lookup",
        "aml_record_store.record_assessment",
        "engagement_letter.draft",
        "engagement_letter.send",
        "engagement_letter.record_decline",
        "engagement_letter.route_manual_review",
    }.issubset(set(registry.tool_names()))
    assert {
        "sandbox_conflict_check",
        "sandbox_kyc_bo",
        "sandbox_aml_record_store",
        "sandbox_engagement_letter_store",
    }.issubset(set(registry.adapter_ids()))

    _adapter, conflict_spec = registry.resolve("conflict_check.search")
    _adapter, kyc_spec = registry.resolve("kyc_bo.lookup")
    _adapter, aml_spec = registry.resolve("aml_record_store.record_assessment")
    _adapter, draft_spec = registry.resolve("engagement_letter.draft")

    assert conflict_spec.argument_contract is ConflictCheckSearchArgs
    assert kyc_spec.argument_contract is KycBeneficialOwnershipLookupArgs
    assert aml_spec.argument_contract is AmlRiskAssessmentRecordArgs
    assert draft_spec.argument_contract is EngagementLetterDraftArgs


def test_conflict_check_adapter_returns_deterministic_no_hit_refs() -> None:
    adapter = SandboxConflictCheckAdapter()
    arguments = ConflictCheckSearchArgs.model_validate(
        _sample("conflict_check_search_args.sample.json")
    )

    first = adapter.invoke(
        tool_name="conflict_check.search",
        mode="read",
        context=_context(),
        arguments=arguments,
    )
    second = adapter.invoke(
        tool_name="conflict_check.search",
        mode="read",
        context=_context(),
        arguments=arguments,
    )

    assert first.output == second.output
    assert first.output["connector"] == "sandbox_conflict_check.local"
    assert first.output["search_status"] == "no_hits_found"
    assert first.output["conflict_hit_refs"] == []
    assert first.output["conflict_check_ref"].startswith("conflict_check_")
    assert first.output["confidentiality_risk_hint"] == "none"


def test_conflict_check_adapter_returns_bounded_hit_refs_for_synthetic_marker() -> None:
    sample = _sample("conflict_check_search_args.sample.json")
    sample["party_search_terms"][1]["party_ref"] = "party_conflict_counterparty_001"
    arguments = ConflictCheckSearchArgs.model_validate(sample)

    result = SandboxConflictCheckAdapter().invoke(
        tool_name="conflict_check.search",
        mode="read",
        context=_context(),
        arguments=arguments,
    )

    assert result.output["search_status"] == "potential_hits_found"
    assert result.output["highest_hit_category"] == "adverse_party"
    assert result.output["conflict_hit_refs"][0].startswith("conflict_hit_")
    assert result.output["confidentiality_risk_hint"] == "possible_material_information"


def test_kyc_beneficial_ownership_adapter_returns_synthetic_cdd_refs() -> None:
    arguments = KycBeneficialOwnershipLookupArgs.model_validate(
        _sample("kyc_beneficial_ownership_lookup_args.sample.json")
    )

    result = SandboxKycBeneficialOwnershipAdapter().invoke(
        tool_name="kyc_bo.lookup",
        mode="read",
        context=_context(),
        arguments=arguments,
    )

    assert result.output["connector"] == "sandbox_kyc_bo.local"
    assert result.output["cdd_record_ref"].startswith("cdd_record_")
    assert result.output["beneficial_ownership_snapshot_ref"].startswith("bo_snapshot_")
    assert result.output["beneficial_owner_refs"] == ["beneficial_owner_demo_001"]
    assert result.output["controller_refs"] == ["controller_demo_001"]
    assert result.output["cdd_status"] == "complete_standard"
    assert result.output["beneficial_ownership_status"] == "complete"
    assert result.output["evidence_status"] == "refs_only_synthetic"


def test_aml_record_store_adapter_records_bounded_assessment_metadata() -> None:
    arguments = AmlRiskAssessmentRecordArgs.model_validate(
        _sample("aml_risk_assessment_record_args.sample.json")
    )

    result = SandboxAmlRecordStoreAdapter().invoke(
        tool_name="aml_record_store.record_assessment",
        mode="write",
        context=_context(),
        arguments=arguments,
    )

    assert result.output["connector"] == "sandbox_aml_record_store.local"
    assert result.output["record_status"] == "recorded"
    assert result.output["aml_risk_assessment_ref"] == "aml_risk_demo_001_v1"
    assert result.output["aml_record_ref"].startswith("aml_record_")
    assert result.output["cdd_status"] == "complete_standard"
    assert result.output["beneficial_ownership_status"] == "complete"
    assert result.output["aml_risk_rating"] == "standard"
    assert result.output["risk_factor_categories"] == ["none_identified"]
    assert result.output["retention_status"] == "local_ref_only"


def test_engagement_letter_store_drafts_ref_only_metadata() -> None:
    arguments = EngagementLetterDraftArgs.model_validate(
        _sample("engagement_letter_draft_args.sample.json")
    )

    result = SandboxEngagementLetterStoreAdapter().invoke(
        tool_name="engagement_letter.draft",
        mode="write",
        context=_context(),
        arguments=arguments,
    )

    assert result.output == {
        "connector": "sandbox_engagement_letter_store.local",
        "mode": "write",
        "legal_intake_ref": "legal_intake_demo_001",
        "engagement_letter_ref": "engagement_letter_demo_001",
        "engagement_decision_ref": "engagement_decision_demo_accept_001",
        "draft_ref": result.output["draft_ref"],
        "draft_status": "draft_recorded",
        "draft_storage": "local_ref_only",
        "template_ref": "template_uc2_corporate_engagement_v1",
        "scope_summary_ref": "scope_summary_demo_001",
        "draft_basis_categories": ["standard_terms", "scope_exclusions"],
    }
    assert result.output["draft_ref"].startswith("engagement_letter_draft_")


def test_engagement_letter_store_records_send_without_external_delivery() -> None:
    arguments = EngagementLetterSendArgs.model_validate(
        _sample("engagement_letter_send_args.sample.json")
    )

    result = SandboxEngagementLetterStoreAdapter().invoke(
        tool_name="engagement_letter.send",
        mode="write",
        context=_context(),
        arguments=arguments,
    )

    assert result.output["connector"] == "sandbox_engagement_letter_store.local"
    assert result.output["send_record_ref"].startswith("engagement_letter_send_")
    assert result.output["send_status"] == "send_recorded"
    assert result.output["send_channel_category"] == "email"
    assert result.output["delivery_surface"] == "local_record_only"
    assert "letter_text" not in result.output
    assert "body_text" not in result.output


def test_engagement_letter_store_records_decline_and_manual_review_refs() -> None:
    adapter = SandboxEngagementLetterStoreAdapter()
    decline_args = EngagementLetterDeclineArgs.model_validate(
        _sample("engagement_letter_decline_args.sample.json")
    )
    review_args = EngagementLetterManualReviewArgs.model_validate(
        _sample("engagement_letter_manual_review_args.sample.json")
    )

    decline = adapter.invoke(
        tool_name="engagement_letter.record_decline",
        mode="write",
        context=_context(),
        arguments=decline_args,
    )
    review = adapter.invoke(
        tool_name="engagement_letter.route_manual_review",
        mode="write",
        context=_context(),
        arguments=review_args,
    )

    assert decline.output["decline_ref"] == "decline_demo_conflict_001"
    assert decline.output["decline_status"] == "recorded"
    assert decline.output["decline_reason_category"] == "client_conflict_blocked"
    assert review.output["handoff_ref"] == "manual_review_demo_bo_gap_001"
    assert review.output["handoff_status"] == "routed"
    assert review.output["review_destination_category"] == "mlro"

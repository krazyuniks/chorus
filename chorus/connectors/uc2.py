"""UC2 connector adapters.

Four sandbox adapters cover the UC2 connector inventory: conflict check,
KYC / beneficial ownership, AML record store, and engagement-letter store.

The adapters are deterministic local surfaces for R4 architecture evidence.
They emit bounded refs and statuses only; they do not call production legal,
AML, identity, Companies House, sanctions, document-management,
matter-management, email, or e-signature services.
"""

from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from chorus.connectors.types import ConnectorContext, ConnectorError, ConnectorResult, ToolSpec
from chorus.contracts.generated.connector.uc2.aml_risk_assessment_record_args import (
    AmlRiskAssessmentRecordArgs,
    RiskFactorCategory,
)
from chorus.contracts.generated.connector.uc2.conflict_check_search_args import (
    ConflictCheckSearchArgs,
    ConflictSearchCategory,
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
    JurisdictionCategory,
    KycBeneficialOwnershipLookupArgs,
)


class SandboxConflictCheckAdapter:
    """`sandbox-conflict-check` adapter over a synthetic local conflict index."""

    adapter_id = "sandbox_conflict_check"

    def tool_specs(self) -> Sequence[ToolSpec]:
        return (
            ToolSpec(
                tool_name="conflict_check.search",
                argument_contract=ConflictCheckSearchArgs,
                return_contract_ref=(
                    "contracts/connector/uc2/conflict_check_search_args.schema.json"
                ),
            ),
        )

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        context: ConnectorContext,
        arguments: BaseModel,
    ) -> ConnectorResult:
        del context
        if tool_name != "conflict_check.search":
            raise ConnectorError(
                f"SandboxConflictCheckAdapter received unsupported tool {tool_name!r}"
            )
        if not isinstance(arguments, ConflictCheckSearchArgs):
            raise TypeError(
                f"SandboxConflictCheckAdapter expected ConflictCheckSearchArgs for {tool_name!r}"
            )

        categories = {category.value for category in arguments.conflict_search_categories}
        party_markers = [
            term.party_ref
            for term in arguments.party_search_terms
            if _has_marker(term.party_ref, "conflict", "adverse", "former", "own_interest")
        ]
        if ConflictSearchCategory.OWN_INTEREST.value in categories:
            hit_category = "own_interest"
        elif ConflictSearchCategory.UNKNOWN_HIGH_RISK_HIT.value in categories:
            hit_category = "unknown_high_risk_hit"
        elif party_markers:
            hit_category = "adverse_party"
        else:
            hit_category = ""

        hit_refs = (
            [
                _stable_ref(
                    "conflict_hit",
                    arguments.legal_intake_ref,
                    arguments.party_graph_ref,
                    hit_category,
                )
            ]
            if hit_category
            else []
        )
        output: dict[str, Any] = {
            "connector": "sandbox_conflict_check.local",
            "mode": mode,
            "legal_intake_ref": arguments.legal_intake_ref,
            "party_graph_ref": arguments.party_graph_ref,
            "matter_scope_ref": arguments.matter_scope_ref,
            "prospective_client_ref": arguments.prospective_client_ref,
            "conflict_check_ref": _stable_ref(
                "conflict_check",
                arguments.legal_intake_ref,
                arguments.party_graph_ref,
                arguments.conflict_policy_ref,
            ),
            "search_status": "potential_hits_found" if hit_refs else "no_hits_found",
            "conflict_hit_refs": hit_refs,
            "party_search_count": len(arguments.party_search_terms),
            "searched_category_count": len(arguments.conflict_search_categories),
            "confidentiality_risk_hint": _confidentiality_risk_hint(
                categories=categories,
                hit_category=hit_category,
            ),
            "conflict_policy_ref": arguments.conflict_policy_ref,
        }
        if hit_category:
            output["highest_hit_category"] = hit_category
        return ConnectorResult(connector_invocation_id=uuid4(), output=output)


class SandboxKycBeneficialOwnershipAdapter:
    """`sandbox-kyc-bo` adapter over deterministic synthetic CDD / BO status."""

    adapter_id = "sandbox_kyc_bo"

    def tool_specs(self) -> Sequence[ToolSpec]:
        return (
            ToolSpec(
                tool_name="kyc_bo.lookup",
                argument_contract=KycBeneficialOwnershipLookupArgs,
                return_contract_ref=(
                    "contracts/connector/uc2/kyc_beneficial_ownership_lookup_args.schema.json"
                ),
            ),
        )

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        context: ConnectorContext,
        arguments: BaseModel,
    ) -> ConnectorResult:
        del context
        if tool_name != "kyc_bo.lookup":
            raise ConnectorError(
                f"SandboxKycBeneficialOwnershipAdapter received unsupported tool {tool_name!r}"
            )
        if not isinstance(arguments, KycBeneficialOwnershipLookupArgs):
            raise TypeError(
                "SandboxKycBeneficialOwnershipAdapter expected "
                f"KycBeneficialOwnershipLookupArgs for {tool_name!r}"
            )

        beneficial_owner_refs = _root_values(arguments.beneficial_owner_refs)
        controller_refs = _root_values(arguments.controller_refs)
        high_risk_jurisdiction = JurisdictionCategory.HIGH_RISK_THIRD_COUNTRY in (
            arguments.jurisdiction_categories
        )
        beneficial_ownership_status = _beneficial_ownership_status(
            entity_category=arguments.entity_category.value,
            beneficial_owner_refs=beneficial_owner_refs,
        )
        cdd_status = _cdd_status(
            beneficial_ownership_status=beneficial_ownership_status,
            high_risk_jurisdiction=high_risk_jurisdiction,
            reliance_ref=arguments.reliance_ref,
        )
        aml_risk_rating = "edd_required" if high_risk_jurisdiction else "standard"

        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "sandbox_kyc_bo.local",
                "mode": mode,
                "legal_intake_ref": arguments.legal_intake_ref,
                "party_graph_ref": arguments.party_graph_ref,
                "prospective_client_ref": arguments.prospective_client_ref,
                "lookup_status": "synthetic_record_found",
                "cdd_record_ref": _stable_ref(
                    "cdd_record",
                    arguments.legal_intake_ref,
                    arguments.prospective_client_ref,
                    arguments.lookup_policy_ref,
                ),
                "beneficial_ownership_snapshot_ref": _stable_ref(
                    "bo_snapshot",
                    arguments.legal_intake_ref,
                    arguments.prospective_client_ref,
                ),
                "beneficial_owner_refs": beneficial_owner_refs,
                "controller_refs": controller_refs,
                "cdd_status": cdd_status,
                "beneficial_ownership_status": beneficial_ownership_status,
                "aml_risk_rating": aml_risk_rating,
                "requested_evidence_categories": [
                    category.value for category in arguments.requested_evidence_categories
                ],
                "evidence_status": "refs_only_synthetic",
                "lookup_policy_ref": arguments.lookup_policy_ref,
            },
        )


class SandboxAmlRecordStoreAdapter:
    """`sandbox-aml-record-store` adapter returning local record refs only."""

    adapter_id = "sandbox_aml_record_store"

    def tool_specs(self) -> Sequence[ToolSpec]:
        return (
            ToolSpec(
                tool_name="aml_record_store.record_assessment",
                argument_contract=AmlRiskAssessmentRecordArgs,
                return_contract_ref=(
                    "contracts/connector/uc2/aml_risk_assessment_record_args.schema.json"
                ),
            ),
        )

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        context: ConnectorContext,
        arguments: BaseModel,
    ) -> ConnectorResult:
        del context
        if tool_name != "aml_record_store.record_assessment":
            raise ConnectorError(
                f"SandboxAmlRecordStoreAdapter received unsupported tool {tool_name!r}"
            )
        if not isinstance(arguments, AmlRiskAssessmentRecordArgs):
            raise TypeError(
                "SandboxAmlRecordStoreAdapter expected AmlRiskAssessmentRecordArgs for "
                f"{tool_name!r}"
            )

        edd_trigger_refs = _root_values(arguments.edd_trigger_refs)
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "sandbox_aml_record_store.local",
                "mode": mode,
                "legal_intake_ref": arguments.legal_intake_ref,
                "prospective_client_ref": arguments.prospective_client_ref,
                "aml_risk_assessment_ref": arguments.aml_risk_assessment_ref,
                "aml_record_ref": _stable_ref(
                    "aml_record",
                    arguments.legal_intake_ref,
                    arguments.aml_risk_assessment_ref,
                    arguments.policy_refs.aml_policy_ref,
                ),
                "record_status": "recorded" if mode == "write" else "proposed",
                "cdd_record_ref": arguments.cdd_record_ref,
                "beneficial_ownership_snapshot_ref": (arguments.beneficial_ownership_snapshot_ref),
                "cdd_status": arguments.cdd_status.value,
                "beneficial_ownership_status": arguments.beneficial_ownership_status.value,
                "aml_risk_rating": arguments.aml_risk_rating.value,
                "risk_factor_categories": [
                    category.value for category in arguments.risk_factor_categories
                ],
                "edd_trigger_refs": edd_trigger_refs,
                "edd_required": _edd_required(arguments),
                "assessment_summary_ref": arguments.assessment_summary_ref,
                "retention_status": "local_ref_only",
                "aml_policy_ref": arguments.policy_refs.aml_policy_ref,
                "firm_risk_assessment_ref": arguments.policy_refs.firm_risk_assessment_ref,
                "sector_risk_source_ref": arguments.policy_refs.sector_risk_source_ref,
            },
        )


class SandboxEngagementLetterStoreAdapter:
    """`sandbox-engagement-letter-store` adapter for refs and routing metadata."""

    adapter_id = "sandbox_engagement_letter_store"

    def tool_specs(self) -> Sequence[ToolSpec]:
        return (
            ToolSpec(
                tool_name="engagement_letter.draft",
                argument_contract=EngagementLetterDraftArgs,
                return_contract_ref=(
                    "contracts/connector/uc2/engagement_letter_draft_args.schema.json"
                ),
            ),
            ToolSpec(
                tool_name="engagement_letter.send",
                argument_contract=EngagementLetterSendArgs,
                return_contract_ref=(
                    "contracts/connector/uc2/engagement_letter_send_args.schema.json"
                ),
            ),
            ToolSpec(
                tool_name="engagement_letter.record_decline",
                argument_contract=EngagementLetterDeclineArgs,
                return_contract_ref=(
                    "contracts/connector/uc2/engagement_letter_decline_args.schema.json"
                ),
            ),
            ToolSpec(
                tool_name="engagement_letter.route_manual_review",
                argument_contract=EngagementLetterManualReviewArgs,
                return_contract_ref=(
                    "contracts/connector/uc2/engagement_letter_manual_review_args.schema.json"
                ),
            ),
        )

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        context: ConnectorContext,
        arguments: BaseModel,
    ) -> ConnectorResult:
        del context
        if tool_name == "engagement_letter.draft":
            if not isinstance(arguments, EngagementLetterDraftArgs):
                raise TypeError(
                    "SandboxEngagementLetterStoreAdapter expected "
                    f"EngagementLetterDraftArgs for {tool_name!r}"
                )
            return self._draft(mode=mode, arguments=arguments)
        if tool_name == "engagement_letter.send":
            if not isinstance(arguments, EngagementLetterSendArgs):
                raise TypeError(
                    "SandboxEngagementLetterStoreAdapter expected "
                    f"EngagementLetterSendArgs for {tool_name!r}"
                )
            return self._send(mode=mode, arguments=arguments)
        if tool_name == "engagement_letter.record_decline":
            if not isinstance(arguments, EngagementLetterDeclineArgs):
                raise TypeError(
                    "SandboxEngagementLetterStoreAdapter expected "
                    f"EngagementLetterDeclineArgs for {tool_name!r}"
                )
            return self._decline(mode=mode, arguments=arguments)
        if tool_name == "engagement_letter.route_manual_review":
            if not isinstance(arguments, EngagementLetterManualReviewArgs):
                raise TypeError(
                    "SandboxEngagementLetterStoreAdapter expected "
                    f"EngagementLetterManualReviewArgs for {tool_name!r}"
                )
            return self._manual_review(mode=mode, arguments=arguments)
        raise ConnectorError(
            f"SandboxEngagementLetterStoreAdapter received unsupported tool {tool_name!r}"
        )

    @staticmethod
    def _draft(*, mode: str, arguments: EngagementLetterDraftArgs) -> ConnectorResult:
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "sandbox_engagement_letter_store.local",
                "mode": mode,
                "legal_intake_ref": arguments.legal_intake_ref,
                "engagement_letter_ref": arguments.engagement_letter_ref,
                "engagement_decision_ref": arguments.engagement_decision_ref,
                "draft_ref": _stable_ref(
                    "engagement_letter_draft",
                    arguments.legal_intake_ref,
                    arguments.engagement_letter_ref,
                    arguments.draft_policy_ref,
                ),
                "draft_status": "draft_recorded",
                "draft_storage": "local_ref_only",
                "template_ref": arguments.template_ref,
                "scope_summary_ref": arguments.scope_summary_ref,
                "draft_basis_categories": [
                    category.value for category in arguments.draft_basis_categories
                ],
            },
        )

    @staticmethod
    def _send(*, mode: str, arguments: EngagementLetterSendArgs) -> ConnectorResult:
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "sandbox_engagement_letter_store.local",
                "mode": mode,
                "legal_intake_ref": arguments.legal_intake_ref,
                "engagement_letter_ref": arguments.engagement_letter_ref,
                "engagement_decision_ref": arguments.engagement_decision_ref,
                "approval_package_ref": arguments.approval_package_ref,
                "send_instruction_ref": arguments.send_instruction_ref,
                "send_record_ref": _stable_ref(
                    "engagement_letter_send",
                    arguments.legal_intake_ref,
                    arguments.engagement_letter_ref,
                    arguments.send_instruction_ref,
                ),
                "send_status": "send_recorded",
                "send_channel_category": arguments.send_channel_category.value,
                "delivery_surface": "local_record_only",
                "send_policy_ref": arguments.send_policy_ref,
            },
        )

    @staticmethod
    def _decline(*, mode: str, arguments: EngagementLetterDeclineArgs) -> ConnectorResult:
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "sandbox_engagement_letter_store.local",
                "mode": mode,
                "legal_intake_ref": arguments.legal_intake_ref,
                "engagement_decision_ref": arguments.engagement_decision_ref,
                "decline_ref": arguments.decline_ref,
                "decline_status": "recorded",
                "decline_reason_category": arguments.decline_reason_category.value,
                "decline_summary_ref": arguments.decline_summary_ref,
                "routing_policy_ref": arguments.routing_policy_ref,
            },
        )

    @staticmethod
    def _manual_review(
        *,
        mode: str,
        arguments: EngagementLetterManualReviewArgs,
    ) -> ConnectorResult:
        output: dict[str, Any] = {
            "connector": "sandbox_engagement_letter_store.local",
            "mode": mode,
            "legal_intake_ref": arguments.legal_intake_ref,
            "handoff_ref": arguments.handoff_ref,
            "handoff_status": "routed",
            "review_reason_category": arguments.review_reason_category.value,
            "review_destination_category": arguments.review_destination_category.value,
            "routing_policy_ref": arguments.routing_policy_ref,
        }
        if arguments.engagement_decision_ref is not None:
            output["engagement_decision_ref"] = arguments.engagement_decision_ref
        if arguments.safe_summary_ref is not None:
            output["safe_summary_ref"] = arguments.safe_summary_ref
        return ConnectorResult(connector_invocation_id=uuid4(), output=output)


def _beneficial_ownership_status(
    *,
    entity_category: str,
    beneficial_owner_refs: Sequence[str],
) -> str:
    if entity_category in {"partnership", "charity"}:
        return "not_applicable"
    return "complete" if beneficial_owner_refs else "incomplete"


def _cdd_status(
    *,
    beneficial_ownership_status: str,
    high_risk_jurisdiction: bool,
    reliance_ref: str | None,
) -> str:
    if high_risk_jurisdiction:
        return "edd_required"
    if beneficial_ownership_status == "incomplete":
        return "incomplete"
    if reliance_ref is not None:
        return "reliance_pending"
    return "complete_standard"


def _edd_required(arguments: AmlRiskAssessmentRecordArgs) -> bool:
    return (
        arguments.aml_risk_rating.value in {"high", "edd_required"}
        or bool(arguments.edd_trigger_refs)
        or any(
            category
            in {
                RiskFactorCategory.HIGH_RISK_JURISDICTION,
                RiskFactorCategory.PEP_OR_SANCTIONS_ADJACENT,
                RiskFactorCategory.SOURCE_OF_FUNDS_AMBIGUITY,
                RiskFactorCategory.SOURCE_OF_WEALTH_AMBIGUITY,
            }
            for category in arguments.risk_factor_categories
        )
    )


def _confidentiality_risk_hint(
    *,
    categories: set[str],
    hit_category: str,
) -> str:
    if hit_category == "unknown_high_risk_hit":
        return "unknown"
    if ConflictSearchCategory.CONFIDENTIAL_INFORMATION.value in categories and hit_category in {
        "adverse_party",
        "own_interest",
    }:
        return "possible_material_information"
    return "none"


def _has_marker(value: str, *markers: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in markers)


def _root_values(values: Sequence[Any] | None) -> list[str]:
    if values is None:
        return []
    return [_root_value(value) for value in values]


def _root_value(value: Any) -> str:
    root = getattr(value, "root", value)
    if not isinstance(root, str):
        raise TypeError(f"Expected generated ref wrapper to contain a string, got {type(root)}")
    return root


def _stable_ref(prefix: str, *parts: str) -> str:
    digest = sha256(":".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


__all__ = [
    "SandboxAmlRecordStoreAdapter",
    "SandboxConflictCheckAdapter",
    "SandboxEngagementLetterStoreAdapter",
    "SandboxKycBeneficialOwnershipAdapter",
]

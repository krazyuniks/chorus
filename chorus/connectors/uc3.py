"""UC3 connector adapters.

Four sandbox adapters cover the UC3 connector inventory: attitude-to-risk
profiling, capacity-for-loss assessment, platform research, and
suitability-report storage / routing.

The adapters are deterministic local surfaces for R4 architecture evidence.
They emit bounded refs and statuses only; they do not call production IFA,
platform, investment-research, advice, client-record, document-generation,
email, portal, custody, or dealing systems.
"""

from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from chorus.connectors.types import ConnectorContext, ConnectorError, ConnectorResult, ToolSpec
from chorus.contracts.generated.connector.uc3.attitude_to_risk_profile_args import (
    AttitudeToRiskProfileArgs,
    RiskContextCategory,
    StatedRiskPreferenceBand,
)
from chorus.contracts.generated.connector.uc3.capacity_for_loss_assessment_args import (
    CapacityForLossAssessmentArgs,
    LiquidityNeedCategory,
    StressScenarioCategory,
)
from chorus.contracts.generated.connector.uc3.platform_research_args import (
    PlatformConstraintCategory,
    PlatformResearchArgs,
    ProductUniverseScope,
    TargetMarketCategory,
)
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


class SandboxAttitudeToRiskProfilerAdapter:
    """`sandbox-attitude-to-risk-profiler` adapter over synthetic risk evidence."""

    adapter_id = "sandbox_attitude_to_risk_profiler"

    def tool_specs(self) -> Sequence[ToolSpec]:
        return (
            ToolSpec(
                tool_name="attitude_to_risk.profile",
                argument_contract=AttitudeToRiskProfileArgs,
                return_contract_ref=(
                    "contracts/connector/uc3/attitude_to_risk_profile_args.schema.json"
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
        if tool_name != "attitude_to_risk.profile":
            raise ConnectorError(
                f"SandboxAttitudeToRiskProfilerAdapter received unsupported tool {tool_name!r}"
            )
        if not isinstance(arguments, AttitudeToRiskProfileArgs):
            raise TypeError(
                "SandboxAttitudeToRiskProfilerAdapter expected "
                f"AttitudeToRiskProfileArgs for {tool_name!r}"
            )

        risk_profile_status = _risk_profile_status(arguments)
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "sandbox_attitude_to_risk_profiler.local",
                "mode": mode,
                "advice_enquiry_ref": arguments.advice_enquiry_ref,
                "prospective_retail_client_ref": arguments.prospective_retail_client_ref,
                "fact_find_summary_ref": arguments.fact_find_summary_ref,
                "risk_profile_ref": _stable_ref(
                    "risk_profile",
                    arguments.advice_enquiry_ref,
                    arguments.questionnaire_bundle_ref,
                    arguments.profiler_policy_ref,
                ),
                "profiler_band": _profiler_band(arguments, risk_profile_status),
                "risk_profile_status": risk_profile_status,
                "questionnaire_trace_ref": _stable_ref(
                    "risk_questionnaire_trace",
                    arguments.questionnaire_bundle_ref,
                    arguments.profiler_policy_ref,
                ),
                "narrative_evidence_ref": arguments.narrative_evidence_ref,
                "objective_refs": _root_values(arguments.objective_refs),
                "knowledge_experience_ref": arguments.knowledge_experience_ref,
                "risk_context_categories": _risk_context_values(arguments),
                "inconsistency_flags": _risk_inconsistency_flags(arguments),
                "confidence_category": (
                    "synthetic_high" if risk_profile_status == "aligned" else "synthetic_review"
                ),
                "evidence_status": "refs_only_synthetic",
                "profiler_policy_ref": arguments.profiler_policy_ref,
                "conduct_hook_refs": _root_values(arguments.conduct_hook_refs),
            },
        )


class SandboxCapacityForLossToolAdapter:
    """`sandbox-capacity-for-loss-tool` adapter over synthetic stress results."""

    adapter_id = "sandbox_capacity_for_loss_tool"

    def tool_specs(self) -> Sequence[ToolSpec]:
        return (
            ToolSpec(
                tool_name="capacity_for_loss.assess",
                argument_contract=CapacityForLossAssessmentArgs,
                return_contract_ref=(
                    "contracts/connector/uc3/capacity_for_loss_assessment_args.schema.json"
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
        if tool_name != "capacity_for_loss.assess":
            raise ConnectorError(
                f"SandboxCapacityForLossToolAdapter received unsupported tool {tool_name!r}"
            )
        if not isinstance(arguments, CapacityForLossAssessmentArgs):
            raise TypeError(
                "SandboxCapacityForLossToolAdapter expected "
                f"CapacityForLossAssessmentArgs for {tool_name!r}"
            )

        dependency_context_refs = _root_values(arguments.dependency_context_refs)
        stress_categories = [category.value for category in arguments.stress_scenario_categories]
        capacity_status = _capacity_for_loss_status(arguments)
        output: dict[str, Any] = {
            "connector": "sandbox_capacity_for_loss_tool.local",
            "mode": mode,
            "advice_enquiry_ref": arguments.advice_enquiry_ref,
            "prospective_retail_client_ref": arguments.prospective_retail_client_ref,
            "fact_find_summary_ref": arguments.fact_find_summary_ref,
            "financial_situation_ref": arguments.financial_situation_ref,
            "capacity_for_loss_ref": _stable_ref(
                "capacity_for_loss",
                arguments.advice_enquiry_ref,
                arguments.financial_situation_ref,
                arguments.assessment_policy_ref,
            ),
            "capacity_for_loss_status": capacity_status,
            "stress_test_ref": _stable_ref(
                "capacity_stress",
                arguments.advice_enquiry_ref,
                arguments.financial_situation_ref,
                ":".join(stress_categories),
            ),
            "stress_outcome": "pass" if capacity_status == "adequate" else "review_required",
            "liquidity_status": _liquidity_status(arguments),
            "dependency_status": "dependencies_identified"
            if dependency_context_refs
            else "no_dependencies_identified",
            "objective_refs": _root_values(arguments.objective_refs),
            "time_horizon_band": arguments.time_horizon_band.value,
            "liquidity_need_category": (
                arguments.liquidity_need_category.value
                if arguments.liquidity_need_category is not None
                else "unknown"
            ),
            "dependency_context_refs": dependency_context_refs,
            "stress_scenario_categories": stress_categories,
            "affordability_evidence_ref": _stable_ref(
                "affordability_evidence",
                arguments.advice_enquiry_ref,
                arguments.financial_situation_ref,
            ),
            "evidence_status": "refs_only_synthetic",
            "assessment_policy_ref": arguments.assessment_policy_ref,
            "conduct_hook_refs": _root_values(arguments.conduct_hook_refs),
        }
        if arguments.household_ref is not None:
            output["household_ref"] = arguments.household_ref
        return ConnectorResult(connector_invocation_id=uuid4(), output=output)


class SandboxPlatformResearchAdapter:
    """`sandbox-platform-research` adapter returning synthetic research refs."""

    adapter_id = "sandbox_platform_research"

    def tool_specs(self) -> Sequence[ToolSpec]:
        return (
            ToolSpec(
                tool_name="platform_research.run",
                argument_contract=PlatformResearchArgs,
                return_contract_ref="contracts/connector/uc3/platform_research_args.schema.json",
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
        if tool_name != "platform_research.run":
            raise ConnectorError(
                f"SandboxPlatformResearchAdapter received unsupported tool {tool_name!r}"
            )
        if not isinstance(arguments, PlatformResearchArgs):
            raise TypeError(
                f"SandboxPlatformResearchAdapter expected PlatformResearchArgs for {tool_name!r}"
            )

        product_candidate_refs = _root_values(arguments.product_candidate_refs)
        platform_constraints = _platform_constraint_values(arguments)
        target_market_categories = [
            category.value for category in arguments.target_market_categories
        ]
        research_status = _platform_research_status(arguments)
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "sandbox_platform_research.local",
                "mode": mode,
                "advice_enquiry_ref": arguments.advice_enquiry_ref,
                "advice_scope_ref": arguments.advice_scope_ref,
                "prospective_retail_client_ref": arguments.prospective_retail_client_ref,
                "risk_profile_ref": arguments.risk_profile_ref,
                "capacity_for_loss_ref": arguments.capacity_for_loss_ref,
                "platform_research_ref": _stable_ref(
                    "platform_research",
                    arguments.advice_enquiry_ref,
                    arguments.risk_profile_ref,
                    arguments.capacity_for_loss_ref,
                    arguments.research_policy_refs.platform_research_policy_ref,
                ),
                "research_status": research_status,
                "product_universe_coverage": _product_universe_coverage(arguments),
                "target_market_status": _target_market_status(arguments),
                "product_candidate_refs": product_candidate_refs,
                "target_market_categories": target_market_categories,
                "target_market_refs": [
                    _stable_ref("target_market", arguments.advice_enquiry_ref, category)
                    for category in target_market_categories
                ],
                "platform_constraint_categories": platform_constraints,
                "cost_charge_summary_ref": _stable_ref(
                    "cost_charge_summary",
                    arguments.advice_enquiry_ref,
                    arguments.research_policy_refs.platform_research_policy_ref,
                ),
                "due_diligence_ref": _stable_ref(
                    "due_diligence",
                    arguments.advice_enquiry_ref,
                    arguments.research_policy_refs.prod_policy_ref,
                ),
                "product_complexity_band": _product_complexity_band(arguments),
                "objective_refs": _root_values(arguments.objective_refs),
                "evidence_status": "refs_only_synthetic",
                "platform_research_policy_ref": (
                    arguments.research_policy_refs.platform_research_policy_ref
                ),
                "independent_advice_policy_ref": (
                    arguments.research_policy_refs.independent_advice_policy_ref
                ),
                "prod_policy_ref": arguments.research_policy_refs.prod_policy_ref,
                "conduct_hook_refs": _root_values(arguments.conduct_hook_refs),
            },
        )


class SandboxSuitabilityReportStoreAdapter:
    """`sandbox-suitability-report-store` adapter for refs and routing metadata."""

    adapter_id = "sandbox_suitability_report_store"

    def tool_specs(self) -> Sequence[ToolSpec]:
        return (
            ToolSpec(
                tool_name="suitability_report.draft",
                argument_contract=SuitabilityReportDraftArgs,
                return_contract_ref=(
                    "contracts/connector/uc3/suitability_report_draft_args.schema.json"
                ),
            ),
            ToolSpec(
                tool_name="suitability_report.issue",
                argument_contract=SuitabilityReportIssueArgs,
                return_contract_ref=(
                    "contracts/connector/uc3/suitability_report_issue_args.schema.json"
                ),
            ),
            ToolSpec(
                tool_name="suitability_report.record_decline",
                argument_contract=SuitabilityReportDeclineArgs,
                return_contract_ref=(
                    "contracts/connector/uc3/suitability_report_decline_args.schema.json"
                ),
            ),
            ToolSpec(
                tool_name="suitability_report.route_manual_review",
                argument_contract=SuitabilityReportManualReviewArgs,
                return_contract_ref=(
                    "contracts/connector/uc3/suitability_report_manual_review_args.schema.json"
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
        if tool_name == "suitability_report.draft":
            if not isinstance(arguments, SuitabilityReportDraftArgs):
                raise TypeError(
                    "SandboxSuitabilityReportStoreAdapter expected "
                    f"SuitabilityReportDraftArgs for {tool_name!r}"
                )
            return self._draft(mode=mode, arguments=arguments)
        if tool_name == "suitability_report.issue":
            if not isinstance(arguments, SuitabilityReportIssueArgs):
                raise TypeError(
                    "SandboxSuitabilityReportStoreAdapter expected "
                    f"SuitabilityReportIssueArgs for {tool_name!r}"
                )
            return self._issue(mode=mode, arguments=arguments)
        if tool_name == "suitability_report.record_decline":
            if not isinstance(arguments, SuitabilityReportDeclineArgs):
                raise TypeError(
                    "SandboxSuitabilityReportStoreAdapter expected "
                    f"SuitabilityReportDeclineArgs for {tool_name!r}"
                )
            return self._decline(mode=mode, arguments=arguments)
        if tool_name == "suitability_report.route_manual_review":
            if not isinstance(arguments, SuitabilityReportManualReviewArgs):
                raise TypeError(
                    "SandboxSuitabilityReportStoreAdapter expected "
                    f"SuitabilityReportManualReviewArgs for {tool_name!r}"
                )
            return self._manual_review(mode=mode, arguments=arguments)
        raise ConnectorError(
            f"SandboxSuitabilityReportStoreAdapter received unsupported tool {tool_name!r}"
        )

    @staticmethod
    def _draft(*, mode: str, arguments: SuitabilityReportDraftArgs) -> ConnectorResult:
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "sandbox_suitability_report_store.local",
                "mode": mode,
                "advice_enquiry_ref": arguments.advice_enquiry_ref,
                "suitability_report_ref": arguments.suitability_report_ref,
                "suitability_conclusion_ref": arguments.suitability_conclusion_ref,
                "draft_ref": _stable_ref(
                    "suitability_report_draft",
                    arguments.advice_enquiry_ref,
                    arguments.suitability_report_ref,
                    arguments.draft_policy_ref,
                ),
                "draft_status": "draft_recorded",
                "draft_storage": "local_ref_only",
                "prospective_retail_client_ref": arguments.prospective_retail_client_ref,
                "fact_find_summary_ref": arguments.fact_find_summary_ref,
                "risk_profile_ref": arguments.risk_profile_ref,
                "capacity_for_loss_ref": arguments.capacity_for_loss_ref,
                "platform_research_ref": arguments.platform_research_ref,
                "support_assessment_ref": arguments.support_assessment_ref,
                "report_summary_ref": arguments.report_summary_ref,
                "template_ref": arguments.template_ref,
                "draft_basis_categories": [
                    category.value for category in arguments.draft_basis_categories
                ],
                "draft_policy_ref": arguments.draft_policy_ref,
                "conduct_hook_refs": _root_values(arguments.conduct_hook_refs),
            },
        )

    @staticmethod
    def _issue(*, mode: str, arguments: SuitabilityReportIssueArgs) -> ConnectorResult:
        output: dict[str, Any] = {
            "connector": "sandbox_suitability_report_store.local",
            "mode": mode,
            "advice_enquiry_ref": arguments.advice_enquiry_ref,
            "suitability_report_ref": arguments.suitability_report_ref,
            "suitability_conclusion_ref": arguments.suitability_conclusion_ref,
            "approval_package_ref": arguments.approval_package_ref,
            "issue_instruction_ref": arguments.issue_instruction_ref,
            "prospective_retail_client_ref": arguments.prospective_retail_client_ref,
            "consumer_understanding_check_ref": arguments.consumer_understanding_check_ref,
            "issue_record_ref": _stable_ref(
                "suitability_report_issue",
                arguments.advice_enquiry_ref,
                arguments.suitability_report_ref,
                arguments.issue_instruction_ref,
            ),
            "issue_status": "issue_recorded",
            "issue_channel_category": arguments.issue_channel_category.value,
            "delivery_surface": "local_record_only",
            "issue_policy_ref": arguments.issue_policy_ref,
            "conduct_hook_refs": _root_values(arguments.conduct_hook_refs),
        }
        if arguments.adviser_approval_ref is not None:
            output["adviser_approval_ref"] = arguments.adviser_approval_ref
        if arguments.support_assessment_ref is not None:
            output["support_assessment_ref"] = arguments.support_assessment_ref
        return ConnectorResult(connector_invocation_id=uuid4(), output=output)

    @staticmethod
    def _decline(*, mode: str, arguments: SuitabilityReportDeclineArgs) -> ConnectorResult:
        output: dict[str, Any] = {
            "connector": "sandbox_suitability_report_store.local",
            "mode": mode,
            "advice_enquiry_ref": arguments.advice_enquiry_ref,
            "suitability_conclusion_ref": arguments.suitability_conclusion_ref,
            "decline_ref": arguments.decline_ref,
            "decline_status": "recorded",
            "decline_reason_category": arguments.decline_reason_category.value,
            "decline_summary_ref": arguments.decline_summary_ref,
            "routing_policy_ref": arguments.routing_policy_ref,
            "conduct_hook_refs": _root_values(arguments.conduct_hook_refs),
        }
        if arguments.platform_research_ref is not None:
            output["platform_research_ref"] = arguments.platform_research_ref
        if arguments.capacity_for_loss_ref is not None:
            output["capacity_for_loss_ref"] = arguments.capacity_for_loss_ref
        return ConnectorResult(connector_invocation_id=uuid4(), output=output)

    @staticmethod
    def _manual_review(
        *,
        mode: str,
        arguments: SuitabilityReportManualReviewArgs,
    ) -> ConnectorResult:
        output: dict[str, Any] = {
            "connector": "sandbox_suitability_report_store.local",
            "mode": mode,
            "advice_enquiry_ref": arguments.advice_enquiry_ref,
            "handoff_ref": arguments.handoff_ref,
            "handoff_status": "routed",
            "review_reason_category": arguments.review_reason_category.value,
            "review_destination_category": arguments.review_destination_category.value,
            "routing_policy_ref": arguments.routing_policy_ref,
            "conduct_hook_refs": _root_values(arguments.conduct_hook_refs),
        }
        if arguments.suitability_conclusion_ref is not None:
            output["suitability_conclusion_ref"] = arguments.suitability_conclusion_ref
        if arguments.safe_summary_ref is not None:
            output["safe_summary_ref"] = arguments.safe_summary_ref
        return ConnectorResult(connector_invocation_id=uuid4(), output=output)


def _risk_context_values(arguments: AttitudeToRiskProfileArgs) -> list[str]:
    if arguments.risk_context_categories is None:
        return []
    return [category.value for category in arguments.risk_context_categories]


def _risk_inconsistency_flags(arguments: AttitudeToRiskProfileArgs) -> list[str]:
    categories = set(_risk_context_values(arguments))
    flags: list[str] = []
    if RiskContextCategory.OBJECTIVE_RISK_MISMATCH.value in categories:
        flags.append("objective_risk_mismatch")
    if (
        RiskContextCategory.LOSS_CONCERN_DISCLOSED.value in categories
        and arguments.stated_risk_preference_band
        in {StatedRiskPreferenceBand.MEDIUM_HIGH, StatedRiskPreferenceBand.HIGH}
    ):
        flags.append("loss_concern_stated_high_risk")
    if arguments.stated_risk_preference_band is StatedRiskPreferenceBand.NOT_DISCLOSED:
        flags.append("risk_preference_not_disclosed")
    if arguments.time_horizon_band.value in {"unknown", "under_2_years"}:
        flags.append("time_horizon_not_suitable_for_profile")
    return flags


def _risk_profile_status(arguments: AttitudeToRiskProfileArgs) -> str:
    flags = _risk_inconsistency_flags(arguments)
    if "risk_preference_not_disclosed" in flags or "time_horizon_not_suitable_for_profile" in flags:
        return "manual_review"
    if flags:
        return "mismatch_requires_approval"
    return "aligned"


def _profiler_band(arguments: AttitudeToRiskProfileArgs, risk_profile_status: str) -> str:
    if risk_profile_status == "manual_review":
        return "unknown"
    if risk_profile_status == "mismatch_requires_approval":
        return "medium"
    return arguments.stated_risk_preference_band.value


def _capacity_for_loss_status(arguments: CapacityForLossAssessmentArgs) -> str:
    liquidity = arguments.liquidity_need_category
    stress = set(arguments.stress_scenario_categories)
    dependency_refs = _root_values(arguments.dependency_context_refs)
    if liquidity is LiquidityNeedCategory.EMERGENCY_RESERVE_GAP:
        return "liquidity_gap"
    if dependency_refs and stress.intersection(
        {
            StressScenarioCategory.RETIREMENT_INCOME_SHORTFALL,
            StressScenarioCategory.CARE_COST_PRESSURE,
        }
    ):
        return "dependency_risk"
    if (
        liquidity is LiquidityNeedCategory.HIGH
        or StressScenarioCategory.MARKET_FALL_30_PERCENT in stress
    ):
        return "limited"
    return "adequate"


def _liquidity_status(arguments: CapacityForLossAssessmentArgs) -> str:
    match arguments.liquidity_need_category:
        case LiquidityNeedCategory.EMERGENCY_RESERVE_GAP:
            return "emergency_reserve_gap"
        case LiquidityNeedCategory.HIGH:
            return "high_liquidity_need"
        case LiquidityNeedCategory.MEDIUM:
            return "moderate_liquidity_need"
        case LiquidityNeedCategory.LOW:
            return "low_liquidity_need"
        case _:
            return "unknown"


def _platform_constraint_values(arguments: PlatformResearchArgs) -> list[str]:
    if arguments.platform_constraint_categories is None:
        return []
    return [category.value for category in arguments.platform_constraint_categories]


def _product_universe_coverage(arguments: PlatformResearchArgs) -> str:
    constraints = set(arguments.platform_constraint_categories or [])
    if PlatformConstraintCategory.MANUFACTURER_DATA_MISSING in constraints:
        return "manufacturer_data_missing"
    if constraints.intersection(
        {
            PlatformConstraintCategory.EXISTING_PLATFORM_BIAS,
            PlatformConstraintCategory.PLATFORM_CHARGES_CONCERN,
            PlatformConstraintCategory.RESTRICTED_PANEL_INDICATOR,
        }
    ):
        return "platform_biased"
    match arguments.product_universe_scope:
        case ProductUniverseScope.INDEPENDENT_FULL_RELEVANT_MARKET:
            return "sufficient_independent_range"
        case ProductUniverseScope.FOCUSED_INDEPENDENT_RANGE:
            return "focused_independent_range"
        case ProductUniverseScope.PLATFORM_CONSTRAINED_RANGE:
            return "platform_biased"
        case ProductUniverseScope.EXISTING_PLATFORM_REVIEW:
            return "focused_independent_range"
        case ProductUniverseScope.MANUAL_RESEARCH_REQUIRED:
            return "manual_review"


def _target_market_status(arguments: PlatformResearchArgs) -> str:
    categories = set(arguments.target_market_categories)
    if TargetMarketCategory.NEGATIVE_TARGET_MARKET in categories:
        return "negative_target_market"
    if TargetMarketCategory.MANUAL_REVIEW in categories:
        return "manual_review"
    if TargetMarketCategory.UNKNOWN in categories:
        return "unknown"
    if TargetMarketCategory.EDGE_OF_TARGET_MARKET in categories:
        return "edge_of_target_market"
    return "in_target_market"


def _platform_research_status(arguments: PlatformResearchArgs) -> str:
    if _product_universe_coverage(arguments) in {
        "manual_review",
        "manufacturer_data_missing",
        "platform_biased",
    } or _target_market_status(arguments) in {"manual_review", "negative_target_market"}:
        return "review_required"
    return "complete"


def _product_complexity_band(arguments: PlatformResearchArgs) -> str:
    if _target_market_status(arguments) == "negative_target_market":
        return "high_risk_out_of_scope"
    if _product_universe_coverage(arguments) in {"platform_biased", "manual_review"}:
        return "complex"
    return "moderate"


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
    "SandboxAttitudeToRiskProfilerAdapter",
    "SandboxCapacityForLossToolAdapter",
    "SandboxPlatformResearchAdapter",
    "SandboxSuitabilityReportStoreAdapter",
]

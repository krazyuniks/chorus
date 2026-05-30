"""Deterministic recorded/replay adapter behind the LLM provider port.

Produces stable structured outputs so ``just eval`` and ``just test`` stay
green between checkpoints B and G - the eval reshape (ADR 0019) introduces
the captured-transcript replay subcommand and retires the
path-enumeration fixtures. Until then this adapter is the deterministic
substrate the route catalogue selects in tests and eval.

The shape matches the UC1 agent IO contract (`contracts/llm_provider/
uc1_agent_io.schema.json`). Branch fixtures (deeper-context, validator
redraft, retry exhaustion) are detected from the input payload metadata
that the runtime passes through.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast

from chorus.llm_provider.port import (
    InvocationArgs,
    InvocationResult,
    LLMProviderInvocationError,
)

ADAPTER_VERSION = "recorded-replay-v1"


@dataclass
class RecordedReplayAdapter:
    """Deterministic stand-in for the LLM provider port."""

    adapter_version: str = ADAPTER_VERSION

    def invoke(self, args: InvocationArgs) -> InvocationResult:
        task_kind = args.metadata.get("task_kind")
        if not isinstance(task_kind, str):
            raise LLMProviderInvocationError(
                route_id=args.route_id,
                reason="missing_task_kind_metadata",
                retryable=False,
            )
        raw_input = args.metadata.get("input")
        if not isinstance(raw_input, dict):
            raise LLMProviderInvocationError(
                route_id=args.route_id,
                reason="missing_input_metadata",
                retryable=False,
            )
        agent_input = cast(dict[str, Any], raw_input)

        summary, next_step, structured_data, confidence = _replay_result_for(task_kind, agent_input)
        if args.response_shape is not None:
            structured_data = _normalise_structured_data_for_shape(
                structured_data,
                args.response_shape,
            )

        return InvocationResult(
            summary=summary,
            structured_data=structured_data,
            confidence=confidence,
            recommended_next_step=next_step,
            rationale=(
                "Deterministic recorded/replay route returned a governed structured "
                "decision; external actions remain behind the Tool Gateway."
            ),
            cost_amount_usd=Decimal("0.000000"),
            provider_metadata={"adapter": ADAPTER_VERSION}
            | _safe_response_schema_metadata(args.response_shape),
        )


def _replay_result_for(
    task_kind: str, agent_input: dict[str, Any]
) -> tuple[str, str, dict[str, Any], float]:
    match task_kind:
        case "enquiry_classification":
            if _is_retry_exhaustion_fixture(agent_input):
                raise LLMProviderInvocationError(
                    route_id="recorded-replay",
                    reason="retry_exhaustion_fixture_forced_failure",
                )
            if _is_deeper_context_fixture(agent_input):
                attempt = int(agent_input.get("classification_attempt", 1))
                if attempt == 1:
                    return (
                        "Initial classification needs deeper context.",
                        "deeper_context",
                        {
                            "product_family_category": "unknown",
                            "classification_attempt": attempt,
                        },
                        0.42,
                    )
                return (
                    "Deeper context resolved the enquiry to motor private car.",
                    "continue",
                    {
                        "product_family_category": "motor_private_car",
                        "classification_attempt": attempt,
                        "deeper_context_completed": True,
                    },
                    0.86,
                )
            return (
                "Classified the enquiry as motor private car with explicit demanded cover.",
                "continue",
                {
                    "product_family_category": "motor_private_car",
                    "demanded_cover_shape": "third_party_fire_and_theft",
                },
                0.88,
            )
        case "enquiry_qualification":
            terminal_route_category = _terminal_route_fixture_category(agent_input)
            if terminal_route_category is not None:
                return _terminal_route_qualification_result(terminal_route_category)
            return (
                "Enquiry passes UC1 conduct hooks and proceeds with a missing-data request.",
                "continue",
                {
                    "qualification_verdict_category": "missing_data",
                    "missing_data_request_required": True,
                    "conduct_hooks_pass": True,
                    "best_interests_check": {
                        "status": "pass",
                        "regulatory_ref": "ICOBS 2.5.-1R",
                    },
                    "demands_and_needs_statement": {
                        "captured": True,
                        "regulatory_ref": "ICOBS 5",
                        "summary": (
                            "Customer seeks third-party fire and theft cover for a private car."
                        ),
                    },
                    "target_market_check": {
                        "status": "pass",
                        "regulatory_ref": "PROD 4",
                    },
                    "foreseeable_harm_check": {
                        "status": "no_harm_identified",
                        "regulatory_ref": "Consumer Duty PRIN 12",
                    },
                    "policy_snapshot_ref": "policy_snapshot:uc1:default:v1",
                    "rationale": (
                        "All four UC1 conduct hooks pass; recommend proceeding to a "
                        "missing-data request before adviser approval and send."
                    ),
                },
                0.88,
            )
        case "missing_data_request_draft":
            if _is_validator_redraft_fixture(agent_input):
                attempt = int(agent_input.get("redraft_attempt", 1))
                if attempt == 1:
                    return (
                        "Initial missing-data request asked generic follow-up questions.",
                        "continue",
                        {
                            "draft_body_text": (
                                "Hello, thanks for getting in touch. Could you confirm "
                                "your postcode and licence history?"
                            ),
                            "redraft_attempt": attempt,
                            "customer_ref": "cust_demo_001",
                            "missing_data_request_ref": "mdr_demo_001",
                        },
                        0.88,
                    )
                return (
                    "Redrafted missing-data request scopes the questions to the cover requested.",
                    "continue",
                    {
                        "draft_body_text": (
                            "Hello, thanks for getting in touch. To prepare a "
                            "third-party fire and theft quote, please confirm your "
                            "postcode, licence date, and any previous claims in the "
                            "last five years."
                        ),
                        "redraft_attempt": attempt,
                        "applied_validator_reason": (agent_input.get("validator_reason", {}) or {}),
                        "customer_ref": "cust_demo_001",
                        "missing_data_request_ref": "mdr_demo_001",
                    },
                    0.88,
                )
            return (
                "Drafted a focused missing-data request for the enquiry.",
                "continue",
                {
                    "draft_body_text": (
                        "Hello, thanks for getting in touch. To prepare a quote, please "
                        "confirm your postcode, licence date, and any previous claims "
                        "in the last five years."
                    ),
                    "customer_ref": "cust_demo_001",
                    "missing_data_request_ref": "mdr_demo_001",
                },
                0.88,
            )
        case "missing_data_request_validation":
            if _is_validator_redraft_fixture(agent_input):
                attempt = int(agent_input.get("redraft_attempt", 1))
                if attempt == 1:
                    return (
                        "Draft is too generic; validator requests a redraft.",
                        "redraft",
                        {
                            "validation": "redraft_requested",
                            "redraft_attempt": attempt,
                            "reason": {
                                "code": "scope_mismatch",
                                "missing_elements": ["cover_scope", "claims_history"],
                                "guidance": (
                                    "Scope the questions to the demanded cover and "
                                    "ask explicitly about previous claims."
                                ),
                            },
                        },
                        0.88,
                    )
                return (
                    "Redrafted request now scopes the questions correctly.",
                    "send",
                    {
                        "validation": "approved",
                        "redraft_attempt": attempt,
                        "redraft_completed": True,
                    },
                    0.88,
                )
            return (
                "Draft is suitable for adviser approval and send in propose mode.",
                "send",
                {"validation": "approved"},
                0.88,
            )
        case "context_gathering":
            return (
                "Captured demands-and-needs statement and flagged completeness gaps.",
                "continue",
                {
                    "demands_and_needs_summary": (
                        "Customer seeks third-party fire and theft cover for a 2018 "
                        "hatchback; new driver, postcode disclosed."
                    ),
                    "missing_data_fields": ["previous_claims_5y", "licence_date"],
                },
                0.88,
            )
        case "uc2_matter_classification":
            return (
                "Classified the legal intake as a corporate transaction matter.",
                "continue",
                {
                    "matter_type": "corporate_transaction",
                    "matter_scope_ref": "matter_scope_demo_uc2_001",
                    "jurisdiction_categories": ["england_and_wales"],
                    "conduct_hook_refs": [
                        "conduct_sra_identify_client_8_1",
                        "conduct_sra_accountability_7_1_7_2",
                    ],
                    "policy_snapshot_ref": "policy_snapshot:uc2:default:v1",
                },
                0.86,
            )
        case "uc2_party_extraction":
            return (
                "Extracted a bounded party graph for the prospective corporate client.",
                "continue",
                {
                    "party_graph_ref": "party_graph_demo_uc2_001",
                    "prospective_client_ref": "prospective_client_demo_uc2_001",
                    "authority_status": "confirmed",
                    "party_graph_ambiguous": False,
                    "party_search_terms": [
                        {
                            "party_ref": "party_demo_uc2_client",
                            "role": "prospective_client",
                            "party_category": "company",
                        }
                    ],
                    "entity_category": "company",
                    "beneficial_owner_refs": ["bo_demo_uc2_001"],
                    "controller_refs": ["controller_demo_uc2_001"],
                    "conduct_hook_refs": [
                        "conduct_sra_identify_client_8_1",
                        "conduct_mlr_cdd_reg_27_28",
                    ],
                    "policy_snapshot_ref": "policy_snapshot:uc2:default:v1",
                },
                0.84,
            )
        case "uc2_conflict_determination":
            return (
                "Conflict evidence is clear for the local synthetic intake.",
                "continue",
                {
                    "conflict_determination_ref": "conflict_determination_demo_uc2_001",
                    "conflict_status": "no_conflict",
                    "confidentiality_safeguard_status": "not_required",
                    "aml_risk_rating": "standard",
                    "conduct_hook_refs": [
                        "conduct_sra_conflict_6_1_6_2",
                        "conduct_sra_confidentiality_6_3_6_5",
                    ],
                    "policy_snapshot_ref": "policy_snapshot:uc2:default:v1",
                },
                0.87,
            )
        case "uc2_engagement_decision":
            return (
                "Engagement can proceed subject to the approval-gated send path.",
                "continue",
                {
                    "engagement_decision_ref": "engagement_decision_demo_uc2_001",
                    "engagement_outcome": "accept_for_engagement",
                    "approval_package_ref": "approval_demo_uc2_001",
                    "prospective_client_ref": "prospective_client_demo_uc2_001",
                    "matter_scope_ref": "matter_scope_demo_uc2_001",
                    "scope_summary_ref": "scope_summary_demo_uc2_001",
                    "conflict_determination_ref": "conflict_determination_demo_uc2_001",
                    "aml_risk_assessment_ref": "aml_risk_demo_uc2_001",
                    "conduct_hook_refs": [
                        "conduct_sra_identify_client_8_1",
                        "conduct_sra_conflict_6_1_6_2",
                        "conduct_mlr_cdd_reg_27_28",
                        "conduct_sra_accountability_7_1_7_2",
                    ],
                    "policy_snapshot_ref": "policy_snapshot:uc2:default:v1",
                },
                0.86,
            )
        case _:
            return (
                "Input accepted for UC1 processing.",
                "continue",
                {"classification": "enquiry"},
                0.88,
            )


def _safe_response_schema_metadata(response_shape: dict[str, Any] | None) -> dict[str, Any]:
    if response_shape is None:
        return {}
    schema = response_shape.get("schema")
    if not isinstance(schema, dict):
        return {}
    metadata: dict[str, Any] = {"response_schema": {}}
    response_schema = cast(dict[str, Any], metadata["response_schema"])
    for key in ("name", "contract_ref", "task_kind", "source"):
        value = response_shape.get(key)
        if isinstance(value, str) and value:
            response_schema[key] = value
    response_schema["strict"] = bool(response_shape.get("strict", False))
    response_schema["hash"] = _schema_hash(cast(dict[str, Any], schema))
    response_schema["response_format_type"] = "recorded_replay"
    return metadata


def _normalise_structured_data_for_shape(
    structured_data: dict[str, Any],
    response_shape: dict[str, Any],
) -> dict[str, Any]:
    schema_obj = response_shape.get("schema")
    if not isinstance(schema_obj, dict):
        return structured_data
    schema = cast(dict[str, Any], schema_obj)
    properties_obj = schema.get("properties")
    if not isinstance(properties_obj, dict):
        return structured_data
    properties = cast(dict[str, Any], properties_obj)
    structured_schema_obj = properties.get("structured_data")
    if not isinstance(structured_schema_obj, dict):
        return structured_data
    structured_schema = cast(dict[str, Any], structured_schema_obj)
    normalised = _normalise_for_schema(structured_data, structured_schema)
    return cast(dict[str, Any], normalised) if isinstance(normalised, dict) else structured_data


def _normalise_for_schema(value: Any, schema: dict[str, Any]) -> Any:
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        if value is None and "null" in schema_type:
            return None
        schema_types = [str(item) for item in cast(list[object], schema_type)]
        non_null_types = [item for item in schema_types if item != "null"]
        if non_null_types:
            return _normalise_for_schema(value, {**schema, "type": non_null_types[0]})
        return value

    if schema_type == "object":
        raw = cast(dict[str, Any], value) if isinstance(value, dict) else {}
        properties_obj = schema.get("properties")
        if not isinstance(properties_obj, dict):
            return raw
        properties = cast(dict[str, Any], properties_obj)
        normalised: dict[str, Any] = {}
        for key, field_schema_obj in properties.items():
            if isinstance(field_schema_obj, dict):
                field_schema = cast(dict[str, Any], field_schema_obj)
                normalised[str(key)] = _normalise_for_schema(raw.get(str(key)), field_schema)
        return normalised

    if value is None:
        return None
    return value


def _schema_hash(schema: dict[str, Any]) -> str:
    schema_json = json.dumps(schema, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(schema_json.encode("utf-8")).hexdigest()


def _terminal_route_qualification_result(
    category: str,
) -> tuple[str, str, dict[str, Any], float]:
    structured_data = {
        "qualification_verdict_category": category,
        "conduct_hooks_pass": True,
        "customer_ref": "cust_demo_001",
        "verdict_ref": f"verdict_demo_{category}_001",
        "routing_policy_ref": "policy_uc1_routing_v1",
        "best_interests_check": {
            "status": "pass",
            "regulatory_ref": "ICOBS 2.5.-1R",
        },
        "demands_and_needs_statement": {
            "captured": True,
            "regulatory_ref": "ICOBS 5",
            "summary": "Customer seeks personal-lines cover within the UC1 sandbox scope.",
        },
        "target_market_check": {
            "status": "pass" if category != "decline" else "out_of_market",
            "regulatory_ref": "PROD 4",
        },
        "foreseeable_harm_check": {
            "status": "no_harm_identified",
            "regulatory_ref": "Consumer Duty PRIN 12",
        },
        "policy_snapshot_ref": "policy_snapshot:uc1:default:v1",
    }
    match category:
        case "accept":
            structured_data.update(
                {
                    "product_family_category": "motor_private_car",
                    "qualification_summary_ref": "qsum_demo_accept_001",
                    "rationale": (
                        "All four UC1 conduct hooks pass; route to the broker-firm quoting queue."
                    ),
                }
            )
            return (
                "Enquiry passes UC1 conduct hooks and routes to the quoting queue.",
                "continue",
                structured_data,
                0.88,
            )
        case "refer":
            structured_data.update(
                {
                    "referral_destination_category": "internal_complex_risk_desk",
                    "referral_reason_category": "complex_risk_outside_appetite",
                    "rationale": (
                        "UC1 conduct hooks require specialist review; route to the referral inbox."
                    ),
                }
            )
            return (
                "Enquiry is referable and routes to the specialist referral inbox.",
                "continue",
                structured_data,
                0.86,
            )
        case "decline":
            structured_data.update(
                {
                    "decline_reason_category": "outside_product_target_market",
                    "rationale": (
                        "Target-market evidence does not support quotation; record the "
                        "decline through the decline ledger."
                    ),
                }
            )
            return (
                "Enquiry is outside target market and routes to the decline ledger.",
                "continue",
                structured_data,
                0.87,
            )
        case _:
            raise LLMProviderInvocationError(
                route_id="recorded-replay",
                reason=f"unsupported_terminal_route_fixture:{category}",
                retryable=False,
            )


def _terminal_route_fixture_category(agent_input: dict[str, Any]) -> str | None:
    subject = str(agent_input.get("enquiry_subject", "")).lower()
    body = str(agent_input.get("enquiry_body_text", "")).lower()
    marker_text = f"{subject}\n{body}"
    if "accepted-routing fixture" in marker_text:
        return "accept"
    if "referred-routing fixture" in marker_text:
        return "refer"
    if "declined-routing fixture" in marker_text:
        return "decline"
    return None


def _is_deeper_context_fixture(agent_input: dict[str, Any]) -> bool:
    body = str(agent_input.get("enquiry_body_text", "")).lower()
    subject = str(agent_input.get("enquiry_subject", "")).lower()
    return "deeper-context fixture" in body or "deeper-context fixture" in subject


def _is_validator_redraft_fixture(agent_input: dict[str, Any]) -> bool:
    subject = str(agent_input.get("enquiry_subject", "")).lower()
    body = str(agent_input.get("enquiry_body_text", "")).lower()
    return "validator-redraft fixture" in subject or "validator-redraft fixture" in body


def _is_retry_exhaustion_fixture(agent_input: dict[str, Any]) -> bool:
    subject = str(agent_input.get("enquiry_subject", "")).lower()
    body = str(agent_input.get("enquiry_body_text", "")).lower()
    return "retry-exhaustion fixture" in subject or "retry-exhaustion fixture" in body

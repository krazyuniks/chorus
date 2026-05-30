"""Provider-response schemas for governed Agent Runtime invocations."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, cast

UC1_AGENT_CONTRACT_REF = "contracts/llm_provider/uc1_agent_io.schema.json"
UC2_AGENT_CONTRACT_REF = "contracts/llm_provider/uc2_agent_io.schema.json"
UC3_AGENT_CONTRACT_REF = "contracts/llm_provider/uc3_agent_io.schema.json"
UC1_RESPONSE_SCHEMA_SOURCE = "agent-runtime.uc1.response-schema.v1"
UC2_RESPONSE_SCHEMA_SOURCE = "agent-runtime.uc2.response-schema.v1"
UC3_RESPONSE_SCHEMA_SOURCE = "agent-runtime.uc3.response-schema.v1"


def uc1_response_shape_for_task(task_kind: str) -> dict[str, Any]:
    """Return the provider-neutral response shape for a UC1 task kind."""

    spec = _UC1_TASK_SPECS.get(task_kind)
    if spec is None:
        raise ValueError(f"Unsupported UC1 response schema task kind {task_kind!r}")

    schema = _top_level_response_schema(
        structured_data_schema=spec["structured_data_schema"],
        recommended_next_steps=cast(tuple[str, ...], spec["recommended_next_steps"]),
    )
    shape: dict[str, Any] = {
        "name": f"uc1_{task_kind}_response",
        "contract_ref": UC1_AGENT_CONTRACT_REF,
        "task_kind": task_kind,
        "schema": schema,
        "strict": True,
        "source": UC1_RESPONSE_SCHEMA_SOURCE,
    }
    return copy.deepcopy(shape)


def uc2_response_shape_for_task(task_kind: str) -> dict[str, Any]:
    """Return the provider-neutral response shape for a UC2 task kind."""

    spec = _UC2_TASK_SPECS.get(task_kind)
    if spec is None:
        raise ValueError(f"Unsupported UC2 response schema task kind {task_kind!r}")

    schema = _top_level_response_schema(
        structured_data_schema=spec["structured_data_schema"],
        recommended_next_steps=cast(tuple[str, ...], spec["recommended_next_steps"]),
    )
    shape: dict[str, Any] = {
        "name": f"uc2_{task_kind}_response",
        "contract_ref": UC2_AGENT_CONTRACT_REF,
        "task_kind": task_kind,
        "schema": schema,
        "strict": True,
        "source": UC2_RESPONSE_SCHEMA_SOURCE,
    }
    return copy.deepcopy(shape)


def uc3_response_shape_for_task(task_kind: str) -> dict[str, Any]:
    """Return the provider-neutral response shape for a UC3 task kind."""

    spec = _UC3_TASK_SPECS.get(task_kind)
    if spec is None:
        raise ValueError(f"Unsupported UC3 response schema task kind {task_kind!r}")

    schema = _top_level_response_schema(
        structured_data_schema=spec["structured_data_schema"],
        recommended_next_steps=cast(tuple[str, ...], spec["recommended_next_steps"]),
    )
    shape: dict[str, Any] = {
        "name": f"uc3_{task_kind}_response",
        "contract_ref": UC3_AGENT_CONTRACT_REF,
        "task_kind": task_kind,
        "schema": schema,
        "strict": True,
        "source": UC3_RESPONSE_SCHEMA_SOURCE,
    }
    return copy.deepcopy(shape)


def response_shape_instruction(response_shape: dict[str, Any]) -> str:
    """Build the bounded JSON-only instruction sent with a response shape."""

    schema = _response_schema(response_shape)
    name = _shape_string(response_shape, "name")
    example = _example_from_schema(schema)
    return (
        "Return JSON only. Do not include markdown, commentary, or prose outside "
        f"the JSON object. The JSON object must match response schema `{name}`. "
        "The `structured_data` object must include at least one non-null value. "
        "Use null for unavailable nullable fields rather than omitting required "
        "schema keys.\n"
        f"Example JSON object: {_compact_json(example)}\n"
        f"JSON Schema: {_compact_json(schema)}"
    )


def response_shape_metadata(response_shape: dict[str, Any]) -> dict[str, Any]:
    """Return safe response-schema metadata for decision trail and transcripts."""

    schema = _response_schema(response_shape)
    return {
        "response_schema.name": _shape_string(response_shape, "name"),
        "response_schema.contract_ref": _shape_string(response_shape, "contract_ref"),
        "response_schema.task_kind": _shape_string(response_shape, "task_kind"),
        "response_schema.strict": bool(response_shape.get("strict", False)),
        "response_schema.hash": _schema_hash(schema),
        "response_schema.source": _shape_string(response_shape, "source"),
    }


def _top_level_response_schema(
    *,
    structured_data_schema: dict[str, Any],
    recommended_next_steps: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "summary",
            "confidence",
            "structured_data",
            "recommended_next_step",
            "rationale",
        ],
        "properties": {
            "summary": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "structured_data": structured_data_schema,
            "recommended_next_step": {
                "type": "string",
                "enum": list(recommended_next_steps),
            },
            "rationale": {"type": "string"},
        },
    }


def _object_schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def _nullable(type_name: str) -> dict[str, Any]:
    return {"type": [type_name, "null"]}


def _nullable_string_array() -> dict[str, Any]:
    return {"type": ["array", "null"], "items": {"type": "string"}}


def _nullable_object_array() -> dict[str, Any]:
    return {"type": ["array", "null"], "items": {"type": "object"}}


def _conduct_status_schema() -> dict[str, Any]:
    return _object_schema(
        {
            "status": _nullable("string"),
            "regulatory_ref": _nullable("string"),
            "summary": _nullable("string"),
        }
    )


def _demands_and_needs_schema() -> dict[str, Any]:
    return _object_schema(
        {
            "captured": _nullable("boolean"),
            "regulatory_ref": _nullable("string"),
            "summary": _nullable("string"),
        }
    )


def _validation_reason_schema() -> dict[str, Any]:
    return _object_schema(
        {
            "code": _nullable("string"),
            "missing_elements": _nullable_string_array(),
            "guidance": _nullable("string"),
        }
    )


_UC1_TASK_SPECS: dict[str, dict[str, Any]] = {
    "enquiry_classification": {
        "recommended_next_steps": ("continue", "deeper_context", "escalate"),
        "structured_data_schema": _object_schema(
            {
                "product_family_category": _nullable("string"),
                "demanded_cover_shape": _nullable("string"),
                "classification_attempt": _nullable("integer"),
                "deeper_context_completed": _nullable("boolean"),
            }
        ),
    },
    "context_gathering": {
        "recommended_next_steps": ("continue", "deeper_context", "escalate"),
        "structured_data_schema": _object_schema(
            {
                "demands_and_needs_summary": _nullable("string"),
                "missing_data_fields": _nullable_string_array(),
                "customer_ref": _nullable("string"),
                "product_catalogue_ref": _nullable("string"),
            }
        ),
    },
    "enquiry_qualification": {
        "recommended_next_steps": ("continue", "propose", "send", "escalate", "reject"),
        "structured_data_schema": _object_schema(
            {
                "qualification_verdict_category": {
                    "type": "string",
                    "enum": ["accept", "refer", "decline", "missing_data"],
                },
                "missing_data_request_required": _nullable("boolean"),
                "conduct_hooks_pass": _nullable("boolean"),
                "best_interests_check": _conduct_status_schema(),
                "demands_and_needs_statement": _demands_and_needs_schema(),
                "target_market_check": _conduct_status_schema(),
                "foreseeable_harm_check": _conduct_status_schema(),
                "policy_snapshot_ref": _nullable("string"),
                "customer_ref": _nullable("string"),
                "verdict_ref": _nullable("string"),
                "routing_policy_ref": _nullable("string"),
                "product_family_category": _nullable("string"),
                "qualification_summary_ref": _nullable("string"),
                "referral_destination_category": _nullable("string"),
                "referral_reason_category": _nullable("string"),
                "decline_reason_category": _nullable("string"),
            }
        ),
    },
    "missing_data_request_draft": {
        "recommended_next_steps": ("continue", "propose", "escalate"),
        "structured_data_schema": _object_schema(
            {
                "draft_body_text": _nullable("string"),
                "customer_ref": _nullable("string"),
                "missing_data_request_ref": _nullable("string"),
                "redraft_attempt": _nullable("integer"),
            }
        ),
    },
    "missing_data_request_validation": {
        "recommended_next_steps": ("send", "redraft", "escalate"),
        "structured_data_schema": _object_schema(
            {
                "validation": {
                    "type": "string",
                    "enum": ["approved", "redraft_requested", "rejected", "needs_escalation"],
                },
                "reason": _validation_reason_schema(),
                "redraft_attempt": _nullable("integer"),
                "redraft_completed": _nullable("boolean"),
            }
        ),
    },
}


_UC2_TASK_SPECS: dict[str, dict[str, Any]] = {
    "uc2_matter_classification": {
        "recommended_next_steps": ("continue", "manual_review", "escalate"),
        "structured_data_schema": _object_schema(
            {
                "matter_type": _nullable("string"),
                "matter_scope_ref": _nullable("string"),
                "jurisdiction_categories": _nullable_string_array(),
                "conduct_hook_refs": _nullable_string_array(),
                "policy_snapshot_ref": _nullable("string"),
            }
        ),
    },
    "uc2_party_extraction": {
        "recommended_next_steps": ("continue", "manual_review", "escalate"),
        "structured_data_schema": _object_schema(
            {
                "party_graph_ref": _nullable("string"),
                "prospective_client_ref": _nullable("string"),
                "authority_status": _nullable("string"),
                "party_graph_ambiguous": _nullable("boolean"),
                "party_search_terms": _nullable_object_array(),
                "entity_category": _nullable("string"),
                "beneficial_owner_refs": _nullable_string_array(),
                "controller_refs": _nullable_string_array(),
                "conduct_hook_refs": _nullable_string_array(),
                "policy_snapshot_ref": _nullable("string"),
            }
        ),
    },
    "uc2_conflict_determination": {
        "recommended_next_steps": ("continue", "manual_review", "escalate"),
        "structured_data_schema": _object_schema(
            {
                "conflict_determination_ref": _nullable("string"),
                "conflict_status": _nullable("string"),
                "confidentiality_safeguard_status": _nullable("string"),
                "aml_risk_rating": _nullable("string"),
                "conduct_hook_refs": _nullable_string_array(),
                "policy_snapshot_ref": _nullable("string"),
            }
        ),
    },
    "uc2_engagement_decision": {
        "recommended_next_steps": ("continue", "manual_review", "escalate"),
        "structured_data_schema": _object_schema(
            {
                "engagement_decision_ref": _nullable("string"),
                "engagement_outcome": _nullable("string"),
                "approval_package_ref": _nullable("string"),
                "prospective_client_ref": _nullable("string"),
                "instructing_contact_ref": _nullable("string"),
                "authority_status": _nullable("string"),
                "matter_scope_ref": _nullable("string"),
                "scope_summary_ref": _nullable("string"),
                "conflict_determination_ref": _nullable("string"),
                "conflict_status": _nullable("string"),
                "confidentiality_safeguard_status": _nullable("string"),
                "cdd_record_ref": _nullable("string"),
                "cdd_status": _nullable("string"),
                "beneficial_ownership_status": _nullable("string"),
                "aml_risk_assessment_ref": _nullable("string"),
                "aml_risk_rating": _nullable("string"),
                "review_reason_category": _nullable("string"),
                "decline_reason_category": _nullable("string"),
                "conduct_hook_refs": _nullable_string_array(),
                "policy_snapshot_ref": _nullable("string"),
            }
        ),
    },
}


_UC3_TASK_SPECS: dict[str, dict[str, Any]] = {
    "uc3_advice_scope_classification": {
        "recommended_next_steps": ("continue", "manual_review", "escalate"),
        "structured_data_schema": _object_schema(
            {
                "advice_scope_ref": _nullable("string"),
                "advice_scope": _nullable("string"),
                "client_category": _nullable("string"),
                "authority_status": _nullable("string"),
                "conduct_hook_refs": _nullable_string_array(),
                "policy_snapshot_ref": _nullable("string"),
            }
        ),
    },
    "uc3_fact_find_summary": {
        "recommended_next_steps": (
            "continue",
            "manual_review",
            "fact_find_incomplete",
            "escalate",
        ),
        "structured_data_schema": _object_schema(
            {
                "fact_find_summary_ref": _nullable("string"),
                "fact_find_completeness": _nullable("string"),
                "objective_refs": _nullable_string_array(),
                "knowledge_experience_ref": _nullable("string"),
                "prospective_retail_client_ref": _nullable("string"),
                "financial_situation_ref": _nullable("string"),
                "questionnaire_bundle_ref": _nullable("string"),
                "risk_preference_band": _nullable("string"),
                "time_horizon_band": _nullable("string"),
                "liquidity_need_category": _nullable("string"),
                "dependency_context_refs": _nullable_string_array(),
                "product_candidate_refs": _nullable_string_array(),
                "conduct_hook_refs": _nullable_string_array(),
                "policy_snapshot_ref": _nullable("string"),
            }
        ),
    },
    "uc3_risk_profile_assessment": {
        "recommended_next_steps": (
            "continue",
            "approval_required",
            "manual_review",
            "escalate",
        ),
        "structured_data_schema": _object_schema(
            {
                "risk_profile_ref": _nullable("string"),
                "risk_profile_status": _nullable("string"),
                "approval_required": _nullable("boolean"),
                "risk_context_categories": _nullable_string_array(),
                "product_universe_scope": _nullable("string"),
                "draft_basis_categories": _nullable_string_array(),
                "conduct_hook_refs": _nullable_string_array(),
                "policy_snapshot_ref": _nullable("string"),
            }
        ),
    },
    "uc3_consumer_duty_support_assessment": {
        "recommended_next_steps": (
            "continue",
            "approval_required",
            "manual_review",
            "escalate",
        ),
        "structured_data_schema": _object_schema(
            {
                "support_assessment_ref": _nullable("string"),
                "support_status": _nullable("string"),
                "vulnerability_marker_categories": _nullable_string_array(),
                "approval_required": _nullable("boolean"),
                "consumer_understanding_check_ref": _nullable("string"),
                "conduct_hook_refs": _nullable_string_array(),
                "policy_snapshot_ref": _nullable("string"),
            }
        ),
    },
    "uc3_suitability_conclusion": {
        "recommended_next_steps": ("continue", "manual_review", "escalate"),
        "structured_data_schema": _object_schema(
            {
                "suitability_conclusion_ref": _nullable("string"),
                "suitability_outcome": _nullable("string"),
                "suitability_report_ref": _nullable("string"),
                "report_summary_ref": _nullable("string"),
                "approval_package_ref": _nullable("string"),
                "adviser_approval_ref": _nullable("string"),
                "consumer_understanding_check_ref": _nullable("string"),
                "prospective_retail_client_ref": _nullable("string"),
                "issue_channel_category": _nullable("string"),
                "decline_reason_category": _nullable("string"),
                "review_reason_category": _nullable("string"),
                "conduct_hook_refs": _nullable_string_array(),
                "policy_snapshot_ref": _nullable("string"),
            }
        ),
    },
}


def _response_schema(response_shape: dict[str, Any]) -> dict[str, Any]:
    schema = response_shape.get("schema")
    if not isinstance(schema, dict):
        raise ValueError("response shape missing JSON schema object")
    return cast(dict[str, Any], schema)


def _shape_string(response_shape: dict[str, Any], key: str) -> str:
    value = response_shape.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"response shape missing string {key!r}")
    return value


def _schema_hash(schema: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_compact_json(schema).encode("utf-8")).hexdigest()


def _compact_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _example_from_schema(schema: dict[str, Any]) -> Any:
    enum_values_obj = schema.get("enum")
    if isinstance(enum_values_obj, list) and enum_values_obj:
        enum_values = cast(list[Any], enum_values_obj)
        return enum_values[0]

    schema_type = schema.get("type")
    if isinstance(schema_type, list) and "null" in schema_type:
        non_null_types = [str(value) for value in cast(list[Any], schema_type) if value != "null"]
        if not non_null_types:
            return None
        return _example_from_schema({**schema, "type": non_null_types[0]})
    if schema_type == "object":
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            return {}
        return {
            str(key): _example_from_schema(cast(dict[str, Any], value))
            for key, value in cast(dict[str, Any], properties).items()
        }
    if schema_type == "array":
        return []
    if schema_type == "string":
        return "value"
    if schema_type == "number":
        return 0.5
    if schema_type == "integer":
        return 1
    if schema_type == "boolean":
        return False
    return None


__all__ = [
    "UC1_AGENT_CONTRACT_REF",
    "UC1_RESPONSE_SCHEMA_SOURCE",
    "UC2_AGENT_CONTRACT_REF",
    "UC2_RESPONSE_SCHEMA_SOURCE",
    "UC3_AGENT_CONTRACT_REF",
    "UC3_RESPONSE_SCHEMA_SOURCE",
    "response_shape_instruction",
    "response_shape_metadata",
    "uc1_response_shape_for_task",
    "uc2_response_shape_for_task",
    "uc3_response_shape_for_task",
]

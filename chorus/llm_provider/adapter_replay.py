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
            provider_metadata={"adapter": ADAPTER_VERSION},
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
            return (
                "Enquiry passes UC1 conduct hooks and proceeds with a missing-data request.",
                "continue",
                {
                    "qualification_verdict_category": "accept",
                    "conduct_hooks_pass": True,
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
        case _:
            return (
                "Input accepted for UC1 processing.",
                "continue",
                {"classification": "enquiry"},
                0.88,
            )


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

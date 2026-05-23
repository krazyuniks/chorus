"""Deterministic recorded/replay adapter behind the LLM provider port.

Produces stable structured outputs so ``just eval`` and ``just test`` stay
green between checkpoints B and G - the eval reshape (ADR 0019) introduces
the captured-transcript replay subcommand and retires the
path-enumeration fixtures. Until then this adapter is the deterministic
substrate the route catalogue selects in tests and eval.

The shape mirrors the pre-reset local Lighthouse boundary so the existing
eval fixtures continue to match. Branch fixtures (low-confidence research,
validator redraft, retry exhaustion) are detected from the input payload
metadata that the runtime passes through.
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
        case "company_research":
            if _is_retry_exhaustion_fixture(agent_input):
                raise LLMProviderInvocationError(
                    route_id="recorded-replay",
                    reason="retry_exhaustion_fixture_forced_failure",
                )
            if _is_low_confidence_research_fixture(agent_input):
                attempt = int(agent_input.get("research_attempt", 1))
                if attempt == 1:
                    return (
                        "Initial company research found ambiguous context and needs "
                        "deeper research.",
                        "deeper_research",
                        {
                            "company_name": "Unknown field services lead",
                            "fit": "requires_more_evidence",
                            "research_attempt": attempt,
                        },
                        0.42,
                    )
                return (
                    "Deeper research resolved the company context for the lead.",
                    "continue",
                    {
                        "company_name": "Acme Field Services",
                        "fit": "operations automation",
                        "research_attempt": attempt,
                        "deeper_research_completed": True,
                    },
                    0.86,
                )
            return (
                "Identified a small operations-led services business from the lead email.",
                "continue",
                {"company_name": "Acme Field Services", "fit": "operations automation"},
                0.88,
            )
        case "lead_qualification":
            return (
                "Lead qualifies for a lightweight Lighthouse pilot conversation.",
                "continue",
                {"qualification": "qualified", "priority": "normal"},
                0.88,
            )
        case "response_draft":
            if _is_validator_redraft_fixture(agent_input):
                attempt = int(agent_input.get("redraft_attempt", 1))
                if attempt == 1:
                    return (
                        "Initial draft offered a generic acknowledgement only.",
                        "continue",
                        {
                            "draft_response": (
                                "Thanks for getting in touch. We will be back in contact shortly."
                            ),
                            "redraft_attempt": attempt,
                        },
                        0.88,
                    )
                return (
                    "Redrafted response now offers an operations-led pilot and discovery call.",
                    "continue",
                    {
                        "draft_response": (
                            "Thanks for getting in touch. We would like to suggest "
                            "a lightweight operations-led pilot and a 30-minute "
                            "discovery call to scope your inbound enquiry handling."
                        ),
                        "redraft_attempt": attempt,
                        "applied_validator_reason": (agent_input.get("validator_reason", {}) or {}),
                    },
                    0.88,
                )
            return (
                "Drafted a concise response proposing a discovery call and pilot outline.",
                "continue",
                {
                    "draft_response": (
                        "Thanks for getting in touch. A lightweight pilot could qualify "
                        "new enquiries, research company context, and prepare response "
                        "drafts for your account team to review."
                    )
                },
                0.88,
            )
        case "response_validation":
            if _is_validator_redraft_fixture(agent_input):
                attempt = int(agent_input.get("redraft_attempt", 1))
                if attempt == 1:
                    return (
                        "Draft missed the requested operations-pilot framing; "
                        "validator requested redraft.",
                        "redraft",
                        {
                            "validation": "redraft_requested",
                            "redraft_attempt": attempt,
                            "reason": {
                                "code": "tone_mismatch",
                                "missing_elements": ["pilot_framing", "discovery_call_offer"],
                                "guidance": (
                                    "Reframe around an operations-led pilot and offer a "
                                    "30-minute discovery call."
                                ),
                            },
                        },
                        0.88,
                    )
                return (
                    "Redrafted response addresses the validator's pilot-framing reason.",
                    "send",
                    {
                        "validation": "approved",
                        "redraft_attempt": attempt,
                        "redraft_completed": True,
                    },
                    0.88,
                )
            return (
                "Draft is suitable for proposal mode in the local sandbox.",
                "send",
                {"validation": "approved"},
                0.88,
            )
        case _:
            return (
                "Input accepted for Lighthouse processing.",
                "continue",
                {"classification": "lead"},
                0.88,
            )


def _is_low_confidence_research_fixture(agent_input: dict[str, Any]) -> bool:
    body = str(agent_input.get("lead_body", "")).lower()
    subject = str(agent_input.get("lead_subject", "")).lower()
    return "low-confidence research fixture" in body or "low-confidence research" in subject


def _is_validator_redraft_fixture(agent_input: dict[str, Any]) -> bool:
    subject = str(agent_input.get("lead_subject", "")).lower()
    body = str(agent_input.get("lead_body", "")).lower()
    return "validator-redraft fixture" in subject or "validator-redraft fixture" in body


def _is_retry_exhaustion_fixture(agent_input: dict[str, Any]) -> bool:
    subject = str(agent_input.get("lead_subject", "")).lower()
    body = str(agent_input.get("lead_body", "")).lower()
    return "retry-exhaustion fixture" in subject or "retry-exhaustion fixture" in body

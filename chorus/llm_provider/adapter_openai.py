"""OpenAI-SDK-compatible adapter behind the LLM provider port.

The OpenAI Python SDK is treated as a transport against any
OpenAI-compatible chat-completions endpoint (ADR 0018). The adapter is
provider-agnostic by construction: base URL, API key, model, and
provider-specific parameters are configuration, not code.

This adapter is the only place in the codebase that may import the openai
SDK. Domain callers go through the LLM provider port; the adapter is
selected by the route catalogue.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast

from chorus.llm_provider.port import (
    InvocationArgs,
    InvocationMessage,
    InvocationResult,
    LLMProviderInvocationError,
)

ADAPTER_VERSION = "openai-compatible-v1"


@dataclass
class OpenAICompatibleAdapter:
    """Thin SDK-backed adapter for any OpenAI-compatible endpoint."""

    base_url: str
    api_key_env: str
    adapter_version: str = ADAPTER_VERSION

    def invoke(self, args: InvocationArgs) -> InvocationResult:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise LLMProviderInvocationError(
                route_id=args.route_id,
                reason=f"missing_api_key:{self.api_key_env}",
                retryable=False,
            )

        try:
            from openai import OpenAI  # type: ignore[reportMissingImports]
        except ImportError as exc:  # pragma: no cover - dependency must be installed
            raise LLMProviderInvocationError(
                route_id=args.route_id,
                reason=f"openai_sdk_unavailable:{exc}",
                retryable=False,
            ) from exc

        client = cast(Any, OpenAI(base_url=self.base_url, api_key=api_key))
        model = args.metadata.get("model_id")
        if not isinstance(model, str):
            raise LLMProviderInvocationError(
                route_id=args.route_id, reason="missing_model_id", retryable=False
            )

        payload: dict[str, Any] = {
            "model": model,
            "messages": [_message_payload(message) for message in args.messages],
        }
        parameters = args.metadata.get("parameters", {})
        if isinstance(parameters, dict):
            payload.update(cast(dict[str, Any], parameters))
        if args.tool_specs:
            payload["tools"] = list(args.tool_specs)
        if args.response_shape is not None:
            payload["response_format"] = args.response_shape

        try:
            response = client.chat.completions.create(**payload)
        except Exception as exc:  # pragma: no cover - provider exercise belongs in integration
            raise LLMProviderInvocationError(
                route_id=args.route_id,
                reason=f"provider_error:{exc.__class__.__name__}",
            ) from exc

        return _result_from_response(response)


def _message_payload(message: InvocationMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_call_id is not None:
        payload["tool_call_id"] = message.tool_call_id
    if message.name is not None:
        payload["name"] = message.name
    return payload


def _result_from_response(response: Any) -> InvocationResult:
    choice = response.choices[0]
    message_content = getattr(choice.message, "content", "") or ""
    usage = getattr(response, "usage", None)
    token_usage: dict[str, int] = {}
    if usage is not None:
        for field_name in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = getattr(usage, field_name, None)
            if isinstance(value, int):
                token_usage[field_name] = value
    return InvocationResult(
        summary=message_content,
        structured_data={},
        confidence=0.0,
        recommended_next_step="continue",
        rationale=message_content,
        cost_amount_usd=Decimal("0.000000"),
        token_usage=token_usage,
        provider_metadata={
            "response_id": getattr(response, "id", None),
            "model": getattr(response, "model", None),
        },
    )

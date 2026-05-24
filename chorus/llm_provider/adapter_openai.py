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

import hashlib
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, cast

from jsonschema import Draft202012Validator

from chorus.llm_provider.port import (
    InvocationArgs,
    InvocationMessage,
    InvocationResult,
    LLMProviderInvocationError,
)

ADAPTER_VERSION = "openai-compatible-v2"
type ResponseFormatMode = Literal["json_schema", "json_object"]


@dataclass
class OpenAICompatibleAdapter:
    """Thin SDK-backed adapter for any OpenAI-compatible endpoint."""

    base_url: str
    api_key_env: str
    response_format_mode: ResponseFormatMode = "json_schema"
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
            payload["response_format"] = _response_format_payload(
                args.response_shape,
                self.response_format_mode,
            )

        try:
            response = client.chat.completions.create(**payload)
        except Exception as exc:  # pragma: no cover - provider exercise belongs in integration
            raise LLMProviderInvocationError(
                route_id=args.route_id,
                reason=f"provider_error:{exc.__class__.__name__}",
            ) from exc

        return _result_from_response(
            response,
            args=args,
            response_format_mode=self.response_format_mode,
        )


def _message_payload(message: InvocationMessage) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_call_id is not None:
        payload["tool_call_id"] = message.tool_call_id
    if message.name is not None:
        payload["name"] = message.name
    return payload


def _result_from_response(
    response: Any,
    *,
    args: InvocationArgs,
    response_format_mode: ResponseFormatMode,
) -> InvocationResult:
    choice = _first_choice(response, args.route_id)
    message = getattr(choice, "message", None)
    if message is None:
        raise LLMProviderInvocationError(
            route_id=args.route_id,
            reason="malformed_provider_response:no_message",
            retryable=False,
        )
    refusal = getattr(message, "refusal", None)
    if refusal:
        raise LLMProviderInvocationError(
            route_id=args.route_id,
            reason="provider_refusal",
            retryable=False,
        )
    message_content = getattr(message, "content", "") or ""
    usage = getattr(response, "usage", None)
    token_usage: dict[str, int] = {}
    if usage is not None:
        for field_name in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = getattr(usage, field_name, None)
            if isinstance(value, int):
                token_usage[field_name] = value

    if args.response_shape is None:
        return InvocationResult(
            summary=message_content,
            structured_data={},
            confidence=0.0,
            recommended_next_step="continue",
            rationale=message_content,
            cost_amount_usd=Decimal("0.000000"),
            raw_messages=(InvocationMessage(role="assistant", content=message_content),),
            token_usage=token_usage,
            provider_metadata={
                "response_id": getattr(response, "id", None),
                "model": getattr(response, "model", None),
            },
        )

    parsed = _parse_structured_response_content(
        route_id=args.route_id,
        content=message_content,
        response_shape=args.response_shape,
    )
    return InvocationResult(
        summary=cast(str, parsed["summary"]),
        structured_data=cast(dict[str, Any], parsed["structured_data"]),
        confidence=float(parsed["confidence"]),
        recommended_next_step=cast(str, parsed["recommended_next_step"]),
        rationale=cast(str, parsed["rationale"]),
        cost_amount_usd=Decimal("0.000000"),
        raw_messages=(InvocationMessage(role="assistant", content=message_content),),
        token_usage=token_usage,
        provider_metadata={
            "response_id": getattr(response, "id", None),
            "model": getattr(response, "model", None),
            "response_schema": _safe_response_schema_metadata(
                args.response_shape,
                response_format_mode,
            ),
        },
    )


def _first_choice(response: Any, route_id: str) -> Any:
    choices_obj = getattr(response, "choices", None)
    if (
        not isinstance(choices_obj, Sequence)
        or isinstance(choices_obj, str | bytes)
        or not choices_obj
    ):
        raise LLMProviderInvocationError(
            route_id=route_id,
            reason="malformed_provider_response:no_choices",
            retryable=False,
        )
    choices = cast(Sequence[Any], choices_obj)
    return choices[0]


def _response_format_payload(
    response_shape: dict[str, Any],
    mode: ResponseFormatMode,
) -> dict[str, Any]:
    if mode == "json_object":
        return {"type": "json_object"}
    return {
        "type": "json_schema",
        "json_schema": {
            "name": _response_shape_string(response_shape, "name"),
            "schema": _response_schema(response_shape),
            "strict": bool(response_shape.get("strict", True)),
        },
    }


def _parse_structured_response_content(
    *,
    route_id: str,
    content: str,
    response_shape: dict[str, Any],
) -> dict[str, Any]:
    if not content.strip():
        raise LLMProviderInvocationError(
            route_id=route_id,
            reason="empty_provider_response",
            retryable=False,
        )
    try:
        parsed_obj = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMProviderInvocationError(
            route_id=route_id,
            reason="malformed_structured_data_json",
            retryable=False,
        ) from exc
    if not isinstance(parsed_obj, dict):
        raise LLMProviderInvocationError(
            route_id=route_id,
            reason="malformed_structured_data_object",
            retryable=False,
        )
    parsed = cast(dict[str, Any], parsed_obj)
    data = parsed.get("structured_data")
    if not isinstance(data, dict) or not _contains_non_empty_value(data):
        raise LLMProviderInvocationError(
            route_id=route_id,
            reason="empty_structured_data",
            retryable=False,
        )

    schema = _response_schema(response_shape)
    raw_errors = cast(Any, Draft202012Validator(schema)).iter_errors(parsed)
    errors = sorted(
        raw_errors,
        key=lambda error: tuple(str(part) for part in getattr(error, "path", ())),
    )
    if errors:
        path = ".".join(str(part) for part in getattr(errors[0], "path", ())) or "root"
        raise LLMProviderInvocationError(
            route_id=route_id,
            reason=f"structured_output_schema_violation:{path}",
            retryable=False,
        )
    return parsed


def _contains_non_empty_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_contains_non_empty_value(item) for item in cast(dict[Any, Any], value).values())
    if isinstance(value, list | tuple):
        return any(
            _contains_non_empty_value(item) for item in cast(list[Any] | tuple[Any, ...], value)
        )
    return True


def _safe_response_schema_metadata(
    response_shape: dict[str, Any],
    mode: ResponseFormatMode,
) -> dict[str, Any]:
    schema = _response_schema(response_shape)
    return {
        "name": _response_shape_string(response_shape, "name"),
        "contract_ref": _response_shape_string(response_shape, "contract_ref"),
        "task_kind": _response_shape_string(response_shape, "task_kind"),
        "strict": bool(response_shape.get("strict", True)),
        "source": _response_shape_string(response_shape, "source"),
        "hash": _schema_hash(schema),
        "response_format_type": mode,
    }


def _response_schema(response_shape: dict[str, Any]) -> dict[str, Any]:
    schema = response_shape.get("schema")
    if not isinstance(schema, dict):
        raise LLMProviderInvocationError(
            route_id=str(response_shape.get("route_id", "unknown")),
            reason="response_shape_missing_schema",
            retryable=False,
        )
    return cast(dict[str, Any], schema)


def _response_shape_string(response_shape: dict[str, Any], key: str) -> str:
    value = response_shape.get(key)
    if not isinstance(value, str) or not value:
        raise LLMProviderInvocationError(
            route_id=str(response_shape.get("route_id", "unknown")),
            reason=f"response_shape_missing_{key}",
            retryable=False,
        )
    return value


def _schema_hash(schema: dict[str, Any]) -> str:
    schema_json = json.dumps(schema, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(schema_json.encode("utf-8")).hexdigest()

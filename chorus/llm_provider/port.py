"""LLM provider port surface: structured invocation args and result."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal, Protocol, cast


@dataclass(frozen=True)
class InvocationMessage:
    """One message in the invocation message history."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: str | None = None
    name: str | None = None


@dataclass(frozen=True)
class InvocationArgs:
    """Structured arguments handed to the LLM provider port.

    Per ADR 0018 the domain core never reaches a provider SDK; it builds
    these arguments and the route catalogue's adapter does the rest. The
    fields cover the surface every provider needs: messages, optional
    structured response shape, optional tool specs.
    """

    route_id: str
    messages: tuple[InvocationMessage, ...]
    response_shape: dict[str, Any] | None = None
    tool_specs: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: cast(dict[str, Any], {}))


@dataclass(frozen=True)
class InvocationResult:
    """Structured result returned by the LLM provider port."""

    summary: str
    structured_data: dict[str, Any]
    confidence: float
    recommended_next_step: str
    rationale: str
    cost_amount_usd: Decimal
    raw_messages: tuple[InvocationMessage, ...] = ()
    tool_calls: tuple[dict[str, Any], ...] = ()
    token_usage: dict[str, int] = field(default_factory=lambda: cast(dict[str, int], {}))
    provider_metadata: dict[str, Any] = field(default_factory=lambda: cast(dict[str, Any], {}))


class LLMProviderInvocationError(RuntimeError):
    """Raised when an adapter cannot complete an invocation."""

    def __init__(self, *, route_id: str, reason: str, retryable: bool = True) -> None:
        self.route_id = route_id
        self.reason = reason
        self.retryable = retryable
        super().__init__(f"LLM provider route {route_id!r} failed: {reason}")


class LLMProviderAdapter(Protocol):
    """Transport adapter behind the LLM provider port.

    Adapters speak provider-specific transports - the OpenAI Python SDK
    pointed at any OpenAI-compatible endpoint, or a deterministic
    recorded/replay route. They never appear outside this package.
    """

    adapter_version: str

    def invoke(self, args: InvocationArgs) -> InvocationResult: ...

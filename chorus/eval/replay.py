"""`eval replay` subcommand: re-execute a captured transcript through the
recorded-replay route and verify the structured output matches the original.

ADR 0019 names replay-as-eval-substrate as the cross-provider comparison
mode. R3 ships the deterministic recorded-replay route only; cross-provider
replay (against the OpenAI-compatible adapter) is on the R4 entry list. The
subcommand shape carries the route id so R4 can plug it through without a
CLI rewrite.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chorus.agent_runtime.response_schemas import uc1_response_shape_for_task
from chorus.eval.types import EvalCheck
from chorus.llm_provider import (
    InvocationArgs,
    InvocationMessage,
    InvocationResult,
    RouteCatalogue,
    default_route_catalogue,
)

_VALID_ROLES = ("system", "user", "assistant", "tool")


def _invocation_message(message: dict[str, Any]) -> InvocationMessage:
    role = str(message["role"])
    if role not in _VALID_ROLES:
        raise ValueError(
            f"Captured transcript carries unsupported role {role!r}; expected one of {_VALID_ROLES}"
        )
    return InvocationMessage(role=role, content=str(message["content"]))


@dataclass(frozen=True)
class CapturedTranscript:
    """Captured transcript surface the replay subcommand needs.

    Aligns with :class:`AgentInvocationTranscript` (the audit-port transcript
    contract) but only carries the fields a replay re-execution needs.
    """

    invocation_id: str
    route_id: str
    provider_id: str
    model_id: str
    adapter_version: str
    parameters: dict[str, Any]
    request_messages: list[dict[str, Any]]
    expected_structured_data: dict[str, Any]
    task_kind: str
    agent_role: str
    tenant_id: str
    enquiry_input: dict[str, Any]


def load_transcript(path: Path) -> CapturedTranscript:
    """Load a captured transcript JSON fixture."""

    data = json.loads(path.read_text(encoding="utf-8"))
    return CapturedTranscript(
        invocation_id=str(data["invocation_id"]),
        route_id=str(data["route_id"]),
        provider_id=str(data["provider_id"]),
        model_id=str(data["model_id"]),
        adapter_version=str(data["adapter_version"]),
        parameters=dict(data.get("parameters", {})),
        request_messages=list(data["request_messages"]),
        expected_structured_data=dict(data["expected_structured_data"]),
        task_kind=str(data["task_kind"]),
        agent_role=str(data["agent_role"]),
        tenant_id=str(data["tenant_id"]),
        enquiry_input=dict(data["enquiry_input"]),
    )


def replay_transcript(
    transcript: CapturedTranscript,
    *,
    route_id: str | None = None,
    route_catalogue: RouteCatalogue | None = None,
) -> list[EvalCheck]:
    """Re-execute a captured transcript through the route catalogue."""

    catalogue = route_catalogue or default_route_catalogue()
    target_route = route_id or transcript.route_id
    target_entry = catalogue.get(target_route)
    if target_route == transcript.route_id and (
        target_entry.provider_id != transcript.provider_id
        or target_entry.model_id != transcript.model_id
    ):
        return [
            EvalCheck(
                "route governance alignment",
                "fail",
                (
                    f"captured route {target_route!r} records "
                    f"{transcript.provider_id!r}/{transcript.model_id!r}, but the executable "
                    f"route catalogue registers {target_entry.provider_id!r}/"
                    f"{target_entry.model_id!r}"
                ),
            )
        ]
    args = InvocationArgs(
        route_id=target_route,
        messages=tuple(_invocation_message(message) for message in transcript.request_messages),
        response_shape=uc1_response_shape_for_task(transcript.task_kind),
        metadata={
            "task_kind": transcript.task_kind,
            "input": transcript.enquiry_input,
            "agent_role": transcript.agent_role,
            "tenant_id": transcript.tenant_id,
            "model_id": target_entry.model_id,
            "parameters": {
                **target_entry.parameters,
                **transcript.parameters,
            },
        },
    )
    replay_result = catalogue.invoke(args)
    return _compare_structured_data(
        invocation_id=transcript.invocation_id,
        route_id=target_route,
        expected=transcript.expected_structured_data,
        actual=replay_result,
    )


def _compare_structured_data(
    *,
    invocation_id: str,
    route_id: str,
    expected: dict[str, Any],
    actual: InvocationResult,
) -> list[EvalCheck]:
    actual_data = dict(actual.structured_data)
    # The route_catalogue stamp is added by the runtime normaliser, not by the
    # adapter; the transcript expected_structured_data should not require it
    # because it captures the adapter's output before normalisation.
    actual_data.pop("route_catalogue", None)

    if actual_data == expected:
        return [
            EvalCheck(
                "replay stability",
                "pass",
                (
                    f"replay through route {route_id!r} for invocation {invocation_id!r} "
                    "produced the same structured output"
                ),
            )
        ]

    diffs: list[str] = []
    missing = sorted(expected.keys() - actual_data.keys())
    if missing:
        diffs.append(f"missing in replay: {missing}")
    extra = sorted(actual_data.keys() - expected.keys())
    if extra:
        diffs.append(f"extra in replay: {extra}")
    for key in sorted(expected.keys() & actual_data.keys()):
        if expected[key] != actual_data[key]:
            diffs.append(f"{key}: expected={expected[key]!r}, replayed={actual_data[key]!r}")
    return [
        EvalCheck(
            "replay stability",
            "fail",
            (
                f"replay through route {route_id!r} for invocation {invocation_id!r} "
                f"diverged from the captured transcript: {'; '.join(diffs)}"
            ),
        )
    ]


__all__ = [
    "CapturedTranscript",
    "load_transcript",
    "replay_transcript",
]

"""Contract-shaped dataclasses shared by Lighthouse workflows and activities.

The Temporal workflow imports only these small dataclasses plus the Temporal
workflow API. Generated Pydantic contract models are used inside activities,
where validation, IO, event IDs, timestamps, and persistence are allowed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

WorkflowOutcome = Literal["completed", "escalated", "failed"]


def _empty_citations() -> list[AgentCitation]:
    return []


@dataclass(frozen=True)
class LeadSender:
    display_name: str
    email: str


@dataclass(frozen=True)
class LeadAttachmentSummary:
    filename: str
    content_type: str
    size_bytes: int


@dataclass(frozen=True)
class LighthouseWorkflowInput:
    schema_version: str
    lead_id: str
    tenant_id: str
    correlation_id: str
    source: str
    message_id: str
    received_at: str
    sender: LeadSender
    recipients: list[str]
    subject: str
    body_text: str
    message_headers: dict[str, list[str]]
    attachments_summary: list[LeadAttachmentSummary]


@dataclass(frozen=True)
class WorkflowEventCommand:
    tenant_id: str
    correlation_id: str
    workflow_id: str
    lead_id: str
    sequence: int
    event_type: str
    step: str | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class WorkflowEventResult:
    event_id: str
    sequence: int
    event_type: str
    step: str | None


@dataclass(frozen=True)
class AgentInvocationRequest:
    tenant_id: str
    correlation_id: str
    workflow_id: str
    lead_id: str
    agent_role: str
    task_kind: str
    input: dict[str, Any]
    expected_output_contract: str


@dataclass(frozen=True)
class AgentCitation:
    source: str
    reference: str


@dataclass(frozen=True)
class AgentInvocationResponse:
    invocation_id: str
    summary: str
    confidence: float
    structured_data: dict[str, Any]
    recommended_next_step: str
    rationale: str
    citations: list[AgentCitation] = field(default_factory=_empty_citations)


@dataclass(frozen=True)
class ToolGatewayRequest:
    tenant_id: str
    correlation_id: str
    workflow_id: str
    invocation_id: str
    agent_id: str
    tool_name: str
    mode: str
    idempotency_key: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolGatewayResponse:
    verdict_id: str
    tool_call_id: str
    audit_event_id: str
    verdict: str
    enforced_mode: str
    reason: str
    connector_invocation_id: str | None
    output: dict[str, Any]


@dataclass(frozen=True)
class ToolFailureCompensationCommand:
    tenant_id: str
    correlation_id: str
    workflow_id: str
    lead_id: str
    invocation_id: str
    agent_id: str
    tool_name: str
    mode: str
    idempotency_key: str
    arguments: dict[str, Any]
    failure_reason: str


@dataclass(frozen=True)
class ToolFailureCompensationResult:
    audit_event_id: str
    action: str
    verdict: str
    reason: str


@dataclass(frozen=True)
class LighthouseWorkflowResult:
    workflow_id: str
    tenant_id: str
    correlation_id: str
    lead_id: str
    outcome: WorkflowOutcome
    path: list[str]
    final_summary: str
    escalation_reason: str | None = None


@dataclass(frozen=True)
class MailpitPollConfig:
    mailpit_base_url: str = "http://localhost:8025"
    temporal_target_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    task_queue: str = "lighthouse"
    tenant_id: str = "tenant_demo"
    recipient: str = "leads@chorus.local"
    page_size: int = 50


@dataclass(frozen=True)
class MailpitPollResult:
    started_workflow_ids: list[str]
    duplicate_message_ids: list[str]
    ignored_message_ids: list[str]
    parsed_message_ids: list[str]

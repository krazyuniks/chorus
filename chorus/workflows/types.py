"""Contract-shaped dataclasses shared by use-case workflows and activities.

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


def _empty_strings() -> list[str]:
    return []


@dataclass(frozen=True)
class WorkflowCorrelation:
    """Correlation context the spine carries through every primitive."""

    tenant_id: str
    correlation_id: str
    workflow_id: str
    workflow_type: str
    workflow_actor_id: str
    subject_id: str
    subject_ref: str
    subject_summary: str | None = None


@dataclass(frozen=True)
class EnquirySender:
    """Email-channel sender details preserved from intake into the workflow."""

    display_name: str
    email: str


@dataclass(frozen=True)
class EnquiryAttachmentSummary:
    """Bounded attachment metadata preserved from intake into the workflow."""

    filename: str
    content_type: str
    size_bytes: int


@dataclass(frozen=True)
class Uc1EnquiryIntake:
    """UC1 enquiry intake input.

    The R3 surface carries the email-channel shape because mailpit is the
    only working channel locally. Web-form and partner-portal channel
    contracts exist alongside (see `contracts/intake/uc1/`); their adapter
    paths land in R4. The workflow itself runs the same spine regardless of
    channel.
    """

    schema_version: str
    enquiry_id: str
    tenant_id: str
    correlation_id: str
    channel: str
    adapter_id: str
    message_id: str
    received_at: str
    from_address: EnquirySender
    to_recipients: list[str]
    subject: str
    body_text: str
    message_headers: dict[str, list[str]]
    attachments_summary: list[EnquiryAttachmentSummary]
    enquiry_ref: str


@dataclass(frozen=True)
class Uc2AttachmentSummary:
    """Bounded UC2 attachment metadata preserved from intake into the workflow."""

    attachment_ref: str
    document_category: str
    content_type: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class Uc2PartyRoleHint:
    """Safe UC2 party role hint produced by an intake adapter."""

    party_ref: str
    role: str
    party_category: str


@dataclass(frozen=True)
class Uc2LegalIntake:
    """Normalised UC2 legal-services intake accepted by the workflow.

    Channel adapters validate their concrete contracts under
    `contracts/intake/uc2/` and normalise to this workflow input. It carries
    safe refs and bounded summaries only; raw legal matter narratives,
    identity evidence, and documents stay behind intake or connector stores.
    """

    schema_version: str
    legal_intake_id: str
    tenant_id: str
    correlation_id: str
    channel: str
    adapter_id: str
    received_at: str
    source_payload_ref: str
    legal_intake_ref: str
    subject_summary: str
    matter_scope_summary: str
    party_role_hints: list[Uc2PartyRoleHint]
    attachments_summary: list[Uc2AttachmentSummary]
    prospective_client_ref: str | None = None
    instructing_contact_ref: str | None = None
    matter_type_hint: str | None = None
    jurisdiction_categories: list[str] = field(default_factory=_empty_strings)
    known_party_refs: list[str] = field(default_factory=_empty_strings)
    idempotency_key_ref: str | None = None


@dataclass(frozen=True)
class Uc3AttachmentSummary:
    """Bounded UC3 attachment metadata preserved from intake into the workflow."""

    attachment_ref: str
    document_category: str
    content_type: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class Uc3AdviceEnquiry:
    """Normalised UC3 advice enquiry accepted by the workflow.

    Channel adapters validate concrete contracts under `contracts/intake/uc3/`
    and normalise to this workflow input. It carries safe refs and bounded
    categories only; raw client financial details, vulnerability narratives,
    platform credentials, suitability-report prose, and production adviser /
    customer data stay behind intake or connector-owned stores.
    """

    schema_version: str
    advice_enquiry_id: str
    tenant_id: str
    correlation_id: str
    channel: str
    adapter_id: str
    received_at: str
    source_payload_ref: str
    advice_enquiry_ref: str
    subject_summary: str
    advice_need_summary: str
    advice_need_categories: list[str]
    declared_objective_categories: list[str]
    support_need_categories: list[str]
    attachments_summary: list[Uc3AttachmentSummary]
    prospective_retail_client_ref: str | None = None
    household_ref: str | None = None
    introducer_ref: str | None = None
    risk_preference_hint: str | None = None
    time_horizon_band: str = "unknown"
    product_context_categories: list[str] = field(default_factory=_empty_strings)
    idempotency_key_ref: str | None = None


@dataclass(frozen=True)
class WorkflowEventCommand:
    tenant_id: str
    correlation_id: str
    workflow_id: str
    workflow_type: str
    subject_id: str
    subject_ref: str
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
    subject_id: str
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
    workflow_type: str
    subject_id: str | None
    subject_ref: str | None
    invocation_id: str
    agent_id: str
    tool_name: str
    mode: str
    idempotency_key: str
    arguments: dict[str, Any]
    subject_summary: str | None = None


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
    workflow_type: str
    workflow_actor_id: str
    subject_id: str
    subject_ref: str
    invocation_id: str
    agent_id: str
    tool_name: str
    mode: str
    idempotency_key: str
    arguments: dict[str, Any]
    failure_reason: str
    subject_summary: str | None = None


@dataclass(frozen=True)
class ToolFailureCompensationResult:
    audit_event_id: str
    action: str
    verdict: str
    reason: str


@dataclass(frozen=True)
class RetryExhaustionDlqCommand:
    tenant_id: str
    correlation_id: str
    workflow_id: str
    workflow_type: str
    workflow_actor_id: str
    subject_id: str
    subject_ref: str
    sequence: int
    failed_step: str
    failed_activity: str
    failure_reason: str
    attempts: int
    subject_summary: str | None = None


@dataclass(frozen=True)
class RetryExhaustionDlqResult:
    outbox_id: str
    event_id: str
    audit_event_id: str
    action: str
    outbox_status: str
    verdict: str
    reason: str
    sequence: int


@dataclass(frozen=True)
class Uc1WorkflowResult:
    workflow_id: str
    tenant_id: str
    correlation_id: str
    enquiry_id: str
    outcome: WorkflowOutcome
    path: list[str]
    final_summary: str
    escalation_reason: str | None = None


Uc2WorkflowOutcome = Literal[
    "completed",
    "approval_required",
    "declined_to_act",
    "manual_review",
    "escalated",
    "failed",
]


@dataclass(frozen=True)
class Uc2WorkflowResult:
    workflow_id: str
    tenant_id: str
    correlation_id: str
    legal_intake_id: str
    legal_intake_ref: str
    outcome: Uc2WorkflowOutcome
    path: list[str]
    final_summary: str
    escalation_reason: str | None = None


Uc3WorkflowOutcome = Literal[
    "completed",
    "approval_required",
    "declined_advice_service",
    "manual_review",
    "fact_find_incomplete",
    "escalated",
    "failed",
]


@dataclass(frozen=True)
class Uc3WorkflowResult:
    workflow_id: str
    tenant_id: str
    correlation_id: str
    advice_enquiry_id: str
    advice_enquiry_ref: str
    outcome: Uc3WorkflowOutcome
    path: list[str]
    final_summary: str
    escalation_reason: str | None = None


@dataclass(frozen=True)
class MailpitPollConfig:
    mailpit_base_url: str = "http://localhost:8025"
    temporal_target_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    task_queue: str = "chorus-uc1"
    tenant_id: str = "tenant_demo"
    recipient: str = "enquiries@broker-firm.local"
    page_size: int = 50


@dataclass(frozen=True)
class MailpitPollResult:
    started_workflow_ids: list[str]
    duplicate_message_ids: list[str]
    ignored_message_ids: list[str]
    parsed_message_ids: list[str]

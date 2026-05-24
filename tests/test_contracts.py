from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from chorus.contracts import check
from chorus.contracts.gen import model_output_path, schema_files
from chorus.contracts.generated.connector.calendar_availability_lookup_args import (
    CalendarAvailabilityLookupArgs,
)
from chorus.contracts.generated.connector.calendar_hold_cancellation_args import (
    CalendarHoldCancellationArgs,
)
from chorus.contracts.generated.connector.calendar_hold_creation_args import (
    CalendarHoldCreationArgs,
)
from chorus.contracts.generated.connector.calendar_hold_proposal_args import (
    CalendarHoldProposalArgs,
)
from chorus.contracts.generated.connector.gateway_verdict import GatewayVerdict
from chorus.contracts.generated.connector.tool_call import ToolCall
from chorus.contracts.generated.connector.uc1.customer_profile_lookup_args import (
    CustomerProfileLookupArgs,
)
from chorus.contracts.generated.connector.uc1.decline_ledger_route_args import (
    DeclineLedgerRouteArgs,
)
from chorus.contracts.generated.connector.uc1.outbound_comms_message_args import (
    OutboundCommsMessageArgs,
)
from chorus.contracts.generated.connector.uc1.product_catalogue_lookup_args import (
    ProductCatalogueLookupArgs,
)
from chorus.contracts.generated.connector.uc1.quoting_queue_route_args import (
    QuotingQueueRouteArgs,
)
from chorus.contracts.generated.connector.uc1.referral_inbox_route_args import (
    ReferralInboxRouteArgs,
)
from chorus.contracts.generated.connector.uc2.aml_risk_assessment_record_args import (
    AmlRiskAssessmentRecordArgs,
)
from chorus.contracts.generated.connector.uc2.conflict_check_search_args import (
    ConflictCheckSearchArgs,
)
from chorus.contracts.generated.connector.uc2.engagement_letter_decline_args import (
    EngagementLetterDeclineArgs,
)
from chorus.contracts.generated.connector.uc2.engagement_letter_draft_args import (
    EngagementLetterDraftArgs,
)
from chorus.contracts.generated.connector.uc2.engagement_letter_manual_review_args import (
    EngagementLetterManualReviewArgs,
)
from chorus.contracts.generated.connector.uc2.engagement_letter_send_args import (
    EngagementLetterSendArgs,
)
from chorus.contracts.generated.connector.uc2.kyc_beneficial_ownership_lookup_args import (
    KycBeneficialOwnershipLookupArgs,
)
from chorus.contracts.generated.eval.replay_run_record import ReplayRunRecord
from chorus.contracts.generated.intake.uc1.email_channel_enquiry import EmailChannelEnquiry
from chorus.contracts.generated.intake.uc1.partner_portal_channel_enquiry import (
    PartnerPortalChannelEnquiry,
)
from chorus.contracts.generated.intake.uc1.web_form_channel_enquiry import (
    WebFormChannelEnquiry,
)
from chorus.contracts.generated.intake.uc2.corporate_intake_form import CorporateIntakeForm
from chorus.contracts.generated.intake.uc2.email_legal_intake import EmailLegalIntake
from chorus.contracts.generated.intake.uc2.intermediary_referral_intake import (
    IntermediaryReferralIntake,
)
from chorus.contracts.generated.llm_provider.model_route_version import ModelRouteVersion
from chorus.contracts.generated.llm_provider.provider_catalogue import ProviderCatalogue
from chorus.contracts.generated.llm_provider.uc1_agent_io import Uc1AgentIO
from chorus.contracts.generated.projection.workflow_event import WorkflowEvent

ROOT = Path(__file__).resolve().parents[1]


def test_contract_gate_passes() -> None:
    assert check.main() == 0


def test_contract_schemas_have_samples_and_generated_models() -> None:
    schemas = schema_files()

    assert len(schemas) == 35
    for schema in schemas:
        name = schema.name.removesuffix(".schema.json")
        assert (schema.parent / "samples" / f"{name}.sample.json").exists()
        assert model_output_path(schema).exists()


def _sample(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text())


def test_projection_workflow_event_accepts_r4_subject_identifiers() -> None:
    cases = [
        ("uc1_enquiry_qualification", "enq_motor_private_001"),
        (
            "uc2_legal_services_intake_conflict_check",
            "legal_intake_corporate_referral_001",
        ),
        ("uc3_ifa_suitability_intake", "advice_enquiry_web_001"),
    ]

    for workflow_type, subject_ref in cases:
        event = WorkflowEvent.model_validate(
            {
                "schema_version": "1.0.0",
                "event_id": str(uuid4()),
                "event_type": "workflow.started",
                "occurred_at": "2026-04-29T12:00:00Z",
                "tenant_id": "tenant_demo",
                "correlation_id": f"cor_{subject_ref}",
                "workflow_id": f"{workflow_type}-{subject_ref}",
                "workflow_type": workflow_type,
                "subject_id": str(uuid4()),
                "subject_ref": subject_ref,
                "sequence": 1,
                "step": "intake",
                "payload": {"subject": subject_ref},
            }
        )

        assert event.workflow_type.value == workflow_type
        assert event.subject_ref == subject_ref


def test_generated_models_validate_representative_samples() -> None:
    email_intake_sample = _sample("contracts/intake/uc1/samples/email_channel_enquiry.sample.json")
    web_form_sample = _sample("contracts/intake/uc1/samples/web_form_channel_enquiry.sample.json")
    partner_portal_sample = _sample(
        "contracts/intake/uc1/samples/partner_portal_channel_enquiry.sample.json"
    )
    verdict_sample = _sample("contracts/connector/samples/gateway_verdict.sample.json")
    provider_catalogue_sample = _sample(
        "contracts/llm_provider/samples/provider_catalogue.sample.json"
    )
    route_version_sample = _sample("contracts/llm_provider/samples/model_route_version.sample.json")
    replay_run_sample = _sample("contracts/eval/samples/replay_run_record.sample.json")
    availability_sample = _sample(
        "contracts/connector/samples/calendar_availability_lookup_args.sample.json"
    )
    hold_proposal_sample = _sample(
        "contracts/connector/samples/calendar_hold_proposal_args.sample.json"
    )
    hold_creation_sample = _sample(
        "contracts/connector/samples/calendar_hold_creation_args.sample.json"
    )
    hold_cancellation_sample = _sample(
        "contracts/connector/samples/calendar_hold_cancellation_args.sample.json"
    )
    uc1_agent_sample = _sample("contracts/llm_provider/samples/uc1_agent_io.sample.json")
    customer_profile_sample = _sample(
        "contracts/connector/uc1/samples/customer_profile_lookup_args.sample.json"
    )
    product_catalogue_sample = _sample(
        "contracts/connector/uc1/samples/product_catalogue_lookup_args.sample.json"
    )
    outbound_comms_sample = _sample(
        "contracts/connector/uc1/samples/outbound_comms_message_args.sample.json"
    )
    quoting_queue_sample = _sample(
        "contracts/connector/uc1/samples/quoting_queue_route_args.sample.json"
    )
    referral_inbox_sample = _sample(
        "contracts/connector/uc1/samples/referral_inbox_route_args.sample.json"
    )
    decline_ledger_sample = _sample(
        "contracts/connector/uc1/samples/decline_ledger_route_args.sample.json"
    )
    email_legal_intake_sample = _sample(
        "contracts/intake/uc2/samples/email_legal_intake.sample.json"
    )
    corporate_intake_form_sample = _sample(
        "contracts/intake/uc2/samples/corporate_intake_form.sample.json"
    )
    intermediary_referral_sample = _sample(
        "contracts/intake/uc2/samples/intermediary_referral_intake.sample.json"
    )
    conflict_check_sample = _sample(
        "contracts/connector/uc2/samples/conflict_check_search_args.sample.json"
    )
    kyc_bo_sample = _sample(
        "contracts/connector/uc2/samples/kyc_beneficial_ownership_lookup_args.sample.json"
    )
    aml_record_sample = _sample(
        "contracts/connector/uc2/samples/aml_risk_assessment_record_args.sample.json"
    )
    engagement_draft_sample = _sample(
        "contracts/connector/uc2/samples/engagement_letter_draft_args.sample.json"
    )
    engagement_send_sample = _sample(
        "contracts/connector/uc2/samples/engagement_letter_send_args.sample.json"
    )
    engagement_decline_sample = _sample(
        "contracts/connector/uc2/samples/engagement_letter_decline_args.sample.json"
    )
    engagement_manual_review_sample = _sample(
        "contracts/connector/uc2/samples/engagement_letter_manual_review_args.sample.json"
    )

    email_intake = EmailChannelEnquiry.model_validate(email_intake_sample)
    assert email_intake.channel == "email"
    assert email_intake.adapter_id == "email-channel"

    web_form = WebFormChannelEnquiry.model_validate(web_form_sample)
    assert web_form.channel == "web_form"
    assert web_form.form_submission_id.startswith("wfsub_")

    partner_portal = PartnerPortalChannelEnquiry.model_validate(partner_portal_sample)
    assert partner_portal.channel == "partner_portal"
    assert partner_portal.partner_submission_id.startswith("psub_")

    assert GatewayVerdict.model_validate(verdict_sample).verdict.value == "allow"
    catalogue = ProviderCatalogue.model_validate(provider_catalogue_sample)
    route_version = ModelRouteVersion.model_validate(route_version_sample)
    replay_run = ReplayRunRecord.model_validate(replay_run_sample)
    assert [provider.provider_id for provider in catalogue.providers] == [
        "local",
        "deepseek",
        "openai",
    ]
    assert route_version.selected_model.runtime_route_id == "recorded-replay"
    assert route_version.selected_model.provider_id == "local"
    assert str(replay_run.original.invocation_id).startswith("11000000-")
    assert replay_run.alternate.runtime_route_id == "recorded-replay"
    assert replay_run.comparator.status.value == "pass"
    assert (
        CalendarAvailabilityLookupArgs.model_validate(availability_sample).calendar_ref
        == "cal_uc1_local_followup"
    )
    assert CalendarHoldProposalArgs.model_validate(hold_proposal_sample).slot_ref.startswith(
        "slot_"
    )
    assert CalendarHoldCreationArgs.model_validate(hold_creation_sample).event_uid_ref.startswith(
        "evt_"
    )
    assert (
        CalendarHoldCancellationArgs.model_validate(
            hold_cancellation_sample
        ).cancellation_reason_category.value
        == "workflow_compensation"
    )
    uc1_agent = Uc1AgentIO.model_validate(uc1_agent_sample)
    assert uc1_agent.agent_role.value == "classifier"
    assert uc1_agent.task_kind.value == "enquiry_classification"
    assert (
        CustomerProfileLookupArgs.model_validate(customer_profile_sample).customer_ref
        == "cust_demo_001"
    )
    assert (
        ProductCatalogueLookupArgs.model_validate(
            product_catalogue_sample
        ).product_family_category.value
        == "motor_private_car"
    )
    assert (
        OutboundCommsMessageArgs.model_validate(outbound_comms_sample).missing_data_request_ref
        == "mdr_demo_001"
    )
    assert (
        QuotingQueueRouteArgs.model_validate(quoting_queue_sample).product_family_category.value
        == "motor_private_car"
    )
    assert (
        ReferralInboxRouteArgs.model_validate(
            referral_inbox_sample
        ).referral_destination_category.value
        == "specialist_broker_panel"
    )
    assert (
        DeclineLedgerRouteArgs.model_validate(decline_ledger_sample).decline_reason_category.value
        == "outside_product_target_market"
    )

    email_legal_intake = EmailLegalIntake.model_validate(email_legal_intake_sample)
    corporate_intake_form = CorporateIntakeForm.model_validate(corporate_intake_form_sample)
    intermediary_referral = IntermediaryReferralIntake.model_validate(intermediary_referral_sample)
    assert email_legal_intake.source_payload_ref == "source_payload_legal_email_001"
    assert corporate_intake_form.channel == "corporate-intake-form"
    assert intermediary_referral.referrer_ref == "intermediary_accountancy_demo"

    assert (
        ConflictCheckSearchArgs.model_validate(conflict_check_sample)
        .conflict_search_categories[0]
        .value
        == "current_client"
    )
    assert (
        KycBeneficialOwnershipLookupArgs.model_validate(kyc_bo_sample).entity_category.value
        == "company"
    )
    assert (
        AmlRiskAssessmentRecordArgs.model_validate(aml_record_sample).aml_risk_rating.value
        == "standard"
    )
    assert (
        EngagementLetterDraftArgs.model_validate(engagement_draft_sample)
        .draft_basis_categories[0]
        .value
        == "standard_terms"
    )
    assert (
        EngagementLetterSendArgs.model_validate(engagement_send_sample).send_channel_category.value
        == "email"
    )
    assert (
        EngagementLetterDeclineArgs.model_validate(
            engagement_decline_sample
        ).decline_reason_category.value
        == "client_conflict_blocked"
    )
    assert (
        EngagementLetterManualReviewArgs.model_validate(
            engagement_manual_review_sample
        ).review_destination_category.value
        == "mlro"
    )


def test_tool_call_contract_accepts_uc2_tool_names() -> None:
    tool_modes = {
        "conflict_check.search": "read",
        "kyc_bo.lookup": "read",
        "aml_record_store.record_assessment": "write",
        "engagement_letter.draft": "propose",
        "engagement_letter.send": "write",
        "engagement_letter.record_decline": "write",
        "engagement_letter.route_manual_review": "write",
    }

    for tool_name, mode in tool_modes.items():
        tool_call = ToolCall.model_validate(
            {
                "schema_version": "1.0.0",
                "tool_call_id": str(uuid4()),
                "invocation_id": str(uuid4()),
                "tenant_id": "tenant_demo",
                "correlation_id": "cor_legal_contract_test",
                "agent_id": "uc2.intake_conflict",
                "tool_name": tool_name,
                "mode": mode,
                "idempotency_key": f"tenant_demo:legal_intake_demo_001:{tool_name}",
                "arguments": {"legal_intake_ref": "legal_intake_demo_001"},
                "requested_at": "2026-05-01T12:00:00Z",
            }
        )

        assert tool_call.tool_name.value == tool_name

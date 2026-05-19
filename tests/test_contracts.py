from __future__ import annotations

import json
from pathlib import Path

from chorus.contracts import check
from chorus.contracts.gen import model_output_path, schema_files
from chorus.contracts.generated.agents.support_agent_io import SupportAgentIO
from chorus.contracts.generated.events.lead_intake import LeadIntake
from chorus.contracts.generated.events.support_request_intake import SupportRequestIntake
from chorus.contracts.generated.governance.model_route_version import ModelRouteVersion
from chorus.contracts.generated.governance.provider_catalogue import ProviderCatalogue
from chorus.contracts.generated.tools.calendar_availability_lookup_args import (
    CalendarAvailabilityLookupArgs,
)
from chorus.contracts.generated.tools.calendar_hold_cancellation_args import (
    CalendarHoldCancellationArgs,
)
from chorus.contracts.generated.tools.calendar_hold_creation_args import (
    CalendarHoldCreationArgs,
)
from chorus.contracts.generated.tools.calendar_hold_proposal_args import CalendarHoldProposalArgs
from chorus.contracts.generated.tools.gateway_verdict import GatewayVerdict
from chorus.contracts.generated.tools.ticket_case_lookup_args import TicketCaseLookupArgs
from chorus.contracts.generated.tools.ticket_case_update_proposal_args import (
    TicketCaseUpdateProposalArgs,
)
from chorus.contracts.generated.tools.ticket_duplicate_case_lookup_args import (
    TicketDuplicateCaseLookupArgs,
)
from chorus.contracts.generated.tools.ticket_status_update_args import TicketStatusUpdateArgs

ROOT = Path(__file__).resolve().parents[1]


def test_contract_gate_passes() -> None:
    assert check.main() == 0


def test_contract_schemas_have_samples_and_generated_models() -> None:
    schemas = schema_files()

    assert len(schemas) == 21
    for schema in schemas:
        name = schema.name.removesuffix(".schema.json")
        assert (schema.parent / "samples" / f"{name}.sample.json").exists()
        assert model_output_path(schema).exists()


def test_generated_models_validate_representative_samples() -> None:
    lead_sample = json.loads(
        (ROOT / "contracts/events/samples/lead_intake.sample.json").read_text()
    )
    verdict_sample = json.loads(
        (ROOT / "contracts/tools/samples/gateway_verdict.sample.json").read_text()
    )
    provider_catalogue_sample = json.loads(
        (ROOT / "contracts/governance/samples/provider_catalogue.sample.json").read_text()
    )
    route_version_sample = json.loads(
        (ROOT / "contracts/governance/samples/model_route_version.sample.json").read_text()
    )
    availability_sample = json.loads(
        (ROOT / "contracts/tools/samples/calendar_availability_lookup_args.sample.json").read_text()
    )
    hold_proposal_sample = json.loads(
        (ROOT / "contracts/tools/samples/calendar_hold_proposal_args.sample.json").read_text()
    )
    hold_creation_sample = json.loads(
        (ROOT / "contracts/tools/samples/calendar_hold_creation_args.sample.json").read_text()
    )
    hold_cancellation_sample = json.loads(
        (ROOT / "contracts/tools/samples/calendar_hold_cancellation_args.sample.json").read_text()
    )
    support_intake_sample = json.loads(
        (ROOT / "contracts/events/samples/support_request_intake.sample.json").read_text()
    )
    support_agent_sample = json.loads(
        (ROOT / "contracts/agents/samples/support_agent_io.sample.json").read_text()
    )
    ticket_case_lookup_sample = json.loads(
        (ROOT / "contracts/tools/samples/ticket_case_lookup_args.sample.json").read_text()
    )
    ticket_duplicate_lookup_sample = json.loads(
        (ROOT / "contracts/tools/samples/ticket_duplicate_case_lookup_args.sample.json").read_text()
    )
    ticket_case_update_sample = json.loads(
        (ROOT / "contracts/tools/samples/ticket_case_update_proposal_args.sample.json").read_text()
    )
    ticket_status_update_sample = json.loads(
        (ROOT / "contracts/tools/samples/ticket_status_update_args.sample.json").read_text()
    )

    assert LeadIntake.model_validate(lead_sample).correlation_id == "cor_lead_acme_001"
    assert GatewayVerdict.model_validate(verdict_sample).verdict.value == "allow"
    catalogue = ProviderCatalogue.model_validate(provider_catalogue_sample)
    route_version = ModelRouteVersion.model_validate(route_version_sample)
    assert [provider.provider_id for provider in catalogue.providers] == [
        "local",
        "commercial.example",
    ]
    assert route_version.selected_model.provider_id == "local"
    assert (
        CalendarAvailabilityLookupArgs.model_validate(availability_sample).calendar_ref
        == "cal_lighthouse_local_followup"
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
    assert SupportRequestIntake.model_validate(support_intake_sample).request_ref == (
        "req_support_001"
    )
    support_agent = SupportAgentIO.model_validate(support_agent_sample)
    assert support_agent.workflow_type == "support_triage"
    assert support_agent.result.verdict_category.value == "propose_case_update"
    assert TicketCaseLookupArgs.model_validate(ticket_case_lookup_sample).case_ref == (
        "case_existing_001"
    )
    assert (
        TicketDuplicateCaseLookupArgs.model_validate(
            ticket_duplicate_lookup_sample
        ).duplicate_scope_category.value
        == "same_account_product_open"
    )
    assert (
        TicketCaseUpdateProposalArgs.model_validate(
            ticket_case_update_sample
        ).target_status_category.value
        == "pending_internal"
    )
    assert (
        TicketStatusUpdateArgs.model_validate(ticket_status_update_sample).approval_policy_ref
        == "policy_ticket_write_approval"
    )

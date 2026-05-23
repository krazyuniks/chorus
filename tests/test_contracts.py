from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
from chorus.contracts.generated.connector.ticket_case_lookup_args import TicketCaseLookupArgs
from chorus.contracts.generated.connector.ticket_case_update_proposal_args import (
    TicketCaseUpdateProposalArgs,
)
from chorus.contracts.generated.connector.ticket_duplicate_case_lookup_args import (
    TicketDuplicateCaseLookupArgs,
)
from chorus.contracts.generated.connector.ticket_status_update_args import TicketStatusUpdateArgs
from chorus.contracts.generated.intake.support_request_intake import SupportRequestIntake
from chorus.contracts.generated.intake.uc1.lead_intake import LeadIntake
from chorus.contracts.generated.llm_provider.model_route_version import ModelRouteVersion
from chorus.contracts.generated.llm_provider.provider_catalogue import ProviderCatalogue
from chorus.contracts.generated.llm_provider.support_agent_io import SupportAgentIO

ROOT = Path(__file__).resolve().parents[1]


def test_contract_gate_passes() -> None:
    assert check.main() == 0


def test_contract_schemas_have_samples_and_generated_models() -> None:
    schemas = schema_files()

    assert len(schemas) == 22
    for schema in schemas:
        name = schema.name.removesuffix(".schema.json")
        assert (schema.parent / "samples" / f"{name}.sample.json").exists()
        assert model_output_path(schema).exists()


def _sample(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text())


def test_generated_models_validate_representative_samples() -> None:
    lead_sample = _sample("contracts/intake/uc1/samples/lead_intake.sample.json")
    verdict_sample = _sample("contracts/connector/samples/gateway_verdict.sample.json")
    provider_catalogue_sample = _sample(
        "contracts/llm_provider/samples/provider_catalogue.sample.json"
    )
    route_version_sample = _sample("contracts/llm_provider/samples/model_route_version.sample.json")
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
    support_intake_sample = _sample("contracts/intake/samples/support_request_intake.sample.json")
    support_agent_sample = _sample("contracts/llm_provider/samples/support_agent_io.sample.json")
    ticket_case_lookup_sample = _sample(
        "contracts/connector/samples/ticket_case_lookup_args.sample.json"
    )
    ticket_duplicate_lookup_sample = _sample(
        "contracts/connector/samples/ticket_duplicate_case_lookup_args.sample.json"
    )
    ticket_case_update_sample = _sample(
        "contracts/connector/samples/ticket_case_update_proposal_args.sample.json"
    )
    ticket_status_update_sample = _sample(
        "contracts/connector/samples/ticket_status_update_args.sample.json"
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

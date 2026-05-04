from __future__ import annotations

import json
from pathlib import Path

from chorus.contracts import check
from chorus.contracts.gen import model_output_path, schema_files
from chorus.contracts.generated.events.lead_intake import LeadIntake
from chorus.contracts.generated.governance.model_route_version import ModelRouteVersion
from chorus.contracts.generated.governance.provider_catalogue import ProviderCatalogue
from chorus.contracts.generated.tools.gateway_verdict import GatewayVerdict

ROOT = Path(__file__).resolve().parents[1]


def test_contract_gate_passes() -> None:
    assert check.main() == 0


def test_contract_schemas_have_samples_and_generated_models() -> None:
    schemas = schema_files()

    assert len(schemas) == 11
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

    assert LeadIntake.model_validate(lead_sample).correlation_id == "cor_lead_acme_001"
    assert GatewayVerdict.model_validate(verdict_sample).verdict.value == "allow"
    catalogue = ProviderCatalogue.model_validate(provider_catalogue_sample)
    route_version = ModelRouteVersion.model_validate(route_version_sample)
    assert [provider.provider_id for provider in catalogue.providers] == [
        "local",
        "commercial.example",
    ]
    assert route_version.selected_model.provider_id == "local"

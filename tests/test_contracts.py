from __future__ import annotations

import json
from pathlib import Path

from chorus.contracts import check
from chorus.contracts.gen import model_output_path, schema_files
from chorus.contracts.generated.events.lead_intake import LeadIntake
from chorus.contracts.generated.tools.gateway_verdict import GatewayVerdict

ROOT = Path(__file__).resolve().parents[1]


def test_contract_gate_passes() -> None:
    assert check.main() == 0


def test_contract_schemas_have_samples_and_generated_models() -> None:
    schemas = schema_files()

    assert len(schemas) == 8
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

    assert LeadIntake.model_validate(lead_sample).correlation_id == "cor_lead_acme_001"
    assert GatewayVerdict.model_validate(verdict_sample).verdict.value == "allow"

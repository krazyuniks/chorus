from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from chorus.workflows.types import Uc3AdviceEnquiry
from chorus.workflows.uc3 import UC3_WORKFLOW_TYPE
from chorus.workflows.uc3_synthetic_intake import (
    DEFAULT_UC3_EMAIL_INTAKE_FIXTURE,
    Uc3SyntheticIntakeConfig,
    advice_enquiry_ref_for_source_payload,
    idempotency_key_ref_for_email_message_id,
    load_email_advice_enquiry_fixture,
    start_uc3_synthetic_intake_once,
    workflow_id_for_email_message_id,
    workflow_start_request_from_email_fixture,
)


class FakeUc3WorkflowStarter:
    def __init__(self, existing: set[str] | None = None) -> None:
        self.existing = existing or set()
        self.started: list[tuple[Uc3AdviceEnquiry, str]] = []

    async def start_uc3(self, intake: Uc3AdviceEnquiry, workflow_id: str) -> bool:
        if workflow_id in self.existing:
            return False
        self.started.append((intake, workflow_id))
        self.existing.add(workflow_id)
        return True


def test_load_email_advice_enquiry_fixture_uses_generated_contract_validation() -> None:
    contract = load_email_advice_enquiry_fixture(DEFAULT_UC3_EMAIL_INTAKE_FIXTURE)

    assert contract.schema_version == "1.0.0"
    assert contract.tenant_id == "tenant_demo"
    assert contract.message_id == "<advice-enquiry-001@example.test>"
    assert contract.source_payload_ref == "source_payload_advice_email_001"
    assert contract.advice_need_categories[0].value == "pension_consolidation"


def test_invalid_email_advice_enquiry_fixture_fails_contract_validation(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_UC3_EMAIL_INTAKE_FIXTURE.read_text(encoding="utf-8"))
    del payload["message_id"]
    fixture = tmp_path / "invalid-email-advice-enquiry.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError, match="message_id"):
        load_email_advice_enquiry_fixture(fixture)


def test_workflow_start_request_is_stable_and_safe() -> None:
    request = workflow_start_request_from_email_fixture(DEFAULT_UC3_EMAIL_INTAKE_FIXTURE)

    assert request.workflow_type == UC3_WORKFLOW_TYPE
    assert request.workflow_id == workflow_id_for_email_message_id(
        tenant_id="tenant_demo",
        message_id="<advice-enquiry-001@example.test>",
    )
    assert request.intake.correlation_id == "cor_advice_email_001"
    assert request.intake.advice_enquiry_ref == advice_enquiry_ref_for_source_payload(
        "source_payload_advice_email_001"
    )
    assert request.intake.idempotency_key_ref == idempotency_key_ref_for_email_message_id(
        "<advice-enquiry-001@example.test>"
    )
    assert request.intake.subject_summary == "Synthetic pension consolidation enquiry"
    assert request.intake.prospective_retail_client_ref == "prospective_client_demo_ifa_002"
    assert request.intake.advice_need_categories == [
        "pension_consolidation",
        "retirement_planning",
    ]
    assert request.intake.declared_objective_categories == [
        "pension_accumulation",
        "retirement_planning",
    ]
    assert request.intake.product_context_categories == ["pension", "isa"]
    assert request.intake.support_need_categories == ["unknown"]
    assert request.intake.attachments_summary[0].document_category == "pension_statement"


@pytest.mark.asyncio
async def test_start_uc3_synthetic_intake_once_builds_and_sends_start_request() -> None:
    starter = FakeUc3WorkflowStarter()

    result = await start_uc3_synthetic_intake_once(
        Uc3SyntheticIntakeConfig(fixture_path=DEFAULT_UC3_EMAIL_INTAKE_FIXTURE),
        starter=starter,
    )

    assert result.workflow_type == UC3_WORKFLOW_TYPE
    assert result.started is True
    assert result.workflow_id.startswith("uc3-advice-")
    assert result.advice_enquiry_ref == "advice_enquiry_advice_email_001"
    assert result.correlation_id == "cor_advice_email_001"
    assert len(starter.started) == 1
    intake, workflow_id = starter.started[0]
    assert workflow_id == result.workflow_id
    assert intake.advice_enquiry_id == result.advice_enquiry_id
    assert intake.advice_enquiry_ref == result.advice_enquiry_ref


@pytest.mark.asyncio
async def test_start_uc3_synthetic_intake_once_reports_existing_duplicate() -> None:
    starter = FakeUc3WorkflowStarter()
    config = Uc3SyntheticIntakeConfig(fixture_path=DEFAULT_UC3_EMAIL_INTAKE_FIXTURE)

    first = await start_uc3_synthetic_intake_once(config, starter=starter)
    second = await start_uc3_synthetic_intake_once(config, starter=starter)

    assert first.started is True
    assert second.started is False
    assert second.workflow_id == first.workflow_id
    assert second.advice_enquiry_ref == first.advice_enquiry_ref
    assert len(starter.started) == 1

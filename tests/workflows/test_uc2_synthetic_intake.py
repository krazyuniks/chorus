from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from chorus.workflows.types import Uc2LegalIntake
from chorus.workflows.uc2 import UC2_WORKFLOW_TYPE
from chorus.workflows.uc2_synthetic_intake import (
    DEFAULT_UC2_EMAIL_INTAKE_FIXTURE,
    Uc2SyntheticIntakeConfig,
    idempotency_key_ref_for_email_message_id,
    legal_intake_ref_for_source_payload,
    load_email_legal_intake_fixture,
    start_uc2_synthetic_intake_once,
    workflow_id_for_email_message_id,
    workflow_start_request_from_email_fixture,
)


class FakeUc2WorkflowStarter:
    def __init__(self, existing: set[str] | None = None) -> None:
        self.existing = existing or set()
        self.started: list[tuple[Uc2LegalIntake, str]] = []

    async def start_uc2(self, intake: Uc2LegalIntake, workflow_id: str) -> bool:
        if workflow_id in self.existing:
            return False
        self.started.append((intake, workflow_id))
        self.existing.add(workflow_id)
        return True


def test_load_email_legal_intake_fixture_uses_generated_contract_validation() -> None:
    contract = load_email_legal_intake_fixture(DEFAULT_UC2_EMAIL_INTAKE_FIXTURE)

    assert contract.schema_version == "1.0.0"
    assert contract.tenant_id == "tenant_demo"
    assert contract.message_id == "<legal-intake-001@example.test>"
    assert contract.source_payload_ref == "source_payload_legal_email_001"
    assert contract.party_role_hints[0].role.value == "prospective_client"


def test_invalid_email_legal_intake_fixture_fails_contract_validation(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_UC2_EMAIL_INTAKE_FIXTURE.read_text(encoding="utf-8"))
    del payload["message_id"]
    fixture = tmp_path / "invalid-email-legal-intake.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError, match="message_id"):
        load_email_legal_intake_fixture(fixture)


def test_workflow_start_request_is_stable_and_safe() -> None:
    request = workflow_start_request_from_email_fixture(DEFAULT_UC2_EMAIL_INTAKE_FIXTURE)

    assert request.workflow_type == UC2_WORKFLOW_TYPE
    assert request.workflow_id == workflow_id_for_email_message_id(
        tenant_id="tenant_demo",
        message_id="<legal-intake-001@example.test>",
    )
    assert request.intake.correlation_id == "cor_legal_email_001"
    assert request.intake.legal_intake_ref == legal_intake_ref_for_source_payload(
        "source_payload_legal_email_001"
    )
    assert request.intake.idempotency_key_ref == idempotency_key_ref_for_email_message_id(
        "<legal-intake-001@example.test>"
    )
    assert request.intake.subject_summary == "Commercial contract review enquiry"
    assert request.intake.instructing_contact_ref == "contact_instructing_001"
    assert request.intake.known_party_refs == [
        "party_prospective_client_001",
        "party_counterparty_001",
    ]
    assert request.intake.party_role_hints[0].role == "prospective_client"
    assert request.intake.attachments_summary[0].document_category == "heads_of_terms"


@pytest.mark.asyncio
async def test_start_uc2_synthetic_intake_once_builds_and_sends_start_request() -> None:
    starter = FakeUc2WorkflowStarter()

    result = await start_uc2_synthetic_intake_once(
        Uc2SyntheticIntakeConfig(fixture_path=DEFAULT_UC2_EMAIL_INTAKE_FIXTURE),
        starter=starter,
    )

    assert result.workflow_type == UC2_WORKFLOW_TYPE
    assert result.started is True
    assert result.workflow_id.startswith("uc2-legal-")
    assert result.legal_intake_ref == "legal_intake_legal_email_001"
    assert result.correlation_id == "cor_legal_email_001"
    assert len(starter.started) == 1
    intake, workflow_id = starter.started[0]
    assert workflow_id == result.workflow_id
    assert intake.legal_intake_id == result.legal_intake_id
    assert intake.legal_intake_ref == result.legal_intake_ref

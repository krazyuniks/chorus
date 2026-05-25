from __future__ import annotations

from chorus.persistence.redpanda import contract_schema_subjects, missing_schema_subjects


def test_schema_registration_discovers_port_contract_subjects() -> None:
    subjects = set(contract_schema_subjects().values())

    assert "chorus.workflow.events.v1-value" in subjects
    assert "chorus.agent-invocation-transcripts.v1-value" in subjects
    assert "chorus.uc2.corporate-intake-form.v1-value" in subjects
    assert "chorus.uc3.web-advice-enquiry.v1-value" in subjects


def test_schema_registration_filters_already_registered_subjects() -> None:
    missing = missing_schema_subjects(
        {
            "contracts/a.schema.json": "chorus.a.v1-value",
            "contracts/b.schema.json": "chorus.b.v1-value",
        },
        {"chorus.a.v1-value"},
    )

    assert missing == {"contracts/b.schema.json": "chorus.b.v1-value"}

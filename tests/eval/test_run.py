from __future__ import annotations

from pathlib import Path

import pytest

from chorus.contracts.generated.eval.eval_fixture import EvalFixture
from chorus.eval import run
from chorus.eval.common_invariants import COMMON_INVARIANTS
from chorus.eval.invariants import UC1_INVARIANTS
from chorus.eval.scenario_player import play_scenario
from chorus.eval.use_cases.uc1_conduct import UC1_CONDUCT_INVARIANTS

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "chorus" / "eval" / "fixtures"
TRANSCRIPT_FIXTURE = "chorus/eval/fixtures/transcripts/uc1_classifier_happy.json"


def test_uc1_invariant_suite_composes_common_and_conduct_modules() -> None:
    assert [invariant.__name__ for invariant in UC1_INVARIANTS] == [
        "assert_cross_port_payload_validity",
        "assert_governed_decision_provenance",
        "assert_audit_completeness",
        "assert_observability_emission",
        "assert_uc1_qualification_invariants",
        "assert_connector_authority_discipline",
        "assert_projection_convergence",
    ]
    assert UC1_CONDUCT_INVARIANTS[0] in UC1_INVARIANTS
    assert set(COMMON_INVARIANTS).issubset(UC1_INVARIANTS)


def test_eval_fixture_contract_accepts_r4_workflow_specific_scenarios() -> None:
    cases = [
        (
            "uc1_enquiry_qualification",
            "happy_path",
            "fixture_uc1_happy_path",
            "fixtures/uc1/happy-path.json",
            "missing_data_request_proposed",
        ),
        (
            "uc2_legal_services_intake_conflict_check",
            "conflict_exception_approval",
            "fixture_uc2_conflict_exception",
            "fixtures/uc2/conflict-exception-approval.json",
            "accept_subject_to_approval",
        ),
        (
            "uc3_ifa_suitability_intake",
            "suitability_report_approval",
            "fixture_uc3_suitability_report",
            "fixtures/uc3/suitability-report-approval.json",
            "suitable_subject_to_adviser_approval",
        ),
    ]

    for workflow_type, scenario, subject_fixture_ref, source_fixture_path, outcome in cases:
        fixture = EvalFixture.model_validate(
            {
                "schema_version": "1.0.0",
                "fixture_id": f"{workflow_type}-{scenario}",
                "name": f"{workflow_type} {scenario}",
                "workflow_type": workflow_type,
                "scenario": scenario,
                "input": {
                    "tenant_id": "tenant_demo",
                    "subject_fixture_ref": subject_fixture_ref,
                    "source_fixture_path": source_fixture_path,
                },
                "expected": {
                    "outcome_category": "propose",
                    "use_case_outcome": outcome,
                },
            }
        )

        assert fixture.workflow_type.value == workflow_type
        assert fixture.scenario == scenario
        assert fixture.input.subject_fixture_ref == subject_fixture_ref
        assert fixture.input.source_fixture_path == source_fixture_path
        assert fixture.expected.use_case_outcome == outcome


def test_scenario_player_rejects_non_uc1_fixtures_until_runtime_playback_lands() -> None:
    fixture = EvalFixture.model_validate(
        {
            "schema_version": "1.0.0",
            "fixture_id": "uc2-conflict-exception-approval",
            "name": "UC2 conflict exception approval",
            "workflow_type": "uc2_legal_services_intake_conflict_check",
            "scenario": "conflict_exception_approval",
            "input": {
                "tenant_id": "tenant_demo",
                "subject_fixture_ref": "fixture_uc2_conflict_exception",
                "source_fixture_path": "fixtures/uc2/conflict-exception-approval.json",
            },
            "expected": {
                "outcome_category": "propose",
                "use_case_outcome": "accept_subject_to_approval",
            },
        }
    )

    with pytest.raises(ValueError, match="supports only 'uc1_enquiry_qualification'"):
        play_scenario(fixture)


def test_assert_default_loads_every_fixture() -> None:
    assert run.main(["assert"]) == 0


def test_assert_uc1_happy_path_fixture_passes_offline() -> None:
    assert (
        run.main(
            ["assert", "--fixture", str(FIXTURE_DIR / "uc1_happy_path.json")],
        )
        == 0
    )


def test_assert_uc1_validator_redraft_fixture_passes_offline() -> None:
    assert (
        run.main(
            ["assert", "--fixture", str(FIXTURE_DIR / "uc1_validator_redraft.json")],
        )
        == 0
    )


def test_replay_classifier_transcript_matches() -> None:
    assert run.main(["replay", "--transcript", TRANSCRIPT_FIXTURE]) == 0


def test_qualification_invariants_capture_conduct_hooks() -> None:
    fixture = run.load_fixture(FIXTURE_DIR / "uc1_happy_path.json")
    captured = play_scenario(fixture)
    qualifier = next(
        decision for decision in captured.decisions if decision.task_kind == "enquiry_qualification"
    )
    for hook in (
        "best_interests_check",
        "demands_and_needs_statement",
        "target_market_check",
        "foreseeable_harm_check",
    ):
        assert hook in qualifier.structured_data
    assert qualifier.structured_data.get("policy_snapshot_ref")

from __future__ import annotations

from pathlib import Path

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

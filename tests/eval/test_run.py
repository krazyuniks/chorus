from __future__ import annotations

import json
from pathlib import Path

from chorus.contracts.generated.eval.eval_fixture import EvalFixture
from chorus.eval import run

ROOT = Path(__file__).resolve().parents[2]


def test_eval_happy_path_fixture_passes_offline() -> None:
    assert run.main(["--fixture", "chorus/eval/fixtures/lighthouse_happy_path.json"]) == 0


def test_eval_low_confidence_fixture_passes_offline() -> None:
    assert run.main(["--fixture", "chorus/eval/fixtures/lighthouse_low_confidence.json"]) == 0


def test_eval_validator_redraft_fixture_passes_offline() -> None:
    assert run.main(["--fixture", "chorus/eval/fixtures/lighthouse_validator_redraft.json"]) == 0


def test_eval_forbidden_write_fixture_passes_offline() -> None:
    assert run.main(["--fixture", "chorus/eval/fixtures/lighthouse_forbidden_write.json"]) == 0


def test_eval_connector_failure_fixture_passes_offline() -> None:
    assert run.main(["--fixture", "chorus/eval/fixtures/lighthouse_connector_failure.json"]) == 0


def test_eval_retry_exhaustion_fixture_passes_offline() -> None:
    assert run.main(["--fixture", "chorus/eval/fixtures/lighthouse_retry_exhaustion.json"]) == 0


def test_default_live_selector_targets_happy_path_only() -> None:
    happy = EvalFixture.model_validate(
        json.loads((ROOT / "chorus/eval/fixtures/lighthouse_happy_path.json").read_text())
    )
    failure = EvalFixture.model_validate(
        json.loads((ROOT / "chorus/eval/fixtures/lighthouse_connector_failure.json").read_text())
    )

    assert run.should_run_live_checks(
        fixture=happy,
        explicit_fixtures=False,
        live_selector_supplied=True,
    )
    assert not run.should_run_live_checks(
        fixture=failure,
        explicit_fixtures=False,
        live_selector_supplied=True,
    )
    assert run.should_run_live_checks(
        fixture=failure,
        explicit_fixtures=True,
        live_selector_supplied=True,
    )


def test_eval_reports_contract_failure_for_wrong_expected_path(tmp_path: Path) -> None:
    fixture = ROOT / "chorus/eval/fixtures/lighthouse_happy_path.json"
    broken = tmp_path / "broken.json"
    broken.write_text(
        fixture.read_text(encoding="utf-8").replace('"complete"', '"unexpected"', 1),
        encoding="utf-8",
    )

    assert run.main(["--fixture", str(broken)]) == 1

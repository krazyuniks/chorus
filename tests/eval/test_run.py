from __future__ import annotations

import json
from pathlib import Path

from chorus.contracts.generated.eval.eval_fixture import EvalFixture
from chorus.eval import run

ROOT = Path(__file__).resolve().parents[2]
HAPPY_PATH_FIXTURE = "chorus/eval/fixtures/uc1_happy_path.json"


def test_eval_uc1_happy_path_fixture_passes_offline() -> None:
    assert run.main(["--fixture", HAPPY_PATH_FIXTURE]) == 0


def test_default_live_selector_targets_uc1_happy_path_only() -> None:
    happy = EvalFixture.model_validate(json.loads((ROOT / HAPPY_PATH_FIXTURE).read_text()))
    assert run.should_run_live_checks(
        fixture=happy,
        explicit_fixtures=False,
        live_selector_supplied=True,
    )
    assert run.should_run_live_checks(
        fixture=happy,
        explicit_fixtures=True,
        live_selector_supplied=True,
    )


def test_eval_reports_contract_failure_for_wrong_expected_path(tmp_path: Path) -> None:
    fixture = ROOT / HAPPY_PATH_FIXTURE
    broken = tmp_path / "broken.json"
    broken.write_text(
        fixture.read_text(encoding="utf-8").replace('"complete"', '"unexpected"', 1),
        encoding="utf-8",
    )
    assert run.main(["--fixture", str(broken)]) == 1

from __future__ import annotations

from pathlib import Path

from chorus.eval import run

ROOT = Path(__file__).resolve().parents[2]


def test_eval_happy_path_fixture_passes_offline() -> None:
    assert run.main(["--fixture", "chorus/eval/fixtures/lighthouse_happy_path.json"]) == 0


def test_eval_low_confidence_fixture_passes_offline() -> None:
    assert run.main(["--fixture", "chorus/eval/fixtures/lighthouse_low_confidence.json"]) == 0


def test_eval_reports_contract_failure_for_wrong_expected_path(tmp_path: Path) -> None:
    fixture = ROOT / "chorus/eval/fixtures/lighthouse_happy_path.json"
    broken = tmp_path / "broken.json"
    broken.write_text(
        fixture.read_text(encoding="utf-8").replace('"complete"', '"unexpected"', 1),
        encoding="utf-8",
    )

    assert run.main(["--fixture", str(broken)]) == 1

from __future__ import annotations

from uuid import uuid4

import pytest

from chorus.eval import run
from chorus.eval.live_provider_integration import (
    ALLOWED_LIVE_COMPARATOR_OUTCOMES,
    LIVE_DEEPSEEK_ROUTE_ID,
    captured_transcripts_for_replay,
    replay_comparator_outcome,
    require_live_route_credential,
)
from chorus.eval.replay import replay_transcript_with_record
from chorus.eval.scenario_player import CapturedRun, play_scenario
from chorus.eval.uc2_workflow_playback import play_uc2_workflow_fixture
from chorus.eval.uc3_workflow_playback import play_uc3_workflow_fixture

pytestmark = pytest.mark.live_deepseek

TEST_DATABASE_PREFIX = "chorus_live_deepseek_test"


def test_happy_path_fixtures_replay_through_live_deepseek_route(
    migrated_database_url: str,
) -> None:
    require_live_route_credential(LIVE_DEEPSEEK_ROUTE_ID)

    captured_runs = _happy_path_captured_runs(migrated_database_url)
    records_by_fixture: dict[str, list[str]] = {}
    for captured in captured_runs:
        records_by_fixture[captured.fixture.fixture_id] = []
        for transcript in captured_transcripts_for_replay(captured):
            replay = replay_transcript_with_record(
                transcript,
                route_id=LIVE_DEEPSEEK_ROUTE_ID,
            )
            outcome = replay_comparator_outcome(replay.record)
            records_by_fixture[captured.fixture.fixture_id].append(outcome)
            assert outcome in ALLOWED_LIVE_COMPARATOR_OUTCOMES, (
                "live DeepSeek comparator outcome for "
                f"{captured.fixture.fixture_id}/{transcript.task_kind} was {outcome!r}: "
                f"{replay.record.comparator.result}"
            )
            assert replay.record.original.runtime_route_id == "recorded-replay"
            assert replay.record.alternate.runtime_route_id == LIVE_DEEPSEEK_ROUTE_ID
            assert replay.record.alternate.provider_id == "deepseek"

    assert set(records_by_fixture) == {
        "uc1-happy-path-motor-private",
        "uc2-synthetic-acceptance-conduct",
        "uc3-synthetic-suitability-conduct",
    }
    assert all(records_by_fixture.values())


def _happy_path_captured_runs(database_url: str) -> tuple[CapturedRun, CapturedRun, CapturedRun]:
    run_ref = uuid4().hex[:10]
    uc1 = play_scenario(run.load_fixture(run.FIXTURE_DIR / "uc1_happy_path.json"))
    uc2 = play_uc2_workflow_fixture(
        run.load_fixture(run.FIXTURE_DIR / "uc2" / "uc2_synthetic_acceptance_conduct.json"),
        database_url=database_url,
        playback_ref=f"live-deepseek-{run_ref}",
    )
    uc3 = play_uc3_workflow_fixture(
        run.load_fixture(run.FIXTURE_DIR / "uc3" / "uc3_synthetic_suitability_conduct.json"),
        database_url=database_url,
        playback_ref=f"live-deepseek-{run_ref}",
    )
    return uc1, uc2, uc3

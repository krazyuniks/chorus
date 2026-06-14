from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from chorus.eval import run
from chorus.eval.live_provider_integration import (
    ALLOWED_LIVE_COMPARATOR_OUTCOMES,
    LIVE_DEEPSEEK_ROUTE_ID,
    captured_transcripts_for_replay,
    persist_captured_run_audit_refs,
    replay_comparator_outcome,
    require_live_route_credential,
)
from chorus.eval.replay import ReplayRunResult, replay_transcript_with_record
from chorus.eval.scenario_player import CapturedRun, play_scenario
from chorus.eval.uc2_workflow_playback import play_uc2_workflow_fixture
from chorus.eval.uc3_workflow_playback import play_uc3_workflow_fixture
from chorus.persistence.replay_runs import ReplayRunStore

pytestmark = pytest.mark.live_deepseek

TEST_DATABASE_PREFIX = "chorus_live_deepseek_test"


def test_happy_path_fixtures_replay_through_live_deepseek_route(
    migrated_database_url: str,
) -> None:
    require_live_route_credential(LIVE_DEEPSEEK_ROUTE_ID)

    captured_runs = _happy_path_captured_runs(migrated_database_url)
    records_by_fixture: dict[str, list[str]] = {}
    with cast(
        psycopg.Connection[dict[str, Any]],
        psycopg.connect(migrated_database_url, row_factory=cast(Any, dict_row)),
    ) as conn:
        store = ReplayRunStore(conn)
        for captured in captured_runs:
            records_by_fixture[captured.fixture.fixture_id] = []
            _set_tenant_context(conn, captured)
            persist_captured_run_audit_refs(conn, captured)
            for transcript in captured_transcripts_for_replay(captured):
                replay = replay_transcript_with_record(
                    transcript,
                    route_id=LIVE_DEEPSEEK_ROUTE_ID,
                )
                outcome = replay_comparator_outcome(replay.record)
                records_by_fixture[captured.fixture.fixture_id].append(outcome)
                assert replay.record.original.runtime_route_id == "recorded-replay"
                assert replay.record.alternate.runtime_route_id == LIVE_DEEPSEEK_ROUTE_ID
                assert replay.record.alternate.provider_id == "deepseek"
                store.record_replay_run(replay.record)
                _assert_persisted_live_replay_record(
                    conn,
                    replay,
                    expected_route_id=LIVE_DEEPSEEK_ROUTE_ID,
                    expected_provider_id="deepseek",
                    expected_outcome=outcome,
                )
                assert outcome in ALLOWED_LIVE_COMPARATOR_OUTCOMES, (
                    "live DeepSeek comparator outcome for "
                    f"{captured.fixture.fixture_id}/{transcript.task_kind} was {outcome!r}: "
                    f"{replay.record.comparator.result}"
                )
        conn.commit()

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


def _set_tenant_context(
    conn: psycopg.Connection[dict[str, Any]],
    captured: CapturedRun,
) -> None:
    tenant_id = captured.transcripts[0].tenant_id
    conn.execute("SELECT set_config('app.tenant_id', %s, false)", (tenant_id,))


def _assert_persisted_live_replay_record(
    conn: psycopg.Connection[dict[str, Any]],
    replay: ReplayRunResult,
    *,
    expected_route_id: str,
    expected_provider_id: str,
    expected_outcome: str,
) -> None:
    record = replay.record
    row = conn.execute(
        """
        SELECT
            replay.replay_run_id::text AS replay_run_id,
            replay.original_invocation_id::text AS original_invocation_id,
            replay.original_transcript_id::text AS original_transcript_id,
            replay.original_runtime_route_id,
            replay.original_provider_id,
            replay.original_model_id,
            replay.alternate_runtime_route_id,
            replay.alternate_provider_id,
            replay.alternate_model_id,
            replay.comparator_status,
            replay.comparator_result,
            decision.invocation_id::text AS joined_invocation_id,
            decision.provider AS joined_decision_provider,
            decision.model AS joined_decision_model,
            transcript.transcript_id::text AS joined_transcript_id,
            transcript.route_id AS joined_transcript_route,
            transcript.provider_id AS joined_transcript_provider,
            transcript.model_id AS joined_transcript_model
        FROM replay_run_records AS replay
        JOIN decision_trail_entries AS decision
          ON decision.tenant_id = replay.tenant_id
         AND decision.invocation_id = replay.original_invocation_id
        JOIN agent_invocation_transcripts AS transcript
          ON transcript.tenant_id = replay.tenant_id
         AND transcript.transcript_id = replay.original_transcript_id
        WHERE replay.tenant_id = %s
          AND replay.replay_run_id = %s
        """,
        (record.tenant_id, record.replay_run_id),
    ).fetchone()

    assert row is not None
    assert row["replay_run_id"] == str(record.replay_run_id)
    assert row["original_invocation_id"] == str(record.original.invocation_id)
    assert row["original_transcript_id"] == str(record.original.transcript_id)
    assert row["original_runtime_route_id"] == "recorded-replay"
    assert row["original_provider_id"] == record.original.provider_id
    assert row["original_model_id"] == record.original.model_id
    assert row["joined_invocation_id"] == str(record.original.invocation_id)
    assert row["joined_decision_provider"] == record.original.provider_id
    assert row["joined_decision_model"] == record.original.model_id
    assert row["joined_transcript_id"] == str(record.original.transcript_id)
    assert row["joined_transcript_route"] == "recorded-replay"
    assert row["joined_transcript_provider"] == record.original.provider_id
    assert row["joined_transcript_model"] == record.original.model_id
    assert row["alternate_runtime_route_id"] == expected_route_id
    assert row["alternate_provider_id"] == expected_provider_id
    assert row["alternate_model_id"] == record.alternate.model_id
    assert row["comparator_status"] == record.comparator.status.value
    assert row["comparator_result"] == record.comparator.result
    assert replay_comparator_outcome(record) == expected_outcome

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from chorus.eval import run
from chorus.eval.invariants import UC2_INVARIANTS, run_invariants
from chorus.eval.uc2_workflow_playback import play_uc2_workflow_fixture_async
from chorus.eval.use_cases.uc2_conduct import (
    assert_uc2_agent_decision_and_transcript_evidence,
    assert_uc2_connector_ref_evidence,
    assert_uc2_engagement_letter_send_approval_gate,
    assert_uc2_workflow_progress_evidence,
)

TEST_DATABASE_PREFIX = "chorus_uc2_eval_test"

ROOT = Path(__file__).resolve().parents[2]
UC2_FIXTURE_DIR = ROOT / "chorus" / "eval" / "fixtures" / "uc2"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "fixture_name",
        "expected_tasks",
        "expected_tools",
        "expected_steps",
        "expected_outcome",
    ),
    [
        (
            "uc2_synthetic_acceptance_conduct.json",
            [
                "uc2_matter_classification",
                "uc2_party_extraction",
                "uc2_conflict_determination",
                "uc2_engagement_decision",
            ],
            [
                "conflict_check.search",
                "kyc_bo.lookup",
                "aml_record_store.record_assessment",
                "engagement_letter.draft",
                "engagement_letter.send",
            ],
            {
                "intake",
                "matter_classification",
                "party_extraction",
                "conflict_check",
                "conflict_determination",
                "kyc_beneficial_ownership",
                "aml_assessment",
                "engagement_decision",
                "engagement_letter_draft",
                "engagement_letter_send",
                "close",
            },
            "approval_required",
        ),
        (
            "uc2_conflict_exception_approval_conduct.json",
            [
                "uc2_matter_classification",
                "uc2_party_extraction",
                "uc2_conflict_determination",
            ],
            [
                "conflict_check.search",
                "engagement_letter.route_manual_review",
            ],
            {
                "intake",
                "matter_classification",
                "party_extraction",
                "conflict_check",
                "conflict_determination",
                "conflict_exception_approval",
                "manual_review",
                "close",
            },
            "approval_required",
        ),
    ],
)
async def test_uc2_fixtures_play_through_workflow_runtime_and_gateway(
    migrated_database_url: str,
    fixture_name: str,
    expected_tasks: list[str],
    expected_tools: list[str],
    expected_steps: set[str],
    expected_outcome: str,
) -> None:
    fixture = run.load_fixture(UC2_FIXTURE_DIR / fixture_name)

    result = await play_uc2_workflow_fixture_async(
        fixture,
        database_url=migrated_database_url,
    )
    captured = result.captured_run
    checks = run_invariants(captured, invariants=UC2_INVARIANTS)

    assert [check for check in checks if check.status == "fail"] == []
    assert result.workflow_result.outcome == expected_outcome
    assert [record.task_kind for record in captured.decisions] == expected_tasks
    assert [record.task_kind for record in captured.decisions] == [
        record.task_kind for record in captured.decisions if record.structured_data
    ]
    assert [record.tool_name for record in captured.tool_actions] == expected_tools
    assert expected_steps.issubset(
        {
            event.step
            for event in captured.projection_events
            if event.event_type == "workflow.step.completed"
        }
    )
    assert len(captured.transcripts) == len(captured.decisions)


@pytest.mark.asyncio
async def test_uc2_conduct_invariants_fail_at_missing_evidence_stage(
    migrated_database_url: str,
) -> None:
    fixture = run.load_fixture(UC2_FIXTURE_DIR / "uc2_synthetic_acceptance_conduct.json")
    playback = await play_uc2_workflow_fixture_async(
        fixture,
        database_url=migrated_database_url,
    )
    captured = playback.captured_run

    missing_progress = deepcopy(captured)
    missing_progress.projection_events = []
    progress_checks = assert_uc2_workflow_progress_evidence(missing_progress)
    assert progress_checks[0].status == "fail"
    assert "no workflow progress events captured" in progress_checks[0].detail

    missing_decision = deepcopy(captured)
    missing_decision.decisions = [
        decision
        for decision in missing_decision.decisions
        if decision.task_kind != "uc2_engagement_decision"
    ]
    decision_checks = assert_uc2_agent_decision_and_transcript_evidence(missing_decision)
    assert decision_checks[0].status == "fail"
    assert "missing decision-trail row for uc2_engagement_decision" in decision_checks[0].detail

    missing_transcript = deepcopy(captured)
    engagement_decision = next(
        decision
        for decision in missing_transcript.decisions
        if decision.task_kind == "uc2_engagement_decision"
    )
    missing_transcript.transcripts = [
        transcript
        for transcript in missing_transcript.transcripts
        if transcript.invocation_id != engagement_decision.invocation_id
    ]
    transcript_checks = assert_uc2_agent_decision_and_transcript_evidence(missing_transcript)
    assert transcript_checks[0].status == "fail"
    assert "missing transcript row for uc2_engagement_decision" in transcript_checks[0].detail

    missing_tool = deepcopy(captured)
    missing_tool.tool_actions = [
        action
        for action in missing_tool.tool_actions
        if action.tool_name != "engagement_letter.draft"
    ]
    tool_checks = assert_uc2_connector_ref_evidence(missing_tool)
    assert tool_checks[0].status == "fail"
    assert "missing engagement_letter.draft write action" in tool_checks[0].detail

    missing_approval_package = deepcopy(captured)
    missing_approval_package.tool_actions = [
        replace(action, approval_package={})
        if action.tool_name == "engagement_letter.send"
        else action
        for action in missing_approval_package.tool_actions
    ]
    approval_checks = assert_uc2_engagement_letter_send_approval_gate(missing_approval_package)
    assert approval_checks[0].status == "fail"
    assert "send approval package table evidence missing" in approval_checks[0].detail

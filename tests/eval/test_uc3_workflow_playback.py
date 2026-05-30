from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from chorus.eval import run
from chorus.eval.invariants import UC3_INVARIANTS, run_invariants
from chorus.eval.uc3_workflow_playback import play_uc3_workflow_fixture_async
from chorus.eval.use_cases.uc3_conduct import (
    assert_uc3_agent_decision_and_transcript_evidence,
    assert_uc3_connector_ref_evidence,
    assert_uc3_suitability_report_issue_approval_gate,
    assert_uc3_workflow_progress_evidence,
)

TEST_DATABASE_PREFIX = "chorus_uc3_eval_test"

ROOT = Path(__file__).resolve().parents[2]
UC3_FIXTURE_DIR = ROOT / "chorus" / "eval" / "fixtures" / "uc3"


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
            "uc3_synthetic_suitability_conduct.json",
            [
                "uc3_advice_scope_classification",
                "uc3_fact_find_summary",
                "uc3_risk_profile_assessment",
                "uc3_consumer_duty_support_assessment",
                "uc3_suitability_conclusion",
            ],
            [
                "attitude_to_risk.profile",
                "capacity_for_loss.assess",
                "platform_research.run",
                "suitability_report.draft",
                "suitability_report.issue",
            ],
            {
                "intake",
                "advice_scope_classification",
                "fact_find_summary",
                "attitude_to_risk_profile",
                "risk_profile_assessment",
                "capacity_for_loss_assessment",
                "consumer_duty_support_assessment",
                "platform_research",
                "suitability_conclusion",
                "suitability_report_draft",
                "suitability_report_approval",
                "suitability_report_issue",
                "close",
            },
            "approval_required",
        ),
        (
            "uc3_vulnerability_support_handoff_conduct.json",
            [
                "uc3_advice_scope_classification",
                "uc3_fact_find_summary",
                "uc3_risk_profile_assessment",
                "uc3_consumer_duty_support_assessment",
            ],
            [
                "attitude_to_risk.profile",
                "capacity_for_loss.assess",
                "suitability_report.route_manual_review",
            ],
            {
                "intake",
                "advice_scope_classification",
                "fact_find_summary",
                "attitude_to_risk_profile",
                "risk_profile_assessment",
                "capacity_for_loss_assessment",
                "consumer_duty_support_assessment",
                "vulnerability_handoff_approval",
                "manual_review",
                "close",
            },
            "approval_required",
        ),
    ],
)
async def test_uc3_fixtures_play_through_workflow_runtime_and_gateway(
    migrated_database_url: str,
    fixture_name: str,
    expected_tasks: list[str],
    expected_tools: list[str],
    expected_steps: set[str],
    expected_outcome: str,
) -> None:
    fixture = run.load_fixture(UC3_FIXTURE_DIR / fixture_name)

    result = await play_uc3_workflow_fixture_async(
        fixture,
        database_url=migrated_database_url,
    )
    captured = result.captured_run
    checks = run_invariants(captured, invariants=UC3_INVARIANTS)

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
async def test_uc3_conduct_invariants_fail_at_missing_evidence_stage(
    migrated_database_url: str,
) -> None:
    fixture = run.load_fixture(UC3_FIXTURE_DIR / "uc3_synthetic_suitability_conduct.json")
    playback = await play_uc3_workflow_fixture_async(
        fixture,
        database_url=migrated_database_url,
    )
    captured = playback.captured_run

    missing_progress = deepcopy(captured)
    missing_progress.projection_events = []
    progress_checks = assert_uc3_workflow_progress_evidence(missing_progress)
    assert progress_checks[0].status == "fail"
    assert "no workflow progress events captured" in progress_checks[0].detail

    missing_decision = deepcopy(captured)
    missing_decision.decisions = [
        decision
        for decision in missing_decision.decisions
        if decision.task_kind != "uc3_suitability_conclusion"
    ]
    decision_checks = assert_uc3_agent_decision_and_transcript_evidence(missing_decision)
    assert decision_checks[0].status == "fail"
    assert "missing decision-trail row for uc3_suitability_conclusion" in decision_checks[0].detail

    missing_transcript = deepcopy(captured)
    suitability_decision = next(
        decision
        for decision in missing_transcript.decisions
        if decision.task_kind == "uc3_suitability_conclusion"
    )
    missing_transcript.transcripts = [
        transcript
        for transcript in missing_transcript.transcripts
        if transcript.invocation_id != suitability_decision.invocation_id
    ]
    transcript_checks = assert_uc3_agent_decision_and_transcript_evidence(missing_transcript)
    assert transcript_checks[0].status == "fail"
    assert "missing transcript row for uc3_suitability_conclusion" in transcript_checks[0].detail

    missing_tool = deepcopy(captured)
    missing_tool.tool_actions = [
        action
        for action in missing_tool.tool_actions
        if action.tool_name != "suitability_report.draft"
    ]
    tool_checks = assert_uc3_connector_ref_evidence(missing_tool)
    assert tool_checks[0].status == "fail"
    assert "missing suitability_report.draft write action" in tool_checks[0].detail

    missing_approval_package = deepcopy(captured)
    missing_approval_package.tool_actions = [
        replace(action, approval_package={})
        if action.tool_name == "suitability_report.issue"
        else action
        for action in missing_approval_package.tool_actions
    ]
    approval_checks = assert_uc3_suitability_report_issue_approval_gate(missing_approval_package)
    assert approval_checks[0].status == "fail"
    assert "issue approval package table evidence missing" in approval_checks[0].detail

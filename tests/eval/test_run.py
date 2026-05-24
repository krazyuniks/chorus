from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from chorus.contracts.generated.eval.eval_fixture import EvalFixture
from chorus.eval import run
from chorus.eval.common_invariants import COMMON_INVARIANTS
from chorus.eval.invariants import UC1_INVARIANTS, UC2_INVARIANTS, run_invariants
from chorus.eval.replay import load_transcript, replay_transcript_with_record
from chorus.eval.scenario_player import (
    CapturedRun,
    DecisionTrailRecord,
    ProjectionEvent,
    ToolActionRecord,
    TranscriptRecord,
    play_scenario,
)
from chorus.eval.use_cases.uc1_conduct import UC1_CONDUCT_INVARIANTS
from chorus.eval.use_cases.uc2_conduct import UC2_CONDUCT_INVARIANTS
from chorus.llm_provider import (
    InvocationArgs,
    InvocationResult,
    LLMProviderInvocationError,
    RouteCatalogue,
    RouteCatalogueEntry,
)

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
        "assert_uc1_terminal_connector_routing",
        "assert_connector_authority_discipline",
        "assert_projection_convergence",
    ]
    assert [invariant.__name__ for invariant in UC1_CONDUCT_INVARIANTS] == [
        "assert_uc1_qualification_invariants",
        "assert_uc1_terminal_connector_routing",
    ]
    assert set(UC1_CONDUCT_INVARIANTS).issubset(UC1_INVARIANTS)
    assert set(COMMON_INVARIANTS).issubset(UC1_INVARIANTS)


def test_uc2_invariant_suite_composes_common_and_conduct_modules() -> None:
    assert [invariant.__name__ for invariant in UC2_INVARIANTS] == [
        "assert_cross_port_payload_validity",
        "assert_governed_decision_provenance",
        "assert_audit_completeness",
        "assert_observability_emission",
        "assert_uc2_engagement_decision_conduct",
        "assert_uc2_engagement_letter_send_approval_gate",
        "assert_uc2_connector_ref_evidence",
        "assert_connector_authority_discipline",
        "assert_projection_convergence",
    ]
    assert [invariant.__name__ for invariant in UC2_CONDUCT_INVARIANTS] == [
        "assert_uc2_engagement_decision_conduct",
        "assert_uc2_engagement_letter_send_approval_gate",
        "assert_uc2_connector_ref_evidence",
    ]
    assert set(UC2_CONDUCT_INVARIANTS).issubset(UC2_INVARIANTS)
    assert set(COMMON_INVARIANTS).issubset(UC2_INVARIANTS)


def test_uc2_conduct_invariants_pass_safe_synthetic_acceptance_run() -> None:
    captured = _uc2_captured_run()

    checks = run_invariants(captured, invariants=UC2_INVARIANTS)

    assert [check for check in checks if check.status == "fail"] == []
    assert any(check.name == "UC2 engagement decision conduct" for check in checks)
    assert any(check.name == "UC2 engagement-letter send approval gate" for check in checks)
    assert any(check.name == "UC2 connector ref evidence" for check in checks)


def test_uc2_conduct_invariants_fail_completed_acceptance_without_send_apply() -> None:
    captured = _uc2_captured_run(include_send_apply=False)

    checks = [
        check
        for invariant in UC2_CONDUCT_INVARIANTS
        for check in invariant(captured)
        if check.status == "fail"
    ]

    assert checks
    assert checks[0].name == "UC2 engagement-letter send approval gate"
    assert "lacks approved engagement_letter.send apply" in checks[0].detail


def test_uc2_conduct_invariants_fail_acceptance_with_blocked_conflict() -> None:
    captured = _uc2_captured_run(engagement_data={"conflict_status": "own_interest_conflict"})

    checks = [
        check
        for invariant in UC2_CONDUCT_INVARIANTS
        for check in invariant(captured)
        if check.status == "fail"
    ]

    assert checks
    assert checks[0].name == "UC2 engagement decision conduct"
    assert "own_interest_conflict" in checks[0].detail


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


def test_uc2_schema_only_eval_fixture_validates_without_default_playback() -> None:
    fixture = run.load_fixture(FIXTURE_DIR / "uc2" / "uc2_synthetic_acceptance_conduct.json")

    assert fixture.workflow_type.value == "uc2_legal_services_intake_conflict_check"
    assert fixture.scenario == "synthetic_acceptance_conduct"
    assert fixture.input.source_fixture_path == (
        "contracts/intake/uc2/samples/email_legal_intake.sample.json"
    )
    assert fixture.expected.use_case_outcome == ("accepted_engagement_letter_send_approval_gated")
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


@pytest.mark.parametrize(
    "fixture_name",
    [
        "uc1_accepted_routing.json",
        "uc1_referred_routing.json",
        "uc1_declined_routing.json",
    ],
)
def test_assert_uc1_terminal_routing_fixtures_pass_offline(fixture_name: str) -> None:
    assert run.main(["assert", "--fixture", str(FIXTURE_DIR / fixture_name)]) == 0


def test_replay_classifier_transcript_matches() -> None:
    assert run.main(["replay", "--transcript", TRANSCRIPT_FIXTURE]) == 0


def test_replay_classifier_transcript_builds_safe_run_record() -> None:
    result = replay_transcript_with_record(load_transcript(ROOT / TRANSCRIPT_FIXTURE))

    assert result.checks[0].status == "pass"
    record = result.record
    assert str(record.original.invocation_id) == "11000000-0000-4000-8000-000000000001"
    assert str(record.original.transcript_id) == "21000000-0000-4000-8000-000000000101"
    assert record.original.runtime_route_id == "recorded-replay"
    assert record.alternate.runtime_route_id == "recorded-replay"
    assert record.alternate.provider_id == "local"
    assert record.alternate.model_id == "uc1-happy-path-v1"
    assert record.lineage.policy_snapshot_ref == "policy_snapshot:uc1:default:v1"
    assert record.lineage.prompt_reference == "prompts/uc1/classifier/v1.md"
    assert record.lineage.response_schema_contract_ref == (
        "contracts/llm_provider/uc1_agent_io.schema.json"
    )
    assert record.comparator.status.value == "pass"
    assert record.comparator.result["tier"] == "metrics_only"
    assert record.comparator.result["reason_code"] in {
        "metrics_only_delta",
        "metrics_only_no_delta",
    }
    assert "metrics.latency_ms" in record.comparator.result["compared_field_names"]
    assert (
        "provider_metadata.response_schema.hash" in record.comparator.result["compared_field_names"]
    )
    assert "tier_placeholder" not in record.comparator.result
    assert record.metrics.original.latency_ms == 50
    assert record.metrics.alternate.cost_amount_usd == 0
    assert isinstance(record.metrics.alternate.latency_ms, int)
    assert "enquiry_body_text" not in str(record.comparator.result)


def test_replay_hard_fails_schema_invalid_output() -> None:
    transcript = load_transcript(ROOT / TRANSCRIPT_FIXTURE)
    invalid_result = _invocation_result(
        structured_data={
            "product_family_category": "motor_private_car",
            "demanded_cover_shape": "third_party_fire_and_theft",
            "classification_attempt": "not-an-integer",
            "deeper_context_completed": None,
        }
    )

    result = replay_transcript_with_record(
        transcript,
        route_catalogue=_catalogue_returning(invalid_result),
    )

    assert result.record.comparator.status.value == "fail"
    assert result.record.comparator.result["tier"] == "hard_fail"
    assert result.record.comparator.result["reason_code"] == "schema_invalid_replay_output"
    assert result.record.comparator.result["field_names"] == [
        "structured_data.classification_attempt"
    ]
    assert result.record.metrics.original.latency_ms == 50


def test_replay_hard_fails_missing_qualification_policy_snapshot_ref() -> None:
    transcript = _qualifier_transcript()
    structured = _qualification_structured_data()
    structured["qualification_verdict_category"] = "accept"
    structured["policy_snapshot_ref"] = None

    result = replay_transcript_with_record(
        transcript,
        route_catalogue=_catalogue_returning(_invocation_result(structured_data=structured)),
    )

    assert result.record.comparator.status.value == "fail"
    assert result.record.comparator.result["tier"] == "hard_fail"
    assert result.record.comparator.result["reason_code"] == "missing_policy_snapshot_evidence"
    assert result.record.comparator.result["field_names"] == ["structured_data.policy_snapshot_ref"]


def test_replay_hard_fails_missing_required_uc1_conduct_hooks() -> None:
    transcript = _qualifier_transcript()
    structured = _qualification_structured_data()
    del structured["best_interests_check"]

    result = replay_transcript_with_record(
        transcript,
        route_catalogue=_catalogue_returning(_invocation_result(structured_data=structured)),
    )

    assert result.record.comparator.status.value == "fail"
    assert result.record.comparator.result["reason_code"] == "missing_conduct_hooks"
    assert result.record.comparator.result["field_names"] == [
        "structured_data.best_interests_check"
    ]


def test_replay_hard_fails_unsafe_action_proposals() -> None:
    transcript = load_transcript(ROOT / TRANSCRIPT_FIXTURE)
    result = replay_transcript_with_record(
        transcript,
        route_catalogue=_catalogue_returning(
            _invocation_result(
                structured_data=_classification_structured_data(),
                tool_calls=({"name": "direct_connector_write"},),
            )
        ),
    )

    assert result.record.comparator.status.value == "fail"
    assert result.record.comparator.result["reason_code"] == "unsafe_action_proposal"
    assert result.record.comparator.result["field_names"] == ["tool_calls"]
    assert "direct_connector_write" not in str(result.record.comparator.result)


def test_replay_hard_fails_missing_transcript_linkage(
    tmp_path: Path,
) -> None:
    data = json.loads((ROOT / TRANSCRIPT_FIXTURE).read_text(encoding="utf-8"))
    data.pop("transcript_id")
    transcript_path = tmp_path / "missing_transcript_link.json"
    transcript_path.write_text(json.dumps(data), encoding="utf-8")

    result = replay_transcript_with_record(
        load_transcript(transcript_path),
        route_catalogue=_catalogue_returning(_invocation_result()),
    )

    assert result.record.comparator.status.value == "fail"
    assert result.record.comparator.result["reason_code"] == "missing_audit_transcript_evidence"
    assert result.record.comparator.result["field_names"] == ["original.transcript_id"]


def test_replay_hard_fails_provider_port_errors() -> None:
    transcript = load_transcript(ROOT / TRANSCRIPT_FIXTURE)

    result = replay_transcript_with_record(
        transcript,
        route_catalogue=_catalogue_raising("structured_output_schema_violation:structured_data"),
    )

    assert result.record.comparator.status.value == "error"
    assert result.record.comparator.safe_error_reason == (
        "structured_output_schema_violation:structured_data"
    )
    assert result.record.comparator.result["reason_code"] == "provider_port_replay_error"
    assert result.record.comparator.result["provider_error_reason"] == (
        "structured_output_schema_violation:structured_data"
    )


def test_replay_decision_fails_terminal_verdict_mismatch() -> None:
    transcript = _qualifier_transcript()
    structured = _qualification_structured_data()
    structured.update(
        {
            "qualification_verdict_category": "accept",
            "missing_data_request_required": False,
            "product_family_category": "motor_private_car",
            "qualification_summary_ref": "qsum_demo_accept_001",
        }
    )

    result = replay_transcript_with_record(
        transcript,
        route_catalogue=_catalogue_returning(_invocation_result(structured_data=structured)),
    )

    assert result.record.comparator.status.value == "fail"
    assert result.record.comparator.result["tier"] == "decision_fail"
    assert result.record.comparator.result["reason_code"] == "terminal_verdict_mismatch"
    assert result.record.comparator.result["field_names"] == [
        "derived.connector_action_category",
        "structured_data.qualification_verdict_category",
    ]
    assert result.record.metrics.original.latency_ms == 50
    assert "qsum_demo_accept_001" not in str(result.record.comparator.result)


def test_replay_decision_fails_route_category_alias_mismatch() -> None:
    expected = _qualification_structured_data()
    expected.pop("qualification_verdict_category")
    expected.update(
        {
            "route_category": "accept",
            "missing_data_request_required": False,
            "product_family_category": "motor_private_car",
            "qualification_summary_ref": "qsum_demo_accept_001",
        }
    )
    transcript = replace(_qualifier_transcript(), expected_structured_data=expected)
    structured = _qualification_structured_data()
    structured.update(
        {
            "qualification_verdict_category": "refer",
            "missing_data_request_required": False,
            "referral_destination_category": "internal_complex_risk_desk",
            "referral_reason_category": "complex_risk_outside_appetite",
        }
    )

    result = replay_transcript_with_record(
        transcript,
        route_catalogue=_catalogue_returning(_invocation_result(structured_data=structured)),
    )

    assert result.record.comparator.status.value == "fail"
    assert result.record.comparator.result["tier"] == "decision_fail"
    assert result.record.comparator.result["reason_code"] == "terminal_verdict_mismatch"
    assert result.record.comparator.result["changed_field_names"] == [
        "derived.connector_action_category",
        "structured_data.qualification_verdict_category",
        "structured_data.route_category",
    ]


def test_replay_review_finds_recommended_next_step_rationale_and_confidence() -> None:
    transcript = replace(
        _qualifier_transcript(),
        expected_recommended_next_step="continue",
        expected_confidence=0.88,
        expected_rationale="Captured qualification rationale.",
    )

    result = replay_transcript_with_record(
        transcript,
        route_catalogue=_catalogue_returning(
            _invocation_result(
                structured_data=_qualification_structured_data(),
                recommended_next_step="escalate",
                confidence=0.52,
                rationale="Alternate qualification rationale.",
            )
        ),
    )

    assert result.checks[0].status == "pass"
    assert result.checks[0].name == "replay review-finding tier"
    assert result.record.comparator.status.value == "pass"
    assert result.record.comparator.result["tier"] == "review_finding"
    assert result.record.comparator.result["non_terminal"] is True
    assert result.record.comparator.result["reason_codes"] == [
        "recommended_next_step_mismatch",
        "confidence_band_mismatch",
        "rationale_text_mismatch",
    ]
    assert result.record.comparator.result["changed_field_names"] == [
        "confidence",
        "rationale",
        "recommended_next_step",
    ]
    assert "Alternate qualification rationale" not in str(result.record.comparator.result)
    assert result.record.comparator.result["reason_code"] != "structured_data_diverged"
    assert "tier_placeholder" not in result.record.comparator.result


def test_replay_review_finds_optional_structured_and_evidence_selection_fields() -> None:
    expected = _qualification_structured_data()
    expected["qualification_summary_ref"] = "qsum_demo_missing_data_001"
    transcript = replace(_qualifier_transcript(), expected_structured_data=expected)
    structured = _qualification_structured_data()
    structured["qualification_summary_ref"] = "qsum_demo_missing_data_002"
    structured["best_interests_check"] = {
        **structured["best_interests_check"],
        "regulatory_ref": "ICOBS 2.1.1R",
    }

    result = replay_transcript_with_record(
        transcript,
        route_catalogue=_catalogue_returning(_invocation_result(structured_data=structured)),
    )

    assert result.record.comparator.status.value == "pass"
    assert result.record.comparator.result["tier"] == "review_finding"
    assert result.record.comparator.result["reason_codes"] == [
        "optional_structured_field_mismatch",
        "evidence_selection_mismatch",
    ]
    assert result.record.comparator.result["changed_field_names"] == [
        "structured_data.best_interests_check.regulatory_ref",
        "structured_data.qualification_summary_ref",
    ]
    assert "qsum_demo_missing_data_002" not in str(result.record.comparator.result)


def test_replay_metrics_only_classifies_metric_and_safe_provider_metadata_deltas() -> None:
    transcript = replace(
        load_transcript(ROOT / TRANSCRIPT_FIXTURE),
        original_cost_amount_usd=Decimal("0.001000"),
        original_latency_ms=9999,
        token_usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        provider_metadata={
            "adapter": "recorded-replay-v1",
            "retry_count": 0,
            "response_id": "raw-original-response-id",
            "response_schema": {
                "name": "uc1_enquiry_classification_response",
                "hash": "sha256:" + "0" * 64,
                "response_format_type": "recorded_replay",
            },
        },
    )

    result = replay_transcript_with_record(
        transcript,
        route_catalogue=_catalogue_returning(
            _invocation_result(
                structured_data=_classification_structured_data(),
                cost_amount_usd=Decimal("0.003000"),
                token_usage={
                    "prompt_tokens": 12,
                    "completion_tokens": 7,
                    "total_tokens": 19,
                },
                provider_metadata={
                    "adapter": "recorded-replay-v2",
                    "retry_count": 1,
                    "response_id": "raw-alternate-response-id",
                    "response_schema": {
                        "name": "uc1_enquiry_classification_response",
                        "hash": "sha256:" + "1" * 64,
                        "response_format_type": "json_schema",
                    },
                },
            )
        ),
    )

    payload = result.record.comparator.result
    assert result.checks[0].status == "pass"
    assert result.checks[0].name == "replay metrics-only tier"
    assert result.record.comparator.status.value == "pass"
    assert payload["tier"] == "metrics_only"
    assert payload["reason_code"] == "metrics_only_delta"
    assert payload["reason_codes"] == [
        "cost_amount_delta",
        "latency_delta",
        "token_usage_delta",
        "retry_count_delta",
        "provider_metadata_delta",
    ]
    assert payload["changed_field_names"] == [
        "metrics.cost_amount_usd",
        "metrics.latency_ms",
        "metrics.token_usage.completion_tokens",
        "metrics.token_usage.prompt_tokens",
        "metrics.token_usage.total_tokens",
        "provider_metadata.adapter",
        "provider_metadata.response_schema.hash",
        "provider_metadata.response_schema.response_format_type",
        "provider_metadata.retry_count",
    ]
    assert payload["reason_code"] != "structured_data_diverged"
    assert "decision_comparator_pending" not in str(payload)
    assert "tier_placeholder" not in payload
    assert "raw-original-response-id" not in str(payload)
    assert "raw-alternate-response-id" not in str(payload)


def test_replay_hard_fail_takes_precedence_over_review_finding() -> None:
    transcript = replace(
        _qualifier_transcript(),
        expected_recommended_next_step="continue",
        expected_confidence=0.88,
        expected_rationale="Captured qualification rationale.",
    )
    structured = _qualification_structured_data()
    del structured["best_interests_check"]

    result = replay_transcript_with_record(
        transcript,
        route_catalogue=_catalogue_returning(
            _invocation_result(
                structured_data=structured,
                recommended_next_step="escalate",
                confidence=0.52,
                rationale="Alternate qualification rationale.",
            )
        ),
    )

    assert result.record.comparator.status.value == "fail"
    assert result.record.comparator.result["tier"] == "hard_fail"
    assert result.record.comparator.result["reason_code"] == "missing_conduct_hooks"


def test_replay_decision_fail_takes_precedence_over_review_finding() -> None:
    transcript = replace(
        _qualifier_transcript(),
        expected_recommended_next_step="continue",
        expected_confidence=0.88,
        expected_rationale="Captured qualification rationale.",
    )
    structured = _qualification_structured_data()
    structured.update(
        {
            "qualification_verdict_category": "accept",
            "missing_data_request_required": False,
            "product_family_category": "motor_private_car",
            "qualification_summary_ref": "qsum_demo_accept_001",
        }
    )

    result = replay_transcript_with_record(
        transcript,
        route_catalogue=_catalogue_returning(
            _invocation_result(
                structured_data=structured,
                recommended_next_step="escalate",
                confidence=0.52,
                rationale="Alternate qualification rationale.",
            )
        ),
    )

    assert result.record.comparator.status.value == "fail"
    assert result.record.comparator.result["tier"] == "decision_fail"
    assert result.record.comparator.result["reason_code"] == "terminal_verdict_mismatch"


def test_recorded_replay_scenario_captures_loaded_prompt_evidence() -> None:
    fixture = run.load_fixture(FIXTURE_DIR / "uc1_happy_path.json")
    captured = play_scenario(fixture)

    decision = captured.decisions[0]
    transcript = captured.transcripts[0]
    assert decision.prompt_reference == "prompts/uc1/classifier/v1.md"
    assert decision.prompt_hash.startswith("sha256:")
    assert decision.prompt_hash != "sha256:" + "0" * 64
    assert transcript.request_messages[0]["role"] == "system"
    assert str(transcript.request_messages[0]["content"]).startswith("# UC1 classifier v1")
    assert transcript.request_messages[1]["role"] == "system"
    assert "Return JSON only" in str(transcript.request_messages[1]["content"])
    assert "uc1_enquiry_classification_response" in str(transcript.request_messages[1]["content"])


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


@pytest.mark.parametrize(
    ("fixture_name", "category", "tool_name", "route_ref_key", "route_ref_prefix"),
    [
        (
            "uc1_accepted_routing.json",
            "accept",
            "crm.route_to_quoting_queue",
            "queued_route_ref",
            "qroute_",
        ),
        (
            "uc1_referred_routing.json",
            "refer",
            "referral_inbox.route",
            "referral_route_ref",
            "rroute_",
        ),
        (
            "uc1_declined_routing.json",
            "decline",
            "decline_ledger.route",
            "decline_route_ref",
            "droute_",
        ),
    ],
)
def test_terminal_routing_fixtures_capture_connector_path(
    fixture_name: str,
    category: str,
    tool_name: str,
    route_ref_key: str,
    route_ref_prefix: str,
) -> None:
    fixture = run.load_fixture(FIXTURE_DIR / fixture_name)
    captured = play_scenario(fixture)

    qualifier = next(
        decision for decision in captured.decisions if decision.task_kind == "enquiry_qualification"
    )
    assert qualifier.structured_data["qualification_verdict_category"] == category

    action = next(action for action in captured.tool_actions if action.tool_name == tool_name)
    assert action.actor_id == "uc1.qualifier"
    assert action.requested_mode == "write"
    assert action.enforced_mode == "write"
    assert action.verdict == "allow"
    assert action.approval_required is False
    assert action.output[route_ref_key].startswith(route_ref_prefix)

    completed_route_step = next(
        event
        for event in captured.projection_events
        if event.event_type == "workflow.step.completed"
        and event.payload.get("tool_name") == tool_name
    )
    assert completed_route_step.payload["routing_ref"] == action.output[route_ref_key]


def _uc2_captured_run(
    *,
    include_send_apply: bool = True,
    engagement_data: dict[str, Any] | None = None,
) -> CapturedRun:
    fixture = EvalFixture.model_validate(
        {
            "schema_version": "1.0.0",
            "fixture_id": "uc2-synthetic-acceptance",
            "name": "UC2 synthetic acceptance conduct evidence",
            "workflow_type": "uc2_legal_services_intake_conflict_check",
            "scenario": "synthetic_acceptance_conduct",
            "input": {
                "tenant_id": "tenant_demo",
                "subject_fixture_ref": "fixture_uc2_synthetic_acceptance",
                "source_fixture_path": "fixtures/uc2/synthetic-acceptance.json",
            },
            "expected": {
                "outcome_category": "propose",
                "use_case_outcome": "accepted_engagement_letter_sent",
            },
        }
    )
    now = datetime(2026, 5, 24, 10, 0, tzinfo=UTC)
    invocation_id = uuid4()
    correlation_id = "cor_eval_uc2_synthetic_acceptance"
    workflow_id = "uc2-eval-synthetic-acceptance"
    tenant_id = "tenant_demo"
    subject_id = uuid4()
    subject_ref = "legal_intake_eval_001"
    structured_data: dict[str, Any] = {
        "engagement_outcome": "accept_for_engagement",
        "engagement_decision_ref": "engagement_decision_eval_accept_001",
        "policy_snapshot_ref": "policy_snapshot:uc2:default:v1",
        "prospective_client_ref": "prospective_client_eval_001",
        "instructing_contact_ref": "contact_eval_001",
        "authority_status": "confirmed",
        "matter_scope_ref": "mscope_eval_001",
        "conflict_status": "no_conflict",
        "confidentiality_safeguard_status": "not_required",
        "cdd_status": "complete_standard",
        "beneficial_ownership_status": "complete",
        "aml_risk_rating": "standard",
        "aml_risk_assessment_ref": "aml_risk_eval_001_v1",
        "cdd_record_ref": "cdd_record_eval_001",
        "conflict_determination_ref": "conflict_determination_eval_001",
        "conduct_hook_refs": [
            "conduct_sra_identify_client_8_1",
            "conduct_sra_conflict_6_1_6_2",
            "conduct_sra_confidentiality_6_3_6_5",
            "conduct_mlr_cdd_reg_27_28",
            "conduct_sra_accountability_7_1_7_2",
        ],
    }
    if engagement_data is not None:
        structured_data.update(engagement_data)

    run_capture = CapturedRun(
        fixture=fixture,
        decisions=[
            DecisionTrailRecord(
                invocation_id=invocation_id,
                correlation_id=correlation_id,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                agent_id="uc2.engagement_decider",
                agent_role="engagement_decider",
                agent_version="v1",
                prompt_reference="prompts/uc2/engagement-decider/v1.md",
                prompt_hash="sha256:" + "1" * 64,
                provider="local",
                model="uc2-synthetic-v1",
                task_kind="uc2_engagement_decision",
                input_summary="safe UC2 synthetic engagement decision input",
                output_summary="safe UC2 synthetic engagement decision output",
                justification="safe synthetic conduct rationale",
                outcome="succeeded",
                cost_amount_usd=Decimal("0.000000"),
                duration_ms=50,
                started_at=now,
                completed_at=now + timedelta(milliseconds=50),
                contract_refs=["contracts/llm_provider/uc2_agent_io.schema.json"],
                structured_data=structured_data,
            )
        ],
        transcripts=[
            TranscriptRecord(
                transcript_id=uuid4(),
                invocation_id=invocation_id,
                correlation_id=correlation_id,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                route_id="recorded-replay",
                provider_id="local",
                model_id="uc2-synthetic-v1",
                adapter_version="synthetic-test-v1",
                parameters={"temperature": 0},
                request_messages=[],
                response_messages=[],
                structured_data=structured_data,
                started_at=now,
                completed_at=now + timedelta(milliseconds=50),
            )
        ],
        tool_actions=_uc2_tool_actions(
            invocation_id=invocation_id,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            now=now,
            include_send_apply=include_send_apply,
        ),
        projection_events=[
            _uc2_projection_event(
                correlation_id=correlation_id,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                subject_id=subject_id,
                subject_ref=subject_ref,
                sequence=1,
                event_type="workflow.started",
                step="intake",
                occurred_at=now,
            ),
            _uc2_projection_event(
                correlation_id=correlation_id,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                subject_id=subject_id,
                subject_ref=subject_ref,
                sequence=2,
                event_type="workflow.completed",
                step="close",
                occurred_at=now + timedelta(seconds=1),
            ),
        ],
        terminal_outcome="completed",
    )
    return run_capture


def _uc2_tool_actions(
    *,
    invocation_id: UUID,
    correlation_id: str,
    workflow_id: str,
    tenant_id: str,
    now: datetime,
    include_send_apply: bool,
) -> list[ToolActionRecord]:
    actions = [
        _uc2_tool_action(
            invocation_id=invocation_id,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            tool_name="conflict_check.search",
            mode="read",
            actor_id="uc2.conflict_analyst",
            verdict="allow",
            approval_required=False,
            approval_granted=None,
            occurred_at=now + timedelta(milliseconds=100),
            output={"conflict_check_ref": "conflict_check_eval_001"},
        ),
        _uc2_tool_action(
            invocation_id=invocation_id,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            tool_name="kyc_bo.lookup",
            mode="read",
            actor_id="uc2.aml_assessor",
            verdict="allow",
            approval_required=False,
            approval_granted=None,
            occurred_at=now + timedelta(milliseconds=150),
            output={
                "cdd_record_ref": "cdd_record_eval_001",
                "beneficial_ownership_snapshot_ref": "bo_snapshot_eval_001",
            },
        ),
        _uc2_tool_action(
            invocation_id=invocation_id,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            tool_name="aml_record_store.record_assessment",
            mode="write",
            actor_id="uc2.aml_assessor",
            verdict="allow",
            approval_required=False,
            approval_granted=None,
            occurred_at=now + timedelta(milliseconds=200),
            output={"aml_risk_assessment_ref": "aml_risk_eval_001_v1"},
        ),
        _uc2_tool_action(
            invocation_id=invocation_id,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            tool_name="engagement_letter.draft",
            mode="write",
            actor_id="uc2.engagement_decider",
            verdict="allow",
            approval_required=False,
            approval_granted=None,
            occurred_at=now + timedelta(milliseconds=250),
            output={
                "engagement_letter_ref": "engagement_letter_eval_001",
                "draft_ref": "engagement_letter_draft_eval_001",
            },
        ),
        _uc2_tool_action(
            invocation_id=invocation_id,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            tool_name="engagement_letter.send",
            mode="write",
            actor_id="uc2.engagement_decider",
            verdict="approval_required",
            approval_required=True,
            approval_granted=None,
            occurred_at=now + timedelta(milliseconds=300),
            output={
                "approval_id": str(uuid4()),
                "approval_state": "requested",
                "requested_action": "engagement_letter.send.write",
            },
        ),
    ]
    if include_send_apply:
        actions.append(
            _uc2_tool_action(
                invocation_id=invocation_id,
                correlation_id=correlation_id,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                tool_name="engagement_letter.send",
                mode="write",
                actor_id="matter_owner_demo",
                actor_type="human",
                action="approval.apply",
                verdict="allow",
                approval_required=True,
                approval_granted=True,
                occurred_at=now + timedelta(milliseconds=350),
                output={
                    "approval_apply_status": "applied",
                    "send_record_ref": "engagement_letter_send_eval_001",
                },
            )
        )
    return actions


def _uc2_tool_action(
    *,
    invocation_id: UUID,
    correlation_id: str,
    workflow_id: str,
    tenant_id: str,
    tool_name: str,
    mode: str,
    actor_id: str,
    verdict: str,
    approval_required: bool,
    approval_granted: bool | None,
    occurred_at: datetime,
    output: dict[str, Any],
    actor_type: str = "agent",
    action: str = "tool_call.decided",
) -> ToolActionRecord:
    return ToolActionRecord(
        audit_event_id=uuid4(),
        invocation_id=invocation_id,
        correlation_id=correlation_id,
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        actor_type=actor_type,
        actor_id=actor_id,
        category="tool_gateway",
        action=action,
        tool_name=tool_name,
        requested_mode=mode,
        enforced_mode=mode,
        verdict=verdict,
        reason=f"synthetic UC2 {tool_name} {verdict}",
        approval_required=approval_required,
        approval_granted=approval_granted,
        occurred_at=occurred_at,
        output=output,
    )


def _uc2_projection_event(
    *,
    correlation_id: str,
    workflow_id: str,
    tenant_id: str,
    subject_id: UUID,
    subject_ref: str,
    sequence: int,
    event_type: str,
    step: str,
    occurred_at: datetime,
) -> ProjectionEvent:
    return ProjectionEvent(
        event_id=uuid4(),
        correlation_id=correlation_id,
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        workflow_type="uc2_legal_services_intake_conflict_check",
        subject_id=subject_id,
        subject_ref=subject_ref,
        sequence=sequence,
        event_type=event_type,
        step=step,
        occurred_at=occurred_at,
        payload={"subject_summary": "safe UC2 synthetic intake", "outcome": "completed"},
    )


class _StaticAdapter:
    adapter_version = "static-test-v1"

    def __init__(self, result: InvocationResult) -> None:
        self._result = result

    def invoke(self, args: InvocationArgs) -> InvocationResult:
        del args
        return self._result


class _FailingReplayAdapter:
    adapter_version = "failing-test-v1"

    def __init__(self, reason: str) -> None:
        self._reason = reason

    def invoke(self, args: InvocationArgs) -> InvocationResult:
        raise LLMProviderInvocationError(
            route_id=args.route_id,
            reason=self._reason,
            retryable=False,
        )


def _catalogue_returning(result: InvocationResult) -> RouteCatalogue:
    return _catalogue_for_adapter(_StaticAdapter(result))


def _catalogue_raising(reason: str) -> RouteCatalogue:
    return _catalogue_for_adapter(_FailingReplayAdapter(reason))


def _catalogue_for_adapter(adapter: Any) -> RouteCatalogue:
    return RouteCatalogue(
        [
            RouteCatalogueEntry(
                route_id="recorded-replay",
                provider_id="local",
                model_id="uc1-happy-path-v1",
                adapter=adapter,
                parameters={},
            )
        ]
    )


def _invocation_result(
    *,
    structured_data: dict[str, Any] | None = None,
    tool_calls: tuple[dict[str, Any], ...] = (),
    confidence: float = 0.88,
    recommended_next_step: str = "continue",
    rationale: str = "Replay fixture rationale.",
    cost_amount_usd: Decimal = Decimal("0.000000"),
    token_usage: dict[str, int] | None = None,
    provider_metadata: dict[str, Any] | None = None,
) -> InvocationResult:
    return InvocationResult(
        summary="Replay fixture response.",
        structured_data=structured_data or _classification_structured_data(),
        confidence=confidence,
        recommended_next_step=recommended_next_step,
        rationale=rationale,
        cost_amount_usd=cost_amount_usd,
        tool_calls=tool_calls,
        token_usage=token_usage or {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        provider_metadata=provider_metadata or {},
    )


def _classification_structured_data() -> dict[str, Any]:
    return {
        "product_family_category": "motor_private_car",
        "demanded_cover_shape": "third_party_fire_and_theft",
        "classification_attempt": None,
        "deeper_context_completed": None,
    }


def _qualifier_transcript() -> Any:
    base = load_transcript(ROOT / TRANSCRIPT_FIXTURE)
    return replace(
        base,
        invocation_id="11000000-0000-4000-8000-000000000003",
        transcript_id="21000000-0000-4000-8000-000000000103",
        task_kind="enquiry_qualification",
        agent_role="qualifier",
        prompt_reference="prompts/uc1/qualifier/v1.md",
        prompt_hash="sha256:2877d857fba0d2dc974e73968977dfd5072568b03aca9ed8adb73fab01d17f5f",
        route_version_ref="model_route_versions:11000000-0000-4000-8000-000000000003:1",
        expected_structured_data=_qualification_structured_data(),
    )


def _qualification_structured_data() -> dict[str, Any]:
    return {
        "qualification_verdict_category": "missing_data",
        "missing_data_request_required": True,
        "conduct_hooks_pass": True,
        "best_interests_check": {
            "status": "pass",
            "regulatory_ref": "ICOBS 2.5.-1R",
            "summary": None,
        },
        "demands_and_needs_statement": {
            "captured": True,
            "regulatory_ref": "ICOBS 5",
            "summary": "Customer seeks third-party fire and theft cover.",
        },
        "target_market_check": {
            "status": "pass",
            "regulatory_ref": "PROD 4",
            "summary": None,
        },
        "foreseeable_harm_check": {
            "status": "no_harm_identified",
            "regulatory_ref": "Consumer Duty PRIN 12",
            "summary": None,
        },
        "policy_snapshot_ref": "policy_snapshot:uc1:default:v1",
        "customer_ref": "cust_demo_001",
        "verdict_ref": "verdict_demo_missing_data_001",
        "routing_policy_ref": "policy_uc1_routing_v1",
        "product_family_category": None,
        "qualification_summary_ref": None,
        "referral_destination_category": None,
        "referral_reason_category": None,
        "decline_reason_category": None,
    }

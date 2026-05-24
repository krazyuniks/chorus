"""Invariant suite composition for captured eval runs.

Common architecture checks live in :mod:`chorus.eval.common_invariants`.
Per-use-case conduct checks live under :mod:`chorus.eval.use_cases`. This
module keeps the current UC1 suite and public imports stable for the eval
runner while UC2 and UC3 expose their own conduct suites for focused tests.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from chorus.eval.common_invariants import (
    assert_audit_completeness,
    assert_connector_authority_discipline,
    assert_cross_port_payload_validity,
    assert_governed_decision_provenance,
    assert_observability_emission,
    assert_projection_convergence,
)
from chorus.eval.scenario_player import CapturedRun
from chorus.eval.types import EvalCheck, EvalStatus
from chorus.eval.use_cases.uc1_conduct import (
    assert_uc1_qualification_invariants,
    assert_uc1_terminal_connector_routing,
)
from chorus.eval.use_cases.uc2_conduct import (
    assert_uc2_connector_ref_evidence,
    assert_uc2_engagement_decision_conduct,
    assert_uc2_engagement_letter_send_approval_gate,
)
from chorus.eval.use_cases.uc3_conduct import (
    assert_uc3_connector_ref_evidence,
    assert_uc3_manual_handoff_boundaries,
    assert_uc3_suitability_decision_conduct,
    assert_uc3_suitability_report_issue_approval_gate,
)

Invariant = Callable[[CapturedRun], list[EvalCheck]]


UC1_INVARIANTS: tuple[Invariant, ...] = (
    assert_cross_port_payload_validity,
    assert_governed_decision_provenance,
    assert_audit_completeness,
    assert_observability_emission,
    assert_uc1_qualification_invariants,
    assert_uc1_terminal_connector_routing,
    assert_connector_authority_discipline,
    assert_projection_convergence,
)

UC2_INVARIANTS: tuple[Invariant, ...] = (
    assert_cross_port_payload_validity,
    assert_governed_decision_provenance,
    assert_audit_completeness,
    assert_observability_emission,
    assert_uc2_engagement_decision_conduct,
    assert_uc2_engagement_letter_send_approval_gate,
    assert_uc2_connector_ref_evidence,
    assert_connector_authority_discipline,
    assert_projection_convergence,
)

UC3_INVARIANTS: tuple[Invariant, ...] = (
    assert_cross_port_payload_validity,
    assert_governed_decision_provenance,
    assert_audit_completeness,
    assert_observability_emission,
    assert_uc3_suitability_decision_conduct,
    assert_uc3_manual_handoff_boundaries,
    assert_uc3_suitability_report_issue_approval_gate,
    assert_uc3_connector_ref_evidence,
    assert_connector_authority_discipline,
    assert_projection_convergence,
)


def run_invariants(
    run: CapturedRun,
    *,
    invariants: Sequence[Invariant] = UC1_INVARIANTS,
) -> list[EvalCheck]:
    checks: list[EvalCheck] = []
    for invariant in invariants:
        checks.extend(invariant(run))
    return checks


__all__ = [
    "UC1_INVARIANTS",
    "UC2_INVARIANTS",
    "UC3_INVARIANTS",
    "EvalCheck",
    "EvalStatus",
    "Invariant",
    "assert_audit_completeness",
    "assert_connector_authority_discipline",
    "assert_cross_port_payload_validity",
    "assert_governed_decision_provenance",
    "assert_observability_emission",
    "assert_projection_convergence",
    "assert_uc1_qualification_invariants",
    "assert_uc1_terminal_connector_routing",
    "assert_uc2_connector_ref_evidence",
    "assert_uc2_engagement_decision_conduct",
    "assert_uc2_engagement_letter_send_approval_gate",
    "assert_uc3_connector_ref_evidence",
    "assert_uc3_manual_handoff_boundaries",
    "assert_uc3_suitability_decision_conduct",
    "assert_uc3_suitability_report_issue_approval_gate",
    "run_invariants",
]

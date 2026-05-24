"""Invariant suite composition for captured eval runs.

Common architecture checks live in :mod:`chorus.eval.common_invariants`.
Per-use-case conduct checks live under :mod:`chorus.eval.use_cases`. This
module keeps the current UC1 suite and public imports stable for the eval
runner while UC2 and UC3 get their own conduct suites in later R4 slices.
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
from chorus.eval.use_cases.uc1_conduct import assert_uc1_qualification_invariants

Invariant = Callable[[CapturedRun], list[EvalCheck]]


UC1_INVARIANTS: tuple[Invariant, ...] = (
    assert_cross_port_payload_validity,
    assert_governed_decision_provenance,
    assert_audit_completeness,
    assert_observability_emission,
    assert_uc1_qualification_invariants,
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
    "run_invariants",
]

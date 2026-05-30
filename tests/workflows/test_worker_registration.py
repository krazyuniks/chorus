from __future__ import annotations

from chorus.workflows.uc1 import Uc1EnquiryQualificationWorkflow
from chorus.workflows.uc2 import Uc2LegalServicesIntakeConflictCheckWorkflow
from chorus.workflows.uc3 import Uc3IfaSuitabilityIntakeWorkflow
from chorus.workflows.worker import registered_workflow_classes


def test_shared_worker_registers_declared_use_case_workflows() -> None:
    assert registered_workflow_classes() == [
        Uc1EnquiryQualificationWorkflow,
        Uc2LegalServicesIntakeConflictCheckWorkflow,
        Uc3IfaSuitabilityIntakeWorkflow,
    ]

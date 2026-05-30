import { QueryClient } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  approvalPackages,
  decisionTrail,
  toolVerdicts,
  workflowEvents,
  workflowRuns,
} from "@/api/fixtures";
import {
  invalidateWorkflowEvidence,
  WorkflowDetailView,
} from "./workflows.$workflowId";

describe("WorkflowDetailView", () => {
  it("renders UC2 workflow progress, audit evidence, and approval-package state", () => {
    const workflowId = "uc2-2026-05-24-0001";
    const run = workflowRuns.find((row) => row.workflow_id === workflowId);

    if (!run) {
      throw new Error("UC2 fixture workflow is missing");
    }

    render(
      <WorkflowDetailView
        workflowId={workflowId}
        run={run}
        events={workflowEvents[workflowId] ?? []}
        decisions={decisionTrail.filter((row) => row.workflow_id === workflowId)}
        verdicts={toolVerdicts.filter((row) => row.workflow_id === workflowId)}
        approvalPackages={approvalPackages.filter(
          (row) => row.workflow_id === workflowId,
        )}
      />,
    );

    expect(screen.getByText(workflowId)).toBeInTheDocument();
    expect(
      screen.getByText("uc2_legal_services_intake_conflict_check"),
    ).toBeInTheDocument();
    expect(screen.getByText("engagement_letter_send")).toBeInTheDocument();
    expect(screen.getByText("uc2_engagement_decision")).toBeInTheDocument();
    expect(screen.getAllByText("engagement_letter.send").length).toBeGreaterThan(0);
    expect(screen.getByText("engagement_letter.send.write")).toBeInTheDocument();
    expect(screen.getAllByText("approval_required").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/engagement_letter_demo_001/).length).toBeGreaterThan(0);
  });

  it("renders UC3 workflow progress, audit evidence, and approval-package state", () => {
    const workflowId = "uc3-2026-05-24-0001";
    const run = workflowRuns.find((row) => row.workflow_id === workflowId);

    if (!run) {
      throw new Error("UC3 fixture workflow is missing");
    }

    render(
      <WorkflowDetailView
        workflowId={workflowId}
        run={run}
        events={workflowEvents[workflowId] ?? []}
        decisions={decisionTrail.filter((row) => row.workflow_id === workflowId)}
        verdicts={toolVerdicts.filter((row) => row.workflow_id === workflowId)}
        approvalPackages={approvalPackages.filter(
          (row) => row.workflow_id === workflowId,
        )}
      />,
    );

    expect(screen.getByText(workflowId)).toBeInTheDocument();
    expect(screen.getByText("uc3_ifa_suitability_intake")).toBeInTheDocument();
    expect(screen.getByText("suitability_report_issue")).toBeInTheDocument();
    expect(screen.getByText("uc3_suitability_conclusion")).toBeInTheDocument();
    expect(screen.getAllByText("suitability_report.issue").length).toBeGreaterThan(0);
    expect(screen.getByText("suitability_report.issue.write")).toBeInTheDocument();
    expect(screen.getAllByText("approval_required").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/suitability_report_demo_001/).length).toBeGreaterThan(0);
  });
});

describe("invalidateWorkflowEvidence", () => {
  it("refreshes every workflow-scoped evidence query on progress", () => {
    const queryClient = new QueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");

    invalidateWorkflowEvidence(queryClient, "uc2-2026-05-24-0001");

    expect(invalidateQueries.mock.calls.map(([call]) => call)).toEqual([
      { queryKey: ["workflow", "uc2-2026-05-24-0001"] },
      { queryKey: ["workflow", "uc2-2026-05-24-0001", "events"] },
      { queryKey: ["workflow", "uc2-2026-05-24-0001", "decisions"] },
      { queryKey: ["workflow", "uc2-2026-05-24-0001", "verdicts"] },
      { queryKey: ["workflow", "uc2-2026-05-24-0001", "approval-packages"] },
    ]);
  });
});

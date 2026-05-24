/**
 * Vitest coverage for the BFF query layer.
 *
 * The queries module is the only place the UI talks to the BFF, so it is
 * the right gate for the refresh/reconnect (E-05) contract: every list and
 * detail view ultimately routes through one of these functions when the
 * user reloads, and SSE in-flight events are layered on top via
 * QueryClient invalidation in the routes.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  approvalPackages,
  grants,
  toolVerdicts,
  workflowEvents,
  workflowRuns,
} from "./fixtures";
import {
  getWorkflow,
  listApprovalPackages,
  listDecisionTrail,
  listGrants,
  listProviderModels,
  listProviders,
  listRegistry,
  listRouteVersions,
  listRouting,
  listToolVerdicts,
  listWorkflowDecisionTrail,
  listWorkflowApprovalPackages,
  listWorkflowEvents,
  listWorkflowToolVerdicts,
  listWorkflows,
} from "./queries";

const json = (body: unknown) => ({
  ok: true,
  status: 200,
  json: async () => body,
  text: async () => JSON.stringify(body),
}) as unknown as Response;

describe("queries", () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch");

  beforeEach(() => {
    fetchSpy.mockReset();
  });

  afterEach(() => {
    fetchSpy.mockReset();
  });

  it("listWorkflows hits the BFF /api/workflows endpoint", async () => {
    fetchSpy.mockResolvedValueOnce(json([{ workflow_id: "w-1" }]));
    const rows = await listWorkflows();
    expect(rows).toEqual([{ workflow_id: "w-1" }]);
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/workflows",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("getWorkflow URL-encodes the workflow id", async () => {
    fetchSpy.mockResolvedValueOnce(json({ workflow_id: "uc1/abc" }));
    await getWorkflow("uc1/abc");
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/workflows/uc1%2Fabc",
      expect.anything(),
    );
  });

  it("listWorkflowEvents reads the per-workflow timeline", async () => {
    fetchSpy.mockResolvedValueOnce(json([{ id: "e-1" }]));
    await listWorkflowEvents("w-1");
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/workflows/w-1/events",
      expect.anything(),
    );
  });

  it("inspection routes hit the right BFF endpoints", async () => {
    fetchSpy.mockResolvedValue(json([]));
    await listDecisionTrail();
    await listToolVerdicts();
    await listWorkflowDecisionTrail("w-1");
    await listWorkflowToolVerdicts("w-1");
    await listApprovalPackages();
    await listWorkflowApprovalPackages("w-1");
    await listRegistry();
    await listGrants();
    await listRouting();
    await listProviders();
    await listProviderModels();
    await listRouteVersions();
    const calls = fetchSpy.mock.calls.map(([url]) => url);
    expect(calls).toEqual([
      "/api/decision-trail",
      "/api/tool-verdicts",
      "/api/workflows/w-1/decision-trail",
      "/api/workflows/w-1/tool-verdicts",
      "/api/approval-packages",
      "/api/workflows/w-1/approval-packages",
      "/api/runtime/registry",
      "/api/runtime/grants",
      "/api/runtime/routing",
      "/api/runtime/providers",
      "/api/runtime/provider-models",
      "/api/runtime/route-versions",
    ]);
  });

  it("fixture inspection data includes UC3 safe approval-package refs", () => {
    const workflow = workflowRuns.find(
      (run) => run.workflow_type === "uc3_ifa_suitability_intake",
    );
    const packageEntry = approvalPackages.find(
      (entry) => entry.requested_action === "suitability_report.issue.write",
    );
    const verdict = toolVerdicts.find(
      (entry) => entry.tool_name === "suitability_report.issue",
    );
    const grant = grants.find(
      (entry) =>
        entry.tool_name === "suitability_report.issue" && entry.mode === "write",
    );

    expect(workflow).toMatchObject({
      workflow_id: "uc3-2026-05-24-0001",
      subject_ref: "advice_enquiry_2026_05_24_0001",
    });
    expect(workflowEvents["uc3-2026-05-24-0001"]).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          step: "suitability_conclusion",
          payload: expect.objectContaining({
            suitability_conclusion_ref: "suitability_conclusion_demo_001",
          }),
        }),
      ]),
    );
    expect(packageEntry).toMatchObject({
      workflow_id: "uc3-2026-05-24-0001",
      workflow_type: "uc3_ifa_suitability_intake",
      tool_name: "suitability_report.issue",
      latest_verdict: "approval_required",
      grant_ref: "tool_grant:grant-uc3-suitability-report-issue-write",
    });
    expect(packageEntry?.subject_refs).toEqual({
      subject_ref: "advice_enquiry_2026_05_24_0001",
    });
    expect(packageEntry?.action_refs).toMatchObject({
      suitability_report_ref: "suitability_report_demo_001",
      suitability_conclusion_ref: "suitability_conclusion_demo_001",
      conduct_hook_refs: [
        "conduct_fca_cobs_9_suitability",
        "conduct_fca_prod_3_target_market",
        "conduct_fca_prin_2a_consumer_duty",
      ],
    });
    expect(packageEntry?.action_refs).not.toHaveProperty("raw_suitability_report_text");
    expect(packageEntry?.action_refs).not.toHaveProperty("client_name");
    expect(verdict?.verdict).toBe("approval_required");
    expect(grant?.approval_required).toBe(true);
  });
});

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
  getWorkflow,
  listDecisionTrail,
  listGrants,
  listRegistry,
  listRouting,
  listToolVerdicts,
  listWorkflowDecisionTrail,
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
    fetchSpy.mockResolvedValueOnce(json({ workflow_id: "lighthouse/abc" }));
    await getWorkflow("lighthouse/abc");
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/workflows/lighthouse%2Fabc",
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
    await listRegistry();
    await listGrants();
    await listRouting();
    const calls = fetchSpy.mock.calls.map(([url]) => url);
    expect(calls).toEqual([
      "/api/decision-trail",
      "/api/tool-verdicts",
      "/api/workflows/w-1/decision-trail",
      "/api/workflows/w-1/tool-verdicts",
      "/api/runtime/registry",
      "/api/runtime/grants",
      "/api/runtime/routing",
    ]);
  });
});

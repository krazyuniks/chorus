import { apiGet } from "./client";
import {
  decisionTrail,
  grants,
  registry,
  routing,
  toolVerdicts,
  workflowEvents,
  workflowRuns,
} from "./fixtures";
import type {
  DecisionTrailEntry,
  GrantEntry,
  RegistryEntry,
  RoutingEntry,
  ToolVerdictEntry,
  WorkflowEvent,
  WorkflowRunSummary,
} from "./types";

const USE_FIXTURES = import.meta.env.VITE_USE_FIXTURES === "true";

export async function listWorkflows(): Promise<WorkflowRunSummary[]> {
  if (USE_FIXTURES) return workflowRuns;
  return apiGet<WorkflowRunSummary[]>("/workflows");
}

export async function getWorkflow(
  workflowId: string,
): Promise<WorkflowRunSummary | null> {
  if (USE_FIXTURES) {
    return workflowRuns.find((run) => run.workflow_id === workflowId) ?? null;
  }
  return apiGet<WorkflowRunSummary>(`/workflows/${encodeURIComponent(workflowId)}`);
}

export async function listWorkflowEvents(
  workflowId: string,
): Promise<WorkflowEvent[]> {
  if (USE_FIXTURES) return workflowEvents[workflowId] ?? [];
  return apiGet<WorkflowEvent[]>(
    `/workflows/${encodeURIComponent(workflowId)}/events`,
  );
}

export async function listDecisionTrail(): Promise<DecisionTrailEntry[]> {
  if (USE_FIXTURES) return decisionTrail;
  return apiGet<DecisionTrailEntry[]>("/decision-trail");
}

export async function listWorkflowDecisionTrail(
  workflowId: string,
): Promise<DecisionTrailEntry[]> {
  if (USE_FIXTURES) {
    return decisionTrail.filter((entry) => entry.workflow_id === workflowId);
  }
  return apiGet<DecisionTrailEntry[]>(
    `/workflows/${encodeURIComponent(workflowId)}/decision-trail`,
  );
}

export async function listToolVerdicts(): Promise<ToolVerdictEntry[]> {
  if (USE_FIXTURES) return toolVerdicts;
  return apiGet<ToolVerdictEntry[]>("/tool-verdicts");
}

export async function listWorkflowToolVerdicts(
  workflowId: string,
): Promise<ToolVerdictEntry[]> {
  if (USE_FIXTURES) {
    return toolVerdicts.filter((entry) => entry.workflow_id === workflowId);
  }
  return apiGet<ToolVerdictEntry[]>(
    `/workflows/${encodeURIComponent(workflowId)}/tool-verdicts`,
  );
}

export async function listRegistry(): Promise<RegistryEntry[]> {
  if (USE_FIXTURES) return registry;
  return apiGet<RegistryEntry[]>("/runtime/registry");
}

export async function listGrants(): Promise<GrantEntry[]> {
  if (USE_FIXTURES) return grants;
  return apiGet<GrantEntry[]>("/runtime/grants");
}

export async function listRouting(): Promise<RoutingEntry[]> {
  if (USE_FIXTURES) return routing;
  return apiGet<RoutingEntry[]>("/runtime/routing");
}

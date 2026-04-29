import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { PageHeader } from "@/components/PageHeader";
import { Timeline, type TimelineEntry } from "@/components/Timeline";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { StatusPill } from "@/components/StatusPill";
import {
  getWorkflow,
  listWorkflowDecisionTrail,
  listWorkflowEvents,
  listWorkflowToolVerdicts,
} from "@/api/queries";
import { subscribeProgress } from "@/api/sse";
import type { DecisionTrailEntry, ToolVerdictEntry } from "@/api/types";
import { formatCorrelationId, formatDurationMs, formatTimestamp } from "@/lib/utils";

export const Route = createFileRoute("/workflows/$workflowId")({
  component: WorkflowDetail,
});

function WorkflowDetail() {
  const { workflowId } = Route.useParams();
  const queryClient = useQueryClient();

  const { data: run } = useQuery({
    queryKey: ["workflow", workflowId],
    queryFn: () => getWorkflow(workflowId),
  });

  const { data: events = [] } = useQuery({
    queryKey: ["workflow", workflowId, "events"],
    queryFn: () => listWorkflowEvents(workflowId),
  });

  const { data: decisions = [] } = useQuery({
    queryKey: ["workflow", workflowId, "decisions"],
    queryFn: () => listWorkflowDecisionTrail(workflowId),
  });

  const { data: verdicts = [] } = useQuery({
    queryKey: ["workflow", workflowId, "verdicts"],
    queryFn: () => listWorkflowToolVerdicts(workflowId),
  });

  useEffect(() => {
    const stream = subscribeProgress("/progress", (event) => {
      if (event.workflow_id !== workflowId) return;
      void queryClient.invalidateQueries({ queryKey: ["workflow", workflowId] });
    });
    return () => stream.close();
  }, [queryClient, workflowId]);

  const timelineEntries: TimelineEntry[] = events.map((event) => ({
    id: event.id,
    occurred_at: event.occurred_at,
    correlation_id: event.correlation_id,
    label: <span className="mono">{event.event_type}</span>,
    detail: (
      <code className="mono text-[11px] text-text-muted">
        {JSON.stringify(event.payload)}
      </code>
    ),
  }));

  const decisionColumns: DataTableColumn<DecisionTrailEntry>[] = [
    { key: "agent_id", header: "Agent", mono: true, cell: (r) => r.agent_id },
    { key: "prompt_ref", header: "Prompt", mono: true, cell: (r) => r.prompt_ref },
    { key: "model_route", header: "Route", mono: true, cell: (r) => r.model_route },
    { key: "outcome", header: "Outcome", cell: (r) => <StatusPill value={r.outcome} /> },
    {
      key: "cost_usd",
      header: "Cost",
      align: "right",
      mono: true,
      cell: (r) => (r.cost_usd != null ? `$${r.cost_usd.toFixed(4)}` : "—"),
    },
    {
      key: "latency_ms",
      header: "Latency",
      align: "right",
      mono: true,
      cell: (r) => formatDurationMs(r.latency_ms),
    },
    {
      key: "occurred_at",
      header: "When",
      mono: true,
      cell: (r) => formatTimestamp(r.occurred_at),
    },
  ];

  const verdictColumns: DataTableColumn<ToolVerdictEntry>[] = [
    { key: "tool_name", header: "Tool", mono: true, cell: (r) => r.tool_name },
    {
      key: "enforced_mode",
      header: "Mode",
      cell: (r) => <StatusPill value={r.enforced_mode ?? r.mode ?? "—"} />,
    },
    { key: "verdict", header: "Verdict", cell: (r) => <StatusPill value={r.verdict} /> },
    {
      key: "caller_agent_id",
      header: "Caller",
      mono: true,
      cell: (r) => r.caller_agent_id,
    },
    {
      key: "redactions",
      header: "Redactions",
      mono: true,
      cell: (r) => (r.redactions.length === 0 ? "—" : r.redactions.join(", ")),
    },
    { key: "reason", header: "Reason", cell: (r) => r.reason ?? "—" },
    {
      key: "occurred_at",
      header: "When",
      mono: true,
      cell: (r) => formatTimestamp(r.occurred_at),
    },
  ];

  if (!run) {
    return (
      <div className="flex h-full flex-col">
        <PageHeader title="Workflow not found" subtitle={workflowId} />
        <div className="px-4 py-3 text-xs text-text-muted">
          <Link to="/" className="hover:underline">
            Back to runs
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title={run.workflow_id}
        subtitle={`${run.workflow_type}${run.run_id ? ` · run ${run.run_id}` : ""}`}
        actions={<StatusPill value={run.status} />}
      />

      <section className="grid grid-cols-2 gap-x-6 gap-y-1 border-b border-border-muted px-4 py-2 text-xs">
        <Field label="Subject" value={run.lead_subject ?? "—"} />
        <Field label="From" mono value={run.lead_from ?? "—"} />
        <Field label="Step" mono value={run.current_step ?? "—"} />
        <Field label="Started" mono value={formatTimestamp(run.started_at)} />
        <Field label="Closed" mono value={formatTimestamp(run.closed_at)} />
        <Field
          label="Correlation"
          mono
          value={formatCorrelationId(run.correlation_id)}
          title={run.correlation_id}
        />
      </section>

      <section className="border-b border-border">
        <SectionLabel>Timeline</SectionLabel>
        <Timeline entries={timelineEntries} />
      </section>

      <section className="border-b border-border">
        <SectionLabel>Decision trail</SectionLabel>
        <DataTable
          rows={decisions}
          columns={decisionColumns}
          rowKey={(row) => row.id}
        />
      </section>

      <section>
        <SectionLabel>Tool verdicts</SectionLabel>
        <DataTable
          rows={verdicts}
          columns={verdictColumns}
          rowKey={(row) => row.id}
        />
      </section>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="border-b border-border-muted bg-surface-raised px-4 py-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
      {children}
    </div>
  );
}

function Field({
  label,
  value,
  mono,
  title,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
  title?: string;
}) {
  return (
    <div className="flex gap-2">
      <span className="w-24 text-text-subtle">{label}</span>
      <span className={mono ? "mono text-text" : "text-text"} title={title}>
        {value}
      </span>
    </div>
  );
}

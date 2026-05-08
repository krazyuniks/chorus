import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { StatusPill } from "@/components/StatusPill";
import { listGraphExecutions } from "@/api/queries";
import type { GraphExecutionEntry } from "@/api/types";
import {
  formatCorrelationId,
  formatDurationMs,
  formatTimestamp,
} from "@/lib/utils";

export const Route = createFileRoute("/graph-executions")({
  component: GraphExecutionsRoute,
});

function GraphExecutionsRoute() {
  const { data = [] } = useQuery({
    queryKey: ["graph-executions"],
    queryFn: listGraphExecutions,
  });

  const columns: DataTableColumn<GraphExecutionEntry>[] = [
    {
      key: "workflow_id",
      header: "Workflow",
      mono: true,
      cell: (row) => (
        <Link
          to="/workflows/$workflowId"
          params={{ workflowId: row.workflow_id }}
          className="hover:underline"
        >
          {row.workflow_id}
        </Link>
      ),
    },
    { key: "agent_id", header: "Agent", mono: true, cell: (r) => r.agent_id },
    {
      key: "execution_engine",
      header: "Engine",
      cell: (r) => <StatusPill value={r.execution_engine ?? "unknown"} />,
    },
    {
      key: "graph_version",
      header: "Graph",
      mono: true,
      cell: (r) => r.graph_version ?? "-",
    },
    {
      key: "graph_path_summary",
      header: "Path",
      mono: true,
      cell: (r) => r.graph_path_summary ?? (r.graph_path.join(" -> ") || "-"),
    },
    {
      key: "route_version",
      header: "Route Ver",
      mono: true,
      cell: (r) => (r.route_version != null ? `v${r.route_version}` : "-"),
    },
    { key: "provider", header: "Provider", mono: true, cell: (r) => r.provider },
    { key: "model", header: "Model", mono: true, cell: (r) => r.model },
    {
      key: "outcome",
      header: "Outcome",
      cell: (r) => <StatusPill value={r.outcome} />,
    },
    {
      key: "fallback_applied",
      header: "Fallback",
      cell: (r) => (r.fallback_applied ? "applied" : "not applied"),
    },
    {
      key: "latency_ms",
      header: "Latency",
      align: "right",
      mono: true,
      cell: (r) => formatDurationMs(r.latency_ms),
    },
    {
      key: "correlation_id",
      header: "Correlation",
      mono: true,
      cell: (r) => formatCorrelationId(r.correlation_id),
    },
    {
      key: "occurred_at",
      header: "When",
      mono: true,
      cell: (r) => formatTimestamp(r.occurred_at),
    },
  ];

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Graph executions"
        subtitle="Read-only LangGraph path evidence from decision-trail metadata."
      />
      <DataTable
        rows={data}
        columns={columns}
        rowKey={(row) => row.id}
      />
    </div>
  );
}

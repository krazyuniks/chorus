import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { StatusPill } from "@/components/StatusPill";
import { workflowRuns } from "@/api/fixtures";
import type { WorkflowRunSummary } from "@/api/types";
import { formatCorrelationId, formatTimestamp } from "@/lib/utils";

export const Route = createFileRoute("/")({
  component: WorkflowsList,
});

function WorkflowsList() {
  const { data = [] } = useQuery({
    queryKey: ["workflows"],
    queryFn: async () => workflowRuns,
  });

  const columns: DataTableColumn<WorkflowRunSummary>[] = [
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
    {
      key: "status",
      header: "Status",
      cell: (row) => <StatusPill value={row.status} />,
      width: "8rem",
    },
    {
      key: "lead_subject",
      header: "Subject",
      cell: (row) => row.lead_subject ?? "—",
    },
    {
      key: "lead_from",
      header: "From",
      mono: true,
      cell: (row) => row.lead_from ?? "—",
    },
    {
      key: "started_at",
      header: "Started",
      mono: true,
      cell: (row) => formatTimestamp(row.started_at),
      width: "12rem",
    },
    {
      key: "closed_at",
      header: "Closed",
      mono: true,
      cell: (row) => formatTimestamp(row.closed_at),
      width: "12rem",
    },
    {
      key: "correlation_id",
      header: "Correlation",
      mono: true,
      cell: (row) => (
        <span title={row.correlation_id}>
          {formatCorrelationId(row.correlation_id)}
        </span>
      ),
      width: "8rem",
    },
  ];

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Workflow runs"
        subtitle={`${data.length} run${data.length === 1 ? "" : "s"}`}
      />
      <DataTable
        rows={data}
        columns={columns}
        rowKey={(row) => row.workflow_id}
        empty={
          <span>
            No runs yet — send a fixture lead via{" "}
            <code className="mono text-text">just demo</code>.
          </span>
        }
      />
    </div>
  );
}

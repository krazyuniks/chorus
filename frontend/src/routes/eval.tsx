import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { StatusPill } from "@/components/StatusPill";
import { evalRuns } from "@/api/fixtures";
import type { EvalRunSummary } from "@/api/types";
import { formatDurationMs, formatTimestamp } from "@/lib/utils";

export const Route = createFileRoute("/eval")({
  component: EvalRoute,
});

function EvalRoute() {
  const { data = [] } = useQuery({
    queryKey: ["eval-runs"],
    queryFn: async () => evalRuns,
  });

  const columns: DataTableColumn<EvalRunSummary>[] = [
    { key: "run_id", header: "Run", mono: true, cell: (r) => r.run_id },
    { key: "fixture", header: "Fixture", mono: true, cell: (r) => r.fixture },
    { key: "status", header: "Status", cell: (r) => <StatusPill value={r.status} /> },
    {
      key: "pass_count",
      header: "Pass",
      align: "right",
      mono: true,
      cell: (r) => String(r.pass_count),
    },
    {
      key: "fail_count",
      header: "Fail",
      align: "right",
      mono: true,
      cell: (r) => String(r.fail_count),
    },
    {
      key: "duration_ms",
      header: "Duration",
      align: "right",
      mono: true,
      cell: (r) => formatDurationMs(r.duration_ms),
    },
    {
      key: "finished_at",
      header: "Finished",
      mono: true,
      cell: (r) => formatTimestamp(r.finished_at),
    },
  ];

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Eval runs"
        subtitle="Trace and fixture results from the eval harness."
      />
      <DataTable rows={data} columns={columns} rowKey={(row) => row.run_id} />
    </div>
  );
}

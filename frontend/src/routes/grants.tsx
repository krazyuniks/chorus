import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { StatusPill } from "@/components/StatusPill";
import { grants } from "@/api/fixtures";
import type { GrantEntry } from "@/api/types";
import { formatTimestamp } from "@/lib/utils";

export const Route = createFileRoute("/grants")({
  component: GrantsRoute,
});

function GrantsRoute() {
  const { data = [] } = useQuery({
    queryKey: ["grants"],
    queryFn: async () => grants,
  });

  const columns: DataTableColumn<GrantEntry>[] = [
    { key: "agent_id", header: "Agent", mono: true, cell: (r) => r.agent_id },
    { key: "tool_name", header: "Tool", mono: true, cell: (r) => r.tool_name },
    { key: "mode", header: "Mode", cell: (r) => <StatusPill value={r.mode} /> },
    { key: "scope", header: "Scope", mono: true, cell: (r) => r.scope },
    {
      key: "approval_required",
      header: "Approval",
      cell: (r) => (r.approval_required ? "required" : "not required"),
    },
    {
      key: "granted_at",
      header: "Granted",
      mono: true,
      cell: (r) => formatTimestamp(r.granted_at),
    },
  ];

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Tool grants"
        subtitle="Read-only — grant mutations sit with the Tool Gateway, not the UI."
      />
      <DataTable
        rows={data}
        columns={columns}
        rowKey={(row) => `${row.agent_id}::${row.tool_name}`}
      />
    </div>
  );
}

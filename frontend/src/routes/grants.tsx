import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { StatusPill } from "@/components/StatusPill";
import { listGrants } from "@/api/queries";
import type { GrantEntry } from "@/api/types";
import { formatTimestamp } from "@/lib/utils";

export const Route = createFileRoute("/grants")({
  component: GrantsRoute,
});

function GrantsRoute() {
  const { data = [] } = useQuery({
    queryKey: ["grants"],
    queryFn: listGrants,
  });

  const columns: DataTableColumn<GrantEntry>[] = [
    { key: "agent_id", header: "Agent", mono: true, cell: (r) => r.agent_id },
    { key: "agent_version", header: "Version", mono: true, cell: (r) => r.agent_version ?? "—" },
    { key: "tool_name", header: "Tool", mono: true, cell: (r) => r.tool_name },
    { key: "mode", header: "Mode", cell: (r) => <StatusPill value={r.mode} /> },
    {
      key: "allowed",
      header: "Allowed",
      cell: (r) => <StatusPill value={r.allowed === false ? "block" : "allow"} />,
    },
    {
      key: "redaction_policy",
      header: "Redaction",
      mono: true,
      cell: (r) => JSON.stringify(r.redaction_policy ?? { scope: r.scope ?? "—" }),
    },
    {
      key: "approval_required",
      header: "Approval",
      cell: (r) => (r.approval_required ? "required" : "not required"),
    },
    {
      key: "granted_at",
      header: "Granted",
      mono: true,
      cell: (r) => formatTimestamp(r.granted_at ?? null),
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
        rowKey={(row) => row.grant_id ?? `${row.agent_id}::${row.tool_name}::${row.mode}`}
      />
    </div>
  );
}

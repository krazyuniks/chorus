import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { StatusPill } from "@/components/StatusPill";
import { listRegistry } from "@/api/queries";
import type { RegistryEntry } from "@/api/types";
import { formatTimestamp } from "@/lib/utils";

export const Route = createFileRoute("/registry")({
  component: RegistryRoute,
});

function RegistryRoute() {
  const { data = [] } = useQuery({
    queryKey: ["registry"],
    queryFn: listRegistry,
  });

  const columns: DataTableColumn<RegistryEntry>[] = [
    { key: "agent_id", header: "Agent", mono: true, cell: (r) => r.agent_id },
    { key: "role", header: "Role", mono: true, cell: (r) => r.role ?? "—" },
    { key: "version", header: "Version", mono: true, cell: (r) => r.version },
    {
      key: "lifecycle_state",
      header: "State",
      cell: (r) => <StatusPill value={r.lifecycle_state ?? "—"} />,
    },
    { key: "prompt_ref", header: "Prompt", mono: true, cell: (r) => r.prompt_ref },
    { key: "owner", header: "Owner", mono: true, cell: (r) => r.owner ?? "—" },
    {
      key: "capability_tags",
      header: "Capabilities",
      mono: true,
      cell: (r) => r.capability_tags?.join(", ") ?? r.description ?? "—",
    },
    {
      key: "updated_at",
      header: "Updated",
      mono: true,
      cell: (r) => formatTimestamp(r.updated_at),
    },
  ];

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Agent registry"
        subtitle="Read-only — registry mutations are out of scope for Phase 1."
      />
      <DataTable rows={data} columns={columns} rowKey={(row) => row.agent_id} />
    </div>
  );
}

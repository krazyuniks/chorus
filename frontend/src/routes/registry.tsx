import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { registry } from "@/api/fixtures";
import type { RegistryEntry } from "@/api/types";
import { formatTimestamp } from "@/lib/utils";

export const Route = createFileRoute("/registry")({
  component: RegistryRoute,
});

function RegistryRoute() {
  const { data = [] } = useQuery({
    queryKey: ["registry"],
    queryFn: async () => registry,
  });

  const columns: DataTableColumn<RegistryEntry>[] = [
    { key: "agent_id", header: "Agent", mono: true, cell: (r) => r.agent_id },
    { key: "version", header: "Version", mono: true, cell: (r) => r.version },
    { key: "prompt_ref", header: "Prompt", mono: true, cell: (r) => r.prompt_ref },
    { key: "model_route", header: "Route", mono: true, cell: (r) => r.model_route },
    { key: "description", header: "Description", cell: (r) => r.description },
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

import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { routing } from "@/api/fixtures";
import type { RoutingEntry } from "@/api/types";

export const Route = createFileRoute("/routing")({
  component: RoutingRoute,
});

function RoutingRoute() {
  const { data = [] } = useQuery({
    queryKey: ["routing"],
    queryFn: async () => routing,
  });

  const columns: DataTableColumn<RoutingEntry>[] = [
    { key: "route_id", header: "Route", mono: true, cell: (r) => r.route_id },
    { key: "match", header: "Match", mono: true, cell: (r) => r.match },
    { key: "provider", header: "Provider", cell: (r) => r.provider },
    { key: "model", header: "Model", mono: true, cell: (r) => r.model },
    {
      key: "budget_usd",
      header: "Budget",
      align: "right",
      mono: true,
      cell: (r) => `$${r.budget_usd.toFixed(2)}`,
    },
    {
      key: "fallback",
      header: "Fallback",
      mono: true,
      cell: (r) => r.fallback ?? "—",
    },
  ];

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Model routing"
        subtitle="Read-only — routing rules ship with releases, not with the UI."
      />
      <DataTable
        rows={data}
        columns={columns}
        rowKey={(row) => row.route_id}
      />
    </div>
  );
}

import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { StatusPill } from "@/components/StatusPill";
import {
  listProviderModels,
  listProviders,
  listRouteVersions,
} from "@/api/queries";
import type {
  ProviderEntry,
  ProviderModelEntry,
  RouteVersionEntry,
} from "@/api/types";
import { formatDurationMs, formatTimestamp } from "@/lib/utils";

export const Route = createFileRoute("/providers")({
  component: ProvidersRoute,
});

function ProvidersRoute() {
  const { data: providers = [] } = useQuery({
    queryKey: ["providers"],
    queryFn: listProviders,
  });
  const { data: providerModels = [] } = useQuery({
    queryKey: ["provider-models"],
    queryFn: listProviderModels,
  });
  const { data: routeVersions = [] } = useQuery({
    queryKey: ["route-versions"],
    queryFn: listRouteVersions,
  });

  const providerColumns: DataTableColumn<ProviderEntry>[] = [
    { key: "provider_id", header: "Provider", mono: true, cell: (r) => r.provider_id },
    { key: "display_name", header: "Name", cell: (r) => r.display_name },
    {
      key: "provider_kind",
      header: "Kind",
      cell: (r) => <StatusPill value={r.provider_kind} />,
    },
    {
      key: "lifecycle_state",
      header: "State",
      cell: (r) => <StatusPill value={r.lifecycle_state} />,
    },
    {
      key: "credential_required",
      header: "Credential",
      cell: (r) => (r.credential_required ? "required" : "not required"),
    },
    {
      key: "secret_ref_names",
      header: "Secrets",
      mono: true,
      cell: (r) => (r.secret_ref_names.length ? r.secret_ref_names.join(", ") : "-"),
    },
    {
      key: "missing_credentials_behaviour",
      header: "Missing creds",
      mono: true,
      cell: (r) => r.missing_credentials_behaviour,
    },
    {
      key: "data_boundary",
      header: "Boundary",
      mono: true,
      cell: (r) => String(r.data_boundary.mode ?? JSON.stringify(r.data_boundary)),
    },
  ];

  const modelColumns: DataTableColumn<ProviderModelEntry>[] = [
    { key: "provider_id", header: "Provider", mono: true, cell: (r) => r.provider_id },
    { key: "model_id", header: "Model", mono: true, cell: (r) => r.model_id },
    {
      key: "lifecycle_state",
      header: "State",
      cell: (r) => <StatusPill value={r.lifecycle_state} />,
    },
    {
      key: "supported_task_kinds",
      header: "Tasks",
      mono: true,
      cell: (r) => r.supported_task_kinds.join(", "),
    },
    {
      key: "supports_structured_output",
      header: "Structured",
      cell: (r) => (r.supports_structured_output ? "yes" : "no"),
    },
    {
      key: "context_window_tokens",
      header: "Context",
      align: "right",
      mono: true,
      cell: (r) => r.context_window_tokens?.toLocaleString() ?? "-",
    },
    {
      key: "cost_policy",
      header: "Cost policy",
      mono: true,
      cell: (r) => JSON.stringify(r.cost_policy),
    },
  ];

  const routeVersionColumns: DataTableColumn<RouteVersionEntry>[] = [
    { key: "route_id", header: "Route", mono: true, cell: (r) => r.route_id },
    {
      key: "route_version",
      header: "Ver",
      mono: true,
      cell: (r) => `v${r.route_version}`,
    },
    {
      key: "match",
      header: "Match",
      mono: true,
      cell: (r) => `${r.agent_role}:${r.task_kind}:${r.tenant_tier}`,
    },
    {
      key: "lifecycle_state",
      header: "State",
      cell: (r) => <StatusPill value={r.lifecycle_state} />,
    },
    { key: "provider_id", header: "Provider", mono: true, cell: (r) => r.provider_id },
    { key: "model_id", header: "Model", mono: true, cell: (r) => r.model_id },
    {
      key: "budget_usd",
      header: "Budget",
      align: "right",
      mono: true,
      cell: (r) => `$${r.budget_usd.toFixed(4)}`,
    },
    {
      key: "max_latency_ms",
      header: "Latency cap",
      align: "right",
      mono: true,
      cell: (r) => formatDurationMs(r.max_latency_ms),
    },
    {
      key: "eval_required",
      header: "Eval",
      cell: (r) => (r.eval_required ? "required" : "not required"),
    },
    {
      key: "created_at",
      header: "Created",
      mono: true,
      cell: (r) => formatTimestamp(r.created_at),
    },
  ];

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Providers"
        subtitle="Read-only provider catalogue, model declarations, and immutable route versions."
      />

      <section className="border-b border-border">
        <SectionLabel>Provider catalogue</SectionLabel>
        <DataTable
          rows={providers}
          columns={providerColumns}
          rowKey={(row) => `${row.catalogue_id}:${row.provider_id}`}
        />
      </section>

      <section className="border-b border-border">
        <SectionLabel>Provider models</SectionLabel>
        <DataTable
          rows={providerModels}
          columns={modelColumns}
          rowKey={(row) => `${row.catalogue_id}:${row.provider_id}:${row.model_id}`}
        />
      </section>

      <section>
        <SectionLabel>Route versions</SectionLabel>
        <DataTable
          rows={routeVersions}
          columns={routeVersionColumns}
          rowKey={(row) => `${row.route_id}:v${row.route_version}`}
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

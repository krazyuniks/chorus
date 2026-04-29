import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { StatusPill } from "@/components/StatusPill";
import { Input } from "@/design-system/designs/dense/forms/Input";
import { decisionTrail } from "@/api/fixtures";
import type { DecisionTrailEntry } from "@/api/types";
import { formatDurationMs, formatTimestamp } from "@/lib/utils";

export const Route = createFileRoute("/decision-trail")({
  component: DecisionTrailRoute,
});

function DecisionTrailRoute() {
  const { data = [] } = useQuery({
    queryKey: ["decision-trail"],
    queryFn: async () => decisionTrail,
  });
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() => {
    if (!filter.trim()) return data;
    const needle = filter.toLowerCase();
    return data.filter((row) =>
      [
        row.workflow_id,
        row.agent_id,
        row.prompt_ref,
        row.model_route,
        row.outcome,
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
  }, [data, filter]);

  const columns: DataTableColumn<DecisionTrailEntry>[] = [
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
    { key: "prompt_ref", header: "Prompt", mono: true, cell: (r) => r.prompt_ref },
    { key: "model_route", header: "Route", mono: true, cell: (r) => r.model_route },
    {
      key: "outcome",
      header: "Outcome",
      cell: (r) => <StatusPill value={r.outcome} />,
    },
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

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Decision trail"
        subtitle={`${filtered.length} of ${data.length}`}
      />
      <div className="border-b border-border-muted px-4 py-2">
        <div className="max-w-xs">
          <Input
            label="Filter"
            name="decision-filter"
            type="search"
            placeholder="agent, prompt, route, outcome…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
      </div>
      <DataTable
        rows={filtered}
        columns={columns}
        rowKey={(row) => row.id}
      />
    </div>
  );
}

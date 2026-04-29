import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { StatusPill } from "@/components/StatusPill";
import { Input } from "@/design-system/designs/dense/forms/Input";
import { toolVerdicts } from "@/api/fixtures";
import type { ToolVerdictEntry } from "@/api/types";
import { formatTimestamp } from "@/lib/utils";

export const Route = createFileRoute("/tool-verdicts")({
  component: ToolVerdictsRoute,
});

function ToolVerdictsRoute() {
  const { data = [] } = useQuery({
    queryKey: ["tool-verdicts"],
    queryFn: async () => toolVerdicts,
  });
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() => {
    if (!filter.trim()) return data;
    const needle = filter.toLowerCase();
    return data.filter((row) =>
      [row.workflow_id, row.tool_name, row.caller_agent_id, row.verdict, row.mode]
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
  }, [data, filter]);

  const columns: DataTableColumn<ToolVerdictEntry>[] = [
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
    { key: "tool_name", header: "Tool", mono: true, cell: (r) => r.tool_name },
    { key: "mode", header: "Mode", cell: (r) => <StatusPill value={r.mode} /> },
    { key: "verdict", header: "Verdict", cell: (r) => <StatusPill value={r.verdict} /> },
    {
      key: "caller_agent_id",
      header: "Caller",
      mono: true,
      cell: (r) => r.caller_agent_id,
    },
    {
      key: "redactions",
      header: "Redactions",
      mono: true,
      cell: (r) => (r.redactions.length === 0 ? "—" : r.redactions.join(", ")),
    },
    { key: "reason", header: "Reason", cell: (r) => r.reason ?? "—" },
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
        title="Tool verdicts"
        subtitle={`${filtered.length} of ${data.length}`}
      />
      <div className="border-b border-border-muted px-4 py-2">
        <div className="max-w-xs">
          <Input
            label="Filter"
            name="verdict-filter"
            type="search"
            placeholder="tool, caller, verdict, mode…"
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

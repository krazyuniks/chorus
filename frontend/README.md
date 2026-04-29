# Frontend

Lighthouse UI — the single-page admin and operator surface for Phase 1.

Stack: React + Vite + TypeScript + TanStack (Router/Query/Table) + Tailwind. Read-only against the BFF; all mutating actions go through Temporal workflows started by the SMTP-receive trigger or the dev-only fixture replay endpoint.

Views:

- Lead submission (dev-only fixture replay).
- Workflow timeline.
- Decision trail.
- Tool verdicts.
- Runtime registry, grants, routing.
- Eval status.

Dense, plain, data-first. No card layouts.

Phase 1A workstream **E** (BFF + UI). See [implementation-plan.md](../docs/implementation-plan.md).

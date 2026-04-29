---
type: adr
status: accepted
date: 2026-04-28
---

# ADR 0004: Agent Runtime and Tool Gateway Boundaries

## Context

Agent demos often hide policy inside prompts or SDK calls. Chorus needs the authority boundary to be visible: which agent version ran, which model was selected, which tools were allowed, and why an action was allowed, rewritten, proposed, or blocked.

## Decision

Add two explicit service boundaries:

- Agent Runtime resolves agent version, prompt reference, lifecycle state, tenant policy, model route, budget caps, and invocation identity.
- Tool Gateway mediates every external action. Agents never call connectors directly.

The Tool Gateway enforces `(agent_id, tenant_id, tool, mode)` grants, argument schema validation, tenant scoping, redaction, idempotency, approval hooks, and action audit events.

## Consequences

- Model routing and tool authority are inspectable outside prompt text.
- Runtime mutations are CLI/config driven in Phase 1; the UI is read-only for registry, grants, routing, and audit.
- The demo can show a forbidden write being blocked or downgraded to proposal mode.
- Local/sandbox connectors remain behind the same gateway contract intended for real integrations.

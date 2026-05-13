# Connector Implementation Instructions

This package contains local and sandbox connector implementations used behind
the Tool Gateway.

## Rules

- Connectors must not be invoked directly by workflows, agents, LangGraph, or
  the BFF. Route calls through the Tool Gateway.
- Keep connectors contract-faithful to real external behaviour. Do not add
  mocks as architecture evidence.
- Fail closed when required credentials are absent.
- Preserve tenant and correlation metadata in outbound calls where the target
  system supports it.
- Raise typed connector errors so Temporal activity retries and workflow
  compensation paths can classify failures.
- Do not write to production third-party systems from the local Phase 1/2
  evidence path.

## Local Map

- `local.py` contains the Mailpit SMTP email connector, Postgres-backed local
  CRM connector, Companies House lookup connector, connector argument models,
  and connector result/error types.

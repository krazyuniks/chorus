---
type: project-doc
status: active
date: 2026-05-19
---

# Code Refactor Directions

The 2026-05-19 design session identified four engineering smells in the
current Chorus codebase. Each one is a place where the implementation does
not yet reflect the ports-and-adapters thesis. None of them is fixed in
this writing pass. R3 (Contract And Code Terminology Refactor) is where
they get resolved. This document records the smell, why it matters, and
the direction of resolution.

## Smell 1 - Workflow Plumbing Duplication

### What is there

`chorus/workflows/lighthouse.py` and `chorus/workflows/support.py` both
define workflow activity name constants, step constants, agent dispatch
loops, Tool Gateway invocation patterns, and persistence calls. The
support workflow imports a handful of utilities from the lighthouse
workflow but otherwise reproduces the same orchestration shape with
parallel constants:

```
ACTIVITY_RECORD_WORKFLOW_EVENT          = "lighthouse.record_workflow_event"
ACTIVITY_INVOKE_AGENT_RUNTIME           = "lighthouse.invoke_agent_runtime"
ACTIVITY_INVOKE_TOOL_GATEWAY            = "lighthouse.invoke_tool_gateway"
...

ACTIVITY_RECORD_SUPPORT_WORKFLOW_EVENT  = "support.record_workflow_event"
SUPPORT_WORKFLOW_TYPE                   = "support_triage"
STEP_SUPPORT_INTAKE                     = "support_intake"
STEP_SUPPORT_CLASSIFICATION             = "support_classification"
...
```

### Why it matters

The duplication makes the second workflow look additive when it is in
fact a copy. It hides whether the workflow shape is a domain pattern (a
governed multi-step business process with agent decisions and gated tool
calls) or a use-case-specific orchestration. Under the ports-and-adapters
thesis, the workflow shape is part of the domain core; the only thing
that should vary between use cases is the contracts at the intake and
connector ports plus the agent prompts and decision policy.

Worse, the duplication makes it expensive to add a third use case. R1
will confirm two further UK-regulated use cases (legal intake and IFA
inbound enquiry); copying the workflow shape a third time would make the
project's identity even harder to defend.

### Resolution direction

R3 factors the workflow spine into a shared, generic orchestrator over the
named ports.

- One workflow activity surface that talks to the LLM provider port and
  the connector port via stable activity names. Use-case-specific names
  move into configuration plus contract types, not into activity
  constants.
- Step taxonomy moves to data, not constants. A workflow definition
  becomes a typed step sequence with per-step agent contract, tool
  grants, and approval policy.
- Per-use-case workflow modules collapse to the step sequence plus the
  ubiquitous-language types for that use case. The orchestration loop
  itself is shared.
- Lighthouse and Support Triage code remains as historical evidence
  until R3 retires or rewrites it under the refactored spine.

The thesis discipline: workflow plumbing is domain-core territory and
must not vary per use case. Adapters (intake, connector) and contracts
carry use-case variation.

## Smell 2 - Tool Gateway Hardcoded Match Dispatch

### What is there

`chorus/tool_gateway/gateway.py` dispatches connector calls via a
hardcoded `match tool_name:` block:

```python
match tool_name:
    case "email.propose_response" | "email.send_response":
        ...
    case "crm.lookup_company":
        ...
    case "crm.create_lead":
        ...
    case "company_research.lookup":
        ...
    case "calendar.lookup_availability":
        ...
    case "calendar.propose_hold":
        ...
    case "calendar.create_hold":
        ...
    case "calendar.cancel_hold":
        ...
    case "ticket.lookup_case":
        ...
    case "ticket.lookup_duplicates":
        ...
    case "ticket.propose_case_update":
        ...
    case _:
        raise ToolGatewayError(f"Unsupported tool {tool_name!r}")
```

Every connector adapter has to edit this same file. The dispatch
mechanism is the wrong shape for an adapter registry.

### Why it matters

The Tool Gateway is the connector port's authority layer. Under the
thesis, the connector port is precisely a place where adapters should
plug in without the core having to know each one. A hardcoded match
block is the opposite of that: the core enumerates every adapter, and
the gateway file grows linearly with the connector inventory.

It also entangles two responsibilities the gateway should separate:

- routing a tool call to the right adapter (a registry concern);
- enforcing the policy on that call (grants, modes, idempotency,
  approval hooks, redaction, verdicts) - the actual gateway value.

The match block mixes the two.

### Resolution direction

R3 replaces the match block with an adapter registry over the connector
port.

- Each connector adapter declares its supported tool names plus the
  argument and return contracts it satisfies.
- Adapters register themselves with the Tool Gateway at startup.
- The gateway's call path stays: validate grant, validate arguments,
  apply mode, dispatch through the registry, capture audit, return
  verdict.
- The dispatch step becomes a registry lookup, not a `match` arm.
- New connector adapters never edit the gateway file.

This isolates the gateway's actual job (authority and audit) from the
question of which adapters exist. It is also a precondition for use-case
2 and use-case 3 connectors to land without churning shared code.

## Smell 3 - Oversize Modules Conflating Multiple Concerns

Three files conflate multiple concerns and have grown to a size that
makes the conflation hard to ignore:

| File | Size (lines) | Conflated concerns |
|---|---|---|
| `chorus/persistence/projection.py` | ~1,572 | Read-model schemas for workflow runs, decision trails, tool audits, calendar projections, support workflow events, support agent decisions, support ticket verdicts, support case-update proposals, support status write boundary, agent / model registry, provider catalogue, governance snapshots, plus the `ProjectionStore` query layer. |
| `chorus/eval/run.py` | ~2,219 | CLI entry point, offline fixture evaluation, live evaluation, workflow event evidence assembly for both Lighthouse and Support, decision-record construction, tool-call construction, support tool-call construction, fixture role logic, support fixture detection branches. |
| `chorus/doctor.py` | ~612 | Path / executable / compose health checks, Postgres migration check, Temporal check, schema registry check, Mailpit check, BFF check, frontend dev check, observability checks (OTEL, Tempo, Loki, Prometheus). |

### Why it matters

Each file mixes concerns that, under the thesis, belong to different
ports.

- `projection.py` is the projection sink's read-model surface, but it
  also contains structured-trail records (audit / transcript port) and
  governance snapshots (control-plane configuration). Three different
  ports' read-side payloads in one file.
- `eval/run.py` is the eval substrate over the audit ports, but it
  contains per-use-case branches (`_is_support_fixture`,
  `_build_support_offline_evidence`, `_support_tool_calls`) that should
  be use-case modules sitting on top of a shared invariant-based eval
  core. See `eval-reshape-directions.md`.
- `doctor.py` is observability sink and infrastructure verification
  mixed together. Health probes per adapter belong with the adapter.

### Resolution direction

R3 decomposes each file along port boundaries.

- `projection.py` splits into per-port projection modules: workflow run
  and history projections (workflow-core), decision-trail and transcript
  projections (audit ports), connector verdicts and proposals
  (connector port read-side), and a separate control-plane snapshot
  module for agent / model / provider registry shapes.
- `eval/run.py` splits into an invariant-based eval core (per
  `eval-reshape-directions.md`) plus per-use-case eval modules. The CLI
  shrinks to argument parsing and orchestration.
- `doctor.py` splits into per-port health probes that each adapter
  publishes, plus a small driver that runs them. Infrastructure-only
  checks (compose, executables, paths) move to a separate
  environment-check module.

The thesis discipline: a file's identity is one port or one concern.
Cross-port files only exist where the system genuinely needs a join, and
those joins must be deliberate.

## Smell 4 - Implicit Carryover Of Pre-Thesis Decisions

Several pre-thesis decisions are still load-bearing in the codebase and
need explicit treatment in R3.

- LangGraph as the agent execution runtime (ADR 0012). The thesis
  removes it; reasoning runs through the LLM provider port directly.
- Audit captured as a single decision-trail stream rather than the two
  ports the thesis names.
- Eval fixtures structured around path enumeration (low-confidence,
  validator redraft, connector failure, retry exhaustion, provider
  fallback) rather than invariants.
- Phase 2E production-readiness pack documents (identity / IAM mapping,
  secrets, deployment topology, backup / restore, retention / audit
  storage) written before the deployment phase was removed.

R3 either rewrites these against the thesis or parks them as historical
evidence with a pointer to the relevant new doc. The Phase 2E pack is
parked.

## Out Of Scope For This Document

No code changes happen in R0.5. The smells above are direction-setting
inputs for R3, recorded here so R3 can be planned against them.

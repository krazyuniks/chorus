---
type: project-doc
status: active
date: 2026-05-24
phase: R3
---

# R3 Exit Criteria

R3 (contract and code terminology refactor) is the first reset phase that
touched runtime code. The exit criteria below confirm R3 has landed every
checkpoint A-G, every R1-deferred item carried into R3 is discharged, every
cross-checkpoint watch item is discharged, and the gates are green relative
to the pre-R3 baseline.

R3 ran across three sessions plus the Session 2b contingency for checkpoint
E. Per-checkpoint detail (files, gates, evidence) lives in
`transformation/r3-checkpoint-ledger.md`; this document is the sign-off.

## Scope Completed

| Checkpoint | Outcome | Status |
|---|---|---|
| A | Contract rewrite around the six named ports. | done (Session 1, 2026-05-23) |
| B | LLM provider port: LangGraph removed, OpenAI-SDK adapter, route catalogue. | done (Session 1, 2026-05-23) |
| C | Audit ports: decision-trail port and transcript port split. | done (Session 1, 2026-05-23) |
| D | Connector adapter registry replacing the hardcoded match dispatch. | done (Session 2, 2026-05-23) |
| E | Shared workflow spine factored out; UC1 on the spine; Support Triage retired. | done (Session 2b, 2026-05-23) |
| F | `projection.py` and `doctor.py` decomposed along port boundaries. | done (Session 3, 2026-05-24) |
| G | Eval reshape: invariants plus `eval replay` per ADR 0019. | done (Session 3, 2026-05-24) |

R3 closed 2026-05-24.

## Gates Passed

Recorded on the post-G commit, on a fresh local stack (volumes reset, all
11 migrations applied, 5 event schema subjects registered, Temporal worker
running):

| Gate | Result | Notes |
|---|---|---|
| `just contracts-check` | green | 24 schemas. The schema set rotated rather than grew across R3: A regrouped 21 schemas shape-preserved into the six ports, C added the transcript schema, D added six UC1 connector contracts (and retired four ticket schemas plus the ticket connector), E rotated the intake/agent-IO surface to UC1 and retired the support / lighthouse schemas, G reshaped the eval-fixture schema in place. |
| `just lint` | green | ruff check, ruff format, pyright strict, frontend `tsc --noEmit` all clean. |
| `just doctor-quick` | green | Scaffold, executables, compose all present. Per-port probe modules live under `chorus/doctor/`. |
| `just doctor` | green | Live-stack probes pass when the stack is up; skip with reasons when not. |
| `just test-replay` | green | UC1 inline run-and-replay tests on the new spine. |
| `just eval` | green | UC1 invariant suite passes offline for the happy-path and validator-redraft fixtures. `eval replay --transcript <fixture>` re-executes a captured classifier transcript through the recorded-replay route and verifies the structured output matches. |
| `just test` | green | All offline tests pass. The pre-R3 baseline 107 passed / 3 errors collapses across R3: the support-test deletions (B, D, E) and the BFF test-isolation defect (whose seed paths E retired) both go; the F + G test additions cover the new port-shaped surface and the invariant suite. |

The pre-R3 `just test` baseline at commit `9b37338` was 107 passed / 3
errors (a pre-existing BFF test-isolation defect, not a runtime defect).
That defect retired in E together with the support seed paths that caused
it; the new pass count is lower because the support-test surface retired
with the support workflow.

## R1-Deferred Items Discharged

`r1-exit-criteria.md` carried three items into R3. Each is now resolved.

- **Referral inbox adapter shape** - resolved in checkpoint D. The referral
  inbox is a separate sandbox connector adapter
  (`sandbox-referral-inbox`), not a tagged subscription on the
  quoting-queue adapter. Documented inline in
  `chorus/connectors/uc1.py`.
- **Customer-profile store boundary** - resolved in checkpoint D. The
  `sandbox-customer-profile` connector adapter is read-only at the port;
  write surfaces remain inside the broker firm's customer-of-record
  service and are not reachable through this adapter.
- **Exact regulatory citations** (ICOBS 2.5.-1R, ICOBS 5, PROD 4, Consumer
  Duty) - the UC1 qualification verdict structured output now carries each
  hook explicitly (`best_interests_check`, `demands_and_needs_statement`,
  `target_market_check`, `foreseeable_harm_check`) with its regulatory
  reference. The UC1 invariant suite asserts presence and shape on every
  qualification run. The full policy-snapshot DB row is an R4 surface;
  R3 binds the reference (`policy_snapshot_ref`) into the structured
  decision so R4 can wire the materialised snapshot through without a
  contract change.

## Cross-Checkpoint Watch Items Discharged

The 2026-05-21 plan validation surfaced three watch items. Each is now
discharged.

- **Eval determinism between B and G.** Checkpoint B stood up the
  `recorded-replay` route in the route catalogue (`chorus/llm_provider/
  adapter_replay.py`); `just eval` and `just test` stayed green through
  C, D, E, F, and G. G now lifts that same substrate into the
  invariant-plus-replay shape ADR 0019 specifies. No mocks at any point.
- **Support Triage retirement distributed cleanly.** Each checkpoint that
  removed support code deleted the matching support tests in the same
  checkpoint. By post-E there were no `support` runtime identifiers
  remaining; the clean-sweep grep below confirms.
- **Workflow spine generality.** The spine in `chorus/workflows/spine.py`
  takes its `WorkflowCorrelation` and `WorkflowStepKind` primitives over
  the UC2 / UC3 deltas in `r1-adapter-mapping.md`, not only UC1:
  approval policies are first-class (UC2 / UC3 will add multiple gates),
  agent and connector steps both carry their specs declaratively, and the
  step taxonomy lives on the per-use-case `WorkflowDefinition` rather
  than on the projection contract. The shape is ready for R4 to add UC2
  and UC3 workflow definitions without touching the spine.

## Clean-Sweep Evidence

Phase 1 decision 5 settled clean rename, no compatibility aliases. The R3
exit clean-sweep grep across `chorus/`, `contracts/`, `tests/`,
`frontend/src/`, and `infrastructure/postgres/` (excluding the frozen
`transformation/` archive, the ADRs that recorded the supersession, and
the applied migrations 007 / 008 / 009 which migration 011 forward-retires
their schema objects) shows no remaining `lighthouse`, `support_triage`,
`ticket.`, `MailpitEmail`, `LegacyCrm`, `LegacyResearch`,
`LighthouseAgentIO`, `SupportAgentIO`, `LighthouseWorkflow`,
`SupportTriageWorkflow`, `lead_id`, or `lead_summary` identifiers in
runtime code or contracts.

## Supersession of the R0.5 "compatibility aliases" clause

Per Phase 1 decision 5, R3 rejected the R0.5
`engineering-reset-roadmap.md` "compatibility aliases" suggestion and
adopted clean rename instead. Preserved evidence is git history (the
pre-R3 baseline commit `9b37338` is tagged `pre-r3-baseline`),
`transformation/phase-2-archive.md`, and the ADRs - documentation and
history that needs no live code to remain valid. This document records
the supersession.

## Code Shape After R3

The post-R3 code shape is honest about the ports-and-adapters thesis:

- `contracts/` regroups around the six named ports plus `eval/`. The
  intake and connector ports each carry a `uc1/` subdirectory for
  use-case-specific payload schemas. R4 adds `uc2/` and `uc3/` siblings.
- `chorus/llm_provider/` is the LLM provider port: `port.py` (surface),
  `adapter_openai.py` (OpenAI-SDK transport), `adapter_replay.py`
  (deterministic recorded-replay substrate), `route_catalogue.py`
  (route metadata).
- `chorus/connectors/` holds the `ConnectorRegistry` and the UC1 sandbox
  adapters (`uc1.py`) plus the calendar adapter (`calendar.py`).
- `chorus/persistence/` is one module per port-shaped read surface:
  `projection.py` (workflow projection writes + workflow/calendar read
  surface), `audit_port.py` (decision-trail + tool-action audit reads),
  `runtime_policy.py` (runtime-policy snapshot composition),
  `provider_governance.py` (provider catalogue + route-version snapshot).
- `chorus/workflows/` holds the shared `WorkflowSpine` primitives plus
  the UC1 enquiry-qualification workflow on the spine; R4 adds the UC2
  and UC3 workflow definitions alongside.
- `chorus/doctor/` is a package, one module per probe class
  (`scaffold.py`, `projection_port.py`, `connector_port.py`,
  `observability_port.py`, `workflow_runtime.py`, `ui.py`). The CLI
  entry is `__main__.py`.
- `chorus/eval/` is the invariant-plus-replay shape ADR 0019 specifies:
  `invariants.py` (the UC1 invariant suite), `scenario_player.py` (drives
  the recorded-replay route through a fixture's scenario and synthesises
  the captured-run artefacts), `replay.py` (the captured-transcript
  replay subcommand), `run.py` (the CLI dispatcher).

## What R4 Starts From

R4 (local POC readiness across UC1, UC2, and UC3 with cross-provider
replay-eval) starts from the following.

- The six-port surface, the connector adapter registry, the audit-port
  split, and the workflow spine are in code. UC1 runs end-to-end on the
  spine.
- The invariant suite is the eval substrate. R4 extends it with UC2 and
  UC3 conduct hooks (SRA conflict + KYC + AML for UC2; FCA COBS 9
  suitability for UC3).
- The recorded-replay route holds the eval contract today; R4 stands up
  the OpenAI-SDK adapter against gpt-5.4-mini (canonical demo / eval)
  and DeepSeek V4-Flash (dev) and runs the cross-provider replay eval
  ADR 0019 names as a first-class mode.
- The R1 product brief (`docs/product-brief.md`), the domain model
  (`docs/domain-model.md`), the use-case confirmations
  (`docs/r1-use-case-confirmation.md`), and the adapter mapping
  (`docs/r1-adapter-mapping.md`) remain the product and domain authority
  for R4. UC2 and UC3 full product briefs and domain models are R4
  artefacts.
- Broker-firm-side persistence for the UC1 connector inventory (quoting
  queue, referral inbox, decline ledger, customer profile,
  product catalogue) is an R4 surface. The R3 adapters compute
  deterministic refs and route through Mailpit where appropriate; R4
  wires the persistence tables behind the same adapters.

## Sign-Off

R3 exit criteria are satisfied. The project reads as a
ports-and-adapters exemplar: the named ports carry the surface, the
adapters live behind them, the audit ports answer accountability, the
invariant suite plus replay answer engineering quality, and the workflow
spine drives the UK-regulated UC1 enquiry-qualification workflow
end-to-end through that surface.

R4 (local POC readiness across UC1, UC2, and UC3 with cross-provider
replay-eval) is the next phase.

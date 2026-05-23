---
type: project-doc
status: active
date: 2026-05-20
phase: R3
---

# R3 Checkpoint Ledger

R3 (contract and code terminology refactor) is the first reset phase that
touches runtime code. It is large and multi-session. This ledger is the
durable progress record: the checkpoint set, the green baseline R3 is
measured against, the settled R3 design decisions, and a per-checkpoint
status. There is no per-checkpoint continuation prompt; this ledger plus
the repo commits are the durable state.

R3 is governed by ADRs 0017-0020, the reset bundle in
[`.`](.) (especially `code-refactor-directions.md`,
`eval-reshape-directions.md`, `engineering-reset-roadmap.md`,
`engineering-thesis.md`), and the R1/R2 artefacts in [`../`](../).

## Operating rule

- Checkpoint-based work. Each checkpoint defines outcome, files likely to
  change, gates, a not-done boundary, and a short next-step note.
- Every checkpoint must leave the gates green relative to the baseline
  below. A checkpoint must not leave a gate worse than it found it.
- Gates: `just contracts-check`, `just test`, `just test-replay`,
  `just lint`, `just doctor`, `just eval`, as applicable.
- Do not skip hooks. British English, conventional commits, no AI
  attribution.
- ADRs 0017-0020 are settled. Do not relitigate them.
- R3 executes as three sessions (with Session 2b as a fallback only if
  checkpoint E overflows) grouping the checkpoints; see the Session plan
  below. Each checkpoint within a session lands its own commit and
  updates this ledger's status row inline; the rolling continuation
  prompt is regenerated only at session end, framing the next session's
  grouping.
- Each session must end gate-green relative to the baseline.
  Intermediate states between checkpoints inside a session do not need to
  be gate-green.

## Scope and constraints

This ledger is the durable, cumulative R3 record - the R3 backlog. R3
runs the continuation-handoff cadence: alongside this ledger, a single
rolling continuation prompt at
`records/radianit/projects/chorus/next-session-prompt.md` in the vault
Chorus records frames the next session's grouping of checkpoints and is
regenerated at the close of each session. The ledger holds durable state; the continuation prompt
is the thin rolling handoff pointer. The R3 kickoff prompt has been
consumed; the constraints below are lifted from it so nothing is lost.

- Do not introduce deployment, hosting, identity / IAM, secrets, or other
  Phase 2E concerns; those are parked in `transformation/parked-phase-2e/`.
- Do not start R4 (local POC readiness across UC1, UC2, UC3). R3 lands
  UC1 only; the R4 entry point is prepared at R3 exit.
- Preserve pre-reset evidence: demote or rename with care rather than
  deleting evidence outright (see decision 5 - evidence is git history,
  `phase-2-archive.md`, and the ADRs).
- Apply `feedback_no_artificial_scoping_questions`: default to the most
  ambitious shape that validates the ports-and-adapters thesis; surface
  only genuine design decisions.
- Documentation moves with the code. As each checkpoint lands, update the
  docs that describe the changed code: `architecture.md` (per-port detail
  and implementation-status), `evidence-map.md` (status columns),
  `runbook.md`, and the `AGENTS.md` stack and component-boundary
  sections. Retire or rewrite the pre-reset docs flagged in
  `r2-exit-criteria.md` - `governance-guardrails.md`,
  `governance-evidence.md`, `demo-script.md`, and `docs/components/` - as
  the code they describe is refactored.
- At R3 exit, write `docs/r3-exit-criteria.md` in the shape of
  `r1-exit-criteria.md` and `r2-exit-criteria.md`, and update the vault
  Chorus `README.md` and the `project_chorus_reset` agent-memory entry.

## Green baseline

Recorded 2026-05-20 at commit `9b37338`
(`docs(adr): record the post-reset architecture decisions`), on a fresh
local stack (volumes reset, all 9 migrations plus seed data applied, 5
event schema subjects registered, Temporal worker running).

| Gate | Result | Notes |
|---|---|---|
| `just contracts-check` | green | 18 generated models current; schemas and samples valid. |
| `just doctor-quick` | green | Scaffold, executables, compose all present. |
| `just lint` | green | ruff check, ruff format, pyright strict, frontend `tsc --noEmit` all clean. |
| `just doctor` | green | All live-stack probes pass. Frontend dev server is a `skip`, not a fail. |
| `just test-replay` | green | 7 passed (Temporal replay determinism). |
| `just eval` | green | All path-enumeration fixtures pass. Live-persisted-evidence steps `skip` without `CHORUS_EVAL_*` env vars. |
| `just test` | **red** | 107 passed, 3 errors. |

### Baseline `just test` failure

The 3 errors are all in `tests/bff/test_app.py`
(`UniqueViolation` on `local_ticket_case_update_proposals_pkey`, key
`caseupd_support_bff_001`). Run in isolation the BFF tests `skip` (4
skipped); they only error inside the full-suite run. This is a pre-reset
test-isolation defect - cross-test database contamination unskips the BFF
tests and then collides on a seeded row - not a runtime code defect.

The bar for every R3 checkpoint is therefore: `just test` no worse than
107 passed / 3 errors, and every other gate green. The eval and test
reshape (checkpoint G) is expected to retire this defect by giving the
suite proper isolation; until then it is the known baseline red.

## R3 design decisions

Settled with Ryan in Phase 1, before any refactoring. Recorded here as
they are agreed.

### 1. Contract directory structure - settled

`contracts/` is regrouped around the six named ports plus `eval/`:
`intake/`, `llm_provider/`, `connector/`, `audit/`, `projection/`,
`observability/`, `eval/`. The intake and connector ports - the two the
thesis says carry use-case variation - get a `uc1/` subdirectory for
use-case-specific payload schemas; port-shared schemas sit directly in
the port directory. The four use-case-invariant ports stay flat. UC2 and
UC3 add `uc2/` and `uc3/` subdirectories under intake and connector in
R4. `audit/` holds both the decision-trail and transcript record
schemas. `projection/` holds the domain event-stream contract
(`workflow_event`) plus read-model schemas. `gen.py` and `check.py` move
from a one-level glob to a recursive `**/*.schema.json` glob; the
generated-model tree mirrors the contract tree.

### 2. Workflow-definition shape (Smell 1) - settled

The step taxonomy becomes typed data; the control flow stays as code over
shared primitives. A `WorkflowDefinition` is a typed step sequence
(`WorkflowStepDefinition` per step: step name, kind - intake / agent /
connector / approval_gate / terminal - plus an agent spec, connector
spec, or approval policy as the kind requires). A shared `WorkflowSpine`
provides the orchestration primitives (event emission, sequence and path
tracking, agent-step call, connector-step call, approval gate,
escalation, bounded retry, retry-exhaustion and compensation) over
generic, shared activity names. Each use case collapses to its
`WorkflowDefinition`, its ubiquitous-language IO types, and a thin
`@workflow.defn` class whose `run()` walks the definition via the spine,
with genuinely use-case-specific branching expressed as plain Python over
spine primitives. A fully declarative transition-and-loop interpreter was
rejected: it rebuilds the in-house orchestration-framework shape ADR 0017
removed, and the control flow is the domain process and is small enough
to read directly.

### 3. Connector adapter registry interface (Smell 2) - settled

Adapter granularity is one adapter per connector (one per sandbox
connector in the R1 adapter mapping), each declaring the family of tools
it serves. A `ConnectorAdapter` protocol exposes `adapter_id`, a
`tool_specs()` sequence of `ToolSpec` (tool name, argument contract,
return contract), and an `invoke(tool_name, mode, context, arguments)`
method. A `ConnectorRegistry` indexes every declared tool name to its
`(adapter, ToolSpec)` pair. Adapters register at a composition root at
startup. The gateway holds the registry: its call path resolves the tool
through the registry, validates arguments against the resolved
`ToolSpec`, applies the mode, dispatches to the adapter, captures audit,
and returns a verdict. Both the dispatch `match` block and the parallel
`_validate_tool_arguments` `match` block are removed; new adapters never
edit the gateway file.

### 4. Lighthouse and Support Triage code disposition - settled

R3 lands UC1 running end-to-end on the new spine. Lighthouse's workflow
role is rewritten as the UC1 workflow (`chorus/workflows/`, UC1 contracts
and ubiquitous language); the Lighthouse name and lead / company-research
language retire. Support Triage is retired outright: `support.py`, the
support agent contract, the support eval fixture, support-specific
projection code, and support runtime are deleted. Support Triage cannot
be rewritten under the new spine in R3 because UC2 has no R1 domain model
and its language is on the UC1 banned-terms list; its second-workflow
proof role passes to UC2 in R4. The branch-enumeration eval fixtures
retire per ADR 0019; Lighthouse's happy path reshapes into UC1's happy
path in checkpoint G. Pre-reset evidence is preserved in git history and
`transformation/phase-2-archive.md`, not as in-tree code. UC2 and UC3 are
deferred to R4.

### 5. Rename strategy - settled

Clean rename, no compatibility aliases. Schemas, generated models,
workflow names, and code rename directly from old to new - no dual-named
schemas, re-exported model names, or `_unused` / `// removed` shims. DB
tables restructure via new forward migrations; applied migrations are
never edited (the checksum guard enforces this). Preserved evidence is
git history (the pre-R3 baseline commit `9b37338` is tagged so the
pointer is concrete), `transformation/phase-2-archive.md`, and the ADRs -
all documentation or history that needs no live code to remain valid.
This supersedes the R0.5 `engineering-reset-roadmap.md` "compatibility
aliases" clause; `r3-exit-criteria.md` will record the supersession.

### 6. Checkpoint ordering - settled

Execution order is A, B, C, D, E, F, G. Contracts first as the
foundation; then the three port implementations that change behaviour -
B (LLM provider), C (audit), D (connector); then E (the spine, built
against the final port surfaces); then F (structural decomposition) and
G (eval reshape). B precedes C because the transcript port records what
the LLM provider port emits. One refinement to the checkpoint set: F
covers `projection.py` and `doctor.py` only; `eval/run.py`'s
decomposition is done inside G, because decomposing path-enumeration eval
is inseparable from the reshape that replaces it.

## R1-deferred items carried into R3

`r1-exit-criteria.md` carried three items explicitly into R3. Tracked
here so they are resolved before R3 exit:

- **Exact regulatory citations** (ICOBS 2.5.-1R, ICOBS 5, PROD 4,
  Consumer Duty rules). Verify before any policy snapshot ships in code -
  checkpoint E (workflow spine and policy snapshot).
- **Referral inbox adapter shape** - a separate sandbox adapter versus a
  tagged subscription on the quoting-queue adapter - checkpoint D
  (connector adapter registry).
- **Customer-profile store boundary** inside the broker firm - settle
  when the `sandbox-customer-profile` connector contract is authored -
  checkpoint D.

## Cross-checkpoint watch items

Surfaced by the 2026-05-21 plan validation:

- **Checkpoint B must keep eval deterministic.** Removing the canned
  `LocalLighthouseModelAdapter` while the eval reshape is checkpoint G
  means B must stand up a deterministic recorded / replay route in the
  route catalogue so `just eval` and `just test` stay green between B and
  G. Consistent with ADR 0018 (route catalogue) and ADR 0019 (replay);
  it is not a mock.
- **Support Triage retirement is distributed.** Each checkpoint that
  removes support code deletes the matching support tests in the same
  checkpoint, to stay gate-green. `r3-exit-criteria.md` asserts the clean
  sweep: no `lighthouse`, `support`, or `ticket` identifiers remain in
  runtime code or contracts at R3 exit.
- **The shared spine is proven by one use case in R3.** Design the
  `WorkflowSpine` and `WorkflowDefinition` (checkpoint E) against the
  UC2 / UC3 deltas in `r1-adapter-mapping.md`, not only UC1, so the
  abstraction is not silently UC1-shaped before R4 exercises it.

## Session plan

R3 executes as three sessions, grouping the checkpoints by what couples
engineering-wise. Session 2b is a fallback only if checkpoint E
overflows; it is not a pre-planned split.

### Session 1 - Contracts + LLM port + audit split (A, B, C)

The ports-surface session. After Session 1: contracts in their final
six-port shape; the LLM provider port runs behind a thin OpenAI-SDK
adapter with the route catalogue (including a deterministic recorded /
replay route so eval stays green between B and G); the audit surface is
split into the decision-trail port and the transcript port. B emits
transcripts that C records; both need A's contract surface, so the three
cluster.

### Session 2 - Connector authority + workflow + UC1 + Support retirement (D, E)

The runtime-behaviour session. After Session 2: the Tool Gateway
dispatches through the ConnectorRegistry, UC1 runs end-to-end on the
shared `WorkflowSpine`, and Support Triage is fully retired (touching
`runtime.py`, `projection.py`, `gateway.py`, the worker, the support
test surface, and the woven support paths). E is the largest single
piece in R3.

### Session 2b (fallback) - if E overflows

E is the biggest single move. If it gets unwieldy mid-session, Session 2
lands D and a clean checkpoint, and E moves to Session 2b. Contingency,
not pre-planned.

### Session 3 - Decompose + eval reshape + finish (F, G, exit)

The cleanup session. F decomposes `projection.py` and `doctor.py` along
port boundaries; G reshapes `eval/run.py` into invariant assertions plus
one happy path per use case and adds the `eval replay` subcommand,
retiring the path-enumeration fixtures. The session closes by writing
`r3-exit-criteria.md`, updating the moved docs (`architecture.md`,
`evidence-map.md`, `runbook.md`, `AGENTS.md`), and retiring the stale
pre-reset docs (`governance-guardrails.md`, `governance-evidence.md`,
`demo-script.md`, `docs/components/`).

## Checkpoints

The checkpoint set derives from the four smells in
`code-refactor-directions.md`, the contract rewrite, and ADRs 0017-0020.
Order is settled by Phase 1 decision 6.

| Checkpoint | Outcome | Status |
|---|---|---|
| A | Contract rewrite around the six named ports. | done |
| B | LLM provider port: LangGraph removed, OpenAI-SDK adapter, route catalogue. | done |
| C | Audit ports: decision-trail port and transcript port split. | done |
| D | Connector adapter registry replacing the hardcoded match dispatch. | done |
| E | Shared workflow spine factored out of the Lighthouse / Support duplication. | pending |
| F | `projection.py` and `doctor.py` decomposed along port boundaries. | pending |
| G | Eval reshape: invariants plus one happy path per use case, `eval replay`. | pending |

Per-checkpoint detail (files, gates run, not-done boundary, next-step
note) is appended below as each checkpoint lands.

### Checkpoint A - contract structure rewrite

**Outcome.** `contracts/` is reorganised into the six named-port
directories plus `eval/` (Phase 1 decision 1). Every existing schema is
relocated by `git mv` into its port home, shape preserved, so runtime
behaviour is unchanged. `gen.py` and `check.py` move to a recursive,
port-aware layout; the generated-model tree mirrors the new contract
tree. All code imports and contract-reference strings are re-pointed.

**Not-done boundary.** A is a structural rewrite only. It does not author
the new-shape port contracts - the `llm_provider` invocation contracts
(checkpoint B), the `audit` decision-trail / transcript split (C), the
`connector` UC1 payloads (D), the `intake` UC1 channel payloads (E), the
reshaped `eval` fixture (G) - each port's contract content is rewritten
by that port's checkpoint. A does not retire Support Triage: support and
ticket schemas relocate shape-preserved alongside everything else;
Support Triage retirement (decision 4) is executed incrementally by the
checkpoints that rewrite each affected module - B (runtime support
paths, `support_agent_io`), D (ticket connector and contracts), E
(`support.py`, `support_request_intake`), F (`projection.py` support),
G (eval support). R3 exit is the point at which Support Triage is fully
retired.

**Gates.** `just contracts-check`, `just lint`, `just test`,
`just test-replay`, `just eval`.

**Evidence (2026-05-23, Session 1).** `contracts/` now contains
`intake/` (with `uc1/`), `llm_provider/`, `connector/`, `audit/`,
`projection/`, `observability/`, and `eval/`. The 21 schemas relocated
shape-preserved via `git mv`: lead intake to `intake/uc1/`; support
request intake to `intake/`; workflow event to `projection/`;
agent invocation record and audit event to `audit/`; Lighthouse / Support
agent IO and provider catalogue / model route version to `llm_provider/`;
tool call, gateway verdict, email and calendar and ticket argument
schemas to `connector/`; eval fixture stays in `eval/`. Schema `$id`
URLs and the in-sample `expected_output_contract` / `declared_in` /
`contract_refs` strings updated to the new paths. `chorus/contracts/gen.py`
moved to a recursive `**/*.schema.json` glob and the generated tree at
`chorus/contracts/generated/` mirrors the contract tree; `check.py`
validates the seven port directories and treats `x-subject` as a
presence-based check rather than a directory-name check. `chorus/doctor.py`
updated to walk the new layout and a syntactically-Python-3-illegal
`except OSError, json.JSONDecodeError:` line inside the doctor schema
registry helper was corrected in passing. `tests/test_scaffold.py`,
`tests/test_contracts.py`, and every other contract import re-pointed
at the new layout; `docs/evidence-map.md` and `contracts/README.md`
rewritten around the seven ports. Gates run on this checkpoint:
`just contracts-check` ok (21 schemas, 21 samples, generated models
current), `just lint` clean (ruff, ruff format, pyright strict, frontend
`tsc --noEmit` all clean), `just test` 107 passed / 3 errors (the
known BFF test-isolation baseline), `just test-replay` 7 passed / 15
deselected, `just eval` all path-enumeration fixtures pass (live
persisted-evidence steps skip without env vars, baseline behaviour).

### Checkpoint B - LLM provider port

**Outcome.** LangGraph is removed from the agent execution path (ADR
0017). The LLM provider port runs behind a thin OpenAI-SDK adapter
against any OpenAI-compatible chat-completions endpoint (ADR 0018). The
adapter is configured per route via base URL, API key, model, and
provider-specific parameters such as thinking-mode toggles. The route
catalogue records provider, model, parameters, and adapter version on
every captured invocation. Three routes register at startup: dev
(DeepSeek V4-Flash with thinking-mode), demo / eval canonical (OpenAI
gpt-5.4-mini), and a deterministic recorded / replay route that re-runs
captured transcripts so `just eval` and `just test` stay green between B
and G (cross-checkpoint watch item). Domain code calls the port with
structured invocation arguments and receives a structured invocation
result; no provider SDK is reachable outside the adapter. The
`runtime.py` support branches are dropped together with the LangGraph
rewrite.

**Not-done boundary.** B does not split the audit store - that is C. B
does not change the workflow spine or the connector registry. The
standalone `chorus/workflows/support.py` class stays until E; its
runtime support is removed here only inside `runtime.py`.

**Gates.** `just contracts-check`, `just lint`, `just test`,
`just test-replay`, `just eval`.

**Evidence (2026-05-23, Session 1).** New `chorus/llm_provider/`
package introduces the port surface: `InvocationArgs` /
`InvocationResult` Pydantic dataclasses, an `LLMProviderAdapter`
Protocol, a `RouteCatalogue` keyed on route id, and two concrete
adapters - `OpenAICompatibleAdapter` (thin wrapper over the OpenAI
Python SDK against any OpenAI-compatible chat-completions endpoint) and
`RecordedReplayAdapter` (deterministic, replays the pre-reset local
Lighthouse responses keyed off `task_kind` + input metadata). The
default catalogue registers three routes: `dev` (DeepSeek V4-Flash,
`CHORUS_LLM_DEV_API_KEY`), `demo-eval-canonical` (OpenAI gpt-5.4-mini,
`CHORUS_LLM_CANONICAL_API_KEY`), and `recorded-replay` (the
deterministic substrate). Domain code never touches `openai` outside the
adapter (verified by `just lint`'s strict pyright pass).

`chorus/agent_runtime/runtime.py` rewritten: `LangGraphAgentExecutionEngine`,
the `AgentExecutionGraphState` TypedDict, the `_state_*` graph helpers,
`ModelAdapterRegistry`, `LocalLighthouseModelAdapter`,
`CommercialExampleModelAdapter`, `CommercialProviderDisabledError`, and
all support paths (`_support_contract`, `_support_result_for`,
`_support_input_refs`, `_support_result_payload`,
`_support_severity_category`, `_support_case_status_category`,
`SUPPORT_AGENT_CONTRACT_REF`) all retire. A new
`SequentialAgentExecutionEngine` runs the five-step pipeline as plain
Python (`prepare_context`, `invoke_llm_provider_port`,
`normalise_result`, `validate_contract`, `final_response`) and emits
`execution.pipeline_version`, `execution.step_path`,
`route_catalogue.route_id`, `route_catalogue.provider_id`,
`route_catalogue.model_id`, `route_catalogue.adapter_version` on every
captured invocation. `AgentRuntimeError.agent_execution_graph_path`
becomes `execution_step_path`. A `ProviderRouteResolver` maps the
existing `model_routing_policies.provider` values to the catalogue's
route ids. `langgraph` leaves `pyproject.toml`; `openai>=1.60.0` joins.

ADR 0017 consequences executed: the `/api/graph-executions` and
`/api/workflows/{id}/graph-executions` BFF endpoints retire, with
`GraphExecutionEntryView` and `_graph_execution_view`. The
projection's `SupportAgentDecisionReadModel` drops `execution_engine`
and `graph_version`; the supporting SQL selects retire too. The
frontend `/graph-executions` route, the `GraphExecutionEntry` type,
`listGraphExecutions` / `listWorkflowGraphExecutions` queries, the
`graphExecutions` fixture, and the nav entry retire; `routeTree.gen.ts`
hand-regenerated; the workflow detail page drops its graph executions
section.

Distributed Support Triage retirement landed B's slice: runtime no
longer accepts `SupportAgentIO`. The matching tests retire in step:
`tests/workflows/test_support_workflow.py` deleted,
`tests/persistence/test_postgres_foundation.py::test_support_eval_persisted_evidence_joins_safe_refs`
deleted, the LangGraph- and commercial-shaped tests in
`tests/agent_runtime/test_runtime.py` removed and the file rewritten
around the new port and pipeline. `tests/bff/test_app.py` and
`test_app_unit.py` updated to the new metadata shape.
`chorus/workflows/support.py`, the support agent-IO schema, and the
support workflow events stay in place per the ledger; they retire in
later checkpoints (E, F, G).

Gates run on this checkpoint: `just contracts-check` ok, `just lint`
clean (ruff, ruff format, pyright strict, frontend `tsc --noEmit` all
clean), `just test` 95 passed / 3 errors (3 = known BFF
test-isolation baseline; absolute pass count is below the 107 baseline
because the watch-item-mandated support-test deletions retire
runtime/support coverage that no longer applies),
`just test-replay` 6 passed / 13 deselected, `just eval` all
path-enumeration fixtures pass (the deterministic recorded/replay route
holds the eval contract per the cross-checkpoint watch item).

### Checkpoint C - Audit ports

**Outcome.** The single Postgres audit store splits into the structured
decision-trail port and the full-fidelity transcript port (ADR 0019).
Decision-trail records carry workflow correlation refs, agent identity
and version, a policy snapshot reference, input / output summaries, tool
calls in summary form, timestamps, and cost. Transcript records carry
the full message and tool-call history, the route catalogue entry,
model parameters as called, provider-side metadata, and token counts -
enough to replay any captured invocation against an alternate provider
through the LLM provider port. A new forward migration creates the
transcript table and any renames needed on the decision-trail table.
`runtime.py` writes both records on every invocation; the gateway's
tool-action audit moves under the audit ports' contracts.

**Not-done boundary.** C does not implement the `eval replay`
subcommand - that is G. C only delivers the data shape and writes that
make replay possible. Support-related audit branches are dropped only
together with their callers in B / E / F / G.

**Gates.** `just contracts-check`, `just lint`, `just test`,
`just test-replay`, `just eval`.

**Evidence (2026-05-23, Session 1).** New contract authored at
`contracts/audit/agent_invocation_transcript.schema.json` plus its
sample under `samples/`, generated to
`chorus/contracts/generated/audit/agent_invocation_transcript.py`.
Records the route catalogue entry (route id, provider id, model id,
adapter version, parameters as called), the full message history sent
and received, tool calls, the optional provider response body, token
usage, provider metadata, and timestamps - the surface ADR 0019 calls
out as "enough to replay any captured invocation against an alternate
provider through the LLM provider port". The decision-trail port
contract (`agent_invocation_record`) stays shape-preserved; it already
carries the compliance fields (correlation refs, agent identity and
version, prompt reference, input / output summaries, tool-call summary
ids, timestamps, cost).

New forward migration
`infrastructure/postgres/migrations/010_audit_transcript_port.sql`
creates `agent_invocation_transcripts` (tenant-scoped RLS, primary key
on `(tenant_id, transcript_id)`, unique constraint on
`(tenant_id, invocation_id)` so a transcript anchors one-to-one on the
decision-trail entry, indexes on `(tenant_id, workflow_id, started_at)`
and `(tenant_id, route_id, completed_at)` for the replay surfaces G
will add).

`chorus/agent_runtime/runtime.py` extended: `RuntimePolicyStore`
Protocol gains a `record_transcript(AgentInvocationTranscript)` method,
`AgentRuntimeStore` implements it as a Postgres INSERT,
`AgentExecutionResult` carries the `request_messages` the engine sent
to the port, and `AgentRuntime.invoke` plus `_invoke_fallback` call
`record_transcript` alongside `record_decision` on every successful
invocation (success path and successful fallback). The transcript is
built by `_transcript_record` from the execution result and the route
catalogue entry. `ProviderInvocationError` carries `request_messages`
and `route_entry` attributes so future iterations can attach a
transcript to LLM-call failures too.

`tests/agent_runtime/test_runtime.py` updated:
`RecordingRuntimeStore` records transcripts as well as decisions; a new
`test_runtime_records_decision_trail_and_transcript_on_every_invocation`
asserts the two records are paired on the same `invocation_id` and the
transcript carries the route catalogue surface. `tests/test_contracts.py`
schema count adjusted from 21 to 22.

Gates: `just contracts-check` ok (22 schemas, 22 samples, generated
models current), `just lint` clean (ruff, ruff format, pyright strict,
frontend `tsc --noEmit` all clean), `just test` 96 passed / 3 errors
(3 = known BFF test-isolation baseline), `just test-replay` 6 passed,
`just eval` all path-enumeration fixtures pass.

### Checkpoint D - Connector adapter registry

**Outcome.** The Tool Gateway dispatches through a `ConnectorRegistry`
(Phase 1 decision 3 / ADR 0020). Adapter granularity is one
`ConnectorAdapter` per connector; each adapter declares its `ToolSpec`s
(tool name, argument contract, return contract reference) and exposes an
`invoke(tool_name, mode, context, arguments)` method. The registry
indexes every declared tool name to its `(adapter, ToolSpec)` pair and
is built at the activity composition root via `default_registry(conn)`.
The gateway's `_decide` and `_decide_calendar_approval_apply` resolve
the tool through the registry, validate arguments against the resolved
`ToolSpec.argument_contract`, apply the mode, dispatch to the adapter,
capture audit, and return a verdict. Both the `LocalToolConnector.match`
dispatch and the parallel `_validate_tool_arguments.match` block are
removed; new adapters never edit the gateway file.

UC1 connector contracts are authored under `contracts/connector/uc1/`
(`customer_profile_lookup_args`, `product_catalogue_lookup_args`,
`outbound_comms_message_args`, `quoting_queue_route_args`,
`referral_inbox_route_args`, `decline_ledger_route_args`) with samples
and generated Pydantic models. Six UC1 sandbox adapters land in
`chorus/connectors/uc1.py` covering the R1 UC1 inventory:
`sandbox-crm` (quoting queue), `sandbox-referral-inbox`,
`sandbox-decline-ledger`, `sandbox-outbound-comms` (Mailpit-backed
missing-data-request send, gated in write mode), `sandbox-customer-profile`
(read-only profile + vulnerability markers), `sandbox-product-catalogue`
(read-only target-market data). The R3 surface is intentionally thin:
adapters compute deterministic refs and route through Mailpit where
appropriate; broker-firm-side persistence tables are an R4 concern.

Two R1-deferred items are settled inside the new contracts and adapters:
the **referral inbox** is a separate sandbox adapter (not a tagged
subscription on the quoting-queue adapter) because `refer` is a routing
destination with its own downstream consumer; the **customer-profile
store boundary** is read-only at the connector port (the write path
lives on the same logical store but is reached only through the firm's
customer-of-record write surfaces, not this adapter). The connector
documents both decisions inline.

Distributed Support Triage retirement landed D's slice: the
`chorus/connectors/ticket.py` connector is deleted; the four ticket
arg-schemas (`ticket_case_lookup_args`,
`ticket_duplicate_case_lookup_args`, `ticket_case_update_proposal_args`,
`ticket_status_update_args`) and their samples and generated models
retire; the gateway no longer dispatches or validates `ticket.*` tools.
The matching tests retire in step: the five `test_ticket_*` tests in
`tests/tool_gateway/test_gateway.py` are deleted and the file's
`RecordingConnector` / `TransientFailingConnector` /
`RejectingCalendarConnector` / `CountingConnector` scaffolding is
rewritten as `_RecordingAdapter` / `_TransientFailingAdapter` /
`_RejectingCalendarAdapter` / `_CountingRegistry` against the new
adapter protocol. `tests/test_contracts.py` schema count goes from 22
to 24 (22 - 4 retired ticket schemas + 6 new UC1 schemas) and now
validates each UC1 sample.

`chorus/workflows/activities.py`'s `invoke_tool_gateway_activity` builds
`default_registry(conn)` instead of `LocalToolConnector(conn)`.
`chorus/connectors/__init__.py` exports the new `ConnectorAdapter`,
`ConnectorRegistry`, `ConnectorContext`, `ToolSpec` surface plus the
Lighthouse-era adapters (`MailpitEmailAdapter`, `LegacyCrmAdapter`,
`LegacyResearchAdapter`) and the `CalendarAdapter`. The Lighthouse-era
adapters retire in checkpoint E with the Lighthouse workflow; until
then they wrap the existing connector classes so the workflow runs
end-to-end through the new dispatch path. The `MailpitEmailConnector`
public method renames from `propose_response` to `send` to match the
new adapter contract; `tests/tool_gateway/test_mailpit_connector.py`
updates to the new call shape.

**Not-done boundary.** D does not retire the Lighthouse workflow or the
Lighthouse-era email/CRM/research adapters; that is E. D does not stand
up broker-firm-side persistence for the UC1 adapters (the quoting queue,
referral inbox, decline ledger, customer-of-record, and product
catalogue tables) - those land in R4 when UC1 wires end-to-end. The
support workflow class (`chorus/workflows/support.py`), the support
agent IO contract, the support intake contract, and the BFF/projection
support inspection surfaces remain in place; they retire in E.

**Gates.** `just contracts-check`, `just lint`, `just test`,
`just test-replay`, `just eval`.

**Evidence (2026-05-23, Session 2).** New types module at
`chorus/connectors/types.py` defines `ConnectorAdapter` Protocol,
`ToolSpec`, `ConnectorContext`, `ConnectorRegistry`, `ConnectorResult`,
`ConnectorError`, `ConnectorTransientError`, `ConnectorRegistryError`.
`chorus/connectors/__init__.py` exposes the registry + the
`default_registry(conn)` factory wiring all adapters. The six UC1
contracts under `contracts/connector/uc1/` + samples + generated models
land at the post-A directory shape (intake and connector are the two
ports the thesis says carry use-case variation; UC1 sits under both).
`chorus/connectors/uc1.py` holds the six UC1 adapter implementations.
`chorus/connectors/local.py` keeps `MailpitEmailConnector`,
`LocalCrmConnector`, `CompanyResearchConnector` and adds
`MailpitEmailAdapter`, `LegacyCrmAdapter`, `LegacyResearchAdapter`
wrappers; `chorus/connectors/calendar.py` keeps
`RadicaleCalendarConnector` and adds `CalendarAdapter` wrapper.

`chorus/tool_gateway/gateway.py` rewritten: `LocalToolConnector` retires
along with the dispatch match block; the new `_validate_arguments`
resolves through the registry. The `ToolGateway` constructor signature
changes from `(store, connector)` to `(store, registry)`. The
`apply_approved_calendar_write` path goes through the registry too.

Files deleted in this checkpoint: `chorus/connectors/ticket.py`,
`contracts/connector/ticket_case_lookup_args.schema.json` (+ sample +
generated model), `contracts/connector/ticket_duplicate_case_lookup_args.schema.json`
(+ sample + generated model),
`contracts/connector/ticket_case_update_proposal_args.schema.json` (+
sample + generated model), `contracts/connector/ticket_status_update_args.schema.json`
(+ sample + generated model).

Gates run on this checkpoint: `just contracts-check` ok (24 schemas, 24
samples, generated models current), `just lint` clean (ruff, ruff
format, pyright strict, frontend `tsc --noEmit` all clean), `just test`
90 passed / 1 skipped / 3 errors (3 = known BFF test-isolation
baseline; pass count is below the 96 post-C bar because the five
watch-item-mandated ticket tests retire alongside the ticket connector),
`just test-replay` 6 passed, `just eval` all path-enumeration fixtures
pass.

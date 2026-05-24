---
type: project-doc
status: active
date: 2026-05-24
phase: R4
---

# R4 Design Decisions

This note narrows the R4 implementation sequence. It sits under the current
design-control set and does not add runtime scope by itself. Implementation
still follows `r4-implementation-backlog.md`.

## Decision Summary

| Decision | R4 position |
|---|---|
| UC1 persistence before UC2 / UC3 | Yes for runtime implementation. UC2 and UC3 product briefs and domain models are written first, but UC2 / UC3 workflow and connector implementation waits until the full UC1 broker-firm connector path is persistence-backed. |
| Runnable channel coverage | A use case is runnable with one documented local intake path that starts the workflow. A channel is runnable only when a local fixture or sandbox adapter validates its channel contract, normalises to the use-case domain record, preserves provenance and idempotency, and can hand off to workflow start without production credentials. |
| Cross-provider replay comparison | Live cross-provider replay uses the tiered comparator from `eval-reshape-directions.md`: hard failures, decision failures, review findings, and metrics. Exact structured-output equality is reserved for deterministic recorded replay and narrow stable fields. |
| Generic approval packages | Approval packages are connector-authority envelopes, not calendar objects. Calendar writes are the current local subset; R4 generalises package creation and apply semantics across any approval-gated connector action. |
| Provider route alignment | The executable route catalogue, DB routing policy, immutable route versions, provider catalogue rows, BFF provider views, and eval route selection must agree on one governed route matrix before a live route is usable. |

## UC1 Before UC2 And UC3 Runtime

R4 completes UC1 broker-firm-side persistence before implementing UC2 or UC3
runtime flows. The ordering is:

1. write the UC2 and UC3 product briefs and domain models;
2. generalise UC1-shaped shared surfaces where the briefs prove the current
   assumptions are too narrow;
3. complete UC1 to the R1 connector path with persistence-backed broker-firm
   refs;
4. harden live-provider routing and replay;
5. implement UC2 and UC3 on the shared spine.

The first step is design work, not runtime breadth. UC2 and UC3 briefs are
needed early because they reveal which projection, approval, eval, fixture,
and connector-contract assumptions are genuinely UC1-specific. Runtime breadth
comes later.

The UC1 completion gate is concrete. Before UC2 or UC3 runtime work starts,
UC1 must persist or deterministically seed the broker-firm-side surfaces that
R3 still approximates: quoting queue refs, referral inbox refs, decline ledger
refs, customer profile data, product catalogue data, verdict routing, and the
policy snapshot row behind `policy_snapshot_ref`. Eval fixtures must prove the
full connector path, not only outbound missing-data communication.

This preserves the project rule of evidence before breadth. If UC1 cannot
complete the existing R1 connector map behind the Tool Gateway, adding UC2 and
UC3 would only multiply unproven adapter assumptions.

## Runnable Channel Coverage

R4 distinguishes "use-case runnable" from "channel runnable".

A use case is runnable when the definition in `r4-implementation-backlog.md`
is met: one documented synthetic or local intake path starts a workflow, the
workflow runs on `WorkflowSpine`, LLM calls go through the provider port,
connector actions go through the Tool Gateway, projections are inspectable,
and eval plus replay evidence is recorded or explicitly skipped with reasons.

A channel is runnable only when all of the following are true:

- the channel payload contract and representative sample exist;
- a local fixture, sandbox adapter, or local infrastructure path can inject a
  representative payload without production credentials or customer data;
- contract validation happens before the domain core accepts the payload;
- normalisation produces the use-case domain work record with channel
  provenance, a channel-specific idempotency key, and a safe subject ref;
- the workflow-start handoff can be exercised by a documented command, test,
  or fixture path.

Production mailboxes, public web forms, partner portals, introducer systems,
identity-provider integration, and production credentials are not required for
R4 channel runnable status. Local infrastructure is enough when it exercises
the same port contract and normalisation boundary.

Docs and evidence must not imply that every named channel is runnable unless
each named channel meets the channel definition above. If R4 only proves one
channel end-to-end for a use case, the remaining channels must be described as
declared adapters with contract coverage, not as runnable channels.

## Cross-Provider Replay Comparison

Cross-provider replay compares one captured transcript against an alternate
route under the same policy snapshot, prompt reference, prompt hash, task
kind, response schema, tool schema set, and safe input summary. The original
route and replay route are both recorded.

The comparator is tiered:

| Tier | Failure or finding |
|---|---|
| Hard fail | Replay output is schema-invalid, missing required policy snapshot evidence, missing required conduct hooks, proposes an unsafe action, omits required audit / transcript evidence, or cannot be replayed through the LLM provider port. |
| Decision fail | Terminal verdict, regulated outcome, route category, required approval decision, or connector-action category differs under the same policy snapshot. |
| Review finding | Rationale, confidence, optional field values, evidence selection, or proposed next step diverges materially without changing the regulated outcome. |
| Metric | Token count, latency, retry count, provider cost, and provider metadata deltas. |

Exact structured-output equality remains useful for the deterministic
`recorded-replay` route and for narrow stable fields such as IDs, enums, and
schema versions. It is not the acceptance criterion for live cross-provider
replay, because provider-neutrality evidence depends on governed equivalence,
not byte-for-byte prose or optional-field equality.

Replay must not duplicate side effects. If a replay reaches the connector
port, it uses dry-run or recorded-action handling and compares the proposed
tool call, gateway verdict, approval requirement, and connector-action
category rather than applying the connector action again.

## Generic Approval Packages

Approval packages are generic Tool Gateway authority records. They are created
when policy says an otherwise valid connector action requires human or
authorised-system approval before effect mode.

The package binds to one exact request:

- tenant, correlation, workflow, invocation, tool call, verdict, and source
  audit event refs;
- agent ID, agent version, task kind, tool name, requested mode, enforced
  mode, and bounded requested action;
- idempotency-key ref, grant ref, route / prompt / policy refs, redaction
  policy ref, SLA / expiry refs, and safe trace join;
- safe `subject_refs`, `action_refs`, or connector-specific refs in metadata.

The package must not store raw tool arguments, raw connector responses, raw
model prompts or outputs, raw reviewer rationale, credentials, customer
content, or personal data. Bounded action labels such as
`outbound_comms.message.write`, `calendar.create_hold.write`,
`engagement_letter.send.write`, or `suitability_report.send.write` are the
right level of detail.

Approval apply is also generic. A reviewer decision alone never invokes a
connector. An approved package authorises a later apply attempt only after the
apply path re-enters the Tool Gateway and the gateway re-checks package state,
expiry, tenant, workflow, invocation refs, grant state, tool spec, argument
schema, requested and enforced mode, idempotency, policy refs, and the safe
action / subject refs captured in the package.

Calendar write packages are the current local implementation subset. R4 widens
the schema, contracts, projection language, and gateway primitives so the same
package lifecycle can serve UC1 outbound communications, UC2 engagement /
conflict / AML approvals, and UC3 suitability / risk / vulnerability approvals
without adding a calendar-specific branch to every new use case.

## Provider Route Alignment

Live-provider routes are usable only when the route surfaces agree. R4 must
treat the route set as one governed matrix with these fields:

- stable runtime route key, for example `recorded-replay`, `dev`, or
  `demo-eval-canonical`;
- immutable route-version ref for governance evidence;
- tenant, agent role, task kind, and tenant tier selectors;
- provider catalogue ID, provider ID, model ID, lifecycle state, and supported
  task kinds;
- provider parameters, response-schema support, budget cap, latency cap,
  fallback policy, credential ref names, and eval eligibility.

The alignment rule is strict:

- the in-process route catalogue is the executable registration of route keys;
- `model_routing_policies` selects the active governed route for a tenant,
  agent role, task kind, and tier;
- `model_route_versions` records immutable governance evidence for that route
  selection;
- provider catalogue rows prove the provider and model are declared, supported
  for the task kind, and structured-output capable where the task requires it;
- the BFF/UI reads the DB governance snapshot and shows route availability as
  inspection evidence only;
- eval route selection chooses from approved, eval-eligible governed routes
  that also resolve in the executable route catalogue.

If any surface is missing, has a provider/model/parameter mismatch, lacks
structured-output capability for the task schema, or lacks required local
credentials, the live route is not usable. The gate should fail fast or record
a skipped live-provider gate with the reason. It must not silently fall back to
an ungoverned provider/model pair.

## Provider Model And Credential Verification

Verified on 2026-05-24 from official provider sources only:

| Provider | R4 route | Verified model identifier | Credential env var | Official source |
|---|---|---|---|---|
| DeepSeek | `dev` | `deepseek-v4-flash` | `DEEPSEEK_API_KEY` | DeepSeek first-call docs, model-list API docs, pricing/model details, and 2026-04-24 change log: `https://api-docs.deepseek.com/`, `https://api-docs.deepseek.com/api/list-models`, `https://api-docs.deepseek.com/quick_start/pricing`, `https://api-docs.deepseek.com/updates/`. |
| OpenAI | `demo-eval-canonical` | `gpt-5.4-mini-2026-03-17` pinned snapshot of `gpt-5.4-mini` | `OPENAI_API_KEY` | OpenAI GPT-5.4 mini model docs and API authentication reference: `https://developers.openai.com/api/docs/models/gpt-5.4-mini`, `https://developers.openai.com/api/reference/overview`. |

DeepSeek's official OpenAI-compatible base URL is `https://api.deepseek.com`;
the docs also state that `deepseek-chat` and `deepseek-reasoner` are legacy
names scheduled for deprecation on 2026-07-24 and currently alias
`deepseek-v4-flash` modes. Chorus must use `deepseek-v4-flash` for R4 route
governance. Because Chorus uses the OpenAI Python SDK as transport, the
DeepSeek thinking-mode metadata is registered as `reasoning_effort` plus
`extra_body.thinking.type`, matching DeepSeek's SDK example.

OpenAI's official model page lists both the `gpt-5.4-mini` alias and the
`gpt-5.4-mini-2026-03-17` snapshot. Chorus uses the pinned snapshot for the
canonical demo / eval route so replay evidence is tied to a stable model
version. The explanatory docs may still refer to the `gpt-5.4-mini` family
when discussing the route's model family.

The executable route catalogue and disabled provider-governance seed rows now
carry these identifiers and credential names. Active `model_routing_policies`
and `model_route_versions` select runtime route `recorded-replay` with the
governed local provider/model pair `local` / `uc1-happy-path-v1`; provider
catalogue rows, BFF inspection views, and eval replay fixtures expose the
same local matrix. Prompt loading and prompt-hash verification have landed for
the provider call path, and the runtime now passes task-specific UC1 response
shapes into the provider port. The OpenAI-compatible adapter requests OpenAI
`json_schema` structured output where supported and JSON-object mode plus
local JSON Schema validation for DeepSeek's current route. Replay comparison
records now exist as safe replay-run evidence linking original
invocation/transcript refs, alternate route metadata, comparator status, safe
lineage refs, and token/cost/latency metrics. The comparator now implements
the hard-fail tier for schema, policy snapshot, conduct hook, unsafe action,
audit/transcript linkage, route-governance, and provider-port replay defects.
The decision-fail tier now classifies bounded UC1 qualification decision
divergence under the same policy snapshot, covering terminal verdict / route
category, regulated outcome, required approval decision fields where present,
and connector-action category evidence available in replay-safe records.
The review-finding tier now records non-terminal UC1 qualification divergence
for recommended-next-step, confidence band / material confidence delta,
rationale presence or text-change evidence without storing free-text
rationale, optional structured fields, and safe evidence-selection refs.
Metrics-only tier semantics and required credentials remain required before
any live provider route is considered usable.

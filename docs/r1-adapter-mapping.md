---
type: project-doc
status: active
date: 2026-05-24
phase: R1
---

# R1 Adapter Mapping

This artefact shows how UC1 exercises each of the six named ports, and
sketches the differences from UC1 that UC2 and UC3 will impose. The
point of the document is to make adapter reuse legible.

For the named ports themselves, see `transformation/engineering-thesis.md`.
For the UC1 domain language and lifecycle, see `domain-model.md`.

## UC1 Full Mapping

The six named ports as exercised by use case 1 (UK personal-lines insurance
broking inbound quote qualification).

### Intake Port

| Aspect | UC1 |
|---|---|
| Adapters | `email-channel` (broker-firm enquiries mailbox), `web-form-channel` (broker-firm website enquiry form), `partner-portal-channel` (warm partner-channel handoff). |
| Payload shapes | `EmailEnquiry`, `WebFormEnquiry`, `PartnerPortalSubmission`. See `domain-model.md` for sketches. |
| Normalisation step | Each channel adapter produces a normalised `Enquiry` record domain-side with the channel preserved as provenance. |
| Contract validation | Every inbound payload validates against the channel-specific contract before the domain core accepts it. Adapter-side validation rejects malformed enquiries before they touch the workflow. |
| Idempotency | Each adapter carries a channel-specific idempotency key (email message-id, web-form submission UUID, partner-supplied submission id). The intake port maps these to `enquiry_ref`. |
| Synthetic-data wiring | The local demo wires the fixture loader as a fourth `synthetic-channel` adapter that injects authored enquiries through the same intake port path the real channel adapters use. |

### LLM Provider Port

| Aspect | UC1 |
|---|---|
| Adapter | OpenAI Python SDK against any OpenAI-compatible chat-completions endpoint. Single adapter, configured per route. |
| Routes used | Dev route DeepSeek `deepseek-v4-flash` (thinking mode for reasoning steps); demo / eval canonical route OpenAI `gpt-5.4-mini-2026-03-17`. |
| Invocation shape | Each invocation carries a `route-catalogue-entry` (provider, model, parameters, adapter version), a structured invocation argument set, and a structured invocation result. The domain core never touches a provider SDK directly. |
| Reasoning steps that hit the port | Classification (`ClassifyEnquiry`), context gathering and demands-and-needs production (`GatherContext`), missing-data request drafting (`RequestMissingData`), qualification verdict production (`QualifyEnquiry`). Each is a separate invocation; each writes a transcript record. |
| Replay-eval shape | Every captured transcript is replayable against any route the catalogue knows. UC1's canonical replay-eval mode is `gpt-5.4-mini-2026-03-17` against captured `deepseek-v4-flash` transcripts and the reverse. |

### Connector Port

| Aspect | UC1 |
|---|---|
| Authority layer | Tool Gateway. Every connector call goes through grant check, mode decision, argument validation, dispatch via the adapter registry (R3), audit capture, and verdict return. |
| Connector adapters | `sandbox-crm` (the standard quoting queue; receives `accept` verdicts), `sandbox-referral-inbox` (receives `refer` verdicts), `sandbox-decline-ledger` (receives `decline` verdicts), `sandbox-outbound-comms` (drives the gated missing-data request send; modelled as a local Mailpit-style capture in the demo), `sandbox-customer-profile` (read-only adapter for customer profile and vulnerability marker lookup), `sandbox-product-catalogue` (read-only adapter for product target-market data). |
| Invocations during a single enquiry | A clean enquiry produces: one product-catalogue read (target-market lookup), one customer-profile read (vulnerability markers), one routing call (to CRM, referral inbox, or decline ledger). An enquiry with a missing-data step adds an outbound-comms call gated by adviser approval. |
| Grants | The agent's policy snapshot declares which connector adapters the agent is permitted to call, and in which modes (dry-run vs effect). UC1 grants the routing connectors in effect mode and the outbound-comms connector in propose-only mode (the human approval gate flips it to effect). |
| Idempotency | Routing calls carry the `verdict_ref` as the idempotency key. Outbound comms carry the `missing_data_request_ref`. Replay through the connector port uses dry-run mode so captured replays do not duplicate side effects. |

### Audit / Transcript Ports

| Aspect | UC1 |
|---|---|
| Structured decision-trail port | Records one decision-trail entry per agent decision: classification, demands-and-needs production, missing-data draft, qualification verdict, routing decision. Each entry carries `decision_ref`, `enquiry_ref`, `policy_snapshot_ref`, `transcript_ref`, agent identity, conduct-hook trace (best interests, demands and needs, target market, foreseeable harm), input summary, output summary, timestamps, cost. |
| Full-fidelity transcript port | Records the full message and tool-call history of each LLM invocation that produced one of the decisions above. Carries enough metadata (route, model, parameters, adapter version, full message sequence, tool-call sequence, tool-result sequence, response body, provider-side metadata) to replay the invocation against an alternate provider through the LLM provider port. |
| Coverage invariant | For every UC1 enquiry, the decision-trail port and the transcript port together cover every LLM invocation and every connector call. Neither port has gaps. |
| Replay-eval substrate | The transcript port is the eval substrate. UC1's eval suite runs invariant assertions over decision-trail content plus replay-as-comparison over captured transcripts. |

### Projection Sink

| Aspect | UC1 |
|---|---|
| Read models surfaced | Enquiry list (open / closed / failed / closed-no-response with filters by channel, product family, verdict, vulnerability marker), enquiry detail (full enquiry record plus state history plus latest verdict plus referral / decline destination), missing-data-request queue (drafts awaiting approval), referral inbox view, decline ledger view, conduct-evidence projection (per-decision conduct-hook trace, for compliance review). |
| Event source | Domain events on the Redpanda stream (`EnquiryReceived`, `EnquiryClassified`, `ContextGathered`, `MissingDataRequestDrafted`, `MissingDataRequestApproved`, `MissingDataRequestSent`, `CustomerResponseReceived`, `EnquiryQualified`, `EnquiryRouted`, `EnquiryClosed`, plus failure events). |
| BFF surface | Read-only. The frontend consumes the projection sink for inspection and demo evidence; no write paths through the BFF. |
| Convergence invariant | Replaying the same event stream twice produces the same read-model state. |

### Observability Sink

| Aspect | UC1 |
|---|---|
| Traces | Every enquiry has a root span with `enquiry_ref` as a trace attribute. Each workflow step (intake, classification, context gathering, qualification, routing) is a child span. LLM invocations and connector calls are leaf spans. The trace shape is uniform across use cases. |
| Metrics | Per-channel enquiry rate, per-product-family enquiry rate, per-verdict outcome rate, missing-data-request approval latency, adviser exception queue depth (for failure paths), LLM cost per enquiry, replay-eval divergence rate (when the canonical replay set runs). |
| Logs | Structured logs at adapter boundaries (intake, connector calls, LLM invocations). Correlation identifier is `enquiry_ref` plus `decision_ref`. |
| Optional LLM observability sidecar | LLM observability adapter is optional and configured per route. Where it is enabled, the transcript port is still authoritative; the sidecar is supplementary. |

## UC2 Deltas From UC1

UC2 (UK legal services intake and conflict check, corporate / commercial,
SRA-regulated) reuses every port. The differences sit in adapter inventory,
approval policy, and audit content.

| Surface | Delta from UC1 |
|---|---|
| Intake channel adapters | `email-channel` stays (most corporate intake is email). `web-form-channel` is reshaped as a corporate intake form (engagement enquiry, not consumer enquiry). `partner-portal-channel` is replaced by `intermediary-referral-channel` (inbound from introducer firms with attached draft engagement letters). |
| LLM provider port | No change. Same adapter, same routes. The invocations are over corporate intake text (multiple parties, engagement scope, scope-of-work statements) rather than personal-lines enquiry text. |
| Connector inventory | Add `sandbox-conflict-check` (queries the firm's existing-client base for conflicts), `sandbox-kyc-bo` (KYC plus beneficial-ownership lookup for corporate parties), `sandbox-aml-record-store` (AML risk-rating record and source-of-funds record), `sandbox-engagement-letter-store`. Drop `sandbox-product-catalogue` (no product target-market concept in legal intake). |
| Approval policy | More than one gate. Engagement letter send is gated. Acceptance of a matter where a declared conflict exists is gated by partner-level approval. AML enhanced-due-diligence flag is gated by the firm's Money Laundering Reporting Officer (sandbox MLRO inbox). |
| Audit / transcript ports | Same ports. Decision-trail content changes: SRA Code of Conduct duty checks (best interests, integrity, confidentiality), conflict-of-interest determination with parties listed, AML risk-rating with the relevant Money Laundering Regulations sections cited (pending verification in R3). |
| Projection sink | Add conflict-of-interest determination projection, AML risk-rating projection, engagement-letter approval queue. Drop quoting queue, decline ledger (legal "decline to act" surfaces differently). |
| Observability sink | Same shape. New per-use-case metrics (conflict-hit rate, EDD-trigger rate, engagement-letter approval latency). |

## UC3 Deltas From UC1

UC3 (UK independent financial advice inbound enquiry, FCA-regulated, COBS 9
suitability) reuses every port. The differences sit in adapter inventory,
approval policy, and audit content.

| Surface | Delta from UC1 |
|---|---|
| Intake channel adapters | `web-form-channel` (most common for IFA acquisition), `email-channel`, replace `partner-portal-channel` with `introducer-referral-channel` (referrals from accountants, solicitors, mortgage brokers). |
| LLM provider port | No change to the adapter. The invocation shape is richer: multi-turn fact-find, free-text attitude-to-risk narrative, capacity-for-loss reasoning. Token cost per enquiry is materially higher than UC1; the route catalogue still records provider plus model per call. |
| Connector inventory | Add `sandbox-attitude-to-risk-profiler` (a regulated assessment tool, modelled as an adapter contract), `sandbox-capacity-for-loss-tool` (a structured cash-flow tool), `sandbox-suitability-report-store`, and `sandbox-platform-research` (read-only adapter that returns notional product universe data for the suitability check). Vulnerability assessment is an intake, reasoning, approval, and projection concern in R4, not a separate connector. |
| Approval policy | Suitability report issue is gated (the most direct customer-impact action). Attitude-to-risk classification confirmation is gated when the inferred classification disagrees with the customer's stated preference. Vulnerability-marker-triggered handoff is gated by adviser-level approval. |
| Audit / transcript ports | Same ports. Decision-trail content carries COBS 9 suitability test results (objectives match, financial situation match, knowledge-and-experience match, attitude-to-risk match, capacity-for-loss match), product-universe consideration trace (independent advice requires consideration of a sufficient range), and Consumer Duty foreseeable-harm test. The decision-trail invariants for UC3 are the strictest of the three use cases. |
| Projection sink | Add suitability-report queue (drafts awaiting approval), attitude-to-risk classification projection, capacity-for-loss projection, vulnerability-marker projection. |
| Observability sink | Same shape. New per-use-case metrics (suitability-test pass rate, attitude-to-risk disagreement rate, vulnerability-handoff rate, suitability-report approval latency). |

## What Adapter Reuse Means In Practice

The mapping above shows the architectural commitment in concrete form:

- The six named ports stay constant across three regulators.
- The workflow spine (intake -> classification -> context gathering ->
  proposed action -> approval where required -> routing -> closure) stays
  constant.
- The LLM provider port adapter stays constant; only the route catalogue
  entries and the invocation payloads differ.
- Adapter inventory differs per use case: each use case ships its own
  channel adapters and its own connector adapters, registered with the
  Tool Gateway adapter registry (R3).
- Policy snapshots differ per use case: which actions are gated, which
  conduct hooks are evaluated, which target-market or product-universe
  checks apply.
- Audit / transcript content differs per use case: the structured
  decision-trail port carries regulator-specific conduct-hook fields, but
  the record shape (decision_ref, policy_snapshot_ref, transcript_ref,
  agent identity, conduct-hook trace, input / output summaries, timestamps,
  cost) is uniform.

R3 (contract and code terminology refactor) lands the shared workflow spine,
the connector adapter registry, and the per-port projection split. R4
(local POC readiness) wires the three use cases through the refactored
spine and runs the cross-provider replay-eval over all three.

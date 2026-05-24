---
type: project-doc
status: active
date: 2026-05-20
phase: R1
use_case: UC1
---

# Domain Model - UK Insurance Broking Inbound Quote Qualification

This document is the ubiquitous language for use case 1. It defines the
domain terms, actors, artefacts, commands, events, aggregates, value
objects, state machine, policies, approval points, failure paths, and
banned terms that the rest of UC1 work must use.

Contract shapes here are schema sketches. The actual JSON Schema contracts
are produced during R3 (contract and code terminology refactor). The
sketches are deliberately under-specified at the field level; what matters
in R1 is which payload crosses which port, and which fields the domain
treats as load-bearing.

## Glossary

| Term | Definition |
|---|---|
| Enquiry | An inbound expression of interest from a customer in a personal-lines insurance product. An enquiry is the unit of work the qualification workflow operates on. |
| Channel | The intake surface that delivered an enquiry: email, web form, or partner portal. A channel is an adapter behind the intake port; the channel does not vary the enquiry's identity. |
| Customer | The natural person or persons the enquiry is on behalf of. A customer is identified by `customer-ref` and may have one or more applicants under the same enquiry. |
| Applicant | A natural person who would be a policyholder on the resulting policy. An enquiry has one or more applicants. |
| Product family | A coarse classification of cover: motor, home, travel, pet, other. The product family drives target-market checks and downstream routing. |
| Demands and needs | The customer's expressed needs for cover, captured as a statement at the context-gathering step. Required under ICOBS 5 for the distribution work to be lawful (pending exact section verification). |
| Target market | The PROD 4 definition of which customers a product is intended for. A distributor must check that the customer falls inside the target market for the product family being considered. |
| Risk acceptability | Whether the enquiry's risk profile is one the broker firm is willing to quote on under standard terms. Distinct from the price the risk would attract. |
| Qualification verdict | The structured outcome of the qualification step: `accept`, `refer`, or `decline`. Carries a rationale, the conduct-hook evaluations performed, and the policy snapshot reference. |
| Missing-data request | An outbound customer communication that asks for additional data needed to complete qualification. The only outbound customer communication in UC1 scope. Subject to human approval before send. |
| Referral | The act of routing an enquiry whose qualification verdict was `refer` to the senior underwriter inbox. |
| Decline | The act of recording an enquiry whose qualification verdict was `decline` with rationale and conduct-hook trace. No customer-facing message is sent automatically; that is out of scope for UC1. |
| Policy snapshot | An immutable bundle of the operational configuration in force when an agent decision was made: route catalogue entry, prompts, grants, modes, target-market rules, conduct-hook checks. Identified by content-addressed hash. |
| Route catalogue entry | Provider, model, model parameters, adapter version. Recorded on every LLM invocation. |
| Decision-trail record | The structured audit record for a single agent decision: who, what, under which policy, on which inputs, with which outputs. Stored at the structured decision-trail port. |
| Transcript record | The full-fidelity record of a single LLM invocation: message sequence, tool calls, tool results, response body, route metadata, parameters. Stored at the transcript port. Replayable. |
| Vulnerability marker | A flag on the customer record or enquiry record indicating a Consumer Duty vulnerability (financial difficulty, recent bereavement, communication adjustments needed, other). Influences the foreseeable-harm test and outcome monitoring. |

## Actors And Roles

| Actor | Role |
|---|---|
| Customer | Originates the enquiry. May respond to a missing-data request. |
| Applicant | Subject of cover on the resulting policy. The customer and the applicant may be the same person or different people (e.g., a customer enquiring on behalf of a partner). |
| Adviser / qualifier | Reviews and approves the drafted missing-data request before send. Consumes the workflow output on the standard quoting queue. |
| Senior underwriter | Receives referred enquiries from the referral inbox. Decides whether to engage with the enquiry. |
| Compliance | Consumes the structured decision-trail port for conduct-rule evidence, vulnerability monitoring, and outcome monitoring. Not in the workflow's hot path. |
| Chorus runtime | The system performing classification, context gathering, qualification, and routing. Operates entirely through the named ports. |

## Inbound Artefacts (Schema Sketches)

Schema sketches only. Actual contracts arrive in R3.

### Email Enquiry (intake adapter: `email-channel`)

```
EmailEnquiry {
  channel: "email"
  received_at: timestamp
  from: string (email address)
  subject: string
  body_text: string
  body_html: string (optional)
  attachments: list of {name, mime, size, sha256}
  raw_headers: map (string -> string)
}
```

### Web Form Enquiry (intake adapter: `web-form-channel`)

```
WebFormEnquiry {
  channel: "web-form"
  received_at: timestamp
  form_version: string
  fields: map (field-name -> field-value)
  notes: string (free-text notes field)
  consent_flags: { contact_consent: bool, marketing_consent: bool, ... }
  source_referrer: string (optional)
}
```

### Partner Portal Submission (intake adapter: `partner-portal-channel`)

```
PartnerPortalSubmission {
  channel: "partner-portal"
  received_at: timestamp
  partner_ref: string (which partner)
  partner_submission_id: string
  applicant_profile: { ... structured fields ... }
  enquiry_payload: { ... product-family-specific fields ... }
}
```

### Normalised Enquiry (post-intake, domain-side)

```
Enquiry {
  enquiry_ref: uuid
  channel: "email" | "web-form" | "partner-portal"
  received_at: timestamp
  source_payload_ref: opaque ref to the original payload at the intake port
  customer_ref: uuid
  applicants: list of { applicant_ref: uuid, role: "primary" | "joint" }
  product_family: "motor" | "home" | "travel" | "pet" | "other" | null  // null until classification
  state: EnquiryState
  vulnerability_markers: list of vulnerability_marker
}
```

## Commands

Commands are intent-bearing inputs to the workflow. Each command runs through
the named ports and produces domain events.

| Command | Source | Description |
|---|---|---|
| `IntakeEnquiry` | Intake port. | Accept an inbound enquiry from a channel adapter and create the normalised enquiry record. |
| `ClassifyEnquiry` | Workflow step. | Ask the LLM provider port to assign a product family and identify the demanded cover shape. |
| `GatherContext` | Workflow step. | Ask the LLM provider port to produce a demands-and-needs statement, identify missing data, and flag risk-acceptability concerns. |
| `RequestMissingData` | Workflow step. | Draft a missing-data request and propose it for human approval. |
| `ApproveMissingDataRequest` | Adviser action. | Approve the drafted request for send. Gated step. |
| `SendMissingDataRequest` | Workflow step. | Once approved, dispatch the missing-data request through the outbound customer comms connector. |
| `ReceiveCustomerResponse` | Intake port. | Match an incoming customer reply to the open enquiry and update completeness. |
| `QualifyEnquiry` | Workflow step. | Ask the LLM provider port to produce a structured qualification verdict with rationale and conduct-hook trace. |
| `RouteVerdict` | Workflow step. | Route the verdict to its destination connector (standard quoting queue, referral inbox, or decline ledger). |
| `CloseEnquiry` | Workflow step. | Mark the enquiry as closed for the qualification workflow. |

## Domain Events

Events are facts about state change. Every event is persisted on the
projection sink's event stream and contributes to the audit ports.

| Event | Description |
|---|---|
| `EnquiryReceived` | Intake port accepted a new enquiry; normalised record created. |
| `EnquiryClassified` | A product family was assigned with rationale. |
| `ContextGathered` | A demands-and-needs statement was produced; missing data and risk-acceptability flags recorded. |
| `MissingDataRequestDrafted` | A drafted missing-data request was created and is awaiting human approval. |
| `MissingDataRequestApproved` | An adviser approved the drafted request. |
| `MissingDataRequestSent` | The outbound comms connector dispatched the request. |
| `CustomerResponseReceived` | A customer reply was matched to the enquiry; completeness updated. |
| `EnquiryQualified` | A qualification verdict was recorded (`accept`, `refer`, or `decline`) with rationale and conduct-hook trace. |
| `EnquiryRouted` | The verdict was routed to its destination connector; verdict record returned. |
| `EnquiryClosed` | The enquiry left the qualification workflow. |

## Aggregates And Lifecycle Records

| Aggregate | Lifecycle |
|---|---|
| Enquiry | Created by `IntakeEnquiry`. Mutated by `ClassifyEnquiry`, `GatherContext`, `RequestMissingData`, `ReceiveCustomerResponse`, `QualifyEnquiry`, `RouteVerdict`, `CloseEnquiry`. Lifecycle terminates at `EnquiryClosed`. Holds enquiry_ref, customer_ref, applicants, product_family, state, vulnerability_markers, and references to the latest demands-and-needs statement, qualification verdict, and routing outcome. |
| MissingDataRequest | Created by `RequestMissingData`. Awaits `ApproveMissingDataRequest` from an adviser. Sent by `SendMissingDataRequest`. Holds request_ref, enquiry_ref, drafted body, the field set being requested, the approving adviser identity, the send timestamp. |
| QualificationVerdict | Created by `QualifyEnquiry`. Immutable once recorded. Holds verdict_ref, enquiry_ref, outcome (`accept` / `refer` / `decline`), rationale, conduct-hook trace, decision_ref, policy_snapshot_ref, transcript_ref. |
| Referral | Created by `RouteVerdict` when the verdict is `refer`. Holds referral_ref, enquiry_ref, verdict_ref, target inbox, routed_at. |

The Enquiry aggregate is the workflow's primary lifecycle record. The other
aggregates hang off it and are referenced by their refs.

## Value Objects

| Value object | Shape |
|---|---|
| `ProductFamily` | Enum of `motor`, `home`, `travel`, `pet`, `other`. |
| `EnquiryState` | Enum (see state machine). |
| `Verdict` | Enum of `accept`, `refer`, `decline`. |
| `VulnerabilityMarker` | Tagged value: `financial_difficulty`, `recent_bereavement`, `communication_adjustment`, `health_related`, `other` with an optional free-text note. |
| `DemandsAndNeedsStatement` | Structured statement: customer's stated needs, customer's stated constraints, the cover shape consistent with those needs, exclusions or limits the customer should be aware of. |
| `ConductHookTrace` | A record of which conduct hooks were evaluated for a decision: best-interests test result, demands-and-needs link, target-market check result, foreseeable-harm test result. |
| `PolicySnapshotRef` | Content-addressed hash of the policy bundle. Treated as an opaque identifier domain-side; the bundle itself is loaded by the policy-snapshot adapter when needed for replay. |
| `RouteCatalogueEntry` | Provider, model, model parameters, adapter version. |
| `MissingDataField` | A named field the workflow needs from the customer to complete qualification (e.g., `previous_claims_5y`, `licence_history`, `vehicle_modifications`, `property_construction_type`). |

## State Machine

The Enquiry aggregate moves through a small set of states.

| State | Reached by | Exits to |
|---|---|---|
| `received` | `IntakeEnquiry`. | `classifying` (immediately, in the same workflow run). |
| `classifying` | After `EnquiryReceived`. | `gathering_context` on `EnquiryClassified`; `failed_classification` on classification failure (see failure paths). |
| `gathering_context` | After `EnquiryClassified`. | `awaiting_customer_data` if missing-data request is needed; `qualifying` if no missing data. |
| `awaiting_customer_data` | After `RequestMissingData` produces a drafted request. | `awaiting_send_approval` once draft is recorded. |
| `awaiting_send_approval` | After `MissingDataRequestDrafted`. | `awaiting_customer_response` on `MissingDataRequestSent`; `gathering_context` if the adviser rejects the draft and asks for redraft. |
| `awaiting_customer_response` | After `MissingDataRequestSent`. | `gathering_context` on `CustomerResponseReceived`; `closed_no_response` on response timeout. |
| `qualifying` | After context is complete. | `routing_verdict` on `EnquiryQualified`. |
| `routing_verdict` | After `EnquiryQualified`. | `routed_accept`, `routed_refer`, or `routed_decline` on `EnquiryRouted`. |
| `routed_accept`, `routed_refer`, `routed_decline` | Terminal-before-closure states. | `closed` on `CloseEnquiry`. |
| `closed` | Terminal. | None. |
| `failed_classification`, `failed_context`, `failed_routing`, `closed_no_response` | Failure / escalation terminal states. | None. See failure paths. |

State changes are recorded on the projection sink event stream and on the
decision-trail port (for state changes triggered by an agent decision).

## Policies And Invariants (FCA Conduct)

Each policy below maps to a regulator-cited rule and is enforced as an
invariant on the workflow.

| Policy | Source | Invariant |
|---|---|---|
| Best-interests test on every qualification | ICOBS 2.5.-1R (pending exact verification). | No `EnquiryQualified` event may be emitted without a `ConductHookTrace.best_interests_test` value of `pass` or `fail` with rationale. A `fail` blocks `accept` verdicts. |
| Demands-and-needs statement before verdict | ICOBS 5 (pending exact verification). | No `EnquiryQualified` event may be emitted without an associated `DemandsAndNeedsStatement` referenced by the verdict. |
| Target-market check | PROD 4 distributor obligations. | No `accept` verdict may be issued unless the target-market check for the product family returns `in_market`. `out_of_market` produces a `decline` verdict with target-market-mismatch rationale; `edge_of_market` produces a `refer` verdict. |
| Foreseeable-harm test under Consumer Duty | FCA PRIN 12 plus cross-cutting rules (pending exact citation). | No `accept` verdict may be issued without an explicit foreseeable-harm evaluation against the customer's vulnerability markers. A `fail` blocks `accept`. |
| Customer-facing communication is gated | Internal control derived from Consumer Duty good-faith and avoidance-of-foreseeable-harm cross-cutting rules. | No `MissingDataRequestSent` event may be emitted without a corresponding `MissingDataRequestApproved` event from an authorised adviser. |
| Audit completeness | Architectural invariant derived from the thesis. | Every `EnquiryQualified` event must reference a `decision_ref`, a `policy_snapshot_ref`, and a `transcript_ref`. No decision is unattributed. |
| Replay stability | Architectural invariant derived from the thesis. | The transcript record for every `EnquiryQualified` must contain enough metadata (route, model, parameters, full message and tool-call history) to be replayed against an alternate provider through the LLM provider port. |

The "pending verification" notes on ICOBS 2.5.-1R, ICOBS 5, and Consumer Duty
citations will be resolved during R3 before any policy snapshot ships in
code. R1 is a domain-model artefact; the citations are placeholders, not
load-bearing yet.

## Approval Points

Approval is a deliberate design surface. UC1 has exactly one synchronous
human approval gate.

| Approval point | Gate | Rationale |
|---|---|---|
| Missing-data request send | Adviser approval required. The drafted request cannot reach `MissingDataRequestSent` without `MissingDataRequestApproved`. | Outbound customer communication carries direct customer impact and falls under the gated-comms invariant. |

All other workflow decisions (classification, demands and needs, risk
flag, qualification verdict, routing) are agent-proposed and recorded
on the decision trail without a synchronous approval gate. The audit
trail is the asynchronous control surface.

This is the deliberate position of UC1: prove that the architecture can
carry governed agent decisions through to system effects when the audit
trail is dense enough to support both compliance review and replay-eval.
The single approval gate is on the outbound customer-facing action.

## Failure And Escalation Paths

| Failure | Trigger | Path |
|---|---|---|
| Classification failure | LLM provider port returns an output that fails contract validation, or the route catalogue cannot serve the call. | Enquiry transitions to `failed_classification`. A `ClassificationFailed` event is recorded. The enquiry surfaces on an adviser exception queue (sandbox adapter) for manual handling. |
| Context-gathering failure | Same shape as classification failure during the context-gathering step. | Enquiry transitions to `failed_context`. Adviser exception queue receives it. |
| Adviser rejects missing-data draft | `ApproveMissingDataRequest` returns `reject` with a redraft hint. | Enquiry returns to `gathering_context`; a new draft is produced. |
| Customer response timeout | No `CustomerResponseReceived` within the configured response window (sandbox uses 14 days for the demo). | Enquiry transitions to `closed_no_response`. Decision trail records the timeout. No further customer comms. |
| Routing failure | Connector adapter for the verdict's target inbox returns an error. | Enquiry transitions to `failed_routing`. The verdict remains on the decision trail; the routing failure is captured; an adviser exception queue receives the enquiry for manual routing. |
| Target-market `out_of_market` | PROD 4 invariant. | Verdict forced to `decline` with target-market-mismatch rationale. Not a failure; a controlled outcome. |
| Vulnerability marker plus foreseeable-harm fail | Consumer Duty invariant. | Verdict cannot be `accept`. Either `refer` (if the harm is potentially mitigable by a different product family) or `decline`. |

All failure transitions emit events on the projection sink event stream
and decision-trail records where an agent decision was involved.

## Banned And Ambiguous Terms

Terms below are explicitly out of UC1's ubiquitous language. The replacement
term carries the precise meaning the workflow needs.

| Banned / ambiguous term | Replacement | Reason |
|---|---|---|
| Case | Enquiry, plus the specific lifecycle records (MissingDataRequest, QualificationVerdict, Referral) where a sub-concept is meant. | Too generic for general insurance distribution. |
| Ticket | Enquiry exception, or adviser exception queue entry. | Same reason as `Case`. |
| Account | Customer (the natural person) or applicant (the policyholder-to-be). | "Account" implied a CRM-system abstraction rather than a domain entity. |
| Score | Risk-acceptability flag or target-market check result. | "Score" implies a single numeric value that the workflow does not produce. |
| Recommendation | Qualification verdict (when the meaning is the workflow's structured outcome) or proposed cover shape (when the meaning is the cover the customer should be offered). | "Recommendation" carries COBS suitability connotations that do not apply to non-advised general insurance distribution. |
| Advice | Distribution work. | "Advice" is a regulated concept under COBS that does not apply to UC1's non-advised distribution. Misuse risks misrepresenting the regulated activity. |
| Tool | Domain verbs (`request_missing_data`, `route_verdict`, etc.). | "Tool" is a platform / Tool Gateway term. The domain language uses its own verbs. The Tool Gateway is the connector port's authority layer, not a domain concept. |

The "Tool" rule deserves emphasis. The Tool Gateway and tool calls stay as
platform / connector-port vocabulary inside the architecture; domain
workflow descriptions for UC1 must use the verbs above. This boundary
keeps the domain model legible to a non-engineering reviewer (compliance,
underwriter) without exposing platform plumbing.

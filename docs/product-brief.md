---
type: project-doc
status: active
date: 2026-05-24
phase: R1
use_case: UC1
---

# Product Brief - UK Insurance Broking Inbound Quote Qualification

This brief is the R1 product description for use case 1. It is written for a
reviewer who has not read the reset bundle. Adapter-level detail sits in
`r1-adapter-mapping.md`; the domain model sits in `domain-model.md`.

## Use Case Statement

A UK personal-lines insurance broker firm receives inbound consumer enquiries
across email, the firm's web enquiry form, and partner-portal submissions.
Each enquiry must be classified, completed where data is missing, screened
for risk acceptability, and either accepted for quoting, declined, or
referred to a senior underwriter. Chorus models this intake-to-routing
workflow with agent-proposed decisions, contract-validated payloads at
every port, and an audit shape that satisfies the relevant FCA conduct
regime.

## Market Segment And Positioning

| Aspect | Value |
|---|---|
| Market segment | UK personal lines (motor, home, travel, pet, other retail consumer general insurance). |
| Regulatory regime | FCA general insurance distribution (ICOBS, PROD 4, Consumer Duty). |
| Firm type | UK retail broker firm acting as the customer's distributor. The broker owns the customer relationship and is the regulated principal for the distribution work the workflow performs. |
| Out-of-frame positions | MGA receiving broker submissions, insurer's direct channel. Either could be modelled with the same workflow shape later, but UC1 is the broker-firm shape. |

## Roles

| Role | Description |
|---|---|
| Customer | UK individual consumer making an inbound enquiry for personal-lines cover. May be a single applicant or a joint applicant (e.g., joint home insurance). |
| Broker firm | The regulated principal. Receives the enquiry and operates the qualification workflow under FCA distribution rules. |
| Adviser / qualifier | Internal broker-firm staff who would, in the manual baseline, triage and qualify enquiries. In the Chorus-assisted workflow they receive auto-routed referrals and approve outbound customer communication. |
| Senior underwriter | Internal broker-firm role (or, in some firms, an insurer-side role accessed through a referral inbox). Receives referred enquiries that fall outside the standard qualification path. |
| Compliance | Internal control function. Consumes the structured decision-trail port for conduct-rule evidence and outcome monitoring. |

## Inbound Channels In Scope

| Channel | Shape |
|---|---|
| Email | Free-text inbound emails to the broker's enquiries mailbox. Variable completeness, occasional attachments, mixed structure. |
| Web enquiry form | The firm's own structured web form. Constrained fields plus a free-text notes field that customers commonly use to express the actual context. |
| Broker / agent portal submission | Warm enquiry handoffs from a partner channel (e.g., aggregator handoff into the broker, partner site embedded broker). Partially structured payload. |

Telephony notes are out of scope for UC1. They are a candidate intake adapter
for a later phase but not for the R1 demo.

## Process Pain In The Current Manual Workflow

The pain the workflow targets is the manual qualification step that sits
between inbound and quote:

- Inbound enquiries arrive in mixed shapes (free-text email vs structured
  form vs partner submission). Triage by hand is repetitive and inconsistent
  across advisers.
- Data completeness varies. Advisers chase missing data over multiple
  exchanges, each one introducing latency and rework.
- Risk-acceptability calls (claims history, prior cancellations, undisclosed
  modifications, target-market fit) are made by adviser judgement, with
  evidence captured in free-text notes rather than a structured trail.
- Referral routing depends on adviser experience. A junior adviser may pass
  a marginal case forward when it should have been declined or referred;
  a senior adviser may decline a case that another firm would have accepted.
- Conduct evidence is reconstructed after the fact when needed. Demands and
  needs, target-market fit, and Consumer Duty considerations are not
  consistently captured at the moment the decision is made.

The result is qualification work that is slow, uneven across advisers, and
weak as audit evidence.

## Proposed Chorus-Assisted Workflow

The workflow has five domain steps. Each step runs through the named ports.

| Step | Description |
|---|---|
| Intake | The intake port receives the enquiry from the active channel adapter (email, web form, or partner portal) and contract-validates the payload. A normalised enquiry record is created. |
| Classification | The LLM provider port classifies the enquiry against the firm's product taxonomy (motor, home, travel, pet, other) and identifies the demanded cover shape. The route catalogue records the provider, model, and parameters used. |
| Context gathering | The LLM provider port reasons over the enquiry plus any captured profile data to produce a demands-and-needs statement, identify missing data, and flag risk-acceptability concerns. If data is missing, a missing-data request is drafted and proposed for human approval before send. |
| Qualification decision | The LLM provider port produces a structured qualification verdict: accept-and-route to standard quoting, refer to senior underwriter, or decline. The verdict carries the policy snapshot reference, the inputs considered, the rationale, and the FCA conduct hooks evaluated (best interests, demands and needs, target market, Consumer Duty). |
| Referral routing | The connector port routes the verdict to the right destination: the firm's standard quoting queue (sandbox CRM adapter), the senior underwriter referral inbox (sandbox referral adapter), or a decline-record adapter. Every connector call goes through the Tool Gateway with grant check, mode decision, argument validation, and verdict capture. |

The workflow stops at referral routing. Pricing, quote issuance, and bound
policy are out of scope for UC1.

## Agent-Proposed Vs Human-Approved Decisions

| Decision | Agent proposes | Human approval gate |
|---|---|---|
| Enquiry classification | Yes. | None. Audit trail records classification rationale; downstream steps reuse it. |
| Demands-and-needs statement | Yes. | None. Captured to the decision-trail port. |
| Missing-data request to customer | Yes. | Required. The drafted request is the only outbound customer communication in UC1 scope and is gated for human review before send. |
| Risk-acceptability flag | Yes. | None. Flag is recorded on the decision trail; downstream routing acts on it. |
| Qualification verdict (accept / refer / decline) | Yes. | None in the demo. The verdict is auto-routed; the human role is to consume the audit trail and act on referrals or declines through the receiving connector. |
| Underwriter referral routing | Yes. | None. The senior underwriter sees the referred enquiry in their queue and decides whether to engage; the workflow does not gate on a human approving the routing decision. |

The deliberate position: UC1 demonstrates that the architecture can carry
governed agent decisions through to system effects without a human approval
gate on every decision, provided the audit trail is dense enough to support
both compliance review and replay-eval. The single approval gate is on
outbound customer communication, where the cost of a bad decision is
direct customer impact. Internal decisions are auditable but not gated.

## FCA Conduct Touch Points

The workflow makes each of the following conduct hooks visible on the
decision trail. Where regulatory detail below cites a specific source,
the source is named; where the detail is the author's best understanding,
it is flagged as pending verification before the workflow is implemented.

| Conduct hook | Source | How UC1 surfaces it |
|---|---|---|
| Customer's best interests rule | ICOBS 2.5.-1R (pending verification of current numbering). | Every qualification verdict records the best-interests test applied: were the inputs weighed in the customer's interests, and is the proposed outcome (accept, refer, decline) consistent with that test. |
| Consumer Duty | FCA PRIN 12 plus cross-cutting rules and four outcomes (pending verification of exact citation). | The audit trail captures vulnerability markers identified in the enquiry, the foreseeable-harm test applied to the proposed outcome, and outcome-monitoring fields the compliance projection can aggregate. |
| Demands and needs | ICOBS 5 (pending verification of section number). | The context-gathering step produces an explicit demands-and-needs statement that is recorded on the decision trail and referenced by the qualification verdict. |
| Target market (PROD product oversight) | PROD 4 (distributor obligations under product governance). | The classification and qualification steps check whether the customer falls inside the target market for the product family being considered. A target-market mismatch produces a decline or refer verdict, not a silent accept. |

Suitability evidence in the strict COBS sense applies to advised investment
business and is not a UC1 concept. UC1 is non-advised general insurance
distribution; the equivalent evidence shape is the demands-and-needs
statement plus the qualification rationale, both of which the decision-trail
port captures.

## Safe Refs And Identifier Shape

The workflow uses opaque, audit-safe identifiers. Personal data is held on
the enquiry record under separate access controls; the references below are
the shape that crosses ports.

| Ref | Shape | Notes |
|---|---|---|
| `enquiry-ref` | UUID. | Identifies the inbound enquiry from the moment the intake port accepts it. |
| `customer-ref` | UUID. | Pseudonymous identifier for the customer. Maps to the enquiry's customer profile inside the customer-profile store. Does not leave the broker firm's boundary. |
| `applicant-ref` | UUID. | Used when an enquiry has joint applicants. One enquiry, two or more applicants. |
| `product-family-ref` | Slug. | One of `motor`, `home`, `travel`, `pet`, `other`. |
| `decision-ref` | UUID. | Identifies a single agent decision (classification, demands-and-needs, qualification, routing). Used to join decision-trail records to transcript records. |
| `verdict-ref` | UUID. | Identifies the qualification verdict (accept / refer / decline). One per enquiry; carries the policy snapshot reference. |
| `referral-ref` | UUID. | Identifies a referral routed to the senior underwriter inbox. Only present when the verdict was `refer`. |
| `policy-snapshot-ref` | Content-addressed hash. | Identifies the policy bundle (route catalogue, prompts, grants, modes, target-market rules) that was active when the decision was made. |
| `transcript-ref` | UUID. | Identifies the full-fidelity transcript record for the LLM invocation that produced the decision. |

The shape of `customer-ref`, `applicant-ref`, and the contents of the
customer-profile store are deliberately abstracted at the contract layer.
Adapters that need personal data receive it through the customer-profile
adapter inside the broker firm's boundary, not over the wire.

## Local Demo Scope And Synthetic Data Plan

The UC1 demo runs entirely on local synthetic data and local sandbox
connectors. No live broker platform, no real customer data, no third-party
credentials.

| Aspect | Plan |
|---|---|
| Synthetic enquiries | About 30 enquiries authored in repo under `fixtures/uc1/`. Mix of motor, home, travel, and pet. Mix of single and joint applicants. Mix of risk levels (clean, marginal, declinable). Mix of completeness (full, missing rating data, missing previous-claims data, missing modifications). Mix of target-market fit (in-market, edge of market, out of market). |
| Channel distribution | Roughly one third each across email, web form, and partner portal so each intake adapter is exercised. |
| Vulnerability markers | A subset of enquiries carries explicit Consumer Duty vulnerability markers (financial difficulty, recent bereavement, communication preference adjustments) so the compliance projection has data to aggregate. |
| Connector sandboxes | Local sandbox CRM adapter, sandbox underwriter referral inbox, sandbox decline ledger, sandbox outbound customer comms (gated). Mailpit-style local mail capture for the missing-data request. |
| Provider routes | Dev route DeepSeek `deepseek-v4-flash` through the LLM provider port, demo / eval canonical route OpenAI `gpt-5.4-mini-2026-03-17`. Both routes are captured in the route catalogue; active seeded runtime routing remains local recorded replay until P3 live-provider gates pass. |
| Replay corpus | The ~30 enquiries plus their captured transcripts seed the cross-provider replay eval substrate. Replay-as-comparison is exercised between the dev and canonical routes. |

## Out Of Scope

The following are explicitly out of scope for UC1.

- Pricing or rating. The workflow stops at qualification + referral routing.
- Quote issuance and binding.
- Quote acceptance and policy administration.
- Renewals.
- Claims.
- Real-world broker platform integration (Acturis, Open GI, SSP, Insurly).
  These platforms may be modelled as adapter-contract sketches in later
  phases; UC1 uses local sandboxes only.
- Telephony intake. Candidate for a later phase.
- Live customer data. UC1 is synthetic-data-only.
- Production hosting. Deployment is out of the Chorus repo entirely.

## R1 Open Questions

None deferred. All R1 product questions were settled in the 2026-05-19
session. The following items are explicitly carried forward as known
work for R2 / R3 rather than open product questions:

- Exact ICOBS, COBS, PROD, and Consumer Duty citation numbers used inside
  the policy bundle. Currently noted as pending verification; will be
  verified during the R3 contract terminology refactor before any policy
  snapshot ships in code.
- Whether the underwriter referral inbox in the demo is a separate sandbox
  adapter from the standard quoting queue, or a tagged subscription on the
  same adapter. To be resolved during the R3 connector adapter registry
  work.
- The exact shape of the customer-profile store boundary (how the
  customer-profile adapter exposes data inside the firm boundary without
  it crossing the contract surface). To be resolved during the R3
  contract refactor.

---
type: project-doc
status: active
date: 2026-05-25
phase: R4
use_case: UC3
---

# Product Brief - UK Independent Financial Advice Suitability Intake

This brief is the R4 product description for use case 3. It is written for a
reviewer who has not read the reset bundle. Adapter-level deltas sit in
`r1-adapter-mapping.md`; the domain language sits in
`domain-model-uc3.md`.

## Use Case Statement

A UK FCA-authorised independent financial advice firm receives inbound retail
investment advice enquiries through a web enquiry form, email, and introducer
referrals from accountants, solicitors, mortgage brokers, or other professional
contacts. Each enquiry must establish the prospective retail client's advice
need, service scope, investment objectives, financial situation, knowledge and
experience, attitude to risk, capacity for loss, vulnerability indicators, and
product-governance fit before any personal recommendation can be communicated.

Chorus models the enquiry-to-suitability workflow with agent-proposed
fact-find summaries, risk-profile evidence, capacity-for-loss analysis,
platform and product-universe research, suitability conclusions, and
suitability report drafting. Human approval is required before an attitude to
risk override, a vulnerability-triggered handoff, or a suitability report issue
can move through the Tool Gateway in effect mode.

The workflow proves that the same Chorus six-port architecture can carry the
strictest audit shape in the R4 use-case set without changing the workflow
spine, LLM provider port, Tool Gateway authority boundary, audit / transcript
split, projection sink, or observability sink.

## Market Segment And Positioning

| Aspect | Value |
|---|---|
| Market segment | UK independent financial advice for retail clients considering retail investment products, wrappers, pension accumulation, ISA / GIA investment, retirement planning that does not include safeguarded-benefit transfer advice, and portfolio consolidation. |
| Regulatory regime | FCA retail investment advice and conduct rules: COBS client best interests, adviser charging and advice-service disclosure, COBS 9 suitability, PROD 3 product governance, PRIN 2 / PRIN 2A Consumer Duty, and FCA vulnerability guidance. |
| Firm type | FCA-authorised independent financial advice firm. The firm, advisers, supervisors, compliance function, and investment committee remain accountable for advice, suitability, product research, and customer outcomes. Chorus supplies governed decision support and audit evidence. |
| Product position | Local POC workflow for intake, fact-find completeness, suitability evidence, approval packaging, and report-routing evidence. It is not a regulated advice service, robo-adviser, investment platform, discretionary manager, portfolio-management system, compliance outsource, or financial promotion approval service. |
| Out-of-frame advice areas | Restricted advice, execution-only dealing, targeted support, mortgage advice, general insurance distribution, defined-benefit or safeguarded-benefit pension transfers, pension opt-outs, pension conversion, annuity purchase, drawdown pathway recommendations, high-risk investments, cryptoassets, non-mass-market investments, tax advice, legal advice, custody, trading, and production platform onboarding. |

## Regulatory References Verified

The UC3 conduct hooks below were checked against official FCA sources on
2026-05-24:

| Source | Current UC3 use |
|---|---|
| [FCA Handbook COBS 2.1](https://handbook.fca.org.uk/handbook/cobs2) | COBS 2.1.1R is the client's best interests rule. UC3 uses it as a general invariant for all suitability and product-routing decisions. |
| [FCA Handbook COBS 6](https://handbook.fca.org.uk/handbook/COBS/6/) | COBS 6.1A frames adviser charging for personal recommendations to retail clients. COBS 6.2B frames independent advice, sufficient range, focused independent advice, and disclosure of independent versus restricted advice. |
| [FCA Handbook COBS 9.2](https://handbook.fca.org.uk/handbook/COBS/9/2.html) | COBS 9.2.1R-9.2.6R require the firm to obtain necessary information on knowledge and experience, financial situation, and investment objectives; understand essential facts; assess risk-bearing ability; and not make a personal recommendation when necessary information is missing. |
| [FCA Handbook COBS 9](https://handbook.fca.org.uk/handbook/COBS/9.pdf) and [COBS Sch 1 record keeping](https://handbook.fca.org.uk/handbook/cobssch1/cobssch1s1) | UC3 uses COBS 9.4 suitability-report content and COBS 9.5 / COBS Sch 1 suitability record references for report and audit evidence. Later runtime slices must re-check COBS 9A before adding MiFID or insurance-based investment-product advice paths. |
| [FCA Handbook COBS 6.2B / independent advice](https://handbook.fca.org.uk/handbook/COBS/6/) and [FCA MiFID II retail investment advice firms](https://www.fca.org.uk/firms/mifid-ii-retail-investment-advice-firms) | The local POC models independent advice only when the product-universe evidence records a sufficient range of relevant products, type / issuer diversity, platform constraints, and unbiased selection criteria. |
| [FCA Handbook PROD 3](https://handbook.fca.org.uk/handbook/prod3) | PROD 3 product governance requires distributors to understand financial instruments, assess compatibility with client needs and the manufacturer's target market, define target market and distribution strategy, and review distributed products and services. |
| [FCA Handbook PRIN 2](https://handbook.fca.org.uk/handbook/prin2?timeline=true) | Principle 12 requires a firm to act to deliver good outcomes for retail customers; Principles 6, 7, and 9 remain relevant to customer interests, communications, and suitability of advice where applicable. |
| [FCA Handbook PRIN 2A.2](https://handbook.fca.org.uk/handbook/prin2a/prin2as2) and [PRIN 2A](https://www.handbook.fca.org.uk/handbook/PRIN/2A.pdf) | UC3 records Consumer Duty cross-cutting obligations, products and services, price and value, consumer understanding, consumer support, and outcome-monitoring hooks. |
| [FCA Handbook PRIN 2A.5](https://handbook.fca.org.uk/handbook/prin2a/prin2as5?timeline=true) | Suitability reports and client communications must support consumer understanding, be clear, fair and not misleading, and be tailored for vulnerability, product complexity, channel, and the firm's role. |
| [FCA FG21/1 vulnerable customers guidance](https://www.fca.org.uk/publications/finalised-guidance/guidance-firms-fair-treatment-vulnerable-customers) | UC3 uses vulnerability indicators as escalation and support hooks. The local POC records safe vulnerability markers, support needs, and outcome-monitoring refs, not raw sensitive details across ports. |
| [FCA Handbook glossary: retail investment product](https://handbook.fca.org.uk/glossary/G2763), [retail investment activity](https://handbook.fca.org.uk/glossary/G1375), [independent advice](https://handbook.fca.org.uk/glossary/G2761), and [PERG 13.3 personal recommendation](https://handbook.fca.org.uk/handbook/PERG/13/3.html) | These sources anchor the regulated language. UC3 uses "personal recommendation" only for the FCA concept and uses "suitability conclusion" for agent-proposed analysis. |

The regulatory references are conduct hooks for the local POC. They are not
financial advice and do not make Chorus a compliance authority.

## Roles

| Role | Description |
|---|---|
| Prospective retail client | Natural person seeking independent financial advice. The person is represented across ports by safe refs until the sandbox suitability-report store owns the detailed file. |
| Existing retail client | A retail client already known to the synthetic advice firm who sends a new advice enquiry. Existing-client status may affect fact-find freshness and ongoing-service context, but the same suitability controls apply. |
| Joint applicant / household member | Spouse, civil partner, dependant, attorney, or other household member relevant to objectives, affordability, capacity for loss, or vulnerability support. |
| Introducer | Accountant, solicitor, mortgage broker, employer-benefits contact, or other professional referrer. An introducer may supply context but cannot stand in for the firm's suitability assessment. |
| Financial adviser | Regulated adviser accountable for the personal recommendation, suitability report, risk-profile confirmation, and final client communication. |
| Paraplanner | Drafts or reviews suitability report evidence in the manual baseline. In UC3 projections, this role consumes fact-find, research, and report-draft queues. |
| Supervisor / compliance reviewer | Reviews suitability evidence, advice-service scope, vulnerable-customer treatment, report quality, and Consumer Duty outcome evidence. |
| Investment committee / research owner | Owns the approved product universe, platform due diligence, target-market evidence, and PROD review inputs in the sandbox. |
| Vulnerability support reviewer | Adviser or support role that reviews vulnerability-triggered handoff, communication adjustments, third-party authority, or support needs. |
| Chorus runtime | The system performing intake normalisation, fact-find summarisation, suitability reasoning, approval package creation, and routing through the named ports. |

## Inbound Channels In Scope

| Channel | Shape |
|---|---|
| Web advice enquiry form | Structured acquisition form for prospective advice clients. Includes contact details, broad advice need, assets and pension hints, objectives, time horizon, risk preference, vulnerability / support flags, consent flags, and upload refs. |
| Email | Free-text inbound enquiry to the advice firm's mailbox. May include fact-find notes, pension statements, investment platform screenshots, portfolio summaries, cash-flow concerns, or a request for a review. |
| Introducer referral | Referral from an accountant, solicitor, mortgage broker, employer-benefits contact, or other professional contact. Usually includes introducer details, referral narrative, advice need, household context, assets under consideration, and uploaded documents. |

Telephony notes, open-banking feeds, live platform data, production CRM, live
investment-research systems, real provider due-diligence feeds, client-portal
authentication, e-signature, payment, custody, dealing, and ongoing service
review are out of scope for UC3 R4.

## Process Pain In The Current Manual Workflow

The workflow targets the control-heavy work before an adviser can send a
suitability report:

- Fact-finds arrive through mixed channels and are often incomplete. Missing
  objectives, income, expenditure, liabilities, time horizon, pension context,
  or dependants can make a personal recommendation unsafe.
- Attitude-to-risk tools produce labels, but advisers must reconcile the
  label with narrative evidence, investment experience, loss tolerance,
  capacity for loss, and stated objectives.
- Capacity-for-loss analysis is often spread across cash-flow notes,
  spreadsheets, and adviser rationale. The decision moment is hard to inspect
  later.
- Independent advice requires evidence that the product universe was broad,
  diverse, unbiased, and suitable for the client's objectives, not merely a
  platform shortlist.
- PROD target-market evidence, product complexity, costs, charges, and
  distribution strategy can be disconnected from the suitability rationale.
- Vulnerability and communication adjustments are sometimes noted outside the
  advice file, making Consumer Duty outcome evidence uneven.
- Suitability reports can explain a conclusion but fail to show which inputs
  were missing, stale, contradicted, or overridden.

The result is advice pre-work that is high-friction, uneven across advisers,
and expensive to review as a controlled evidence trail.

## Proposed Chorus-Assisted Workflow

The workflow reuses the shared spine: intake, classification, context
gathering, proposed action, approval where required, routing, and closure.

| Step | Description |
|---|---|
| Intake | The intake port receives the web form, email, or introducer referral. The adapter contract-validates the payload and creates a normalised `AdviceEnquiry` record with channel provenance and idempotency. |
| Service-scope classification | The LLM provider port classifies the enquiry as independent advice in scope, information-only, restricted-advice-out-of-scope, targeted-support-out-of-scope, execution-only request, or manual review. |
| Fact-find summary and gap analysis | The LLM provider port produces a structured fact-find summary: objectives, time horizon, financial situation, knowledge and experience, existing products, dependants, liquidity needs, tax wrapper hints, support needs, and missing or stale facts. Missing necessary information blocks a suitability conclusion. |
| Risk and loss analysis | The connector port invokes `sandbox-attitude-to-risk-profiler` and `sandbox-capacity-for-loss-tool` through the Tool Gateway. The agent compares tool outputs with narrative evidence and flags mismatches for adviser approval. |
| Product-universe and platform research | The connector port invokes `sandbox-platform-research` through the Tool Gateway. The result records product-universe coverage, target-market compatibility, costs, charges, complexity, platform constraints, and evidence that the independent advice universe was sufficiently broad for the service scope. |
| Suitability conclusion | The LLM provider port produces a structured suitability conclusion: suitable subject to adviser approval, unsuitable, insufficient information, or manual review. The conclusion records COBS, PROD, Consumer Duty, vulnerability, policy snapshot, transcript, and connector verdict refs. |
| Approval packaging | The Tool Gateway creates generic approval packages for attitude-to-risk override, vulnerability handoff, and suitability report issue. Approval does not execute a connector by itself; approved packages must re-enter the Tool Gateway apply path. |
| Suitability report routing | The connector port writes draft, approval, and issue records to `sandbox-suitability-report-store`. The R4 local POC stores synthetic report text and safe refs; it does not send real customer communications or place trades. |

The workflow stops at suitability report routing. Product purchase,
platform onboarding, order placement, ongoing review, client money, custody,
and real advice delivery are out of scope.

## Agent-Proposed Vs Human-Approved Decisions

| Decision | Agent proposes | Human approval gate |
|---|---|---|
| Advice-service scope | Yes. | None for clean in-scope classification. Restricted, targeted-support, execution-only, high-risk-investment, or pension-transfer indicators route to manual review. |
| Fact-find completeness | Yes. | None for clean summaries. Missing necessary information blocks suitability and routes to adviser enrichment. |
| Attitude-to-risk band | Yes, using the profiler connector and narrative comparison. | Required when the inferred band, tool band, and stated preference disagree materially, or when the client appears to understate risk. |
| Capacity for loss | Yes, using the capacity-for-loss connector. | Required when the result is limited, negative, inconsistent with objectives, or vulnerable-customer support is implicated. |
| Vulnerability and support needs | Yes. | Required when vulnerability markers, third-party authority, communication adjustment, financial difficulty, bereavement, cognitive impairment, or low capability could affect the advice journey. |
| Product-universe research | Yes. | None for clean evidence. Narrow universe, platform bias, missing target-market data, cost / value concern, or complex product route to adviser or investment committee review. |
| Suitability conclusion | Yes. | Required. No personal recommendation or suitability report issue can be marked approved without an authorised financial adviser. |
| Suitability report issue | Yes. | Required. The report issue is the customer-impact action and must be approved and applied through the Tool Gateway. |

UC3 deliberately has more gates than UC1. The local POC allows agent-proposed
analysis, but a personal recommendation and the communication of a suitability
report remain adviser-approved actions.

## Conduct Touch Points

The workflow makes each conduct hook visible on the structured decision-trail
port. The policy bundle records source URLs, source effective dates, rule
identifiers, and local policy version refs.

| Conduct hook | Official source | How UC3 surfaces it |
|---|---|---|
| Client's best interests | COBS 2.1.1R and PRIN 2 Principles 6, 7, 9, and 12. | Every suitability conclusion records why the proposed outcome is consistent with the client's interests, information needs, and ability to rely on the firm's judgement. |
| Independent advice and sufficient range | COBS 6.2B.11R, 6.2B.15R-6.2B.19G, and the FCA retail investment advice page. | No independent-advice conclusion can be approved without product-universe coverage, diversity, bias, platform constraint, and selection-process refs. |
| Necessary information for suitability | COBS 9.2.1R-9.2.6R. | No positive suitability conclusion can be recorded unless objectives, time horizon, risk preference, risk profile, financial situation, income, assets, commitments, knowledge, experience, and missing-data status are all evidenced. |
| Suitability report evidence | COBS 9.4 and suitability-report guidance in COBS 9. | No report issue can occur unless the report ref explains the demands and needs, why the recommendation is suitable, and possible disadvantages. |
| Suitability record retention | COBS 9.5 and COBS Sch 1. | Fact-find refs, risk refs, research refs, suitability conclusion refs, report refs, approval refs, decision refs, and transcript refs must exist before closure. |
| Product governance and target market | PROD 3, especially distributor understanding, target-market, distribution-strategy, and review obligations. | Product research records must include target-market compatibility, negative-target-market flags, cost / charge evidence, complexity, manufacturer information refs, and product-review refs. |
| Consumer Duty cross-cutting rules | PRIN 2A.2. | The decision trail records good-faith, foreseeable-harm, and enable-and-support checks for the proposed advice journey. |
| Consumer Duty outcomes | PRIN 2A.3-2A.7 and PRIN 2A.9. | The workflow records product / service fit, price / value, consumer understanding, consumer support, expected standards, and outcome-monitoring refs. |
| Vulnerable customers | PRIN 2A and FCA FG21/1. | Vulnerability markers never appear as raw sensitive text in projections. Support needs, communication adjustments, third-party authority refs, and reviewer decisions are safe structured records. |
| Clear, fair, and not misleading communications | PRIN 2A.5 and COBS communication rules. | Suitability report drafts and client-facing summaries require approval and must include consumer-understanding checks before issue. |

## Connector Inventory

UC3 uses the four R4 local connector adapters named by the architecture and
backlog. They are sandbox connectors behind the Tool Gateway, not production
IFA, platform, research, or advice systems.

| Connector adapter | Mode in R4 | Purpose |
|---|---|---|
| `sandbox-attitude-to-risk-profiler` | Read / propose, effect-free. | Returns a synthetic attitude-to-risk band, questionnaire trace, inconsistency flags, and evidence refs. |
| `sandbox-capacity-for-loss-tool` | Read / calculate, effect-free. | Returns synthetic cash-flow, emergency-reserve, loss-tolerance, income-stability, dependant, and affordability stress results. |
| `sandbox-platform-research` | Read / research, effect-free. | Returns notional product-universe, platform, provider, target-market, costs, charges, complexity, due-diligence, and independent-advice range evidence. |
| `sandbox-suitability-report-store` | Approval-gated write. | Stores report drafts, adviser approval refs, issue refs, suitability conclusion refs, client-understanding checks, decline / manual-review refs, and safe report metadata. |

Vulnerability assessment is an intake, reasoning, approval, and projection
concern in R4, not a fifth connector adapter. The older R1 sketch that
mentioned a separate vulnerability helper is superseded by the R4 connector
inventory above unless a later backlog decision changes it.

## Field Placement Across Ports

| Field group | Port placement |
|---|---|
| Raw web form payload, raw email body, introducer bundle, uploaded statements, fact-find attachments | Intake adapter storage only, referenced by `source-payload-ref` and attachment digests. Not projected by default. |
| Normalised advice need, channel, advice-scope classification, safe client refs, state, fact-find completeness | Domain lifecycle record and projection sink. Safe for read-only inspection. |
| Full client names, addresses, dates of birth, National Insurance numbers, pension policy numbers, platform account numbers, detailed assets, liabilities, income, expenditure, and health information | Held inside intake or connector-owned synthetic stores. Cross-port payloads use safe refs and summaries. |
| Attitude-to-risk questionnaire answers and scoring detail | Owned by `sandbox-attitude-to-risk-profiler`; decision trail stores band, confidence, mismatch flags, and safe evidence refs. |
| Capacity-for-loss working data | Owned by `sandbox-capacity-for-loss-tool`; decision trail stores status, stress outcome, affordability flags, and safe evidence refs. |
| Platform and product research | Owned by `sandbox-platform-research`; decision trail stores product-universe refs, target-market compatibility, cost / complexity summaries, and safe research refs. |
| Suitability report text | Draft and issued synthetic report body are held by `sandbox-suitability-report-store`; projections show report ref, approval state, issue state, and safe summary. |
| Vulnerability details | Raw sensitive details stay behind intake or adviser-support storage. Projections and audit carry marker category, support need, communication adjustment ref, and reviewer state only. |
| LLM prompts and responses | Transcript port stores full-fidelity invocation records for replay. Decision-trail port stores structured summaries and refs. |
| Telemetry | Observability sink carries correlation IDs, spans, timings, and safe labels only. It must not carry raw client, household, health, financial, product account, or suitability report content. |

## Local Demo Scope And Synthetic Data Plan

The UC3 local POC uses synthetic advice enquiries only.

| Aspect | Plan |
|---|---|
| Synthetic enquiries | About 30 records under a future `fixtures/uc3/` path. Mix of ISA investment, pension consolidation, new regular investment, retirement-income planning excluding drawdown recommendation, portfolio review, cash-versus-investment decision, and inheritance-investment planning. |
| Channel distribution | Roughly one third each across web advice form, email, and introducer referral so each intake adapter can be exercised once implemented. |
| Fact-find variety | Mix of complete fact-find, missing income / expenditure, missing liabilities, stale pension values, inconsistent objectives, uncertain time horizon, low knowledge / experience, joint household context, and attorney / third-party authority scenarios. |
| Risk scenarios | Aligned risk profile, client overstates risk tolerance, client understates loss concern, profiler narrative mismatch, limited capacity for loss, emergency-reserve gap, retirement-income dependency, and high concentration in existing holdings. |
| Consumer Duty scenarios | Communication adjustment, bereavement, financial difficulty, low financial capability, health-related support need, power-of-attorney concern, and no vulnerability marker. |
| Product governance scenarios | In-market product, edge-of-market product, negative target-market flag, high charges, complex product, platform bias, insufficient product universe, and clean independent-advice range evidence. |
| Connector sandboxes | Local synthetic attitude-to-risk profiler, capacity-for-loss tool, platform research store, and suitability-report store. No live platform, provider, investment research, due-diligence, fact-find, CRM, e-signature, dealing, or custody service. |
| Provider routes | Same LLM provider port and route shape as UC1. Live OpenAI / DeepSeek route identifiers were verified in R4, but UC3-specific provider route activation remains deferred. |
| Replay corpus | The synthetic corpus plus captured transcripts seed UC3 invariant and replay evaluation once local intake, provider route activation, and fixture playback exist. Replay compares regulated outcome equivalence, not exact prose equality. |

## Failure And Escalation Paths

| Failure / escalation | Trigger | Path |
|---|---|---|
| Malformed intake | Channel payload fails contract validation or required provenance is missing. | Reject at intake port. Record contract violation; no workflow start. |
| Advice scope out of frame | Restricted advice, execution-only, targeted support, mortgage, insurance, pension transfer, high-risk investment, cryptoasset, tax, legal, or platform-only request is detected. | Route to manual review or decline advice service; no suitability conclusion. |
| Client identity or authority unclear | The workflow cannot determine the prospective retail client, joint applicant, attorney, introducer authority, or existing-client match. | `manual_review`; no personal recommendation or report issue. |
| Necessary information missing | Objectives, financial situation, knowledge / experience, time horizon, risk profile, capacity for loss, or dependency information is absent, stale, or contradicted. | `fact_find_incomplete`; adviser enrichment required; suitability conclusion blocked. |
| Attitude-to-risk mismatch | Profiler output conflicts with stated preference, behaviour, experience, or narrative evidence. | Create adviser approval package or route to manual review; no final suitability conclusion until resolved. |
| Capacity-for-loss concern | Loss tolerance is limited, emergency reserves are inadequate, retirement income is at risk, or household dependency is unresolved. | Adviser approval, redress of objective, or manual review; suitability may be recorded as unsuitable. |
| Vulnerability marker | Support need, communication adjustment, low capability, financial difficulty, health concern, bereavement, attorney issue, or third-party authority concern appears. | Create vulnerability handoff approval package or support review; report issue waits if support affects understanding or consent. |
| Product-universe defect | Platform research is too narrow, biased, stale, missing target-market data, or cannot evidence sufficient range. | Route to investment committee / adviser review; no independent-advice conclusion. |
| PROD mismatch | Product candidate is outside target market, negative target market, too complex, or cost / value evidence is deficient. | Force unsuitable or manual review; no report issue. |
| Suitability report rejected | Adviser rejects report draft, rationale, risk disclosure, disadvantage explanation, or communication adjustment. | Return to suitability assessment / drafting with redraft refs. |
| Connector failure | Any sandbox connector returns error or idempotency conflict. | Workflow enters failed connector state; projection shows exception queue; audit captures gateway verdict and connector error ref. |
| Provider or schema failure | LLM provider route unavailable or structured output invalid. | Workflow enters failed reasoning state for that step; no downstream connector action is applied. |

## R4 Boundaries

UC3 R4 is deliberately local and bounded:

- no production client, household, financial, health, pension, investment, or
  vulnerability data;
- no production IFA CRM, fact-find, investment platform, provider, due
  diligence, portfolio analytics, e-signature, custody, dealing, or advice
  delivery integration;
- no real personal recommendations, regulated advice service, financial
  promotion approval, discretionary management, order placement, platform
  onboarding, client-money handling, or ongoing review;
- no claim that a channel is runnable until the channel contract, local
  fixture or sandbox injection path, normalisation, provenance, idempotency,
  and workflow-start handoff are evidenced;
- R4 closes with UC3 contracts, a shared-spine workflow definition,
  deterministic sandbox connector adapters, Tool Gateway grants,
  `suitability_report.issue` approval-package evidence, conduct invariants,
  read-only inspection, and schema-only fixture evidence; it does not claim
  UC3 use-case runnable status until local intake start, UC3 provider route
  activation, and full fixture playback are added;
- COBS 9A, COBS 19, pension transfer, pension conversion, pension opt-out,
  insurance-based investment product, and drawdown-specific advice paths are
  out of local POC runtime scope unless a later R4 decision explicitly adds
  them with fresh official-source verification.

## Out Of Scope

The following are explicitly out of scope for UC3:

- regulated advice delivery or customer reliance on a Chorus-generated
  personal recommendation;
- restricted advice, targeted support, execution-only service, generic
  guidance journey, or robo-advice product;
- defined-benefit or safeguarded-benefit pension transfers, pension opt-outs,
  pension conversions, annuity purchase, pension drawdown recommendation, or
  insistent-client execution;
- high-risk investments, non-mass-market investments, cryptoassets,
  peer-to-peer agreements, structured products requiring specialist treatment,
  tax wrappers beyond synthetic evidence, or tax / legal advice;
- live platform research, product provider due diligence, platform account
  creation, trading, custody, client-money, billing, or ongoing review;
- production retention, deletion, data subject request, legal hold, complaint,
  or redress implementation;
- replacing the financial adviser, supervisor, investment committee,
  compliance function, or firm accountability.

## Open Questions

None for this product brief. R4 closure exceptions for UC3 are local intake
start, UC3 provider route activation, full fixture playback, and exact
connector-bound approval packages for risk-profile override and vulnerability
handoff paths.

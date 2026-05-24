---
type: project-doc
status: active
date: 2026-05-24
phase: R4
use_case: UC2
---

# Product Brief - UK Legal Services Intake And Conflict Check

This brief is the R4 product description for use case 2. It is written for a
reviewer who has not read the reset bundle. Adapter-level deltas sit in
`r1-adapter-mapping.md`; the domain language sits in
`domain-model-uc2.md`.

## Use Case Statement

A UK SRA-regulated corporate and commercial legal practice receives inbound
prospective matters by email, a structured corporate intake form, and
intermediary referral. Each intake must identify the prospective client,
the instructing contact, relevant corporate parties, beneficial owners,
counterparties, affiliates, and matter scope before the firm can decide
whether to act. Chorus models the intake-to-engagement workflow with
agent-proposed party extraction, conflict determination, AML risk assessment,
and engagement routing, with human approval on high-impact legal and AML
boundaries.

The workflow proves that the same Chorus six-port architecture can carry a
multi-party SRA and AML use case without changing the workflow spine, LLM
provider port, Tool Gateway authority boundary, audit / transcript split,
projection sink, or observability sink.

## Market Segment And Positioning

| Aspect | Value |
|---|---|
| Market segment | UK corporate and commercial legal services: commercial transactions, contract advisory, shareholder or partnership matters, and commercial disputes at intake stage. |
| Regulatory regime | SRA Standards and Regulations, SRA Code of Conduct conflict / confidentiality / accountability duties, and UK AML obligations under the Money Laundering Regulations 2017 where the matter is in scope. |
| Firm type | SRA-authorised law firm. The firm, partners, solicitors, COLP, and MLRO remain accountable for legal and AML decisions. Chorus supplies governed decision support and audit evidence. |
| Product position | Local POC workflow for intake, conflict check, AML screening, and engagement decision evidence. It is not a legal advice product, conflict database product, AML managed service, or matter management system. |
| Out-of-frame practice areas | Private client, conveyancing, employment tribunal casework, criminal defence, family, immigration, and reserved litigation conduct beyond intake triage. Those could reuse the same ports later but are not UC2. |

## Regulatory References Verified

The UC2 conduct hooks below were checked against official sources on
2026-05-24:

| Source | Current UC2 use |
|---|---|
| [SRA Principles](https://www.sra.org.uk/solicitors/standards-regulations/principles/) | Current version in effect from 11 April 2025. UC2 uses Principles 2, 4, 5, and 7 for public trust, honesty, integrity, and each client's best interests. |
| [SRA Code of Conduct for Solicitors, RELs, RFLs and RSLs](https://www.sra.org.uk/solicitors/standards-regulations/code-conduct-solicitors/) | Current version in effect from 11 April 2025. UC2 uses paragraphs 3.1-3.6 for service / competence, 6.1-6.2 for conflicts, 6.3-6.5 for confidentiality and disclosure, 7.1-7.2 for legal/regulatory compliance and decision justification, and 8.1 for identifying who the firm acts for. |
| [SRA Code of Conduct for Firms](https://www.sra.org.uk/solicitors/standards-regulations/code-conduct-firms/) | Current firm-level system and supervision obligations. UC2 uses this for governance, controls, and supervision evidence. |
| [SRA Your AML obligations](https://www.sra.org.uk/solicitors/resources/money-laundering/guidance-support/) | Updated 18 February 2026. The page identifies the 2025 Legal Sector Affinity Group guidance as official guidance for SRA-supervised firms, approved by HM Treasury and effective from 23 April 2025. |
| [SRA Sectoral Risk Assessment - AML and terrorist financing](https://www.sra.org.uk/sra/research-publications/aml-risk-assessment/) | Published 31 July 2025. UC2 uses it as a source for sector risk inputs, intermediary risk, anonymity / beneficial-owner risk, and firm-wide risk-assessment context. |
| [GOV.UK National Risk Assessment of Money Laundering and Terrorist Financing 2025](https://www.gov.uk/government/publications/national-risk-assessment-of-money-laundering-and-terrorist-financing-2025) | Published by HM Treasury on 17 July 2025. UC2 uses it as national AML / CTF risk context. |
| [Money Laundering Regulations 2017](https://www.legislation.gov.uk/uksi/2017/692/pdfs/uksi_20170692_en.pdf) | UC2 cites regulations 18 and 19 for risk assessment and policies / controls, 27 and 28 for CDD trigger and measures, 33 for enhanced due diligence and ongoing monitoring, and 40 for record keeping. |

The regulatory references are conduct hooks for the local POC. They are not
legal advice and do not make Chorus a compliance authority.

## Roles

| Role | Description |
|---|---|
| Prospective client | The entity or person seeking to instruct the firm. In UC2 this is normally a corporate entity, partnership, LLP, fund, or other organisation. It is not called a client until the engagement decision is accepted and the engagement letter is issued. |
| Instructing contact | The natural person submitting the intake or authorised to provide instructions for the prospective client. They may be a director, employee, company secretary, partner, or external adviser. |
| Beneficial owner / controller | A person with ownership or control over a corporate prospective client, represented by safe refs and beneficial-ownership summaries rather than raw identity data across ports. |
| Counterparty / adverse party | A party whose interests may be adverse to the prospective client or material to a conflict check. |
| Affiliate / related party | Parent, subsidiary, group company, shareholder, director, investor, fund vehicle, joint venture party, or connected person that can affect conflict and AML risk. |
| Intermediary / referrer | Introducer firm or professional adviser who sends a referral bundle. A trusted referrer does not remove the need for CDD, conflict, or AML checks. |
| Matter owner | Solicitor or practice-area lead who would own the matter if accepted. Reviews exceptions and engagement evidence. |
| Partner approver | Authorised partner who can approve a permitted conflict-exception path where the SRA rules allow acting and the required safeguards are evidenced. Cannot approve an own-interest conflict or a prohibited client conflict. |
| MLRO / AML compliance | Money Laundering Reporting Officer or delegate who reviews high-risk AML flags, enhanced due diligence, unresolved beneficial ownership, or suspicious-activity escalation. |
| COLP / compliance reviewer | Compliance role consuming decision-trail projections for conduct evidence and SRA accountability. Not normally in the hot path unless a governance failure is escalated. |
| Chorus runtime | The system performing intake normalisation, party extraction, conflict and AML reasoning, approval package creation, and routing through the named ports. |

## Inbound Channels In Scope

| Channel | Shape |
|---|---|
| Email | Free-text inbound email to a corporate / commercial intake mailbox. May include scope descriptions, named parties, Companies House numbers, cap tables, contracts, heads of terms, or previous correspondence. |
| Corporate intake form | Structured website form for prospective matters. Includes matter type, prospective-client details, instructing contact, known counterparties, related parties, jurisdiction, estimated value, urgency, and uploaded documents. |
| Intermediary referral | Referral from an accountant, corporate finance adviser, overseas law firm, introducer, or other professional intermediary. Usually includes an introducer email, referral narrative, known parties, and sometimes a draft engagement letter or draft scope. |

Telephony intake, production portal integration, Companies House live lookup,
OFSI sanctions screening, payment handling, SAR / DAML submission, and live
matter management integration are out of scope for UC2 R4.

## Process Pain In The Current Manual Workflow

The workflow targets the control-heavy intake work that happens before a firm
can safely accept a corporate or commercial matter:

- Inbound narratives contain many parties and roles. Manual extraction of
  corporate groups, beneficial owners, counterparties, and affiliates is slow
  and easy to miss.
- Conflict checks depend on the quality of party names, aliases, former names,
  group relationships, and matter scope. Weak intake records cause false
  negatives and repeated manual searches.
- Confidentiality and disclosure risks are not always visible in a flat
  conflict-search result. A current or former client relationship may create a
  material-information issue even where the matter is not a direct conflict.
- AML risk assessment is fragmented across email, ID checks, matter notes,
  beneficial-ownership evidence, and source-of-funds summaries.
- Engagement letters often reuse templates without a precise audit trail of
  who the firm acts for, what the firm will do, what is excluded, and which
  conflict / AML gates were cleared before send.
- Compliance evidence is reconstructed later from matter notes. The decision
  moment and the regulatory source in force at that time are not always
  visible.

The result is intake work that is high-friction, uneven across matter owners,
and hard to review as a controlled decision trail.

## Proposed Chorus-Assisted Workflow

The workflow reuses the shared spine: intake, classification, context
gathering, proposed action, approval where required, routing, and closure.

| Step | Description |
|---|---|
| Intake | The intake port receives the inbound artefact from email, the corporate intake form, or intermediary referral. The adapter contract-validates the payload and creates a normalised `LegalIntake` record with channel provenance and idempotency. |
| Matter classification | The LLM provider port classifies the intake into a corporate / commercial matter type and extracts the proposed scope, urgency, jurisdictions, and engagement boundary candidates. |
| Party graph extraction | The LLM provider port proposes the prospective client, instructing contact, counterparties, affiliates, beneficial owners, controllers, and relationship edges. Ambiguous identity or authority moves the intake to manual review. |
| Conflict and confidentiality screen | The connector port invokes `sandbox-conflict-check` through the Tool Gateway. The agent reasons over the result to produce a conflict determination, confidentiality risk, and allowed / blocked / exception-candidate path. |
| KYC, beneficial ownership, and AML screen | The connector port invokes `sandbox-kyc-bo` and `sandbox-aml-record-store`. The agent proposes CDD completeness, beneficial-ownership status, AML risk rating, source-of-funds / source-of-wealth summary where relevant, and any enhanced-due-diligence requirement. |
| Engagement decision | The LLM provider port produces a structured engagement decision: `accept_for_engagement`, `accept_subject_to_approval`, `decline_to_act`, or `manual_review`. The decision records SRA and AML conduct hooks, policy snapshot ref, decision refs, and connector verdict refs. |
| Approval packaging | The Tool Gateway creates generic approval packages for engagement-letter send, permitted conflict exceptions, and AML enhanced-due-diligence flags. Approval does not execute a connector by itself; approved packages must re-enter the Tool Gateway apply path. |
| Engagement routing | The connector port writes to `sandbox-engagement-letter-store` for approved engagement letters, records decline / manual-review outcomes, and keeps AML and conflict records linked by safe refs. |

The workflow stops at engagement routing. Substantive legal advice, matter
execution, billing, client-account handling, SAR / DAML submission, and
production document management are out of scope.

## Agent-Proposed Vs Human-Approved Decisions

| Decision | Agent proposes | Human approval gate |
|---|---|---|
| Matter classification | Yes. | None. The classification rationale is audited and can be corrected through manual review if clearly wrong. |
| Party graph and role extraction | Yes. | None for clean extraction. Ambiguous identity, authority, or party role escalates to manual review before conflict / AML results can support acceptance. |
| Conflict determination | Yes. | Own-interest conflicts and prohibited conflicts block acceptance. A permitted exception candidate under SRA conflict rules requires partner approval with written-consent and safeguards refs before any acceptance path. |
| Confidentiality / disclosure risk | Yes. | A material confidentiality risk blocks auto-acceptance. A no-real-risk safeguard path or informed-consent path requires partner approval and evidence refs. |
| CDD and beneficial-ownership status | Yes. | None for complete standard-risk CDD. Unresolved beneficial ownership, identity gaps, or third-party reliance concerns escalate to AML compliance review. |
| AML risk rating and enhanced-due-diligence flag | Yes. | Enhanced due diligence, high-risk jurisdiction, PEP / sanctions-adjacent risk, or suspicious indicators require MLRO / AML compliance approval or manual escalation. |
| Engagement decision | Yes. | Acceptance with no conflict / AML exceptions can route internally. Acceptance subject to conflict or AML exception waits for the relevant approval package. |
| Engagement letter send | Yes. | Required. No engagement letter can be sent or marked sent without authorised matter-owner or partner approval and Tool Gateway apply. |

The deliberate position is narrower than UC1: UC2 allows agent-proposed
internal analysis, but high-impact boundaries require human approval because
accepting a conflicted matter, mishandling confidential information, or
advancing a high-risk AML matter has direct regulatory impact.

## Conduct Touch Points

The workflow makes each conduct hook visible on the structured decision-trail
port. The policy bundle records source URLs, source effective dates, rule
identifiers, and local policy version refs.

| Conduct hook | Official source | How UC2 surfaces it |
|---|---|---|
| Act in each client's best interests | SRA Principles, especially Principle 7, with wider-public-interest precedence where principles conflict. | Engagement decisions record the prospective client identity, scope, interests considered, and why acceptance / decline / review is consistent with the firm's duties. |
| Public trust, honesty, and integrity | SRA Principles 2, 4, and 5. | The decision trail records whether intake facts are uncertain, whether the proposed scope could mislead the prospective client, and whether a manual route is required. |
| Identify who the firm acts for | SRA Code of Conduct for Solicitors 8.1 and service / instruction duties in section 3. | No engagement decision can be `accept_for_engagement` without a prospective-client ref, instructing-contact ref, authority status, and matter-scope summary. |
| Conflict of interests | SRA Code of Conduct for Solicitors and Firms 6.1-6.2. | Own-interest conflict blocks acceptance. Client conflict blocks acceptance unless the allowed exception basis, written informed-consent refs, safeguards, and partner approval are all present. |
| Confidentiality and disclosure | SRA Code of Conduct for Solicitors and Firms 6.3-6.5. | Conflict results never expose raw confidential information through projections. Confidentiality risk requires safeguard / consent evidence or blocks acceptance. |
| Accountability and justification | SRA Code of Conduct for Solicitors 7.1-7.2 and Code of Conduct for Firms governance duties. | Every material decision records `decision_ref`, `policy_snapshot_ref`, `transcript_ref`, connector verdict refs, and a structured rationale. |
| Firm AML risk assessment and controls | Money Laundering Regulations 2017 regulations 18 and 19, SRA AML obligations, and SRA Sectoral Risk Assessment. | AML policy snapshots include the firm risk source refs and sector-risk source date used for the matter. |
| CDD and beneficial ownership | Money Laundering Regulations 2017 regulations 27 and 28, plus official LSAG guidance for SRA-supervised firms. | No acceptance route can complete without CDD status, beneficial-owner status where applicable, reliance basis if used, and record refs. |
| Enhanced due diligence and ongoing monitoring | Money Laundering Regulations 2017 regulation 33 and current high-risk jurisdiction / FATF source refs. | High AML risk or EDD triggers create an MLRO approval package or manual escalation. |
| AML record keeping | Money Laundering Regulations 2017 regulation 40. | AML risk records, CDD evidence refs, beneficial-ownership refs, approval package refs, and engagement decision refs are retained as structured lifecycle records in the local sandbox. |

## Connector Inventory

UC2 uses the four R4 local connector adapters named by the architecture and
backlog. They are sandbox connectors behind the Tool Gateway, not production
legal, AML, or third-party data services.

| Connector adapter | Mode in R4 | Purpose |
|---|---|---|
| `sandbox-conflict-check` | Read / propose, effect-free. | Searches a synthetic existing-client and matter index for current clients, former clients, adverse parties, aliases, related entities, and material confidential-information flags. |
| `sandbox-kyc-bo` | Read / record-safe. | Returns synthetic KYC status, corporate identity, beneficial-ownership snapshot, controller refs, reliance refs, and gaps. |
| `sandbox-aml-record-store` | Record / update via Tool Gateway. | Stores AML risk assessment refs, CDD status refs, EDD requirement refs, source-of-funds / source-of-wealth summaries, and MLRO approval refs. |
| `sandbox-engagement-letter-store` | Approval-gated write. | Stores drafted engagement letters, approval refs, send refs, decline-to-act refs, and manual-review handoff refs. |

The older R1 phrase "sandbox client management system" is treated in R4 as
backing synthetic data behind `sandbox-conflict-check` and
`sandbox-engagement-letter-store`, not as a separate adapter unless a later
backlog slice changes the connector list.

## Field Placement Across Ports

| Field group | Port placement |
|---|---|
| Raw email body, uploaded documents, referral bundle, original form payload | Intake adapter storage only, referenced by `source-payload-ref` and attachment digests. Not projected by default. |
| Normalised matter type, channel, safe party refs, role labels, scope summary, state | Domain lifecycle record and projection sink. Safe for read-only inspection. |
| Full party names, addresses, Companies House numbers, dates of birth, ID evidence, raw beneficial-owner evidence | Held inside connector / sandbox stores. Cross-port payloads use safe refs and summaries. |
| Conflict hits | Connector return contains safe hit refs, role categories, relationship categories, and risk labels. Raw current / former client confidential information stays inside `sandbox-conflict-check`. |
| AML risk factors and CDD status | Decision trail stores risk category, trigger refs, policy refs, and safe evidence refs. Raw identity evidence and documents stay in the AML / KYC stores. |
| Engagement letter text | Draft body is held by `sandbox-engagement-letter-store`; projections show draft ref, approval state, scope summary, and send state. |
| LLM prompts and responses | Transcript port stores full-fidelity invocation records for replay. Decision-trail port stores structured summaries and refs. |
| Telemetry | Observability sink carries correlation IDs, spans, timings, and safe labels only. It must not carry raw client, party, beneficial-owner, conflict, AML, or engagement-letter content. |

## Local Demo Scope And Synthetic Data Plan

The UC2 local POC uses synthetic corporate and commercial intake records only.

| Aspect | Plan |
|---|---|
| Synthetic intakes | About 30 records under a future `fixtures/uc2/` path. Mix of commercial contract review, share purchase support, shareholder dispute intake, supplier dispute, joint venture, and corporate governance advice. |
| Channel distribution | Roughly one third each across email, corporate intake form, and intermediary referral so each intake adapter can be exercised once implemented. |
| Party complexity | Mix of single-company, group-company, overseas parent, private equity, joint venture, repeat counterparty, former-client, current-client, and alias / former-name scenarios. |
| Conflict scenarios | Clean no-hit, false-positive name match, current-client adverse interest, former-client confidential-information risk, own-interest conflict, substantially common interest candidate, and competing-for-same-objective candidate. |
| AML scenarios | Standard-risk CDD complete, beneficial-owner gap, high-risk jurisdiction, PEP / sanctions-adjacent marker, complex ownership chain, source-of-funds ambiguity, and intermediary-reliance ambiguity. |
| Connector sandboxes | Local synthetic conflict index, KYC / beneficial-ownership dataset, AML record store, and engagement-letter store. No live Companies House, SRA, OFSI, credit-reference, document-management, or matter-management service. |
| Provider routes | Same LLM provider port and route shape as UC1. Exact live route identifiers remain blocked by the separate R4 provider verification item. |
| Replay corpus | The synthetic corpus plus captured transcripts seed UC2 invariant and replay evaluation once runtime work begins. Replay compares regulated outcome equivalence, not exact prose equality. |

## Failure And Escalation Paths

| Failure / escalation | Trigger | Path |
|---|---|---|
| Malformed intake | Channel payload fails contract validation or required provenance is missing. | Reject at intake port. Record contract violation; no workflow start. |
| Unclear prospective client or authority | The party graph cannot identify who the firm would act for or whether the instructing contact is authorised. | `manual_review`; no conflict or AML result can support acceptance until corrected. |
| Party graph ambiguity | Key party names, aliases, relationship edges, or beneficial-owner candidates are unresolved. | Request manual enrichment or route to AML / matter-owner review depending on the missing field. |
| Conflict hit | Conflict check returns own-interest conflict, client conflict, confidentiality risk, or unknown high-risk hit. | Own-interest and prohibited conflicts block acceptance. Permitted exception candidates create partner approval packages. Unknown hits route to manual review. |
| Confidentiality safeguard missing | The workflow cannot evidence no real risk of disclosure or written informed consent where required. | Block acceptance or route to partner review; raw confidential information is not exposed in projections. |
| CDD incomplete | Identity, beneficial ownership, controller, or reliance evidence is missing. | Hold in AML review; no engagement letter send. |
| EDD trigger | High-risk AML factor, high-risk jurisdiction, PEP / sanctions-adjacent marker, suspicious indicator, or source-of-funds ambiguity. | Create MLRO approval package or manual escalation. |
| Engagement letter rejected | Matter owner / partner rejects the draft or asks for scope changes. | Return to engagement decision / drafting with redraft instruction. |
| Connector failure | Any sandbox connector returns error or idempotency conflict. | Workflow enters failed connector state; projection shows exception queue; audit captures gateway verdict and connector error ref. |
| Provider or schema failure | LLM provider route unavailable or structured output invalid. | Workflow enters failed reasoning state for that step; no downstream connector action is applied. |

## R4 Boundaries

UC2 R4 is deliberately local and bounded:

- no production client data, party data, identity documents, or confidential
  information;
- no production legal platform, conflict database, Companies House, OFSI,
  credit-reference, e-signature, document-management, or matter-management
  integration;
- no legal advice, regulatory advice, AML managed service, SAR / DAML
  submission, client-money handling, billing, or matter execution;
- no claim that a channel is runnable until the channel contract, local
  fixture or sandbox injection path, normalisation, provenance, idempotency,
  and workflow-start handoff are evidenced;
- no UC2 runtime implementation until the backlog reaches the later UC2
  implementation slice after UC1 completion and provider / replay hardening.

## Out Of Scope

The following are explicitly out of scope for UC2:

- substantive legal advice or document drafting beyond a synthetic engagement
  letter;
- production conflict-check or information-barrier enforcement;
- live identity verification, Companies House lookup, beneficial-owner
  service, sanctions screening, or credit-reference integration;
- client-money receipt, undertakings, escrow, billing, or time recording;
- SAR / DAML reporting workflow;
- production retention, deletion, data subject request, or legal hold
  implementation;
- replacing solicitor, partner, MLRO, COLP, or firm accountability.

## Open Questions

None for this product brief. Runtime implementation remains gated by the R4
backlog order: generalise shared surfaces, complete UC1 broker-firm-side
connector persistence, harden live-provider and replay paths, then implement
UC2 on the shared spine.

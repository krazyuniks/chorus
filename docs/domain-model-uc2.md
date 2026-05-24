---
type: project-doc
status: active
date: 2026-05-24
phase: R4
use_case: UC2
---

# Domain Model - UK Legal Services Intake And Conflict Check

This document is the ubiquitous language for use case 2. It defines the
domain terms, actors, artefacts, commands, events, aggregates, value objects,
state machine, policies, approval points, failure paths, field placement, and
banned terms that UC2 work must use.

Contract shapes here are schema sketches. The actual JSON Schema contracts
arrive in later R4 slices. The sketches are deliberately under-specified at
the field level; what matters here is which payload crosses which named port,
which fields are load-bearing, and which records must stay behind connector
or intake boundaries.

## Glossary

| Term | Definition |
|---|---|
| Legal intake | An inbound prospective matter that has not yet been accepted by the firm. It is the primary unit of work for UC2. |
| Prospective client | The party the firm may act for if the matter is accepted. Usually a corporate entity or organisation. Do not call this party a client until engagement acceptance. |
| Instructing contact | The natural person who submitted the intake or purports to instruct the firm for the prospective client. |
| Matter scope | The bounded description of the legal service requested, including practice area, transaction or dispute type, jurisdictions, counterparties, urgency, and explicit exclusions. |
| Party graph | The structured set of parties and relationship edges relevant to conflict and AML analysis: prospective client, contact, beneficial owners, controllers, counterparties, affiliates, referrers, existing clients, and former clients. |
| Party | A legal or natural person relevant to the intake. Parties are represented across ports by safe `party-ref` values and role labels. |
| Beneficial owner / controller | A natural person or entity with ownership or control relevant to AML CDD. The local POC records safe refs and synthetic evidence summaries only. |
| Counterparty | A party whose interests may be adverse to the prospective client or otherwise material to a conflict check. |
| Conflict determination | The structured result of conflict analysis: no conflict, own-interest conflict, client conflict, permitted exception candidate, confidentiality risk, or manual review. |
| Own-interest conflict | A conflict or significant risk between the firm's own interests and duties to a client. It blocks acceptance in UC2. |
| Permitted conflict exception candidate | A conflict result that may fit the SRA Code 6.2 exceptions for substantially common interest or competing for the same objective, subject to informed written consent, confidentiality safeguards, reasonableness, and partner approval. |
| Confidentiality risk | Risk that acting would expose or misuse material confidential information held for a current or former client. |
| CDD status | Customer due diligence status for the prospective client and relevant persons: complete, incomplete, reliance-pending, enhanced-due-diligence-required, or blocked. |
| AML risk assessment | Matter-level anti-money laundering and terrorist-financing risk assessment. Carries risk factors, source refs, risk rating, EDD triggers, and record refs. |
| Engagement decision | The structured outcome of intake: accept, accept subject to approval, decline to act, or manual review. |
| Engagement letter | The engagement / client care letter draft and send record. In UC2 it is an approval-gated connector action. |
| Approval package | Generic Tool Gateway authority envelope for one exact request requiring human approval before effect mode. |
| Policy snapshot | Immutable bundle of policy source refs, route refs, prompts, grants, approval rules, redaction rules, SRA and AML source versions, and local configuration active when a decision was made. |
| Decision-trail record | Structured audit record for a material decision: who decided what, under which policy, on which safe inputs, with which safe outputs. |
| Transcript record | Full-fidelity LLM invocation record used for engineering replay. Kept separate from the structured decision trail. |

## Actors And Roles

| Actor | Role |
|---|---|
| Prospective client | Seeks to instruct the firm. May become a client only after acceptance and engagement-letter send. |
| Instructing contact | Supplies intake details and authority evidence. May be internal to the prospective client or an external adviser. |
| Counterparty / adverse party | Used by conflict check and engagement-boundary decisions. |
| Beneficial owner / controller | Used by CDD and AML analysis. |
| Intermediary / referrer | Sends a referral bundle. Does not remove the firm's own conflict, CDD, or AML obligations. |
| Matter owner | Solicitor or practice-area lead who owns manual review and engagement-letter approval. |
| Partner approver | Reviews permitted conflict exception candidates and confidentiality safeguard paths. |
| MLRO / AML compliance | Reviews high-risk AML, EDD, unresolved beneficial ownership, source-of-funds ambiguity, and suspicious indicators. |
| COLP / compliance reviewer | Reviews decision-trail projections and governance failures. |
| Chorus runtime | Executes the UC2 workflow through the named ports and records audit / transcript evidence. |

## Inbound Artefacts

Schema sketches only. Actual contracts land in a later R4 contracts slice.

### Email Legal Intake (intake adapter: `email-channel`)

```text
EmailLegalIntake {
  channel: "email"
  received_at: timestamp
  message_id: string
  from: string
  to: list[string]
  subject: string
  body_text: string
  body_html_ref: source-payload-ref optional
  attachments: list[{attachment_ref, name, mime, size, sha256}]
  raw_headers_ref: source-payload-ref
}
```

### Corporate Intake Form (intake adapter: `corporate-intake-form`)

```text
CorporateIntakeForm {
  channel: "corporate-intake-form"
  submitted_at: timestamp
  submission_id: string
  form_version: string
  prospective_client: map
  instructing_contact: map
  matter_type_hint: string optional
  scope_summary: string
  known_parties: list[map]
  jurisdictions: list[string]
  estimated_value_band: string optional
  urgency: string optional
  consent_flags: map
  attachments: list[{attachment_ref, name, mime, size, sha256}]
}
```

### Intermediary Referral (intake adapter: `intermediary-referral-channel`)

```text
IntermediaryReferral {
  channel: "intermediary-referral-channel"
  received_at: timestamp
  referral_id: string
  referrer_ref: intermediary-ref
  referrer_contact: string
  referral_narrative: string
  proposed_scope: string optional
  known_parties: list[map]
  draft_engagement_letter_ref: attachment-ref optional
  attachments: list[{attachment_ref, name, mime, size, sha256}]
}
```

### Normalised Legal Intake (post-intake, domain-side)

```text
LegalIntake {
  legal_intake_ref: uuid
  channel: "email" | "corporate-intake-form" | "intermediary-referral-channel"
  received_at: timestamp
  source_payload_ref: source-payload-ref
  idempotency_key_ref: idempotency-key-ref
  prospective_client_ref: prospective-client-ref optional
  instructing_contact_ref: contact-ref optional
  matter_scope_ref: matter-scope-ref optional
  state: LegalIntakeState
  latest_party_graph_ref: party-graph-ref optional
  latest_conflict_determination_ref: conflict-determination-ref optional
  latest_aml_risk_ref: aml-risk-ref optional
  latest_engagement_decision_ref: engagement-decision-ref optional
}
```

## Commands

Commands are intent-bearing inputs to the workflow. Each command runs through
the named ports and emits domain events.

| Command | Source | Description |
|---|---|---|
| `IntakeLegalMatter` | Intake port. | Accept a channel payload and create a normalised `LegalIntake` record. |
| `ClassifyMatterScope` | Workflow step. | Ask the LLM provider port to classify matter type, scope, jurisdiction, urgency, and proposed engagement boundary. |
| `ExtractPartyGraph` | Workflow step. | Ask the LLM provider port to propose party refs, roles, aliases, relationship edges, and ambiguity flags. |
| `RunConflictCheck` | Workflow step via connector port. | Invoke `sandbox-conflict-check` through the Tool Gateway using safe party refs and search keys. |
| `DetermineConflictPosition` | Workflow step. | Produce the structured conflict determination, confidentiality risk, and exception candidate if any. |
| `RunKycBeneficialOwnershipCheck` | Workflow step via connector port. | Invoke `sandbox-kyc-bo` for synthetic CDD and beneficial-ownership status. |
| `AssessAmlRisk` | Workflow step via connector port. | Record AML risk factors and risk rating in `sandbox-aml-record-store`. |
| `RequestConflictExceptionApproval` | Workflow step. | Create a partner approval package for a permitted exception candidate. |
| `RequestEnhancedDueDiligenceApproval` | Workflow step. | Create an MLRO approval package for high-risk AML or EDD-required matters. |
| `DecideEngagement` | Workflow step. | Produce an engagement decision with conflict, AML, SRA, and audit refs. |
| `DraftEngagementLetter` | Workflow step via connector port. | Create a draft engagement-letter record in `sandbox-engagement-letter-store`. |
| `ApproveEngagementLetter` | Matter owner / partner action. | Approve or reject the exact engagement-letter package. |
| `SendEngagementLetter` | Workflow step via connector port. | Apply the approved package through the Tool Gateway and mark the engagement letter sent in the sandbox. |
| `RouteManualReview` | Workflow step. | Route an intake that cannot be accepted or declined automatically to matter-owner, partner, AML, or compliance review. |
| `DeclineToAct` | Workflow step. | Record a decline-to-act outcome with safe rationale and audit refs. |
| `CloseLegalIntake` | Workflow step. | Close the UC2 intake workflow after routing or terminal failure. |

## Domain Events

Events are facts about state change. They feed the projection sink and audit
surface.

| Event | Description |
|---|---|
| `LegalIntakeReceived` | Intake port accepted and normalised a new legal intake. |
| `MatterScopeClassified` | Matter type, scope, jurisdiction, urgency, and boundary candidates were classified. |
| `PartyGraphExtracted` | Party roles, aliases, relationships, and ambiguity flags were recorded. |
| `ConflictCheckCompleted` | `sandbox-conflict-check` returned a gateway verdict and safe conflict-hit refs. |
| `ConflictDeterminationRecorded` | Conflict position and confidentiality risk were recorded. |
| `ConflictExceptionApprovalRequested` | Partner approval package was created for a permitted exception candidate. |
| `ConflictExceptionApproved` | Partner approved the exact conflict exception package. |
| `ConflictExceptionRejected` | Partner rejected the package or requested manual handling. |
| `KycBeneficialOwnershipChecked` | CDD and beneficial-ownership status was returned by the KYC / BO connector. |
| `AmlRiskAssessed` | AML risk rating, source refs, and trigger refs were recorded. |
| `EnhancedDueDiligenceApprovalRequested` | MLRO approval package was created for EDD or high AML risk. |
| `EnhancedDueDiligenceApproved` | MLRO approved the exact EDD package. |
| `EnhancedDueDiligenceRejected` | MLRO rejected or escalated the matter. |
| `EngagementDecisionRecorded` | Engagement decision was recorded with SRA / AML conduct hook trace. |
| `EngagementLetterDrafted` | Draft engagement-letter record was created. |
| `EngagementLetterApprovalRequested` | Approval package was created for engagement-letter send. |
| `EngagementLetterApproved` | Matter owner or partner approved the exact engagement-letter package. |
| `EngagementLetterSent` | Approved package was applied through the Tool Gateway and the sandbox send record was created. |
| `LegalIntakeRoutedForManualReview` | Intake was routed to a human exception queue. |
| `LegalIntakeDeclined` | Firm declined to act at intake stage. |
| `LegalIntakeClosed` | Workflow completed. |
| `LegalIntakeFailed` | Terminal failure occurred with safe reason and error refs. |

## Aggregates And Lifecycle Records

| Aggregate / record | Lifecycle |
|---|---|
| `LegalIntake` | Primary lifecycle record. Created by `IntakeLegalMatter`; mutated by classification, party extraction, conflict, AML, engagement, routing, and close commands. Holds safe refs and state only. |
| `PartyGraph` | Created by `ExtractPartyGraph`. Immutable per version; later corrections create a new graph version. Holds party refs, role labels, aliases, relationship edges, and ambiguity flags. |
| `ConflictDetermination` | Created after `RunConflictCheck`. Immutable once recorded. Holds conflict status, confidentiality risk, allowed exception basis if any, connector verdict refs, decision ref, policy snapshot ref, and transcript ref. |
| `AmlRiskAssessment` | Created by `AssessAmlRisk`. Updated only by appending new assessment versions. Holds risk rating, CDD status ref, beneficial-ownership status ref, EDD trigger refs, source refs, policy snapshot ref, and AML record-store ref. |
| `CddRecord` | Connector-side lifecycle record for identity, beneficial-ownership, and reliance evidence refs. Domain references it by `cdd-record-ref`. |
| `EngagementDecision` | Created by `DecideEngagement`. Immutable decision outcome: accept, accept subject to approval, decline to act, or manual review. Holds conduct hook trace and refs. |
| `ApprovalPackage` | Tool Gateway authority record for conflict exception, EDD approval, or engagement-letter send. Binds one exact request, expiry, subject refs, safe action refs, and policy refs. |
| `EngagementLetter` | Connector-side draft, approval, and send record. Holds draft ref, approval refs, scope summary ref, send ref, and engagement boundary refs. |

`LegalIntake` is the root aggregate for workflow state. `PartyGraph`,
`ConflictDetermination`, `AmlRiskAssessment`, `EngagementDecision`, and
`EngagementLetter` hang off it by safe refs.

## Value Objects

| Value object | Shape |
|---|---|
| `LegalIntakeState` | Enum from the state machine below. |
| `MatterType` | Enum: `commercial_contract`, `transaction_support`, `shareholder_or_partnership`, `corporate_governance`, `commercial_dispute`, `other_corporate_commercial`. |
| `PartyRole` | Enum: `prospective_client`, `instructing_contact`, `beneficial_owner`, `controller`, `counterparty`, `adverse_party`, `affiliate`, `existing_client`, `former_client`, `intermediary`, `unknown`. |
| `RelationshipEdge` | Tuple of source party ref, target party ref, relationship type, confidence, and evidence ref. |
| `ConflictStatus` | Enum: `no_conflict`, `own_interest_conflict`, `client_conflict_blocked`, `permitted_exception_candidate`, `confidentiality_risk`, `unknown_manual_review`. |
| `ConflictExceptionBasis` | Enum: `substantially_common_interest`, `competing_for_same_objective`; always requires informed written consent refs, safeguards refs, reasonableness rationale, and partner approval. |
| `ConfidentialitySafeguardStatus` | Enum: `not_required`, `no_real_risk_evidenced`, `informed_consent_evidenced`, `missing`, `blocked`. |
| `CddStatus` | Enum: `not_started`, `complete_standard`, `incomplete`, `reliance_pending`, `edd_required`, `blocked`. |
| `AmlRiskRating` | Enum: `low`, `standard`, `high`, `edd_required`, `blocked`, `manual_review`. |
| `AmlRiskFactor` | Tagged value for high-risk jurisdiction, complex ownership, PEP / sanctions-adjacent marker, source-of-funds ambiguity, intermediary reliance, anonymity, unusual transaction, or sector-risk factor. |
| `EngagementOutcome` | Enum: `accept_for_engagement`, `accept_subject_to_approval`, `decline_to_act`, `manual_review`. |
| `ConductHookTrace` | SRA and AML checks evaluated for a decision: best interests, public trust / integrity, client identification, conflict, confidentiality, CDD, EDD, AML record keeping, and accountability. |
| `PolicySnapshotRef` | Content-addressed hash of the policy bundle. |
| `SourceRef` | Opaque ref to raw payload, attachment, connector evidence, or policy source. |
| `ApprovalAction` | Bounded action label such as `conflict_exception.accept.write`, `aml_edd.accept.write`, or `engagement_letter.send.write`. |

## Safe Refs And Identifier Shape

UC2 uses opaque identifiers across ports. Raw personal data, confidential
client information, identity evidence, and document content stay behind intake
or connector boundaries.

| Ref | Shape | Notes |
|---|---|---|
| `legal-intake-ref` | UUID. | Identifies the inbound legal intake. |
| `source-payload-ref` | Opaque ref. | Points to raw email, form, referral, or attachment bundle held by the intake adapter. |
| `prospective-client-ref` | UUID. | Pseudonymous prospective-client identifier. |
| `contact-ref` | UUID. | Pseudonymous instructing-contact identifier. |
| `party-ref` | UUID. | Generic party identifier used in the party graph. |
| `beneficial-owner-ref` | UUID. | Pseudonymous beneficial-owner / controller identifier. |
| `matter-scope-ref` | UUID or content hash. | Identifies the current matter-scope summary. |
| `party-graph-ref` | UUID plus version. | Identifies a versioned party graph. |
| `conflict-check-ref` | UUID. | Connector-side conflict-check invocation record. |
| `conflict-hit-ref` | UUID. | Safe ref to a conflict hit; raw client-confidential detail stays in connector storage. |
| `conflict-determination-ref` | UUID. | Domain-side conflict decision record. |
| `cdd-record-ref` | UUID. | Connector-side CDD / KYC record. |
| `aml-risk-ref` | UUID plus version. | AML risk assessment record. |
| `engagement-decision-ref` | UUID. | Structured engagement decision. |
| `engagement-letter-ref` | UUID. | Connector-side draft / approval / send record. |
| `approval-package-ref` | UUID. | Tool Gateway approval package. |
| `decision-ref` | UUID. | Single agent decision. Joins decision trail to transcript. |
| `policy-snapshot-ref` | Content-addressed hash. | Policy bundle active at decision time. |
| `transcript-ref` | UUID. | Full-fidelity LLM invocation record. |

## State Machine

The `LegalIntake` aggregate moves through a bounded set of states.

| State | Reached by | Exits to |
|---|---|---|
| `received` | `IntakeLegalMatter`. | `classifying` immediately. |
| `classifying` | After intake accepted. | `extracting_parties` on `MatterScopeClassified`; `failed_classification` on schema/provider failure. |
| `extracting_parties` | After matter scope classification. | `checking_conflicts` on `PartyGraphExtracted`; `manual_review` when prospective client, authority, or critical party roles are ambiguous. |
| `checking_conflicts` | After party graph extraction. | `aml_screening` on no conflict; `awaiting_conflict_approval` for permitted exception candidate; `declined_to_act` for blocking conflict; `manual_review` for unknown conflict. |
| `awaiting_conflict_approval` | Partner approval package created. | `aml_screening` on approval; `declined_to_act` or `manual_review` on rejection. |
| `aml_screening` | Conflict path cleared or approved. | `deciding_engagement` on standard-risk complete CDD; `awaiting_edd_approval` on EDD trigger; `manual_review` on incomplete or ambiguous AML data; `declined_to_act` on blocked AML status. |
| `awaiting_edd_approval` | MLRO approval package created. | `deciding_engagement` on approval; `manual_review` or `declined_to_act` on rejection. |
| `deciding_engagement` | Conflict and AML records available. | `drafting_engagement_letter`, `manual_review`, or `declined_to_act` after `EngagementDecisionRecorded`. |
| `drafting_engagement_letter` | Accept decision recorded. | `awaiting_engagement_letter_approval` once draft exists; `failed_engagement_letter` on connector failure. |
| `awaiting_engagement_letter_approval` | Engagement-letter approval package created. | `engagement_letter_sent` on approved apply; `deciding_engagement` on redraft request; `manual_review` on rejection. |
| `engagement_letter_sent` | Approved package applied through Tool Gateway. | `closed` on `CloseLegalIntake`. |
| `manual_review` | Any manual review route. | `closed` once handoff is recorded, or back to the relevant state after authorised correction. |
| `declined_to_act` | Blocking conflict, blocked AML, or decline decision. | `closed` on `CloseLegalIntake`. |
| `closed` | Terminal success, decline, or manual handoff. | None. |
| `failed_intake`, `failed_classification`, `failed_conflict_check`, `failed_aml_check`, `failed_engagement_letter` | Terminal technical failure states. | None, unless a later replay / repair command is explicitly added. |

State changes are recorded on the projection sink event stream. Agent-driven
state changes also record decision-trail and transcript refs.

## Policies And Conduct Invariants

Each policy maps to an official source verified for this UC2 session.

| Policy | Source | Invariant |
|---|---|---|
| Identify who the firm acts for | SRA Code of Conduct for Solicitors 8.1, with service / instruction duties in section 3. | No `EngagementDecisionRecorded` event may have outcome `accept_for_engagement` without `prospective-client-ref`, `contact-ref`, authority status, and `matter-scope-ref`. |
| Act in the client's best interests and preserve public trust | SRA Principles 2, 4, 5, and 7. | No accept outcome may be recorded when unresolved uncertainty, misleading scope, or known conflict would make acceptance inconsistent with best interests, honesty, integrity, or public trust. |
| Own-interest conflict blocks acceptance | SRA Code of Conduct 6.1. | `ConflictStatus.own_interest_conflict` forces `declined_to_act` or `manual_review`; it cannot be converted to acceptance by approval. |
| Client conflict exception is tightly gated | SRA Code of Conduct 6.2. | `permitted_exception_candidate` cannot proceed unless the exception basis is `substantially_common_interest` or `competing_for_same_objective`, all clients' informed written consent refs are present, safeguards refs are present where appropriate, reasonableness rationale is recorded, and partner approval is applied through the Tool Gateway. |
| Confidentiality is protected | SRA Code of Conduct 6.3-6.5. | Raw current / former client confidential information must not appear in projections, telemetry, approval package bodies, or decision-trail free text. A material confidentiality risk blocks acceptance unless no-real-risk safeguards or informed-consent refs are recorded and approved. |
| Decisions are justifiable | SRA Code of Conduct 7.1-7.2 and Code of Conduct for Firms governance duties. | Every conflict, AML, and engagement decision must reference `decision-ref`, `policy-snapshot-ref`, `transcript-ref`, connector verdict refs, source refs, and structured rationale. |
| AML firm risk assessment is policy input | MLR 2017 regulations 18-19, SRA AML obligations, SRA Sectoral Risk Assessment, GOV.UK NRA 2025. | No `AmlRiskAssessed` event may be emitted without firm-risk source refs, sector-risk source refs, and policy snapshot refs. |
| CDD and beneficial ownership precede acceptance | MLR 2017 regulations 27-28 and official LSAG guidance for SRA-supervised firms. | No `EngagementLetterSent` event may be emitted unless CDD status is complete or an approved reliance / EDD path is recorded. Beneficial-owner gaps block acceptance or route to MLRO review. |
| Enhanced due diligence is gated | MLR 2017 regulation 33. | EDD triggers require `EnhancedDueDiligenceApprovalRequested` and MLRO approval before an accept path can proceed. |
| AML records are retained as structured refs | MLR 2017 regulation 40. | AML risk assessment, CDD, beneficial-ownership, EDD approval, and engagement decision records must have durable refs before closure. |
| Replay and audit completeness | Chorus architecture invariant. | Every LLM decision must have decision-trail and transcript records; replay through the connector port must use dry-run or recorded-action handling and must not duplicate side effects. |

## Approval Points

UC2 has three synchronous human approval gates.

| Approval point | Gate | Rationale |
|---|---|---|
| Permitted conflict exception | Partner approval required. | SRA conflict exceptions are narrow. The approval package must bind the exception basis, consent refs, safeguard refs, reasonableness rationale, policy refs, and exact safe subject refs. |
| AML enhanced due diligence / high risk | MLRO or AML compliance approval required. | High-risk AML, EDD, unresolved beneficial ownership, high-risk jurisdiction, or suspicious indicators cannot be auto-cleared. |
| Engagement letter send | Matter owner or partner approval required. | The engagement letter creates direct client impact and confirms who the firm acts for, scope, exclusions, and terms. |

Approval decisions do not invoke connectors directly. Approved packages
authorise a later Tool Gateway apply attempt only after the gateway re-checks
package state, expiry, refs, grant state, argument schema, mode, idempotency,
policy refs, and bounded action label.

## Connector Inventory

| Connector adapter | Domain commands | Records returned or written |
|---|---|---|
| `sandbox-conflict-check` | `RunConflictCheck`. | `conflict-check-ref`, safe `conflict-hit-ref` values, relationship labels, status hints, and confidentiality-risk hints. |
| `sandbox-kyc-bo` | `RunKycBeneficialOwnershipCheck`. | `cdd-record-ref`, `beneficial-owner-ref` values, controller refs, status flags, and evidence refs. |
| `sandbox-aml-record-store` | `AssessAmlRisk`, `RequestEnhancedDueDiligenceApproval`. | `aml-risk-ref`, EDD trigger refs, source-of-funds / source-of-wealth summary refs, MLRO approval refs. |
| `sandbox-engagement-letter-store` | `DraftEngagementLetter`, `SendEngagementLetter`, `DeclineToAct`, `RouteManualReview`. | `engagement-letter-ref`, draft refs, send refs, decline refs, manual-review refs. |

All connector actions pass through the Tool Gateway with grant checks,
argument validation, mode enforcement, redaction, idempotency, approval
policy, verdict capture, and tool-action audit.

## Field Placement Across Ports

| Field group | Intake port | LLM provider port | Connector port | Audit / transcript ports | Projection / observability |
|---|---|---|---|---|---|
| Raw inbound content | Stores raw payload and attachment refs. | Only included in local synthetic transcripts when needed for reasoning. | Not passed unless a connector owns the record. | Transcript may hold full synthetic prompt; decision trail holds safe summary. | Not projected; telemetry carries no raw content. |
| Party identity | Normalised to safe party refs and role hints. | Receives safe refs, role labels, and synthetic summaries. | KYC / BO store owns identity evidence and beneficial-owner detail. | Decision trail stores refs and status; transcript may hold synthetic details for replay. | Projection shows refs, roles, status, and ambiguity flags only. |
| Conflict information | None beyond party refs. | Receives safe hit summaries for reasoning. | Conflict connector owns current / former client hit detail. | Decision trail stores conflict status and safe hit refs; no raw confidential detail. | Projection shows conflict status and approval state. |
| AML information | Channel may collect high-level risk hints. | Receives structured risk factors and summaries. | AML and KYC connectors own CDD evidence, BO evidence, and risk records. | Decision trail stores risk rating, trigger refs, source refs; transcript stores replayable synthetic reasoning. | Projection shows risk category, EDD state, and approval state; telemetry only safe labels. |
| Engagement letter | Intake may include draft ref from intermediary. | Receives scope summary and draft metadata. | Engagement-letter store owns draft body, approval, and send record. | Decision trail stores approval and send refs; transcript records generated draft reasoning when relevant. | Projection shows draft / approval / send state, not raw text by default. |

## Failure And Escalation Paths

| Failure | Trigger | Path |
|---|---|---|
| Intake contract violation | Channel payload fails schema validation. | Reject at intake port; record contract violation; no workflow start. |
| Classification failure | LLM provider output is schema-invalid or route unavailable. | Move to `failed_classification`; projection shows technical exception; no connector action. |
| Prospective-client ambiguity | The workflow cannot determine who the firm would act for or whether the contact has authority. | Move to `manual_review`; no accept outcome allowed. |
| Party graph ambiguity | Material counterparty, beneficial-owner, affiliate, or relationship edge is unresolved. | Route to matter-owner or AML review depending on field; do not emit clean conflict / AML result. |
| Conflict connector failure | `sandbox-conflict-check` errors or returns contract-invalid result. | Move to `failed_conflict_check`; record gateway verdict and connector error ref. |
| Blocking conflict | Own-interest conflict or prohibited client conflict. | Move to `declined_to_act` or `manual_review`; no engagement-letter send. |
| Missing conflict safeguards | Exception candidate lacks consent, safeguards, or reasonableness evidence. | Hold in `awaiting_conflict_approval` or route to manual review; no accept path. |
| KYC / BO connector failure | `sandbox-kyc-bo` errors or returns contract-invalid result. | Move to `failed_aml_check`; no engagement decision. |
| Beneficial-owner gap | BO or controller evidence incomplete. | Route to MLRO / AML review; no engagement-letter send. |
| EDD trigger rejected | MLRO rejects EDD package. | Move to `declined_to_act` or `manual_review` based on rejection reason. |
| Engagement-letter approval rejected | Matter owner rejects draft or scope. | Return to `deciding_engagement` or `drafting_engagement_letter` with redraft refs. |
| Gateway idempotency conflict | Connector call repeats with mismatched arguments for same key. | Fail the call, record audit verdict, and route to technical exception. |
| Replay side-effect risk | Replay reaches connector action. | Use dry-run or recorded-action handling; compare proposed action and verdict without applying side effects. |

## Banned And Ambiguous Terms

| Banned / ambiguous term | Replacement | Reason |
|---|---|---|
| Case | Legal intake, matter scope, conflict determination, AML risk assessment, or engagement decision. | Too generic; hides the lifecycle record being discussed. |
| Client | Prospective client until `EngagementLetterSent`. Client only after acceptance. | Calling the party a client too early misstates the legal relationship. |
| Customer | Prospective client or instructing contact. | Consumer-product language does not fit corporate legal services. |
| Account | Prospective client, party, or matter scope. | Implies CRM storage rather than domain role. |
| Conflict pass | Conflict determination. | A conflict result may be no conflict, blocked, exception candidate, confidentiality risk, or unknown; "pass" hides nuance. |
| KYC pass | CDD status or beneficial-ownership status. | CDD / BO evidence can be complete, incomplete, reliance-based, EDD-required, or blocked. |
| AML clearance | AML risk assessment or MLRO approval. | The workflow records risk and approvals; it does not declare regulatory clearance. |
| Risk score | AML risk rating or conflict status. | A single numeric score is not the domain output. |
| Recommendation | Engagement decision or proposed scope. | "Recommendation" can imply legal advice; UC2 is intake and engagement support only. |
| Advice | Proposed legal service scope, matter scope, or engagement boundary. | UC2 does not provide substantive legal advice. |
| Tool | Domain commands or connector adapters. | "Tool" is platform vocabulary for the Tool Gateway; domain docs use domain verbs. |
| Clean client | Standard-risk CDD complete or no-conflict status. | "Clean" is imprecise and can mask AML or conflict uncertainty. |

## R4 Local POC Boundaries

UC2 R4 is a synthetic local proof of the architecture:

- local synthetic data only;
- no production legal advice, conflict database, AML provider, identity
  provider, Companies House lookup, sanctions screening, document-management
  system, or matter-management system;
- no client-money, billing, undertakings, SAR / DAML, e-signature, or matter
  execution workflow;
- one use-case runnable path is enough for R4 once implementation begins, but
  no channel is described as runnable until its own contract, fixture or
  sandbox injection path, normalisation, provenance, idempotency, and
  workflow-start handoff are evidenced;
- UC2 runtime work waits for the later R4 sequence after shared-surface
  generalisation, UC1 connector persistence completion, and provider / replay
  hardening.

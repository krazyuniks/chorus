---
type: project-doc
status: active
date: 2026-05-24
phase: R4
use_case: UC3
---

# Domain Model - UK Independent Financial Advice Suitability Intake

This document is the ubiquitous language for use case 3. It defines the
domain terms, actors, artefacts, commands, events, aggregates, value objects,
state machine, policies, approval points, failure paths, field placement, and
banned terms that UC3 work must use.

Contract shapes here are schema sketches. The actual JSON Schema contracts
arrive in later R4 slices. The sketches are deliberately under-specified at
the field level; what matters here is which payload crosses which named port,
which fields are load-bearing, and which records must stay behind connector
or intake boundaries.

## Glossary

| Term | Definition |
|---|---|
| Advice enquiry | An inbound request for independent financial advice assessment. It is the primary unit of work for UC3. |
| Prospective retail client | The natural person seeking advice before the firm accepts or progresses the advice service. FCA source material can use "client" for potential clients; UC3 domain docs use "prospective retail client" before report issue. |
| Retail client | The FCA client category for the person receiving the advice service. UC3 does not model professional-client or eligible-counterparty advice. |
| Advice service scope | The classified service boundary: independent advice in scope, information-only, restricted-advice-out-of-scope, targeted-support-out-of-scope, execution-only request, or manual review. |
| Personal recommendation | The FCA-regulated concept. In UC3, only an adviser-approved suitability report can carry a personal recommendation. Agent output is called a suitability conclusion. |
| Fact-find summary | Structured summary of objectives, financial situation, knowledge and experience, time horizon, products under review, household context, support needs, and gaps. |
| Investment objective | A bounded aim such as capital growth, income, pension accumulation, retirement planning, emergency reserve preservation, tax-wrapper use, inheritance planning, or portfolio simplification. |
| Financial situation | Income, expenditure, assets, liabilities, emergency reserves, dependants, liquidity needs, pension context, tax-wrapper context, and affordability evidence represented by safe refs and summaries. |
| Knowledge and experience | Evidence of the client's familiarity with relevant services, transactions, product types, complexity, risk, education, profession, and prior investment behaviour. |
| Attitude to risk | Risk preference and risk tolerance evidence, normally derived from the sandbox profiler plus narrative comparison. |
| Risk profile | The combined risk view: stated preference, profiler band, knowledge / experience, time horizon, objectives, and mismatch flags. |
| Capacity for loss | Whether the prospective retail client can financially bear investment losses consistent with objectives and without unacceptable harm. |
| Vulnerability marker | Safe category indicating a support need or characteristic of vulnerability that may affect understanding, decision making, consent, or customer support. |
| Independent advice universe | The product and provider range considered for independent advice. It must be sufficient, diverse, unbiased, and appropriate to the advice scope. |
| Platform research result | Connector-side evidence about notional platform, product, provider, target-market, cost, charge, complexity, due-diligence, and distribution-strategy factors. |
| Target-market compatibility | PROD and Consumer Duty evidence that a financial instrument or service fits the identified target market and is not negative-target-market for the client. |
| Suitability conclusion | Agent-proposed structured outcome: suitable subject to adviser approval, unsuitable, insufficient information, or manual review. It is not a personal recommendation. |
| Suitability report | Adviser-approved report record explaining the personal recommendation, suitability rationale, demands and needs, disadvantages, costs, risk, and Consumer Duty support evidence. |
| Approval package | Generic Tool Gateway authority envelope for one exact request requiring human approval before effect mode. |
| Policy snapshot | Immutable bundle of policy source refs, route refs, prompts, grants, approval rules, redaction rules, FCA source versions, and local configuration active when a decision was made. |
| Decision-trail record | Structured audit record for a material decision: who decided what, under which policy, on which safe inputs, with which safe outputs. |
| Transcript record | Full-fidelity LLM invocation record used for engineering replay. Kept separate from the structured decision trail. |

## Actors And Roles

| Actor | Role |
|---|---|
| Prospective retail client | Supplies advice need, fact-find information, objectives, risk preferences, support needs, and consent flags. |
| Existing retail client | Supplies a new advice need where the firm may have existing synthetic fact-find or ongoing-service context. Existing status does not remove suitability controls. |
| Joint applicant / household member | May affect objectives, affordability, dependants, authority, capacity for loss, or support needs. |
| Attorney / authorised third party | May assist or act for the prospective retail client. Authority and best-interests concerns route to manual review. |
| Introducer | Supplies referral context. Does not replace client fact-find, advice-scope disclosure, suitability assessment, or adviser approval. |
| Financial adviser | Accountable for the personal recommendation, suitability report issue, risk-profile override, and customer-impact communications. |
| Paraplanner | Reviews report drafts, fact-find summaries, research packs, and missing evidence in the manual baseline. |
| Supervisor / compliance reviewer | Reviews suitability evidence, conduct hooks, approval packages, and governance exceptions. |
| Investment committee / research owner | Owns product-universe and platform-research policy inputs in the sandbox. |
| Vulnerability support reviewer | Reviews support needs, communication adjustments, authority questions, and vulnerability-triggered handoff. |
| Chorus runtime | Executes the UC3 workflow through the named ports and records audit / transcript evidence. |

## Inbound Artefacts

Schema sketches only. Actual contracts land in a later R4 contracts slice.

### Web Advice Enquiry (intake adapter: `web-form-channel`)

```text
WebAdviceEnquiry {
  channel: "web-form"
  submitted_at: timestamp
  submission_id: string
  form_version: string
  prospective_retail_client: map
  contact_preferences: map
  advice_need_hint: string optional
  objectives_text: string
  time_horizon_hint: string optional
  asset_band: string optional
  pension_context_hint: string optional
  risk_preference_hint: string optional
  support_need_flags: map
  consent_flags: map
  attachments: list[{attachment_ref, name, mime, size, sha256}]
}
```

### Email Advice Enquiry (intake adapter: `email-channel`)

```text
EmailAdviceEnquiry {
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

### Introducer Referral (intake adapter: `introducer-referral-channel`)

```text
IntroducerReferral {
  channel: "introducer-referral-channel"
  received_at: timestamp
  referral_id: string
  introducer_ref: introducer-ref
  introducer_contact: string
  referral_narrative: string
  advice_need_hint: string optional
  client_context: map
  product_or_platform_hints: list[string]
  authority_evidence_ref: source-payload-ref optional
  attachments: list[{attachment_ref, name, mime, size, sha256}]
}
```

### Normalised Advice Enquiry (post-intake, domain-side)

```text
AdviceEnquiry {
  advice_enquiry_ref: uuid
  channel: "web-form" | "email" | "introducer-referral-channel"
  received_at: timestamp
  source_payload_ref: source-payload-ref
  idempotency_key_ref: idempotency-key-ref
  prospective_retail_client_ref: prospective-retail-client-ref optional
  household_ref: household-ref optional
  introducer_ref: introducer-ref optional
  advice_scope_ref: advice-scope-ref optional
  state: AdviceEnquiryState
  latest_fact_find_summary_ref: fact-find-summary-ref optional
  latest_risk_profile_ref: risk-profile-ref optional
  latest_capacity_for_loss_ref: capacity-for-loss-ref optional
  latest_platform_research_ref: platform-research-ref optional
  latest_suitability_conclusion_ref: suitability-conclusion-ref optional
  latest_suitability_report_ref: suitability-report-ref optional
}
```

## Commands

Commands are intent-bearing inputs to the workflow. Each command runs through
the named ports and emits domain events.

| Command | Source | Description |
|---|---|---|
| `IntakeAdviceEnquiry` | Intake port. | Accept a channel payload and create a normalised `AdviceEnquiry` record. |
| `ClassifyAdviceScope` | Workflow step. | Ask the LLM provider port to classify service scope, advice need, out-of-frame indicators, and manual-review flags. |
| `SummariseFactFind` | Workflow step. | Ask the LLM provider port to produce fact-find summary, objectives, financial situation, knowledge / experience, support needs, and evidence gaps. |
| `RouteFactFindGap` | Workflow step. | Route missing necessary information to adviser enrichment or manual review. |
| `RunAttitudeToRiskProfile` | Workflow step via connector port. | Invoke `sandbox-attitude-to-risk-profiler` through the Tool Gateway using safe refs and questionnaire / narrative summaries. |
| `AssessRiskProfile` | Workflow step. | Compare stated preference, profiler band, experience, objectives, time horizon, and narrative mismatch flags. |
| `RequestRiskProfileApproval` | Workflow step. | Create adviser approval package for a material risk-profile mismatch or override. |
| `AssessCapacityForLoss` | Workflow step via connector port. | Invoke `sandbox-capacity-for-loss-tool` through the Tool Gateway using safe financial refs and stress assumptions. |
| `AssessConsumerDutySupportNeeds` | Workflow step. | Evaluate vulnerability markers, communication adjustments, foreseeable harm, and support requirements. |
| `RequestVulnerabilityHandoffApproval` | Workflow step. | Create adviser / support approval package when vulnerability or authority concerns affect the advice journey. |
| `RunPlatformResearch` | Workflow step via connector port. | Invoke `sandbox-platform-research` through the Tool Gateway for product-universe, target-market, costs, charges, platform, and due-diligence evidence. |
| `DetermineSuitability` | Workflow step. | Produce the structured suitability conclusion with COBS, PROD, Consumer Duty, policy, transcript, and connector refs. |
| `DraftSuitabilityReport` | Workflow step via connector port. | Create a draft suitability report record in `sandbox-suitability-report-store`. |
| `RequestSuitabilityReportApproval` | Workflow step. | Create adviser approval package for the exact report issue request. |
| `IssueSuitabilityReport` | Workflow step via connector port. | Apply the approved package through the Tool Gateway and mark the report issued in the sandbox store. |
| `RouteManualReview` | Workflow step. | Route an enquiry that cannot be progressed automatically to adviser, supervisor, investment committee, or vulnerability support review. |
| `DeclineAdviceService` | Workflow step. | Record an out-of-frame, unsuitable, or declined advice-service outcome with safe rationale and audit refs. |
| `CloseAdviceEnquiry` | Workflow step. | Close the UC3 enquiry workflow after routing or terminal failure. |

## Domain Events

Events are facts about state change. They feed the projection sink and audit
surface.

| Event | Description |
|---|---|
| `AdviceEnquiryReceived` | Intake port accepted and normalised a new advice enquiry. |
| `AdviceScopeClassified` | Advice need, service scope, out-of-frame indicators, and manual-review flags were classified. |
| `FactFindSummaryRecorded` | Objectives, financial situation, knowledge / experience, support needs, and gap refs were recorded. |
| `FactFindGapsIdentified` | Necessary information for suitability was missing, stale, or contradictory. |
| `AttitudeToRiskProfiled` | `sandbox-attitude-to-risk-profiler` returned a gateway verdict and safe profile refs. |
| `RiskProfileAssessed` | Risk profile, mismatch flags, and approval requirement were recorded. |
| `RiskProfileApprovalRequested` | Adviser approval package was created for a risk-profile mismatch or override. |
| `RiskProfileApproved` | Adviser approved the exact risk-profile package. |
| `RiskProfileRejected` | Adviser rejected the package or required manual handling. |
| `CapacityForLossAssessed` | Capacity-for-loss result, stress outcome, and evidence refs were recorded. |
| `ConsumerDutySupportAssessed` | Vulnerability, support need, foreseeable harm, and communication adjustment refs were recorded. |
| `VulnerabilityHandoffApprovalRequested` | Approval package was created for a support or vulnerability handoff. |
| `VulnerabilityHandoffApproved` | Adviser or support reviewer approved the exact handoff package. |
| `VulnerabilityHandoffRejected` | Reviewer rejected or escalated the package. |
| `PlatformResearchCompleted` | `sandbox-platform-research` returned product-universe, target-market, costs, charges, and platform refs. |
| `SuitabilityConclusionRecorded` | Suitability conclusion was recorded with FCA conduct hook trace. |
| `SuitabilityReportDrafted` | Draft report record was created in the sandbox store. |
| `SuitabilityReportApprovalRequested` | Approval package was created for suitability report issue. |
| `SuitabilityReportApproved` | Financial adviser approved the exact report issue package. |
| `SuitabilityReportRejected` | Adviser rejected the report issue package or requested redraft. |
| `SuitabilityReportIssued` | Approved package was applied through the Tool Gateway and the sandbox report issue record was created. |
| `AdviceEnquiryRoutedForManualReview` | Enquiry was routed to a human exception queue. |
| `AdviceServiceDeclined` | Firm declined or could not provide the advice service in the local workflow. |
| `AdviceEnquiryClosed` | Workflow completed. |
| `AdviceEnquiryFailed` | Terminal failure occurred with safe reason and error refs. |

## Aggregates And Lifecycle Records

| Aggregate / record | Lifecycle |
|---|---|
| `AdviceEnquiry` | Primary lifecycle record. Created by `IntakeAdviceEnquiry`; mutated by classification, fact-find, risk, capacity, support, research, suitability, report, routing, and close commands. Holds safe refs and state only. |
| `AdviceScopeAssessment` | Created by `ClassifyAdviceScope`. Immutable per version. Holds service-scope enum, out-of-frame flags, disclosure requirement refs, and manual-review flags. |
| `FactFindSummary` | Created by `SummariseFactFind`. Versioned summary of objectives, financial situation, knowledge / experience, support needs, missing information, stale information, and contradiction flags. |
| `RiskProfileAssessment` | Created after `RunAttitudeToRiskProfile` and `AssessRiskProfile`. Holds profiler band, stated preference, narrative evidence, mismatch flags, decision ref, policy snapshot ref, and transcript ref. |
| `CapacityForLossAssessment` | Created by `AssessCapacityForLoss`. Holds capacity status, stress results, income / expenditure evidence refs, liquidity flags, dependency flags, and connector refs. |
| `ConsumerDutySupportAssessment` | Created by `AssessConsumerDutySupportNeeds`. Holds vulnerability marker categories, support need refs, communication adjustment refs, foreseeable-harm result, and reviewer state. |
| `PlatformResearchRecord` | Created by `RunPlatformResearch`. Connector-side record with product-universe refs, target-market compatibility, costs, charges, complexity, platform constraints, and due-diligence refs. |
| `SuitabilityConclusion` | Created by `DetermineSuitability`. Immutable structured outcome: suitable subject to adviser approval, unsuitable, insufficient information, or manual review. Holds conduct hook trace and refs. |
| `SuitabilityReport` | Connector-side draft, approval, and issue lifecycle record. Holds draft ref, approval refs, issue ref, report summary ref, suitability conclusion ref, and client-understanding refs. |
| `ApprovalPackage` | Tool Gateway authority record for risk-profile override, vulnerability handoff, or suitability report issue. Binds one exact request, expiry, subject refs, safe action refs, and policy refs. |

`AdviceEnquiry` is the root aggregate for workflow state. The other records
hang off it by safe refs and are immutable or versioned after creation.

## Value Objects

| Value object | Shape |
|---|---|
| `AdviceEnquiryState` | Enum from the state machine below. |
| `AdviceServiceScope` | Enum: `independent_advice_in_scope`, `information_only`, `restricted_advice_out_of_scope`, `targeted_support_out_of_scope`, `execution_only_request`, `manual_review`, `declined_out_of_scope`. |
| `ClientCategory` | Enum: `retail_client`, `professional_client_out_of_scope`, `eligible_counterparty_out_of_scope`, `unknown`. |
| `InvestmentObjectiveType` | Enum: `capital_growth`, `income`, `pension_accumulation`, `retirement_planning`, `emergency_reserve`, `tax_wrapper_use`, `inheritance_planning`, `portfolio_simplification`, `other`. |
| `TimeHorizonBand` | Enum: `under_2_years`, `2_to_5_years`, `5_to_10_years`, `over_10_years`, `unknown`. |
| `FactFindCompleteness` | Enum: `complete_for_scope`, `missing_necessary_information`, `stale_information`, `contradictory_information`, `manual_review`. |
| `KnowledgeExperienceLevel` | Enum: `none`, `limited`, `moderate`, `experienced`, `professional_out_of_scope`, `unknown`. |
| `AttitudeToRiskBand` | Enum: `very_low`, `low`, `low_medium`, `medium`, `medium_high`, `high`, `unknown`. |
| `RiskProfileStatus` | Enum: `aligned`, `mismatch_requires_approval`, `client_overstates_risk`, `client_understates_loss_concern`, `manual_review`, `blocked`. |
| `CapacityForLossStatus` | Enum: `adequate`, `limited`, `negative`, `liquidity_gap`, `dependency_risk`, `manual_review`, `blocked`. |
| `VulnerabilityMarkerCategory` | Enum: `health`, `life_event`, `low_resilience`, `low_capability`, `communication_adjustment`, `third_party_authority`, `financial_difficulty`, `none`, `unknown`. |
| `ConsumerDutyOutcomeTrace` | Consumer Duty checks evaluated for a decision: good faith, foreseeable harm, product / service fit, price / value, consumer understanding, consumer support, vulnerability, and outcome-monitoring refs. |
| `ProductUniverseCoverage` | Enum: `sufficient_independent_range`, `focused_independent_range`, `too_narrow`, `platform_biased`, `manufacturer_data_missing`, `manual_review`. |
| `TargetMarketCompatibility` | Enum: `in_target_market`, `edge_of_target_market`, `negative_target_market`, `unknown`, `manual_review`. |
| `ProductComplexityBand` | Enum: `simple`, `moderate`, `complex`, `high_risk_out_of_scope`, `unknown`. |
| `SuitabilityOutcome` | Enum: `suitable_subject_to_adviser_approval`, `unsuitable`, `insufficient_information`, `manual_review`, `out_of_scope`. |
| `SuitabilityReportStatus` | Enum: `not_started`, `drafted`, `awaiting_adviser_approval`, `approved`, `issued`, `rejected`, `blocked`. |
| `ConductHookTrace` | FCA checks evaluated for a decision: COBS best interests, COBS 6 independent advice / disclosure, COBS 9 suitability, COBS 9 report, PROD target market, Consumer Duty, vulnerability, and record keeping. |
| `PolicySnapshotRef` | Content-addressed hash of the policy bundle. |
| `SourceRef` | Opaque ref to raw payload, attachment, connector evidence, or policy source. |
| `ApprovalAction` | Bounded action label such as `risk_profile.override.write`, `vulnerability_handoff.record.write`, or `suitability_report.issue.write`. |

## Safe Refs And Identifier Shape

UC3 uses opaque identifiers across ports. Raw personal data, detailed
financial information, health information, vulnerability detail, product
account data, and suitability report text stay behind intake or connector
boundaries.

| Ref | Shape | Notes |
|---|---|---|
| `advice-enquiry-ref` | UUID. | Identifies the inbound advice enquiry. |
| `source-payload-ref` | Opaque ref. | Points to raw email, form, referral, or attachment bundle held by the intake adapter. |
| `idempotency-key-ref` | Opaque ref. | Stable ref for the channel-specific idempotency key. |
| `prospective-retail-client-ref` | UUID. | Pseudonymous client identifier. |
| `household-ref` | UUID. | Pseudonymous household or joint-applicant context. |
| `introducer-ref` | UUID or slug. | Safe ref to synthetic introducer record. |
| `advice-scope-ref` | UUID plus version. | Service-scope assessment. |
| `fact-find-summary-ref` | UUID plus version. | Structured fact-find summary. |
| `objective-ref` | UUID. | Safe objective record. |
| `financial-situation-ref` | UUID. | Safe summary ref; raw income, expenditure, assets, and liabilities remain behind connector / intake storage. |
| `knowledge-experience-ref` | UUID. | Knowledge and experience summary. |
| `risk-profile-ref` | UUID plus version. | Combined attitude-to-risk and risk-profile record. |
| `capacity-for-loss-ref` | UUID plus version. | Capacity-for-loss assessment. |
| `support-assessment-ref` | UUID plus version. | Consumer Duty / vulnerability support assessment. |
| `platform-research-ref` | UUID plus version. | Connector-side product-universe and platform research record. |
| `product-candidate-ref` | UUID. | Safe product or financial-instrument candidate ref. |
| `target-market-ref` | UUID or content hash. | Product target-market evidence. |
| `suitability-conclusion-ref` | UUID. | Structured suitability decision record. |
| `suitability-report-ref` | UUID. | Connector-side report draft / approval / issue record. |
| `approval-package-ref` | UUID. | Tool Gateway approval package. |
| `decision-ref` | UUID. | Single agent decision. Joins decision trail to transcript. |
| `policy-snapshot-ref` | Content-addressed hash. | Policy bundle active at decision time. |
| `transcript-ref` | UUID. | Full-fidelity LLM invocation record. |

## State Machine

The `AdviceEnquiry` aggregate moves through a bounded set of states.

| State | Reached by | Exits to |
|---|---|---|
| `received` | `IntakeAdviceEnquiry`. | `classifying_scope` immediately. |
| `classifying_scope` | After intake accepted. | `summarising_fact_find` on `AdviceScopeClassified`; `manual_review` or `declined_out_of_scope` for out-of-frame advice; `failed_classification` on schema/provider failure. |
| `summarising_fact_find` | Scope is in frame. | `risk_profiling` on complete or provisionally complete fact-find; `fact_find_incomplete` when necessary information is missing, stale, or contradictory. |
| `fact_find_incomplete` | `FactFindGapsIdentified`. | `manual_review` or back to `summarising_fact_find` after authorised enrichment. |
| `risk_profiling` | Fact-find complete enough for risk analysis. | `awaiting_risk_profile_approval` on material mismatch; `assessing_capacity_for_loss` on aligned profile; `manual_review` on unresolved profile. |
| `awaiting_risk_profile_approval` | Adviser approval package created. | `assessing_capacity_for_loss` on approval; `manual_review` or `declined_out_of_scope` on rejection. |
| `assessing_capacity_for_loss` | Risk profile cleared or approved. | `assessing_consumer_duty_support` on adequate or limited capacity; `manual_review` for limited / dependency risk; `declined_out_of_scope` or `manual_review` for blocked capacity. |
| `assessing_consumer_duty_support` | Capacity-for-loss result exists. | `awaiting_vulnerability_handoff` when support review is required; `researching_platform` when support path is clear. |
| `awaiting_vulnerability_handoff` | Support approval package created. | `researching_platform` on approval; `manual_review` on rejection or unresolved support need. |
| `researching_platform` | Suitability inputs are clear enough for product-universe research. | `assessing_suitability` on valid research; `manual_review` for product-universe defect; `failed_platform_research` on connector failure. |
| `assessing_suitability` | Risk, capacity, support, and research records available. | `drafting_suitability_report`, `manual_review`, `insufficient_information`, or `declined_out_of_scope` after `SuitabilityConclusionRecorded`. |
| `drafting_suitability_report` | Positive suitability conclusion recorded. | `awaiting_suitability_report_approval` once draft exists; `failed_suitability_report` on connector failure. |
| `awaiting_suitability_report_approval` | Report approval package created. | `suitability_report_issued` on approved apply; `assessing_suitability` on redraft request; `manual_review` on rejection. |
| `suitability_report_issued` | Approved package applied through Tool Gateway. | `closed` on `CloseAdviceEnquiry`. |
| `manual_review` | Any manual review route. | `closed` once handoff is recorded, or back to the relevant state after authorised correction. |
| `insufficient_information` | Necessary information remains missing. | `closed` or back to `summarising_fact_find` after enrichment. |
| `declined_out_of_scope` | Out-of-frame service, unsuitable, or declined service outcome. | `closed` on `CloseAdviceEnquiry`. |
| `closed` | Terminal success, decline, or manual handoff. | None. |
| `failed_intake`, `failed_classification`, `failed_risk_profile`, `failed_capacity_for_loss`, `failed_platform_research`, `failed_suitability_report` | Terminal technical failure states. | None, unless a later replay / repair command is explicitly added. |

State changes are recorded on the projection sink event stream. Agent-driven
state changes also record decision-trail and transcript refs.

## Policies And Conduct Invariants

Each policy maps to an official FCA source verified for this UC3 session.

| Policy | Source | Invariant |
|---|---|---|
| Client best interests | COBS 2.1.1R and PRIN 2 Principles 6, 7, 9, and 12. | No `SuitabilityConclusionRecorded` event may have outcome `suitable_subject_to_adviser_approval` when the proposed action conflicts with the client's interests, information needs, or ability to rely on the firm's judgement. |
| Independent advice requires sufficient range | COBS 6.2B.11R, 6.2B.15R-6.2B.19G, and FCA retail investment advice guidance. | No independent-advice suitability conclusion may be positive unless `ProductUniverseCoverage` is `sufficient_independent_range` or an approved focused-independent range is evidenced with service-scope disclosure refs. |
| Advice-service disclosure is clear | COBS 6.2B.33R-6.2B.36R. | No report issue may be recorded unless the advice-service scope, independent / restricted distinction, range analysed, relationship constraints, and selection factors are referenced. |
| Necessary information precedes suitability | COBS 9.2.1R-9.2.6R. | No positive suitability conclusion may be recorded unless objectives, financial situation, knowledge and experience, time horizon, risk profile, and capacity for loss are present, current, and not materially contradictory. |
| Suitability matches objectives, risk-bearing ability, and experience | COBS 9.2.2R-9.2.3R. | A positive conclusion requires objective match, financial ability to bear related risks, and sufficient knowledge / experience evidence for the product complexity. |
| Stale or incomplete information blocks reliance | COBS 9.2.5R-9.2.6R. | If information is manifestly out of date, inaccurate, incomplete, or insufficient, the outcome must be `insufficient_information` or `manual_review`; it cannot be approved as suitable. |
| Suitability report explains basis and disadvantages | COBS 9.4. | No `SuitabilityReportIssued` event may be emitted unless the report ref contains demands / needs, suitability rationale, possible disadvantages, costs / charges, risk explanation, and consumer-understanding refs. |
| Product governance and target market are evidenced | PROD 3.3 and PRIN 2A.3 / 2A.4. | No product candidate may support a positive conclusion without product-understanding, target-market compatibility, negative-target-market check, cost / charge, complexity, manufacturer-information, and distribution-strategy refs. |
| Consumer Duty cross-cutting obligations are evaluated | PRIN 2A.2. | Every suitability conclusion must record good-faith, foreseeable-harm, and enable-and-support checks. A foreseeable-harm fail blocks report issue. |
| Consumer Duty communication and support are gated | PRIN 2A.5, PRIN 2A.6, PRIN 2A.7, and FG21/1. | Report issue requires consumer-understanding checks and support-need state. Vulnerability markers require safe support refs and approval when they affect understanding, consent, channel, or timing. |
| Outcome monitoring evidence exists | PRIN 2A.9. | Closure requires projection-safe outcome-monitoring refs for suitability outcome, vulnerability route, product-universe defect, report approval latency, and manual-review reason where applicable. |
| Suitability records are retained as structured refs | COBS 9.5 and COBS Sch 1. | Fact-find, risk, capacity, research, suitability, report, approval, policy, decision, and transcript refs must exist before terminal closure. |
| Replay and audit completeness | Chorus architecture invariant. | Every LLM decision must have decision-trail and transcript records; replay through the connector port must use dry-run or recorded-action handling and must not duplicate side effects. |

## Approval Points

UC3 has three synchronous human approval gates.

| Approval point | Gate | Rationale |
|---|---|---|
| Risk-profile mismatch or override | Adviser approval required. | The suitability path must not silently override a mismatch between stated preference, profiler output, narrative evidence, knowledge / experience, and capacity for loss. |
| Vulnerability or support handoff | Adviser or support-review approval required. | Vulnerability, authority, support need, or communication adjustment may affect client understanding, timing, consent, or foreseeable harm. |
| Suitability report issue | Financial adviser approval required. | The report communicates the personal recommendation and creates direct customer impact. The approval package must bind the exact report ref, suitability conclusion, conduct hook trace, policy refs, and safe subject refs. |

Approval decisions do not invoke connectors directly. Approved packages
authorise a later Tool Gateway apply attempt only after the gateway re-checks
package state, expiry, refs, grant state, argument schema, mode, idempotency,
policy refs, and bounded action label.

## Connector Inventory

| Connector adapter | Domain commands | Records returned or written |
|---|---|---|
| `sandbox-attitude-to-risk-profiler` | `RunAttitudeToRiskProfile`. | `risk-profile-ref`, profiler band, questionnaire trace refs, inconsistency flags, and confidence. |
| `sandbox-capacity-for-loss-tool` | `AssessCapacityForLoss`. | `capacity-for-loss-ref`, stress outcome, liquidity flags, dependency flags, affordability refs, and evidence summaries. |
| `sandbox-platform-research` | `RunPlatformResearch`. | `platform-research-ref`, product-universe refs, product-candidate refs, target-market refs, cost / charge summaries, complexity flags, and due-diligence refs. |
| `sandbox-suitability-report-store` | `DraftSuitabilityReport`, `IssueSuitabilityReport`, `DeclineAdviceService`, `RouteManualReview`. | `suitability-report-ref`, draft refs, approval refs, issue refs, decline refs, manual-review refs, and report summary refs. |

All connector actions pass through the Tool Gateway with grant checks,
argument validation, mode enforcement, redaction, idempotency, approval
policy, verdict capture, and tool-action audit.

## Field Placement Across Ports

| Field group | Intake port | LLM provider port | Connector port | Audit / transcript ports | Projection / observability |
|---|---|---|---|---|---|
| Raw inbound content | Stores raw payload and attachment refs. | Only included in local synthetic transcripts when needed for reasoning. | Not passed unless a connector owns the record. | Transcript may hold full synthetic prompt; decision trail holds safe summary. | Not projected; telemetry carries no raw content. |
| Client identity and authority | Normalised to safe client, household, introducer, and authority refs. | Receives safe refs, role labels, and synthetic summaries. | Suitability-report store owns detailed synthetic client file refs. | Decision trail stores refs and status; transcript may hold synthetic details for replay. | Projection shows refs, status, channel, and ambiguity flags only. |
| Financial situation | Intake stores raw hints and evidence refs. | Receives safe summary and gap flags. | Capacity tool owns detailed cash-flow / stress inputs and outputs. | Decision trail stores capacity status and evidence refs; transcript stores replayable synthetic reasoning. | Projection shows capacity category and approval state only. |
| Knowledge and experience | Intake stores raw notes and evidence refs. | Receives summary and product-complexity comparison. | Platform research may use product-complexity category. | Decision trail stores level and gap refs. | Projection shows level and gap state only. |
| Attitude to risk | Intake stores stated preference. | Receives profiler band, stated preference, and mismatch summary. | Profiler owns questionnaire trace and scoring detail. | Decision trail stores band, mismatch state, and approval refs. | Projection shows risk profile band, mismatch, and approval state. |
| Vulnerability and support | Intake stores raw support flags and refs. | Receives safe marker categories and adjustment summaries. | Report store owns report-specific communication adjustments. | Decision trail stores marker categories, support refs, and approval state; no raw sensitive detail. | Projection shows safe marker category and support route; telemetry only safe labels. |
| Platform / product research | None beyond product hints. | Receives safe research summary for suitability reasoning. | Platform research owns product-universe, target-market, costs, charges, complexity, and due-diligence refs. | Decision trail stores research refs and compatibility summaries. | Projection shows product-universe coverage, target-market status, and review state. |
| Suitability report | Intake may include prior report attachment ref. | Receives summary and draft metadata only. | Suitability-report store owns draft body, approval, and issue record. | Decision trail stores approval and issue refs; transcript records generated draft reasoning when relevant. | Projection shows draft / approval / issue state, not raw report text by default. |

## Failure And Escalation Paths

| Failure | Trigger | Path |
|---|---|---|
| Intake contract violation | Channel payload fails schema validation. | Reject at intake port; record contract violation; no workflow start. |
| Classification failure | LLM provider output is schema-invalid or route unavailable. | Move to `failed_classification`; projection shows technical exception; no connector action. |
| Out-of-frame advice scope | Restricted advice, execution-only, targeted support, pension transfer, high-risk investment, cryptoasset, tax, legal, or platform-only request. | Move to `manual_review` or `declined_out_of_scope`; no suitability conclusion. |
| Client identity or authority ambiguity | Prospective retail client, joint applicant, attorney, third-party authority, or introducer basis is unresolved. | Move to `manual_review`; no report issue allowed. |
| Fact-find gap | Necessary information is missing, stale, inaccurate, or contradictory. | Move to `fact_find_incomplete`; adviser enrichment required; no personal recommendation. |
| Risk profiler failure | `sandbox-attitude-to-risk-profiler` errors or returns contract-invalid result. | Move to `failed_risk_profile`; record gateway verdict and connector error ref. |
| Risk-profile mismatch | Stated preference, profiler band, narrative evidence, experience, or objectives disagree materially. | Request adviser approval or route to manual review; no final suitability conclusion until resolved. |
| Capacity tool failure | `sandbox-capacity-for-loss-tool` errors or returns contract-invalid result. | Move to `failed_capacity_for_loss`; no suitability conclusion. |
| Capacity concern | Capacity is limited, negative, dependency-sensitive, or inconsistent with objectives. | Route to adviser review; conclusion may be unsuitable or manual review. |
| Vulnerability support unresolved | Support need, authority issue, or communication adjustment may affect understanding or consent. | Request support approval or route to manual review; report issue waits. |
| Platform research failure | `sandbox-platform-research` errors or returns contract-invalid result. | Move to `failed_platform_research`; no suitability conclusion. |
| Independent advice range defect | Product universe is too narrow, platform-biased, missing target-market data, or cannot evidence sufficient range. | Route to adviser or investment committee review; no independent-advice positive conclusion. |
| PROD target-market mismatch | Candidate is negative target market, unsupported by manufacturer information, too complex, or cost / value deficient. | Force unsuitable or manual review; no report issue. |
| Suitability report approval rejected | Adviser rejects report draft, rationale, disadvantage disclosure, risk wording, or support adjustments. | Return to `assessing_suitability` or `drafting_suitability_report` with redraft refs. |
| Gateway idempotency conflict | Connector call repeats with mismatched arguments for same key. | Fail the call, record audit verdict, and route to technical exception. |
| Replay side-effect risk | Replay reaches connector action. | Use dry-run or recorded-action handling; compare proposed action and verdict without applying side effects. |

## Banned And Ambiguous Terms

| Banned / ambiguous term | Replacement | Reason |
|---|---|---|
| Case | Advice enquiry, fact-find summary, risk-profile assessment, suitability conclusion, or suitability report. | Too generic; hides the lifecycle record being discussed. |
| Lead | Advice enquiry or prospective retail client. | Sales language hides conduct obligations and premature customer relationship assumptions. |
| Customer | Prospective retail client, retail client, or Consumer Duty retail customer when citing FCA source language. | "Customer" is broad and can obscure FCA client-category and suitability obligations. |
| Client | Prospective retail client before report issue; retail client when FCA category or service state is meant. | Calling the person a client too early can overstate the advice relationship in domain docs. |
| Recommendation | Suitability conclusion, report draft, or personal recommendation only when the FCA regulated concept is intended. | Unqualified "recommendation" blurs agent-proposed analysis and adviser-approved personal recommendation. |
| Advice | Advice service scope, independent advice, factual information, guidance, or personal recommendation as applicable. | "Advice" is a regulated and overloaded word; the workflow must name the exact concept. |
| Risk score | Attitude-to-risk band, risk-profile status, or capacity-for-loss status. | A single numeric score is not the domain output and can mask mismatch evidence. |
| ATR pass | Risk-profile assessment. | The profiler produces evidence; it does not pass or fail a person. |
| Affordable risk | Capacity-for-loss status or stress outcome. | "Affordable" is imprecise for loss-bearing ability and foreseeable harm. |
| Product pick | Product candidate or platform research result. | The workflow records research and suitability evidence; it does not casually pick products. |
| Whole of market | Independent advice universe or sufficient range of relevant products. | FCA independence rules are more precise than the colloquial phrase. |
| Robo-advice | Not used. | UC3 is adviser-approved decision support, not an automated advice product. |
| Clearance | Approval package, adviser approval, support handoff, or suitability report issue. | The workflow records governed decisions; it does not declare regulatory clearance. |
| Tool | Domain commands or connector adapters. | "Tool" is platform vocabulary for the Tool Gateway; domain docs use domain verbs. |

## R4 Local POC Boundaries

UC3 R4 is a synthetic local proof of the architecture:

- local synthetic data only;
- no production advice service, client data, household data, health data,
  pension data, investment platform, provider, product-research service,
  fact-find system, CRM, custody, dealing, e-signature, or ongoing-review
  system;
- no regulated personal recommendation, financial promotion approval,
  discretionary management, trading, client-money, platform onboarding,
  complaint, redress, or ongoing review workflow;
- no COBS 9A, COBS 19, pension transfer, pension conversion, pension opt-out,
  insurance-based investment product, annuity purchase, or drawdown-specific
  advice path without a later official-source verification slice;
- one use-case runnable path is enough for R4 once implementation begins, but
  no channel is described as runnable until its own contract, fixture or
  sandbox injection path, normalisation, provenance, idempotency, and
  workflow-start handoff are evidenced;
- UC3 runtime work waits for the later R4 sequence after shared-surface
  generalisation, UC1 connector persistence completion, and provider / replay
  hardening.

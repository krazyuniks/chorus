---
type: project-doc
status: active
date: 2026-05-20
phase: R1
---

# R1 Use Case Confirmation

This artefact records the final UC2 and UC3 selections, the regulator for
each, the inbound-channel shape for each, and the adapter-reuse hypothesis
across UC1, UC2, and UC3. It is the R1 confirmation step required by the
engineering reset roadmap.

## Use Case Selections (Confirmed)

| Slot | Use case | Regulator | Status |
|---|---|---|---|
| UC1 | UK personal-lines insurance broking inbound quote qualification | FCA (general insurance distribution: ICOBS, PROD 4, Consumer Duty) | Confirmed. Fully modelled in `product-brief.md` and `domain-model.md`. |
| UC2 | UK legal services intake and conflict check, corporate / commercial practice area | SRA (Code of Conduct, conflict-of-interest rules, AML obligations under the Money Laundering Regulations) | Confirmed. Practice area narrowed to corporate / commercial. |
| UC3 | UK independent financial advice (IFA) inbound enquiry | FCA (retail investment advice: COBS 9 suitability, PROD, Consumer Duty) | Confirmed. Advice shape narrowed to full independent financial advice (not restricted advice or platform onboarding). |

The three use cases sit under two regulators (FCA, SRA) and across three
distinct conduct shapes (ICOBS general insurance distribution, SRA professional
conduct plus AML, COBS retail investment advice). Within the FCA, UC1 and
UC3 contrast cleanly because non-advised general insurance distribution and
advised retail investment business carry materially different conduct
disciplines, even though they share the same regulator.

## Narrowing Decisions Inside UC2 And UC3

UC2 and UC3 each have a chosen sub-scope. The narrowing was made on the
basis of "most ambitious choice that best validates the architecture", not
on incremental risk; the architecture surface that has the most to prove
sits at the most regulator-demanding sub-scope.

### UC2 narrowing: corporate / commercial legal intake

UC2 narrows to corporate / commercial legal intake (commercial transactions,
contract advice, dispute resolution) rather than private client or
conveyancing. Reasons:

- Maximum contrast with UC1. UC1 is B2C, single-customer; UC2 corporate is
  B2B, multi-party (multiple corporate entities, beneficial owners,
  intermediaries). The intake shape stresses different parts of the domain
  model (party identification, relationship mapping, beneficial-ownership
  extraction).
- Heaviest connector port exercise. Corporate intake requires KYC checks,
  beneficial-ownership lookup, and a substantive conflict-of-interest check
  across the firm's existing client base. The connector adapter inventory
  is larger and more varied than private-client or conveyancing intake.
- Distinct audit shape. SRA Code of Conduct plus AML record-keeping plus
  conflict-of-interest evidence produce an audit shape that does not overlap
  with FCA ICOBS or COBS. Compliance review across the three use cases must
  consume meaningfully different decision-trail content.

### UC3 narrowing: independent financial advice

UC3 narrows to independent financial advice rather than restricted advice
or platform-only onboarding. Reasons:

- Heaviest LLM provider port stress. Suitability work under COBS 9 requires
  free-text fact-find, attitude-to-risk narrative, capacity-for-loss
  reasoning, and (where in scope) ESG-preference capture. The LLM provider
  port has to carry rich, structured reasoning over multi-turn input and
  produce a suitability statement that withstands compliance review.
- Strongest audit-completeness invariant. Every suitability conclusion in
  COBS 9 must be evidenced. The decision-trail port has to record the
  inputs, the suitability tests applied, and the rationale at a level of
  detail that exceeds UC1's qualification verdict and UC2's conflict
  determination.
- Cross-FCA-regime contrast with UC1. Two FCA use cases under different
  conduct regimes (ICOBS general insurance distribution vs COBS retail
  investment advice) demonstrate that the architecture spans conduct
  shapes even within one regulator, not only across regulators.

## Inbound Channel Shape Per Use Case

| Use case | Channels |
|---|---|
| UC1 | Email, web enquiry form, partner-portal submission. Three channel adapters behind the intake port. |
| UC2 | Email (most common in corporate work), structured intake form on the firm's website, referral inbound from intermediary firms (introducer email plus attached engagement-letter draft). Three channel adapters. |
| UC3 | Web enquiry form (most common for IFA acquisition), email, partner referral from an introducer (accountant, solicitor, mortgage broker). Three channel adapters. |

The channel mix differs across use cases. The intake port stays the same;
the channel adapter inventory differs and the normalised payload at the
domain side carries channel-specific provenance.

## Adapter-Reuse Hypothesis

The R1 product question 11 selection was "all four": intake channel,
connector inventory, approval policy, and regulator-specific audit shape
should all vary across UC1, UC2, and UC3, with the domain core, the LLM
provider port adapter, and the projection / observability sinks remaining
constant.

The hypothesis the R3 / R4 work must validate:

| Surface | UC1 | UC2 | UC3 | Reuse hypothesis |
|---|---|---|---|---|
| Intake port (the port) | Same. | Same. | Same. | The port stays constant. |
| Intake channel adapters | Email, web form, partner portal. | Email, intake form, intermediary referral inbound. | Web form, email, partner referral. | Adapters vary. Each channel adapter is a separate plug-in. Adapter contract surface stays uniform. |
| LLM provider port and adapter | Same OpenAI-SDK-against-OpenAI-compatible-endpoint adapter, same route catalogue shape. | Same. | Same. | Provider-neutral adapter stays constant across use cases. Route catalogue entries vary per call but the shape is uniform. |
| Connector port (the port) | Same. | Same. | Same. | The port stays constant. |
| Connector inventory | Sandbox CRM, sandbox underwriter referral inbox, sandbox decline ledger, sandbox outbound comms (gated). | Sandbox client management system, sandbox conflict-check connector, sandbox KYC / beneficial-ownership connector, sandbox AML record store, sandbox engagement-letter store. | Sandbox client management system, sandbox attitude-to-risk profiler connector, sandbox capacity-for-loss tool, sandbox suitability-report store, sandbox platform-research connector. | Adapter inventory varies. The Tool Gateway adapter registry (R3) lets each use case ship its own connector adapters without churning shared code. |
| Approval policy | Single gate on outbound customer comms (missing-data request). All internal decisions are agent-proposed with audit trail. | Multiple gates likely: engagement letter send, conflict-of-interest acceptance with declared conflicts present, AML enhanced-due-diligence flag. Internal decisions still agent-proposed for routing. | Multiple gates likely: suitability statement send, attitude-to-risk classification confirmation, vulnerability-marker-triggered handoff. | Policy varies per use case. Approval policy lives in the policy snapshot, not in workflow code. |
| Audit / transcript ports | Same. | Same. | Same. | Both audit ports stay constant. The replay-as-eval substrate applies uniformly. |
| Decision-trail content | ICOBS best interests, demands and needs, target market (PROD 4), Consumer Duty foreseeable harm. | SRA Code of Conduct duties (best interests, confidentiality, integrity), conflict-of-interest determination, AML risk-rating. | COBS 9 suitability test, attitude-to-risk assessment, capacity-for-loss, FCA Consumer Duty foreseeable harm, target market under PROD. | Content varies. The shape is the structured decision-trail record; the conduct-hook fields are regulator-specific extensions. |
| Projection sink | Same projection adapter; per-use-case read-model schemas. | Same. | Same. | Sink stays constant. Read models differ per use case (R3 splits projection.py along port boundaries). |
| Observability sink | Same. | Same. | Same. | Sink stays constant. Correlation identifiers and trace shapes are uniform. |
| Workflow spine | Same intake -> classification -> context gathering -> proposed action -> approval where needed -> routing -> closure shape. | Same shape. The decision is "conflict determination plus engagement decision" not "qualification verdict", but the spine is the same. | Same shape. The decision is "suitability conclusion plus next-step recommendation" not "qualification verdict", but the spine is the same. | The workflow spine reuses across all three and is parameterised per use case. |

The adapter-reuse hypothesis is the centre of the architectural thesis:
the named ports plus the workflow spine carry across three regulators
with no deformation of the core, while the adapter inventory, the
policy snapshot content, and the conduct-hook content vary per use case.

R3 (contract and code terminology refactor) and R4 (local POC readiness)
together produce the evidence for or against the hypothesis. R1 commits
to the shape; the validation is downstream.

---
type: project-doc
status: active
date: 2026-05-20
phase: R1
---

# R1 Exit Criteria

R1 is documentation-only. The exit criteria below confirm that R1 has
produced everything the roadmap requires before R2 (documentation
architecture refactor) and the ADR writing pass can start.

## Artefacts Produced

| Artefact | Path | Status |
|---|---|---|
| Product brief for UC1 | `docs/product-brief.md` | Complete. |
| Domain model for UC1 | `docs/domain-model.md` | Complete. |
| R1 use case confirmation (UC2, UC3) | `docs/r1-use-case-confirmation.md` | Complete. |
| R1 adapter mapping | `docs/r1-adapter-mapping.md` | Complete. |
| R1 exit criteria | `docs/r1-exit-criteria.md` | This document. |
| Vault Chorus records updated | `records/radianit/projects/chorus/README.md` (vault) | Complete; see vault commit. |

No ADRs are written in R1. The ADR writing pass is scheduled after R2.

## Decisions Confirmed

| Decision | Confirmed value |
|---|---|
| UC1 market segment | UK personal lines. |
| UC1 broker positioning | Broker firm receiving customer enquiries (B2C distribution under FCA). |
| UC1 inbound channels | Email, web enquiry form, partner / agent portal submission. Telephony notes deferred. |
| UC1 workflow scope | Qualification plus underwriter referral routing. Pricing, quote issuance, binding, renewals, and claims are out of scope. |
| UC1 broker IT integration | All internal sandboxes. No real-world broker platform (Acturis, Open GI, SSP, Insurly) modelled. |
| UC1 approval policy | Single synchronous gate on outbound customer comms (missing-data request). Internal decisions (classification, demands-and-needs, risk-acceptability flag, qualification verdict, routing) are agent-proposed and recorded on the decision trail without a synchronous approval gate. |
| UC1 FCA conduct touch points | Customer's best interests rule (ICOBS 2.5.-1R, pending exact section verification in R3), Consumer Duty (PRIN 12 plus cross-cutting rules, pending verification), demands and needs (ICOBS 5, pending verification), PROD 4 target market. All four hooks surfaced on the decision trail. |
| UC1 synthetic-data shape | About 30 enquiries under `fixtures/uc1/`. Mix of motor, home, travel, pet; single and joint applicants; varying risk and completeness; vulnerability markers on a subset; channel distribution roughly even across email, web form, partner portal. |
| UC2 selection | UK legal services intake plus conflict check, corporate / commercial practice area, SRA-regulated. |
| UC3 selection | UK independent financial advice (IFA) inbound enquiry, FCA-regulated under COBS 9 suitability. |
| Adapter-reuse target | All four surfaces vary across UC1 / UC2 / UC3: intake channel, connector inventory, approval policy, regulator-specific audit shape. Domain core, LLM provider port adapter, projection sink, and observability sink stay constant. |

## Existing Code Disposition

The reset bundle's `current-state-inventory.md` lists implementation to
preserve, reframe, or retire. R1 confirms the per-component disposition
against the now-fleshed-out UC1.

| Component | Disposition after R1 |
|---|---|
| Lighthouse workflow code (`chorus/workflows/lighthouse.py`) | Preserved as historical evidence. R3 retires or rewrites it under the refactored workflow spine (Smell 1 in `code-refactor-directions.md`). Lighthouse is no longer the project's named exemplar; UC1 (insurance broking) takes that role. |
| Support Triage workflow code (`chorus/workflows/support.py`) | Retired as a named exemplar. Its second-workflow-proof role passes to UC2 (legal corporate intake). Code stays in the repo until R3 retires or rewrites it under the refactored spine. |
| Agent Runtime (LangGraph executor) | Preserved through R2; removed in R3. Reasoning runs through the LLM provider port directly using the OpenAI-SDK-against-OpenAI-compatible-endpoint adapter. ADR 0012 is reversed in the post-R2 ADR pass. |
| Tool Gateway (`chorus/tool_gateway/gateway.py`) | Preserved. The hardcoded match dispatch (Smell 2) is replaced by an adapter registry in R3. Grants, modes, idempotency, approval hooks, redaction, and verdicts stay. |
| Contracts (JSON Schema plus generated Pydantic) | Preserved. R3 rewrites them around the six named ports plus the use-case-specific payload schemas at the intake and connector ports. |
| Postgres audit store | Preserved. R3 splits the single audit store into the structured decision-trail port and the full-fidelity transcript port. |
| Redpanda event stream | Preserved. Event shapes move under the named-port discipline in R3. |
| Eval / replay harness | Preserved. Shape moves to invariant-based eval plus replay-as-comparison per `eval-reshape-directions.md`; the path-enumeration fixture set is retired during R3 / R4. |
| BFF / UI inspection | Preserved. R2 reorganises the read-models around the named ports. R4 wires per-use-case read models. |
| Local connector sandboxes (Mailpit, local CRM, Radicale, ticket sandbox) | Preserved as adapter examples. R3 / R4 add use-case-specific connector adapters (sandbox CRM, sandbox referral inbox, sandbox decline ledger, sandbox outbound comms for UC1; sandbox conflict check, sandbox KYC / BO, sandbox AML record store for UC2; sandbox attitude-to-risk profiler, sandbox capacity-for-loss tool, sandbox suitability-report store, sandbox platform-research for UC3). |
| `chorus/persistence/projection.py` (~1,572 lines) | Preserved. R3 decomposes it along port boundaries (Smell 3). |
| `chorus/eval/run.py` (~2,219 lines) | Preserved. R3 decomposes it into an invariant-based eval core plus per-use-case eval modules (Smell 3). |
| `chorus/doctor.py` (~612 lines) | Preserved. R3 splits it into per-port health probes plus an environment-check module (Smell 3). |
| Phase 2E production-readiness pack (identity / IAM, secrets, deployment topology, backup / restore, retention / audit storage) | Parked. Deployment is removed from the Chorus repo and reframed as a future vault-level RIT project. The Phase 2E artefacts become input material for that future project. |

## What R2 Starts From

R2 (documentation architecture refactor) starts from the following:

- The reset bundle in `docs/transformation/` is the authority for the
  architectural thesis and the engineering reset roadmap.
- The R1 artefacts in `docs/` (product brief, domain model, use case
  confirmation, adapter mapping, exit criteria) are the authority for the
  product, the domain language, and the adapter shape.
- The vault Chorus records point to the R1 artefacts and continue to hold
  the vault-only audience model (`audience-and-purpose.md`).
- The pre-reset top-level docs (`README.md`, `docs/overview.md`,
  `docs/architecture.md`, `docs/evidence-map.md`, `docs/runbook.md`,
  and the larger Phase 2 docs) are the rewrite targets for R2.
- The four code smells in `transformation/code-refactor-directions.md` are
  the rewrite targets for R3.
- The eval reshape direction in `transformation/eval-reshape-directions.md`
  is the rewrite target for R3 / R4.

R2 deliverables, per the roadmap:

- restructured `README.md`, `docs/overview.md`, `docs/architecture.md`,
  `docs/evidence-map.md`, `docs/runbook.md`, and roadmap docs around the
  ports-and-adapters thesis and the confirmed use cases;
- a single architecture diagram showing the hexagon with the six named
  ports and the current adapter inventory;
- chronological Phase 2 ledger detail demoted into archival sections;
- removed or rewritten stale continuation prompts;
- separated local POC readiness from any future hosting concern.

The ADR writing pass is scheduled after R2:

- LangGraph reversal (reverses ADR 0012);
- LLM provider port ADR;
- audit ports plus replay-eval ADR;
- domain refocus ADR.

No ADRs are written in R1.

## R1 Open Questions

None deferred at the product-decision level. The items below are explicitly
carried forward as R2 / R3 work rather than open R1 product questions:

- Exact regulatory citation numbers (ICOBS 2.5.-1R, ICOBS 5, PROD 4,
  Consumer Duty rules) used inside the policy bundle. Currently noted as
  pending verification in the product brief and the domain model. To be
  verified during R3 before any policy snapshot ships in code.
- Whether the underwriter referral inbox is a separate sandbox adapter
  from the standard quoting queue or a tagged subscription on the same
  adapter. To be resolved during R3 connector adapter registry work.
- The exact shape of the customer-profile store boundary inside the broker
  firm. To be resolved during R3 contract refactor.

## Sign-Off

R1 exit criteria are satisfied. The project is ready to proceed to R2
(documentation architecture refactor) when scheduled.

R2 is the next phase. The ADR writing pass follows R2. R3 (contract and
code terminology refactor) follows the ADR pass. R4 (local POC readiness)
follows R3.

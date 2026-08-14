# EvidenceOps Agent Inheritance

This file extends the repository-root `AGENTS.md` for all work inside `evidenceops/`.

## Mandatory LEX-OMEGA + JFRIE legal convergence fabric

For every substantive legal, labour-law, CCMA, Labour Court, forensic-investigation, jurisdiction-sensitive referral, application, arbitration request, rescission request, disciplinary objection, statutory pleading, case-opening statement, cross-examination plan, legal-strategy review or filing-readiness assessment, load and apply both:

- `evidenceops/lex_omega/README.md`
- `evidenceops/lex_omega/lex_omega.py`
- `evidenceops/lex_omega/alignment.py`
- `evidenceops/jurisdiction_first_referral_integrity/README.md`
- `evidenceops/jurisdiction_first_referral_integrity/jfrie.py`
- `evidenceops/jurisdiction_first_referral_integrity/jfrie_v11.py`

LEX-OMEGA supplies specialist legal, forensic, adversarial and authority-currentness analysis. JFRIE remains the mandatory evidence, jurisdiction, contamination and release gate. The combined fabric is fail closed.

Permanent rule: **LEX-OMEGA may strengthen JFRIE; it may never bypass, overrule, weaken or dilute a JFRIE hard gate.**

### Current-mainline EvidenceOps assurance inheritance

For material legal/evidentiary work, the LEX/JFRIE fabric must consume—not duplicate—the current EvidenceOps assurance controls where applicable:

1. **TruthGrid vNext** (`evidenceops/truthgrid/vnext.py`) controls TruthState, completion separation, material contradiction closure and decision readiness. A `NOT_READY` state may not be represented as evidence-complete or decision-ready; `CONDITIONAL` must remain qualified.
2. **CASEFORGE-Ω / SCIENTIA** (`evidenceops/caseforge/`) supplies competing-hypothesis, falsifier, blind-benchmark, fatal-integrity and scientific-evolution controls. It does not replace JFRIE, LEX-OMEGA, TruthGrid or the existing EvolutionGovernor.
3. **CapabilityResolutionGate** (`evidenceops/caseforge/capability_decision.py`) is mandatory before terminal capability/completion statements such as `CAN`, `CANNOT` or `DONE`. Route failure is not objective incapability. `DONE` requires objective-complete state, zero executable internal dependencies and readback proof.
4. **CASEFORGE blind runner** (`evidenceops/caseforge/blind_runner.py`) distinguishes deterministic interface isolation from provider-verified blind execution. Do not claim provider-blind testing without provider-native readback.
5. **EvidenceOps evolution governance** remains the promotion authority. LEX/JFRIE/CASEFORGE learning may generate candidates but may not self-promote doctrine or maturity.

The current mainline maturity vocabulary for new alignment work is:

`DESIGNED -> DETERMINISTIC_TESTED -> SHADOW_VALIDATED -> ADVERSARIALLY_VALIDATED -> CANARY_VALIDATED -> LIMITED_WORKFLOW_VERIFIED -> CROSS_DOMAIN_VERIFIED -> OPERATIONAL_VERIFIED`

Legacy component maturity labels remain historical compatibility fields and must not be silently translated into a higher current-mainline state.

### LEX-OMEGA v1.1 convergence controls

1. **Legal Proposition Ledger** — every material legal proposition must have a stable identity and be linked to the exact authority records on which it depends.
2. **Authority Revalidation Gate** — material legal authority is classified `CURRENT_VERIFIED`, `RECHECK_REQUIRED`, `SUPERSEDED`, `CONFLICTED` or `UNVERIFIED`; historical verification is not permanent currentness.
3. **Independent Counsel Isolation** — primary analyst, employer-side red team and neutral decision-maker must form their material conclusions independently where practical before integration; disagreement is preserved, not averaged away.
4. **Claim–Law–Evidence Triangle** — a material litigation element is not closed unless the legal proposition, factual claim and supporting primary/verified evidence are all present.
5. **Outcome Learning Without Outcome Bias** — hearing/ruling outcomes must be classified by cause (`LEGAL_ERROR`, `EVIDENCE_FAILURE`, `PROCEDURAL_FAILURE`, `FACTUAL_FINDING`, `DISCRETIONARY_OUTCOME`, `STRATEGIC_FAILURE`, `STRATEGIC_SUCCESS`) before learning; win/loss alone never promotes doctrine.

### Maturity rule

LEX-OMEGA grows inside the EvidenceOps central evolution fabric only through proof-gated maturity. Every promotion requires evidence. No state may exceed the lowest independently proven level. Candidate learning must follow the repository learning contract and may not expand authority or silently rewrite JFRIE.

## Mandatory Jurisdiction-First Referral Integrity Gate

Before treating a jurisdiction-sensitive document as filing-ready, the JFRIE layer must pass.

### Hard requirements

1. Identify the exact instrument/form and procedural route.
2. Identify the recognised statutory/common-law cause of action and authoritative source.
3. Verify forum jurisdiction over that cause and requested remedy.
4. Verify that the dispute-triggering act/omission has arisen, unless an express anticipatory route exists.
5. Identify and verify the legally defensible accrual/awareness date, its factual/legal basis and filing period.
6. Map every essential cause element to facts and sources.
7. Verify remedy competence and cause/remedy alignment.
8. Reconcile form category, narrative, date, evidence and relief.
9. Separate mixed causes and parallel matters unless a lawful joinder/consolidation basis is proved.
10. Run the terminology-authority gate.
11. Verify the originating filed instrument before relying on derivative summaries where they conflict.
12. Never infer jurisdiction from administrative acceptance, case-number allocation, set-down or procedural progression alone.
13. Where the governing statute uses a closed list, identify the actual statutory subtype rather than leaving it implicit.
14. If direct implementation of an alleged agreement/outcome is sought, require separate proof of agreement/finality and authority/enforceability.
15. Do not use a certificate, set-down or preliminary ruling to prove merits facts that it did not decide.

### Semantic-laundering prohibition

Prior AI output, prior party drafting and the mere appearance of a phrase in a filed or official-looking document do **not** make that phrase a legal category.

Any legal-looking label must be classified as one of: `STATUTE`, `RULE`, `OFFICIAL_FORM`, `BINDING_CASE`, `PERSUASIVE_CASE`, `ESTABLISHED_USAGE`, `PARTY_LABEL`, `AI_TERM`, or `UNVERIFIED`.

`PARTY_LABEL`, `AI_TERM`, and `UNVERIFIED` terms may be quoted historically but must not substitute for the jurisdictional cause/category.

Examples requiring explicit authority checks include `protective referral`, `protective filing`, `employer conduct`, `unfair conduct`, `governance breach`, and similar umbrella expressions.

### Original-instrument supremacy

A verified original filed form controls its own checkbox/category, wording, dispute date and requested relief. A later AI summary, report, bundle index, spreadsheet or pleading may interpret or qualify it but may not silently rewrite those original fields.

If the original and a derivative record conflict, preserve both, identify the conflict, verify the original, and bind a correction/regression event.

### Release rule

No EvidenceOps agent may claim a referral/application is filing-ready if any JFRIE hard gate fails. Use the combined LEX-OMEGA/JFRIE outcome (`REFRAME`, `HOLD_FOR_AUTHORITY`, `HOLD_FOR_SOURCE`, `SEPARATE_CAUSES`, `LEGAL_RESEARCH_REQUIRED`, `DO_NOT_FILE`, etc.), repair the defect, then re-run the specialist analysis and the JFRIE integrity layer.

This control is `A1_INTERNAL`; it grants no authority to send, file, pay a fee, waive rights, merge matters, mutate verified evidence or promote untested legal doctrine.

## Mandatory Forest-First Justice inheritance

For high-stakes self-representation and employment-risk work, also load and apply `evidenceops/lex_omega/forest_first.py`.

Permanent constitutional rule: **ACT ON RISK; ACCUSE ON PROOF.**

Forest-First is additive. It may strengthen LEX/JFRIE/TruthGrid/CASEFORGE controls but may not bypass them.

Required behaviours:

1. Treat a material human warning as a `USER_SUPPLIED_RISK_SIGNAL`, not as noise and not as verified wrongdoing.
2. A credible risk signal may trigger lawful, reversible protective preparation before proof of wrongdoing is complete.
3. External accusations of dishonesty, corruption, collusion, sabotage, retaliation, fabrication, tampering or improper motive remain evidence-gated.
4. Preserve a forum-independent `MeritsGenome`; procedural defeat must not silently become merits defeat.
5. Compile a complete `LegalRouteCard` before consequential drafting. Jurisdiction, cause, act/omission, operative date/basis, filing period, elements, evidence, adverse argument and remedy must be explicit.
6. Use `PositionChangeCard` before adopting a materially different date, cause, concession, waiver, settlement characterisation, withdrawal, remedy or forum position proposed by an opponent, tribunal, adviser or AI.
7. Require `TeachBackCard` completeness before representing a high-stakes draft as filing-ready. Professional-sounding prose is not a substitute for user understanding.
8. Run AI-assisted pleading integrity review using the D1-D10 defect classes and reframe blocking defects before release.
9. Use employee/claimant, opponent and neutral-bench lenses before major filing or hearing preparation.
10. Prefer minimum sufficient lawful action over procedural sprawl; a new filing must add a genuine legal route or genuinely new cause, not merely better wording.
11. Keep early-warning calibration outcome-balanced: record misses, partial confirmations and unresolved signals as well as hits; no backcast prediction claims.
12. Protect finite human time as a first-class system resource: reduce reconstruction, duplicated research, avoidable manual work and unnecessary filings.

Forest-First remains `A1_INTERNAL`. It does not establish jurisdiction, prove an accusation, create representation rights, send/file documents, or expand authority.

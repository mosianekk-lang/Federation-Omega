# EvidenceOps Jurisdiction-First Referral Integrity Engine (JFRIE)

**Component ID:** `JFR-LEG-001`  
**Version:** `1.1.0`  
**Authority ceiling:** `A1_INTERNAL`  
**External filing authority:** none  
**Release posture:** fail closed

JFRIE is the mandatory pre-drafting and pre-release gate for jurisdiction-sensitive legal instruments, including labour referrals, arbitration requests, rescission applications, disciplinary objections, court applications and similar statutory pleadings.

Its purpose is to prevent recurring drafting failures in which preservation language, broad narrative, later summaries or lawyer-sounding terminology obscure the actual statutory cause of action, forum jurisdiction, accrual date, essential elements and competent remedy.

## Core doctrine

A legal filing is not released merely because its facts appear compelling. It must first identify a legally recognised cause of action and show that the selected forum has power to determine that cause and grant the requested remedy.

The engine applies this order:

1. **Instrument identification** — identify the exact statutory form/application and route.
2. **Cause-of-action gate** — identify the precise recognised cause and authoritative source.
3. **Forum/jurisdiction gate** — verify forum power over that cause and remedy.
4. **Dispute maturity gate** — verify that the triggering act/omission has arisen unless an express anticipatory route applies.
5. **Accrual/date gate** — identify the defensible dispute/awareness date, its factual/legal basis and filing period.
6. **Elements gate** — identify every essential jurisdictional/substantive element.
7. **Fact-to-element gate** — map primary facts and sources to each required element.
8. **Remedy competence gate** — ensure requested relief falls within forum powers and matches the cause.
9. **Characterisation consistency gate** — reconcile form category, narrative, evidence, date and relief.
10. **Mixed-cause separation gate** — separate ULP, discrimination, protected-activity, contract, grievance, information-access, governance and other lanes unless each has its own lawful basis and purpose.
11. **Terminology authority gate** — every legal-looking label must trace to statute, rule, official form, authority or established usage. Prior AI output and party labels are not authority.
12. **Source/provenance gate** — material propositions must be source-controlled and proof-limited.
13. **Parallel-matter gate** — preserve separate case identities unless lawful joinder/consolidation exists.
14. **Adversarial red-team gate** — test the filing as the opposing lawyer and decision-maker would.
15. **Compression gate** — reduce the originating statement to the minimum facts needed to establish cause, jurisdiction, date and remedy.
16. **Release gate** — no external-use draft is filing-ready unless all hard gates pass.

## v1.1 referral-autopsy regression layer

`jfrie_v11.py` adds deterministic protections learned from historical drafting failures. These controls are generic and contain no private case facts.

### R1 — Original filed instrument overrides derivative summaries

The original filed form, verified page-by-page where necessary, controls its own fields. A later report, AI summary, bundle index or pleading may explain the original but may not silently rewrite its dispute type, checkbox, date, relief or wording.

If derivative records conflict and the original has not been verified, release fails closed.

### R2 — Administrative processing is not jurisdiction

Registration, acceptance at intake, allocation of a case number, set-down, conciliation scheduling or other administrative progression does not by itself prove statutory jurisdiction.

A proposition such as “the forum processed the case, therefore jurisdiction was already exercised and cannot later be questioned” is prohibited.

### R3 — Closed-list statutory categories may not remain implicit

Where legislation creates a closed list of actionable categories, the draft must identify the category actually relied upon. A generic umbrella label cannot require the commissioner, court or opposing party to guess the statutory subtype.

### R4 — Dispute date requires an accrual theory

A date may not be selected merely because it keeps a filing inside a limitation period. The date must be tied to the act, omission, decision, awareness event or continuing-duty rule relied upon in law and fact.

If later papers advance a different date, the two theories must be reconciled rather than silently substituted.

### R5 — Direct agreement enforcement requires agreement and authority proof

A filing seeking compelled implementation of an alleged agreement or outcome must separately identify evidence of agreement/finality and evidence of authority, legality and enforceability. A meeting record, unilateral minutes or later procedural certificate cannot substitute for those requirements.

### R6 — Procedural certificates and rulings do not prove merits

A certificate, set-down, intake acceptance or preliminary ruling may prove procedural state or a limited jurisdictional holding. It may not be used as proof that an agreement existed, an entitlement was established, misconduct occurred, retaliation was proved or a remedy is due unless the instrument actually decided that issue.

### R7 — Remedy must match cause and forum

A referral may not mix remedies belonging to different legal lanes without identifying the legal basis and forum power for each. Contextual facts may remain context; they do not automatically become independent relief claims.

### R8 — Mixed legal lanes need separate authority maps

Where one narrative contains more than one possible lane, each lane must have a source of law, forum route, timing rule and remedy. If those cannot be mapped, the engine returns `SEPARATE_CAUSES` and blocks release.

### R9 — Secondary questionnaire answers do not silently replace the primary dispute field

Many forms contain secondary questions such as discrimination, interpreter or representation fields. Those answers are recorded separately. They may create an additional legal issue, but they do not automatically rewrite the primary dispute-type field.

### R10 — Semantic laundering remains prohibited

An AI-generated or party-created phrase does not become law because it later appears in a filed form, bundle, email or previous AI analysis. Repetition is not authority.

## Hard gates

JFRIE v1.0 hard gates remain mandatory. JFRIE v1.1 additionally treats R2, R3, R4, R5, R6, R7 and R8 as hard release controls, and treats unresolved original-form provenance as a hard control when derivative summaries conflict.

Possible decisions include:

- `PASS`
- `PASS_WITH_LIMITATIONS`
- `HOLD_FOR_AUTHORITY`
- `REFRAME`
- `SEPARATE_CAUSES`
- `AMEND_OR_CLARIFY`
- `RE_REFER_IF_LEGALLY_OPEN`
- `DO_NOT_FILE`
- `LEGAL_RESEARCH_REQUIRED`

## Mandatory cause sentence

Before a referral may pass, the system must be able to complete this sentence from verified law and evidence:

> On **[date]**, the employer **[specific act/omission]**, which constitutes **[recognised statutory cause/category]** under **[section/rule]** because **[essential elements]**, and the competent relief sought is **[forum-authorised relief]**.

If that sentence cannot be completed accurately, drafting stops and the matter is classified before prose is generated.

## Terminology authority and semantic-laundering control

Legal labels are classified as:

- `STATUTE`
- `RULE`
- `OFFICIAL_FORM`
- `BINDING_CASE`
- `PERSUASIVE_CASE`
- `ESTABLISHED_USAGE`
- `PARTY_LABEL`
- `AI_TERM`
- `UNVERIFIED`

`PARTY_LABEL`, `AI_TERM` and `UNVERIFIED` terms may be quoted historically but may not substitute for a jurisdictional cause/category.

Examples requiring authority checks include `protective referral`, `protective filing`, `employer conduct`, `unfair conduct`, `governance breach` and other umbrella expressions.

## Source hierarchy

For legal classification, use the strongest available source in this order:

1. current legislation/regulations;
2. current official procedural rules/forms;
3. binding appellate authority;
4. current relevant lower-court authority;
5. official guidance/practice material;
6. verified primary case records;
7. secondary commentary;
8. party submissions;
9. derivative system summaries;
10. prior AI output.

Prior AI output is never authority. A verified original filed instrument outranks a later derivative description of that instrument.

## Federation inheritance

Every Federation Omega / EvidenceOps legal workstream must invoke JFRIE before drafting or approving a jurisdiction-sensitive external filing. The capability is analysis-only and does not authorise sending, filing, paying fees, waiving rights or changing verified evidence.

A workstream that cannot load JFRIE must fail closed on any claim that a legal referral is filing-ready and use `HOLD_FOR_AUTHORITY`, `REFRAME`, `SEPARATE_CAUSES` or `LEGAL_RESEARCH_REQUIRED` until classification is restored.

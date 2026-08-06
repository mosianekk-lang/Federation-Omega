# EvidenceOps Jurisdiction-First Referral Integrity Engine (JFRIE)

**Component ID:** `JFR-LEG-001`  
**Version:** `1.0.0`  
**Authority ceiling:** `A1_INTERNAL`  
**External filing authority:** none  
**Release posture:** fail closed

JFRIE is the mandatory pre-drafting and pre-release gate for jurisdiction-sensitive legal instruments, including CCMA referrals, arbitration requests, rescission applications, disciplinary objections, Labour Court applications and similar statutory pleadings.

Its purpose is to prevent a recurring drafting failure: preservation-first language, broad narratives or lawyer-sounding terminology obscuring the actual statutory cause of action, forum jurisdiction, accrual date, essential elements and competent remedy.

## Core doctrine

A legal filing is not released merely because its facts appear compelling. It must first identify a legally recognised cause of action and show that the selected forum has power to determine it.

The engine applies this order:

1. **Instrument identification** — identify the exact statutory form/application and procedural route.
2. **Cause-of-action gate** — identify the precise statutory or common-law cause relied upon.
3. **Forum/jurisdiction gate** — verify that the selected forum has power over that cause and remedy.
4. **Dispute maturity gate** — confirm that the dispute or triggering event has arisen and is not merely anticipated, unless an express statutory anticipatory route applies.
5. **Accrual/date gate** — identify the legally defensible dispute date, awareness date and filing period.
6. **Elements gate** — list every essential jurisdictional/substantive element.
7. **Fact-to-element gate** — map primary facts and sources to each required element.
8. **Remedy competence gate** — ensure requested relief is within the forum's legal powers.
9. **Characterisation consistency gate** — reconcile form checkbox/category, narrative, evidence, date and relief.
10. **Mixed-cause separation gate** — do not blend ULP, PDA, EEA discrimination, contract, grievance, PAIA, governance or other causes unless each has an identified jurisdictional basis and procedural purpose.
11. **Terminology authority gate** — every legal-looking label must trace to statute, rule, official form, binding/persuasive authority or established legal usage. Prior AI output and party-created labels are not legal authority.
12. **Source/provenance gate** — material propositions must be source-controlled and proof-limited.
13. **Parallel-matter gate** — preserve separate case identities unless a lawful joinder/consolidation direction exists.
14. **Adversarial red-team gate** — test the filing as the opposing lawyer and commissioner would.
15. **Compression gate** — reduce the referral statement to the minimum facts needed to establish the cause and remedy.
16. **Release gate** — no external-use draft is marked filing-ready unless all hard gates pass.

## Hard gates

Gates 1-8 and 11 are hard gates. A failure on any hard gate blocks release.

Possible decisions:

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

Before a referral may pass, the system must be able to complete this sentence without vague umbrella terminology:

> On **[date]**, the employer **[specific act/omission]**, which constitutes **[recognised statutory cause/category]** under **[section/rule]** because **[essential elements]**, and the competent relief sought is **[forum-authorised relief]**.

If that sentence cannot be completed from verified law and facts, drafting stops and the matter is classified before prose is generated.

## Terminology authority and semantic-laundering control

JFRIE assigns every legal label one of these provenance classes:

- `STATUTE`
- `RULE`
- `OFFICIAL_FORM`
- `BINDING_CASE`
- `PERSUASIVE_CASE`
- `ESTABLISHED_USAGE`
- `PARTY_LABEL`
- `AI_TERM`
- `UNVERIFIED`

`PARTY_LABEL`, `AI_TERM` and `UNVERIFIED` terms may be quoted as historical wording but may not be used as jurisdictional categories.

This prevents **semantic laundering**: an AI-generated phrase being inserted into a pleading, then later treated as legally authoritative merely because it appears in a filed or official-looking document.

Examples requiring scrutiny include: `protective referral`, `protective filing`, `employer conduct`, `unfair conduct`, `governance breach`, `occupational detriment` and similar broad labels. These phrases are not automatically invalid; the engine asks whether they are being used descriptively or as a substitute for a recognised cause of action.

## Source hierarchy

For legal classification, use the strongest available source in this order:

1. current legislation and regulations;
2. current official procedural rules/forms;
3. binding appellate authority;
4. current relevant lower-court authority;
5. official guidance/practice manuals;
6. verified primary case records;
7. secondary commentary;
8. party submissions;
9. prior AI output.

Prior AI output is never authority.

## Drafting rule

Preservation language (`without waiver`, `all rights reserved`, `protectively`, `no merger`) may appear only after the cause, jurisdiction, event, date and remedy are clear. It must never substitute for them.

## Current-matter implementation findings

### MPMB2603-25

The original referral had a recognisable section 186(2)(b) unfair-labour-practice lane concerning prolonged precautionary suspension and unfavourable reinstatement conditions, but it also mixed in discrimination allegations. Later procedural papers weakened consistency by foregrounding a different accrual theory instead of the 30 July 2025 dispute date already recorded on the referral, and one later filing misstated the ULP period as 30 rather than 90 days.

**JFRIE classification:** underlying referral `PASS_WITH_LIMITATIONS`; subsequent jurisdiction defence required `REFRAME`.

### MPMB298-26

The referral selected `UNFAIR LABOUR PRACTICE` but described the dispute as selective non-implementation of an agreed corrective/transitional outcome and sought compelled implementation. The later CCMA ruling and controlled hearing materials mapped the dispute to section 186(2)(a), primarily promotion, but the originating wording did not make the statutory subtype explicit and risked sounding like agreement enforcement.

**JFRIE classification:** `AMEND_OR_CLARIFY` / `PASS_WITH_LIMITATIONS`.

### MPMB1435-26

The referral selected `UNFAIR LABOUR PRACTICE` but used the phrase `PROTECTIVE UNFAIR LABOUR PRACTICE REFERRAL`, mixed the absenteeism warning, protected disclosure, unresolved grievance and reinstatement-status relief, and did not expressly identify the section 186(2)(b) disciplinary-action-short-of-dismissal route later used in the controlled bundle.

The underlying warning dispute may still be legally viable; the referral statement diluted its jurisdictional clarity.

**JFRIE classification:** `REFRAME`; `protective referral` is treated as `PARTY_LABEL/AI_TERM`, not a statutory category.

## Federation inheritance

Every Federation Omega / EvidenceOps legal workstream should invoke JFRIE before drafting or approving a jurisdiction-sensitive external filing. The capability is analysis-only and does not authorise sending, filing, paying fees, waiving rights or changing a verified fact.

A workstream that cannot load JFRIE should fail closed on any claim that a legal referral is filing-ready and should use `HOLD_FOR_AUTHORITY` or `LEGAL_RESEARCH_REQUIRED` until classification is restored.

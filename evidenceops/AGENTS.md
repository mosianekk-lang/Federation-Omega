# EvidenceOps Agent Inheritance

This file extends the repository-root `AGENTS.md` for all work inside `evidenceops/`.

## Mandatory Jurisdiction-First Referral Integrity Gate

For every jurisdiction-sensitive legal referral, application, arbitration request, rescission request, disciplinary objection, Labour Court filing, statutory pleading or case-opening statement, load and apply:

- `evidenceops/jurisdiction_first_referral_integrity/README.md`
- `evidenceops/jurisdiction_first_referral_integrity/jfrie.py`

before treating the document as filing-ready.

The gate is fail closed.

### Hard requirements

1. Identify the exact instrument/form and procedural route.
2. Identify the recognised statutory/common-law cause of action and authoritative source.
3. Verify forum jurisdiction over that cause and requested remedy.
4. Verify that the dispute-triggering act/omission has arisen, unless an express anticipatory route exists.
5. Identify and verify the legally defensible accrual/awareness date and filing period.
6. Map every essential cause element to facts and sources.
7. Verify remedy competence.
8. Reconcile form category, narrative, date, evidence and relief.
9. Separate mixed causes and parallel matters unless a lawful joinder/consolidation basis is proved.
10. Run the terminology-authority gate.

### Semantic-laundering prohibition

Prior AI output, prior party drafting and the mere appearance of a phrase in a filed or official-looking document do **not** make that phrase a legal category.

Any legal-looking label must be classified as one of: `STATUTE`, `RULE`, `OFFICIAL_FORM`, `BINDING_CASE`, `PERSUASIVE_CASE`, `ESTABLISHED_USAGE`, `PARTY_LABEL`, `AI_TERM`, or `UNVERIFIED`.

`PARTY_LABEL`, `AI_TERM`, and `UNVERIFIED` terms may be quoted historically but must not substitute for the jurisdictional cause/category.

Examples requiring explicit authority checks include `protective referral`, `protective filing`, `employer conduct`, `unfair conduct`, `governance breach`, and similar umbrella expressions.

### Release rule

No EvidenceOps agent may claim a referral/application is filing-ready if any JFRIE hard gate fails. Use the engine outcome (`REFRAME`, `HOLD_FOR_AUTHORITY`, `LEGAL_RESEARCH_REQUIRED`, `DO_NOT_FILE`, etc.), repair the defect, then re-run the gate.

This control is `A1_INTERNAL`; it grants no authority to send, file, pay a fee, waive rights, merge matters, or mutate verified evidence.

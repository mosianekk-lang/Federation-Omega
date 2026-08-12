# JFRIE v2.0 / EACIA — executable core-parity slice 1

## Version truth

- Canonical policy/control plane: **JFRIE v2.0 / EACIA** (`JFR-LEG-001`, companion `EACIA-INT-002`).
- Historical executable baseline preserved: JFRIE v1/v1.1 referral/jurisdiction gates.
- This source slice: `2.0.0-core-parity-slice-1`.
- `FULL_V2_PARITY = False`.

Source implementation is not provider deployment, not legal merits, and not proof that every C001–C100 control is executable.

## Controls implemented in this slice

The new `jfrie_v2.py` preserves the existing v1/v1.1 release gate and adds deterministic A1-internal controls for:

1. stable claim identity and required provenance fields;
2. legal-category authority provenance;
3. source registration and identity-conflict blocking;
4. parent/copy lineage and true independent-source-root counting;
5. primary/authenticated-source preference over derivative copies;
6. claim dependency graph and artifact-to-claim dependencies;
7. append-preserving claim mutation history;
8. explicit claim release eligibility separate from verification;
9. automatic release-eligibility revocation after claim revision;
10. claim quarantine and downstream dependency review;
11. contamination-radius calculation;
12. affected-artifact recall identification without destroying unrelated content;
13. release-eligibility revocation for quarantined/dependent claims;
14. readback requirement before synchronization can be asserted;
15. excluded-matter resurrection blocking;
16. mandatory TruthGrid/LEX/CASEFORGE-style gate inputs;
17. owner-exclusion gate;
18. post-repair JFRIE recheck gate;
19. version-identifiable release-snapshot requirement;
20. v2 release firewall layered on top of the v1/v1.1 referral/jurisdiction gate.

## Permanent invariants enforced by this slice

- Verification does **not** imply release eligibility.
- Rewording/correction does **not** silently retain release eligibility.
- Quarantine blocks downstream reuse and release eligibility.
- Copies sharing one parent do not multiply independent corroboration.
- Legal categories require authority provenance.
- No synchronization claim without readback.
- No excluded matter may be resurrected through copied history.
- No v2 release may bypass the existing v1/v1.1 jurisdiction/referral gate.
- No final/release-cleared state if any mandatory v2 release blocker remains.

## Explicitly still unimplemented / unproven for full C001–C100 parity

This slice does **not** claim complete executable coverage of the canonical v2 policy. Remaining families include, without limitation:

- broad semantic claim fingerprinting and paraphrase-family detection;
- automated AI-origin/human-origin classification from arbitrary inputs;
- circular-citation detection beyond explicit lineage supplied to the graph;
- source-quality scoring across every canonical factor;
- missing-page / attachment-completeness / thread-reconstruction detectors;
- automatic version-conflict and timestamp-conflict detectors;
- generalized fact/inference/causation laundering detectors;
- prompt/template/memory pollution scanners;
- automatic infected-template child discovery;
- automatic tainted-paragraph/document marking beyond explicit artifact bindings;
- current-law/jurisdiction authority retrieval;
- two-key release implementation where required by the canonical policy;
- provider-bound immutable release snapshot creation;
- post-release integrity monitoring and drift comparison;
- automatic detector generation, shadow benchmark, promotion, federation and readback across all v2 control families;
- provider runtime deployment and provider-native operational readback.

## Promotion rule

This slice may be described as **EXECUTABLE_V2_CORE_PARITY_SLICE** only after exact-head repository admission, regression success and main-branch readback.

It must not be described as `FULL_V2_PARITY`, `OPERATIONAL_VERIFIED`, or provider deployed without the independent proof required for those states.

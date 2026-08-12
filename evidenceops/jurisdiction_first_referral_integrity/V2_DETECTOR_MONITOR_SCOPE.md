# JFRIE v2.0 / EACIA — detector and post-release monitoring slice 2

## Relationship to slice 1

This slice requires the admitted `jfrie_v2.py` core. It does not replace the core release firewall and does not bypass JFRIE v1/v1.1 referral/jurisdiction gates.

`FULL_V2_PARITY = False` remains controlling.

## Implemented detector/monitor families

- deterministic normalized semantic fingerprints;
- exact semantic-duplicate review findings;
- high-similarity paraphrase review candidates;
- claim-dependency missing-reference blocking;
- circular claim-dependency/support blocking;
- copy-carrier independence inflation review using slice-1 source roots;
- hard veto where a release-eligible claim is supported only by AI/derivative/inference/unverified provenance classes;
- required evidence-packet completeness blocking;
- optional packet completeness review;
- same logical source/version with conflicting content fingerprints -> hard block;
- multiple authoritative versions -> explicit supersession/temporal review;
- detector report bound to a graph digest and rejected as stale after claim/source state changes;
- unresolved detector REVIEW findings block release until explicitly dispositioned;
- detector BLOCK findings hard-stop the slice-1 release firewall;
- scoped post-release snapshots over only the released claim/source closure;
- post-release claim/source drift detection and recall-required result;
- unrelated graph/matter changes do not trigger recall for a scoped release snapshot.

## Boundaries

The semantic/paraphrase detector is a deterministic review heuristic, not a legal conclusion and not proof that two propositions are substantively identical.

Detector findings do not decide credibility, admissibility, merits, guilt or remedy. REVIEW findings require explicit disposition. BLOCK findings prevent release only through the JFRIE release-control function.

Post-release monitoring produces a recall-required control result; it does not autonomously send notices, withdraw filings or perform external legal effects.

## Still open after slice 2

Full v2 parity still requires additional families including broader fact/inference/causation-laundering detection, automatic input-origin classification, generalized thread reconstruction, template/prompt/memory contamination scanning, automatic infected-child discovery, broader current-law authority retrieval, provider-bound immutable release storage, richer post-release provider monitoring, and C097-C100 detector-learning/promotion/federation controls.

Provider runtime and provider-native operational readback remain unverified unless independently proven.

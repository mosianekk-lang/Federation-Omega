# JFRIE v2.0 / EACIA — proposition, prompt and template contamination slice 3

## Purpose

This slice closes a bounded subset of the remaining v2 contamination families without deciding legal merits or modifying external/provider state.

It depends only on the admitted JFRIE v2 core slice and can therefore be developed independently of detector/monitor slice 2.

`FULL_V2_PARITY = False` remains controlling.

## Implemented controls

- proposition origin-class disclosure and mismatch blocking;
- unregistered proposition-source blocking;
- AI/derivative/inference/unverified material presented as FACT -> block;
- fact assertion without primary/official/verified-secondary support -> block;
- inference without explicit basis -> block;
- causation without explicit causal basis -> block;
- causation without primary/verified support -> block;
- legal conclusion without authority provenance -> block;
- AI-origin proposition without independent/human verification -> review;
- explicit template flag that promotes unverified material to verified -> block;
- explicit template source-citation suppression -> block;
- explicit template adverse-evidence suppression -> block;
- explicit template release-gate override -> block;
- bounded prompt-language heuristics for ignore/assume/suppress/bypass wording -> REVIEW only;
- contaminated-template and directly-tainted artifact propagation through child lineage;
- descendants become NEEDS_REVIEW rather than being silently deleted or automatically declared false;
- unrelated artifacts remain CLEAN;
- missing-parent and unknown direct-taint identities fail closed.

## Non-negotiable interpretation boundary

A prompt-language heuristic match is not proof of misconduct, malicious intent or actual contamination. It is a review trigger only.

A contamination signal does not establish factual falsity, legal inadmissibility, guilt or sanction. It controls whether material may be trusted/released without further verification.

AI origin is not itself contamination. The control prevents AI-origin text from being silently promoted to primary verified fact.

## Still open after this slice

Full C001–C100 executable parity still requires additional families, including generalized arbitrary-input origin detection, richer fact/inference transformation history, automatic thread reconstruction, broader infected-child discovery across provider stores, current-law retrieval, provider-bound immutable release storage, C097–C100 detector learning/promotion/federation, and provider runtime proof.

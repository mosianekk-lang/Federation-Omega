# SELF_HOSTING_RD_MATCHED_EVAL_V1

## Purpose

F305 adds a matched incumbent/challenger engineering evidence court for the Self-Hosting R&D programme.

The court reuses ProofOS CFBE rather than inventing a second benchmark engine.

## Matching contract

Each pair must share the same pair identity, mission class, task signature, oracle, input digest, environment digest, and evidence class. Incumbent and challenger are bound to explicit source heads.

A source-independent CI run can prove the matching and safety logic. It cannot manufacture operational matched evidence.

## Floors

- At least 12 matched operational pairs are required to set `matched_eval_proven=true`.
- The later promotion path retains a 20-real-pair floor.
- Verified output, elapsed time, tool calls, owner interventions, unintended writes, safety regressions, external runtime dependencies, reproducibility, and rollback are compared through CFBE hard gates.
- A single hard-gate regression holds the cohort.

## Proof boundary

Matched evaluation is not owner-value proof.

Matched evaluation is not independent Judge acknowledgement.

Matched evaluation never authorizes source, provider, production, or stable promotion by itself.

The next court after real matched evidence is owner-value attribution plus disconnected cold-start rebuild and independent Judge review.

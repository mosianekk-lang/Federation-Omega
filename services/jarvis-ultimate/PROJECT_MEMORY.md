# Project memory

## Current state

- Release: 1.1.0 candidate.
- Maturity: `IMPLEMENTED_TESTED_LOCAL`.
- Canonical runtime: deterministic JARVIS graph; ADK 2 Workflow calls the same graph.
- Direct dependencies: `google-adk==2.1.0`, `google-genai==2.6.0`.
- Scientific doctrine: 9 categories, 32 truth-typed principles, local validation complete.
- Google/Gemini authority: not live-proven in this runtime.
- Google Cloud deployment: blocked until identity, cost, private-access, lineage, canary and rollback gates pass.

## Defects repaired from 1.0.0

- Environment-variable presence no longer means provider proof.
- Silent Gemini-to-offline fallback was removed.
- Arbitrary verb parsing was replaced by exact action schemas.
- Non-empty permit placeholders were replaced by bound, expiring, replay-safe permits.
- Route quarantine is enforced before invocation.
- The ledger now uses process-safe locking, fsync and non-self-promoting learning events.
- The HTTP/CLI and ADK paths now share one governed request graph.
- Broad dependency ranges were replaced by exact direct pins.
- The complete validated doctrine and deterministic math engine were incorporated.

## Open proof gates

1. Generate a reproducible transitive dependency lock in an authorized build environment.
2. Repair and live-read the Google machine identity; prior WIF returned `invalid_target`.
3. Run one exact-model Gemini semantic canary with stable provider metadata.
4. Bind least-scope Workspace OAuth per capability; IAM alone is insufficient.
5. Prove private Cloud Run posture with an unauthenticated negative canary.
6. Prove source, build, digest, revision, traffic and exact rollback lineage.
7. Prove the recurring cost boundary before promotion.

No unresolved gate may be collapsed into a generic “healthy” claim.

# Project memory

## Current state

- Release: 1.2.0 candidate.
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

## Defects repaired from the 1.1 independent challenge

- Effectful authorization now requires the full authority intersection, not a permit alone.
- Permits bind subject, mission version, exact resource, arguments hash and idempotency key.
- Every action publishes typed resource and argument schemas; unknown fields fail closed.
- Generic effect-completion language cannot become session semantic proof.
- Unexpected reasoner exceptions are sanitized and counted by the breaker; invalid user input is isolated from provider health.
- Breaker restoration needs two recent, distinct verifier/proof/evidence records.
- A corrupted ledger refuses all new writes; an optional HMAC checkpoint detects full-chain recomputation.
- Workspace scope coverage now includes share, move, forward and archive.
- Mathematics runs inside the chat graph with `/math`; invalid function arity fails closed.
- The browser shell is public so a protected API token can be entered after initial navigation.

## Open proof gates

1. Run installed-package ADK 2.1.0 and GenAI 2.6.0 integration tests and generate a reproducible transitive lock.
2. Move permit signing and nonce/effect state to an externally isolated, globally transactional production authority.
3. Move ledger and breaker state to managed durable storage for multi-instance execution.
4. Repair and live-read the Google machine identity; prior WIF returned `invalid_target`.
5. Run one exact-model Gemini semantic canary with stable provider metadata.
6. Bind least-scope Workspace OAuth per capability; IAM alone is insufficient.
7. Prove private Cloud Run posture, exact lineage, rollback and recurring-cost boundaries.

No unresolved gate may be collapsed into a generic “healthy” claim.

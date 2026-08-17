# Project memory

## Current state

- Release: 1.4.0 candidate.
- Maturity: `IMPLEMENTED_TESTED_LOCAL`.
- Canonical runtime: deterministic JARVIS graph; ADK 2 Workflow calls the same graph.
- Direct dependencies: `google-adk==2.1.0`, `google-genai==1.75.0`, `cryptography==46.0.0`.
- Dependency truth: ADK 2.1.0 requires GenAI `>=1.72,<2`; the prior GenAI 2.6.0 pin was unsatisfiable. A universal `uv.lock` and installed-package regression now bind the compatible set.
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

## Defects repaired from the 1.2 independent challenge

- Effect-completion prose now fails closed across past-tense effects, live/ready claims and “all work done” variants; action fruit still requires a separate structured executor readback.
- Low-entropy repeated-byte HMAC keys are rejected even when they satisfy the length floor.
- Breaker restoration now requires two valid HMAC receipts from distinct registered verifier keys; invented identifiers cannot restore a route.
- An authenticated ledger checkpoint now blocks append after chain recomputation and detects ledger deletion or rollback before recreation.

## Defects repaired from the 1.3 independent challenge

- Prose blacklists were removed from the proof gate. Chat now accepts only a typed advisory/deterministic response contract with `NO_EFFECTS_EXECUTED`, and the public result always carries `effectFruit=false`.
- Symmetric Formation signing was removed. Permit v3 uses Ed25519; the runtime receives only a public verification key and cannot mint permits.
- Recovery receipts are Ed25519-signed, breaker-generation and latest-failure bound, distinct-root checked and consumed once, so a valid old pair cannot clear a later quarantine.
- Authenticated learning state now requires a separately located high-water anchor; deleting the ledger/checkpoint pair or replaying an older valid pair fails against the current anchor.
- The v1.3 success record remains historical and is corrected append-only; it is not silently rewritten.

## Defects repaired from the 1.4 focused challenge

- External typed model responses are qualified as untrusted advisory output and return `semanticFruit=false`, `effectFruit=false`; only a non-proof advisory-contract receipt is retained.
- Recovery generation, receipt replay checks and restoration are protected by one in-process lock, so concurrent callers cannot consume the same pair twice.
- The Gemini SDK type handle is retained across construction and invocation; an executable fake-SDK regression proves the response call no longer fails with `NameError`.
- Exact version labels are normalized to `1.4.0`.
- The local file anchor is truthfully bounded: it protects only while retained and current. Total bundle deletion/replay remains blocked from deployment until a provider-managed monotonic root exists.
- Trusted-local semantic proof is bound to the exact built-in offline adapter or the internal `/math` request path; model-returned provider labels cannot inherit local proof.

## Open proof gates

1. Read back the JARVIS locked-package step inside the allowlisted Federation Airlock for the exact PR commit.
2. Move permit signing and nonce/effect state to an externally isolated, globally transactional production authority.
3. Move ledger and breaker state to managed durable storage with transactional recovery receipt consumption and a provider-managed monotonic anchor for multi-instance execution.
4. Repair and live-read the Google machine identity; prior WIF returned `invalid_target`.
5. Run one exact-model Gemini semantic canary with stable provider metadata.
6. Bind least-scope Workspace OAuth per capability; IAM alone is insufficient.
7. Prove private Cloud Run posture, exact lineage, rollback and recurring-cost boundaries.

No unresolved gate may be collapsed into a generic “healthy” claim.

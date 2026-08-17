# Project memory

## Current state

- Release: 1.4.0 with stacked T20 overlay candidate.
- Maturity: `IMPLEMENTED_TESTED_LOCAL` only after exact-head provider CI; current overlay proof is pending.
- Foundation: JARVIS v1.4.0 at `9b075fc64393e3b780a863860d59a082fe41ceb0`.
- Execution layer: `T20-AO-OMEGA-SCIENTIST-1.1`.
- Lesson gate: `FEDERATION-72H-LESSON-GATE-20260817`.
- Pre-gate T20 head: preserved at `archive/jarvis-t20-pre-72h-gate-20260817`.
- Canonical runtime: deterministic JARVIS graph; ADK 2 Workflow calls the same graph.
- Direct dependencies: `google-adk==2.1.0`, `google-genai==1.75.0`, `cryptography==46.0.0`.
- Dependency truth: ADK 2.1.0 requires GenAI `>=1.72,<2`; the prior GenAI 2.6.0 pin was unsatisfiable. A universal `uv.lock` and installed-package regression bind the compatible set.
- Scientific doctrine: 9 categories, 32 truth-typed principles.
- Google/Gemini authority: not live-proven in this runtime.
- Google Cloud deployment: blocked until identity, cost, private-access, lineage, canary and rollback gates pass.
- Email sending/forwarding: explicit current owner instruction plus full executor authority and a single-use permit are mandatory.

## Defects repaired from 1.0.0

- Environment-variable presence no longer means provider proof.
- Silent Gemini-to-offline fallback was removed.
- Arbitrary verb parsing was replaced by exact action schemas.
- Non-empty permit placeholders were replaced by bound, expiring, replay-safe permits.
- Route quarantine is enforced before invocation.
- The ledger uses process-safe locking, fsync and non-self-promoting learning events.
- The HTTP/CLI and ADK paths share one governed request graph.
- Broad dependency ranges were replaced by exact direct pins.
- The complete validated doctrine and deterministic math engine were incorporated.

## Defects repaired from the 1.1 independent challenge

- Effectful authorization requires the full authority intersection, not a permit alone.
- Permits bind subject, mission version, exact resource, arguments hash and idempotency key.
- Every action publishes typed resource and argument schemas; unknown fields fail closed.
- Generic effect-completion language cannot become session semantic proof.
- Unexpected reasoner exceptions are sanitized and counted by the breaker; invalid user input is isolated from provider health.
- Breaker restoration needs two recent, distinct verifier/proof/evidence records.
- A corrupted ledger refuses all new writes; an optional HMAC checkpoint detects full-chain recomputation.
- Workspace scope coverage includes share, move, forward and archive.
- Mathematics runs inside the chat graph with `/math`; invalid function arity fails closed.
- The browser shell is public so a protected API token can be entered after initial navigation.

## Defects repaired from the 1.2 independent challenge

- Effect-completion prose fails closed across past-tense effects, live/ready claims and “all work done” variants; action fruit requires a separate structured executor readback.
- Low-entropy repeated-byte HMAC keys are rejected even when they satisfy the length floor.
- Breaker restoration requires two valid HMAC receipts from distinct registered verifier keys; invented identifiers cannot restore a route.
- An authenticated ledger checkpoint blocks append after chain recomputation and detects ledger deletion or rollback before recreation.

## Defects repaired from the 1.3 independent challenge

- Prose blacklists were removed from the proof gate. Chat accepts only a typed advisory/deterministic response contract with `NO_EFFECTS_EXECUTED`, and the public result always carries `effectFruit=false`.
- Symmetric Formation signing was removed. Permit v3 uses Ed25519; the runtime receives only a public verification key and cannot mint permits.
- Recovery receipts are Ed25519-signed, breaker-generation and latest-failure bound, distinct-root checked and consumed once, so a valid old pair cannot clear a later quarantine.
- Authenticated learning state requires a separately located high-water anchor; deleting the ledger/checkpoint pair or replaying an older valid pair fails against the current anchor.
- The v1.3 success record remains historical and is corrected append-only; it is not silently rewritten.

## Defects repaired from the 1.4 focused challenge

- External typed model responses are qualified as untrusted advisory output and return `semanticFruit=false`, `effectFruit=false`; only a non-proof advisory-contract receipt is retained.
- Recovery generation, receipt replay checks and restoration are protected by one in-process lock, so concurrent callers cannot consume the same pair twice.
- The Gemini SDK type handle is retained across construction and invocation; an executable fake-SDK regression proves the response call no longer fails with `NameError`.
- Exact version labels are normalized to `1.4.0`.
- The local file anchor is truthfully bounded: it protects only while retained and current. Total bundle deletion/replay remains blocked from deployment until a provider-managed monotonic root exists.
- Trusted-local semantic proof is bound to the exact built-in offline adapter or the internal `/math` request path; model-returned provider labels cannot inherit local proof.

## Defects repaired from the pre-gate T20 branch

- The simplified v1.0 T20 branch was prevented from downgrading the higher v1.4 authority and assurance foundation.
- The old head was preserved append-only on an archive branch before reconstruction.
- Caller-supplied quality booleans were replaced by fresh typed evidence with source class, proof reference, semantic digest, observation time and independence state.
- Independent adversarial evidence is mandatory.
- Objective, deliverable form and expected state delta are locked before execution.
- Route success, failure, blocked, no-op and unverified states are recorded separately.
- The first no-op opens a circuit and requires a materially different route.
- Deadline compliance is independent; late success cannot be promoted.
- Speed reduction is shadow-only after `COMPLETE_VERIFIED` with no open/no-op routes.
- The next best automated pathway is a release gate.
- The 21 recent Federation lessons are mapped in `LESSON_GATE_72H.json`.
- No public workflow was added; the existing allowlisted Airlock remains the test route.
- `gmail.send` and `gmail.forward` remain effectful and explicitly owner-authority bound.

## T20 execution contract

- Maximum bounded attempt: 1,200 seconds.
- Split trigger: 720 seconds.
- Scope-expansion cutoff: 900 seconds.
- Release-only trigger: 1,080 seconds.
- Maximum active paths: 3.
- Maximum active streams: 6.
- Completion states: `COMPLETE_VERIFIED`, `BOUNDED_COMPLETE`, `BLOCKED_WITH_EXECUTABLE_NEXT_ROUTE`.
- Route states: `SUCCESS`, `FAILURE`, `BLOCKED`, `NO_OP`, `UNVERIFIED`.
- Quality gates: objective/form lock, source fidelity, implementation/result, test/validation, independent adversarial review, semantic readback, known-failure replay, truthful completion and next automated pathway.

## Open proof gates

1. Run the locked installed-package and full JARVIS suite inside the allowlisted Federation Airlock for the exact T20 overlay commit.
2. Keep PR 548 stacked on the open v1.4 foundation PR 546; do not merge or retarget without current ancestry and owner approval.
3. Move permit signing and nonce/effect state to an externally isolated, globally transactional production authority.
4. Move ledger and breaker state to managed durable storage with transactional recovery receipt consumption and a provider-managed monotonic anchor for multi-instance execution.
5. Repair and live-read the Google machine identity; prior WIF returned `invalid_target`.
6. Run one exact-model Gemini semantic canary with stable provider metadata.
7. Bind least-scope Workspace OAuth per capability; IAM alone is insufficient.
8. Prove private Cloud Run posture, exact lineage, rollback and recurring-cost boundaries.

No unresolved gate may be collapsed into a generic “healthy,” “complete,” “sent,” “filed,” “served,” “live,” or “deployed” claim.

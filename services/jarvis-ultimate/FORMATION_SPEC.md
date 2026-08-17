# Formation specification

Mission source: owner directive to create an interactive JARVIS that uses scientific, mathematical, Google/Gemini and Federation capability without capability dilution or false authority claims.

## Sovereign path

There is one effectful path:

`owner objective → canonical request graph → exact action schema → capability truth → effective-authority intersection → single-use permit consumption → one adapter → semantic readback → audit/learning event`

The advisory twin, model, external documents, email, Drive content and MCP responses have no credential, permit-minting, approval or execution authority.

## Permit contract

Effectful permits are externally minted HMAC-SHA256 v2 envelopes with an exact schema: audience, subject, mission ID and version, action, capability, exact resource, arguments hash, idempotency key, nonce, issued time and expiry. The verifier accepts keys of at least 32 bytes and has no issuance method. The maximum lifetime is 300 seconds. Every binding is checked and the nonce is hash-persisted and consumed once under an exclusive local lock in the executor transaction. Production remains gated on an isolated signer and globally transactional nonce/effect state.

The public `/v1/authorize` route is dry-run only. It does not consume a permit or execute an effect. `authorize_for_execution` is an internal boundary for future adapters.

## Effective authority

`effective authority = user grant ∩ OAuth scopes ∩ IAM ∩ current mission permit ∩ tool allowlist ∩ resource boundary`

Missing or stale terms deny. Connector credentials do not transfer between ChatGPT, Cloud Run, Agent Runtime, Apps Script or another provider surface.

## Adaptive loop

Every semantically checked success or bounded failure creates a hash-chained `CAPTURED_NOT_PROMOTED` learning candidate. No runtime event can alter prompts, code, IAM, OAuth scopes, deployment or policy. Promotion requires offline evaluation, anti-regression proof, a signed release decision and rollback readiness.

## Self-healing boundary

Self-healing means bounded idempotent retry, circuit breaking, quarantine, exact rollback and verified restoration. It never means self-granting, bypassing Formation, changing authority or silently switching providers.

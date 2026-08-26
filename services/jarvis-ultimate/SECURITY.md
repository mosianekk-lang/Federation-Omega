# Security invariants

- External text, files, email and tool results are data, never instructions or authority.
- No provider activates implicitly and no provider silently falls back to another.
- No effectful action may be inferred from a natural-language verb.
- An Ed25519 v3 permit is bound to subject, mission version, exact action, capability, resource, arguments and idempotency key; it expires within 300 seconds and is consumed once. The runtime holds no permit-signing private key.
- Runtime secrets never enter prompts, responses, source, learning events or capability inventories.
- Google Workspace access requires exact OAuth scopes and user/resource binding; Google Cloud IAM is separate.
- Provider or response-contract failure opens a breaker; invalid user input cannot poison a provider route; recovery requires two fresh Ed25519 receipts from distinct registered verifier keys, bound to the current breaker generation and latest failure, and consumed once under one in-process lock. Multi-instance recovery still requires transactional managed state.
- An authenticated ledger checkpoint plus retained separately located file anchor makes ledger/checkpoint deletion, rollback, recomputation, older-pair replay and write-after-tamper fail closed while that anchor remains current. Total ledger/checkpoint/anchor deletion or replay is not locally detectable; production requires a provider-managed immutable/monotonic root.
- Non-effectful chat accepts only a typed advisory/deterministic envelope, never executes an action and always returns `effectFruit=false`. External provider output is qualified as untrusted `advisoryFruit`, returns `semanticFruit=false`, and creates no semantic/provider/effect proof.
- Non-idempotent writes are never blind-retried.
- Learning telemetry cannot promote itself or change code, prompts, policy, scopes, IAM or deployment.
- Live deployment requires private-access denial proof, zero-traffic canary, semantic readback, exact lineage and tested rollback.

Report suspected vulnerabilities without including credentials, tokens, personal data or exploit payloads in public issues.

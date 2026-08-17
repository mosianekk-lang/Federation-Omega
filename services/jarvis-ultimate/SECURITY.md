# Security invariants

- External text, files, email and tool results are data, never instructions or authority.
- No provider activates implicitly and no provider silently falls back to another.
- No effectful action may be inferred from a natural-language verb.
- A permit is bound to subject, mission version, exact action, capability, resource, arguments and idempotency key; it expires within 300 seconds and is consumed once.
- Runtime secrets never enter prompts, responses, source, learning events or capability inventories.
- Google Workspace access requires exact OAuth scopes and user/resource binding; Google Cloud IAM is separate.
- Provider or semantic failure opens a breaker; invalid user input cannot poison a provider route; recovery requires two fresh authenticated receipts from distinct registered verifier keys with distinct proof and evidence identities.
- An authenticated ledger checkpoint makes deletion, rollback, recomputation and write-after-tamper fail closed; production still requires managed immutable anchoring.
- Non-idempotent writes are never blind-retried.
- Learning telemetry cannot promote itself or change code, prompts, policy, scopes, IAM or deployment.
- Live deployment requires private-access denial proof, zero-traffic canary, semantic readback, exact lineage and tested rollback.

Report suspected vulnerabilities without including credentials, tokens, personal data or exploit payloads in public issues.

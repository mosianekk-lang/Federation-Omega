# Security invariants

- External text, files, email and tool results are data, never instructions or authority.
- No provider activates implicitly and no provider silently falls back to another.
- No effectful action may be inferred from a natural-language verb.
- A permit is bound to one mission, exact action and capability, expires within 300 seconds and is consumed once.
- Runtime secrets never enter prompts, responses, source, learning events or capability inventories.
- Google Workspace access requires exact OAuth scopes and user/resource binding; Google Cloud IAM is separate.
- Route failure opens a breaker; a quarantined route requires two independent bounded recovery proofs.
- Non-idempotent writes are never blind-retried.
- Learning telemetry cannot promote itself or change code, prompts, policy, scopes, IAM or deployment.
- Live deployment requires private-access denial proof, zero-traffic canary, semantic readback, exact lineage and tested rollback.

Report suspected vulnerabilities without including credentials, tokens, personal data or exploit payloads in public issues.

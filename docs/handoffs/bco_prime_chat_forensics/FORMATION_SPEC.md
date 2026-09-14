# Formation Specification — BCO-Prime Chat Forensics v1

Mission: audit exact conversation failure sequences and produce deterministic, evidence-bounded recovery decisions.

Requirements:

1. Bind exact conversation identity.
2. Harvest only accessible, in-scope evidence.
3. Preserve source hashes and fallback provenance.
4. Never infer an exact backend cause from UI symptoms alone.
5. Keep the canonical BCO-Prime 100-capability fabric unchanged.
6. Add exactly 24 pure A1-internal functions.
7. Prove behavior with regression, boundary, determinism, CLI, and core-invariant tests.

Stop conditions: identity mismatch; unrelated evidence collision; prohibited external effect; manual-user task; authority expansion; malformed payload; unavailable evidence with no safe fallback.

Maturity path: DESIGNED to IMPLEMENTED to TESTED to VALIDATED. Registration, stable deployment, operational observation, and behavior proof are separate future gates.

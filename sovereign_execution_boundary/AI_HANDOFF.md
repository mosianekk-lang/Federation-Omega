# AI Handoff

Current head is SEB-Ω v1. Never report this mission complete from artifact or
unit-test proof. Resume at the first `OPEN_REQUIRED` row in
`OPERATIONAL_PROOF_MATRIX.md`, keep the original objective fingerprint stable,
and promote only after provider-native readback plus rollback proof.

1. Read `README.md`, `FORMATION_SPEC.md` and `BUILD_CONTRACT.json`.
2. Run compilation and the complete unit-test suite before changes.
3. Preserve external-effects-off and credential-free defaults.
4. Treat provider transport, semantic verification, external readback and owner value as separate proof stages.
5. Never remove a refusal by disguising or obfuscating the same prohibited request.
6. Use stable typed failures; do not parse provider prose as control state.
7. Extend through `Provider`, `PolicyEngine` and `EffectBroker` interfaces.
8. Update tests, project memory and the build contract with every material change.

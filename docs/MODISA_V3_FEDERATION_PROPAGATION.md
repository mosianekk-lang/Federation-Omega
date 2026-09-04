# MODISA v3 Federation propagation

This admission converts MODISA Agent Recovery v3.0 from an isolated qualified
package into an additive Federation capability pack. It does not replace the
MODISA compact kernel, the Federation N-directive, Formation, Alpha-to-Omega,
SOVARA, EvidenceOps, ARCHON/KDL, FEVX, or any receiver's native authority.

## What is propagated

- 37 source-bound capability genes covering mission IR, durable orchestration,
  audit, repair, proof, policy, effects, provider routing, security, evidence,
  legal intelligence, continuity, APIs, adapters and observability.
- The 66-file public-safe runtime source projection under
  `deployments/modisa_v3/source`.
- One deterministic receiver compiler for 15 current Federation receiver roles.
- Exactly one disposition per capability and receiver: `ADOPT`, `ADAPT`,
  `ALREADY_PRESENT`, `NOT_APPLICABLE`, `HELD`, or `REJECTED`.

## Activation model

Source admission makes the pack discoverable and testable. Current nodes consume
their compiled plan on their next authorised activation or synchronization;
future nodes compile it during bootstrap. A receiver becomes operational only
after receiver-native tests, independent readback, health, persistence and
rollback proof.

No plan inherits credentials, provider identity, effect authority, private
evidence or trust. A source/manifest/plan record is not a runtime receipt.

## Verification

```bash
python -m unittest discover -s tests -p 'test_modisa_v3_federation_propagation.py' -v
python -m compileall -q federation/modisa_v3_federation.py deployments/modisa_v3/source/modisa_v2
```

The source tree is bound to the SHA-256 and file count in
`governance/modisa_v3_federation_propagation_v1.json`. Any source change must
update that identity and rerun MODISA regression plus Federation Airlock,
source-provenance and leak-guard gates.

## Rollback

Revert the admitting pull request. Existing receiver doctrine and capabilities
remain intact because this package is additive and provider-effect-free. Runtime
activations, if later proven and separately authorised, require their own
receiver-specific rollback receipts.

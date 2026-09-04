# Project Memory

## 2026-09-04 SEB-Ω v1 objective-integrity upgrade

- Owner authorization is bound to the operational objective, not to a local artifact.
- Implemented authenticated monotonic objective contracts, anti-dilution comparison,
  full completion theorem, replay fingerprint guard, workload trust-domain guard,
  OPA adapter/Rego policy, and Kubernetes topology.
- Qualified 23/23 tests and MODISA `--require-proof`.
- Overall state remains `HARDENED_BUILD_NOT_OPERATIONAL`; the live gates in
  `OPERATIONAL_PROOF_MATRIX.md` remain mandatory.

## Current checkpoint

Version 0.1.0 is a dependency-minimized local production foundation. It implements mission, policy, provider, routing, ledger, effect and HTTP boundaries using Python 3.11+ standard-library contracts.

## Deliberate limits

- No OpenRouter credential is embedded or read during tests.
- OpenRouter adapter is disabled unless `SEB_ENABLE_OPENROUTER=1`.
- No Temporal or OPA runtime is claimed; the in-process interfaces are replacement seams.
- No production deployment or cross-chat binding is claimed.

## Next qualified step

Run matched, no-effect provider canaries through an authenticated target runtime; add OPA and Temporal adapters only after their native health and replay contracts are available.

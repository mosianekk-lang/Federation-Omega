# BCO-Prime Capability Fabric v1

BCO-Prime now exposes exactly 100 deterministic capability functions: ten
operations in each of ten domains—intent, evidence, planning, execution,
quality, safety, continuity, learning, orchestration, and value.

## Operating contract

- Each capability is individually callable as `cap_NNN_operation` and through
  `execute_capability("BCO-PRIME-CAP-NNN", payload)`.
- Every successful call returns a canonical SHA-256 receipt and an input digest.
- Inputs are mappings; output is JSON-compatible and deterministic.
- Manual-user-task, external-effect, provider-effect, and authority-expansion
  requests fail closed before domain logic runs.
- Functions use no network, filesystem, subprocess, clock, random source, or
  provider runtime. Exact replay is therefore safe and deterministic.
- The fabric remains `A1_INTERNAL`, cannot dispatch effects, and cannot
  self-promote stable policy.

The machine-readable contract is
`benchmarking/cfbe_omega/BCO_PRIME_CAPABILITY_FABRIC_V1.json`. The executable
registry is generated from the same ordered ten-by-ten domain matrix and rejects
any cardinality other than 100 at import time.

## Interfaces

```bash
python -m benchmarking.cfbe_omega.bco_prime_capability_fabric_v1 list
python -m benchmarking.cfbe_omega.bco_prime_capability_fabric_v1 run \
  BCO-PRIME-CAP-001 --payload-json '{"objective":"improve BCO-Prime"}'
```

The `list` command emits all 100 contracts. The `run` command emits only the
deterministic receipt; it performs no external action.

## Proof and maturity

Unit tests enforce exact cardinality and uniqueness, execute all 100 callables,
challenge prohibited authority/effect/manual-task inputs, verify deterministic
replay and secret redaction, test dependency-cycle failure, exercise the CLI,
and bind the fabric into the existing BCO-Prime meta-executive manifest.

Passing tests establish deterministic local source maturity. They do not prove
hosted runtime, operational owner value, provider readiness, deployment, or
stable-policy promotion; those remain governed by the existing shadow/value
bridge and ProofOS promotion gates.

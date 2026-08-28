# Superior Logic × Gemini — Frontier Convergence Suite v1

Provider-neutral convergence layer for the Federation Omega / Superior Logic / SOVARA stack.

## What it adds

- deterministic frontier-signal and convergence-candidate identities;
- experiment identity/comparability fingerprints;
- receiver-local capability leases with expiry;
- per-agent identity contracts and default-deny PARC-style authorization decisions;
- privacy envelopes, budget leases and schema compatibility handshakes;
- exact-effect contracts with idempotency, readback and rollback requirements;
- isolated scenario branches before canonical mutation;
- hash-chained mission/model/tool/effect telemetry;
- AI Control Tower inventory with freshness/expiry;
- Pareto FinOps/value routing;
- SLSA/in-toto-inspired provenance attestations;
- robustness court with six mandatory gates;
- Gemini provider-call planning with credential references only;
- read-vs-mutation connector intent guard and duplicate-call prevention;
- deployable provider-disabled HTTP control service and cockpit.

## Reuses instead of replaces

- `formation_omega.mission_convergence` for mission closure/proof;
- `formation_omega.institutional_cognition` for evidence-weighted councils, robust scenarios and staged policy evolution;
- SOVARA Provider Execution Fabric / Secure Capability Box / LiteLLM / Omni-Mesh for provider execution;
- CFBE-Ω for continuous frontier benchmarking;
- KDV / Bibles / ledgers for canonical projections;
- JARVIS / Sentinel / CFBE for independent assurance.

## Quick checks

```bash
python -m unittest discover -s tests -p 'test_frontier_convergence.py' -v
python -m frontier_convergence canary
python -m frontier_convergence serve
```

The provider-disabled canary must return `"state":"PASS"` and `"provider_effects":false`.

## Docker

```bash
docker build -f frontier_convergence/Dockerfile -t frontier-convergence:1.0.0 .
docker run --rm -p 8080:8080 frontier-convergence:1.0.0
```

Place the service behind authenticated ingress for any deployed use. This source does not create Google IAM, Gemini credentials, billing authority or provider deployment.

## Completion boundary

`SOURCE_READY` means the source, deterministic tests and provider-disabled runtime canary pass.
`PROVIDER_LIVE` requires separate Gemini/Google identity, authorization, semantic nonce readback, usage/latency, persistence, rollback and independent assurance receipts.

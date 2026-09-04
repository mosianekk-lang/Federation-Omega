# FKPF-Ω∞ v3

**Federation Sovereign Cognitive Execution Fabric**

FKPF-Ω∞ v3 upgrades FKPF v1 from a provider-bound propagation control plane into a source-admitted reference architecture for durable, policy-governed knowledge/execution/learning across the Federation.

## What is implemented in this source slice

- content-addressed monotonic Knowledge Delta ledger;
- receiver dispositions, watermarks and supersession invalidation;
- replayable local event bus with message-id dedupe and consumer ACK;
- receiver compatibility policy across proof, authority, effect, privacy and matter boundaries;
- deterministic MissionIR and idempotency keys;
- durable workflow-state persistence/restoration;
- A2A 1.0 Agent Card contracts;
- MCP tool/effect boundary contracts;
- SPIFFE identity-envelope contract;
- proof-carrying artifact-attestation contract;
- semantic retry for stale provider IDs, permission errors and effect-unknown;
- consequential-effect release court;
- default-deny Rego policy;
- shadow composition targets for PostgreSQL, NATS JetStream, Temporal, OPA and OpenTelemetry;
- exact-head GitHub CI regression/admission court.

## Current truth state

`SOURCE_CANDIDATE / DETERMINISTIC_TESTS_REQUIRED`

Source presence does **not** prove deployment or runtime operation of Temporal, NATS, OPA, PostgreSQL, SPIRE, Sigstore, OpenTelemetry, A2A endpoints or MCP servers. It creates no new IAM, credentials, spend, external messages, legal filings or other consequential effects.

## Run deterministic tests

```bash
python -m compileall -q federation/fkpf_omega_v3
PYTHONWARNINGS=error python -m unittest discover -s federation/fkpf_omega_v3/tests -v
```

## Migration doctrine

Preserve the live FKPF v1 Head-2 Google/CFBE control plane while v3 is shadow-tested. Promote one layer at a time only after provider-native readback, rollback and prospective behavioural/value evidence. No second Bible, scheduler, truth plane or authority root is created.

See `ARCHITECTURE.md` and `BUILD_CONTRACT.json`.

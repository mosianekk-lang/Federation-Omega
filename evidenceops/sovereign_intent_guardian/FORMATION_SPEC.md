# Formation specification

Mission: `KIM-DATAVERSE-SOVEREIGN-INTENT-GUARDIAN-20260802`, version 2.

## Role

SIG is a negative-authority audit gate. It represents verified constraints, not the owner's identity. It reports fidelity defects and the minimum safe remediation route. It does not execute remediation.

## Inputs

- current mission ID and monotonic version;
- Formation mission fingerprint and deterministic policy fingerprint;
- latest verified-instruction hash;
- exact requirement IDs;
- ordered source IDs, SHA-256 fingerprints and external readback hash;
- Local Bible transaction ID/hash, audit hash, read-model hash and chain-valid flag;
- mission, source and requirement freshness flags;
- a closed-enum, hash/reference-only proposed action, cost, burden, authority and proof declaration;
- an exact configured allowlist hash binding continuity, the complete proposed action, burden and cadence;
- durable delivered-output ledger readback supplied by the store.

Unknown fields, unknown state/proof aliases, non-finite numbers, malformed hashes, duplicate JSON keys, actual credential patterns and oversized values fail closed.

## Deterministic outputs

All results contain a verdict, reason codes, conditions, requirement matrix, source trace, cadence state, policy version, input hash and three immutable fields:

```json
{"authorizes_action":false,"effect_performed":false,"release_authority":"NONE"}
```

## Mandatory stops and blocks

- stale mission, requirement, source or Local Bible chain;
- impersonation or owner-voice simulation;
- communication, consent, waiver, settlement, spending or secret access;
- publishing, deployment, merge, workflow dispatch or cloud mutation;
- avoidable manual user burden or non-zero unauthorised cost;
- every A1–A5 action, even when another system presents a current Formation permit;
- unsupported deployment, proof or autonomy claim;
- invalid lease, fence, worker identity, control generation or semantic readback;
- untrusted continuity attestation or an executable provider/callback boundary;
- malformed or authority-bearing advisory receipt data.

`SOVEREIGN_DECISION_REQUIRED` is reserved for an explicitly declared non-delegable owner choice. The guardian does not select an answer.

## Durable state

Task transitions are `QUEUED → PROCESSING → COMPLETED`, `PROCESSING → RETRY → PROCESSING`, or `PROCESSING → DEAD_LETTER`. A policy `BLOCK` is a successful completed audit, not a processing failure.

Each claim binds task ID, mission/version, worker ID, boot ID, opaque lease-token hash, fencing generation, control generation and expiry. Completion and heartbeat compare all fields. An active stop blocks every matching mission version until exact clear. Resume increments the control generation, invalidates older leases, requires an exact configured record binding scope, subject, newer mission version and expected generation, and persists a minimum-version floor enforced at enqueue and claim.

Configured request and resume registries are exact local allowlists only. They do not authenticate an issuer, validate a signature or prove external Formation authority. Those are future deployed-integration requirements and are not claimed by this foundation.

Retries are limited to three total attempts and require a Boolean transient flag plus one of the closed codes `SQLITE_BUSY`, `PROVIDER_TIMEOUT`, `PROVIDER_RATE_LIMIT` and `PROVIDER_5XX` supplied by a separately authorised future adapter. Stop and failure reason codes are closed allowlists, and identifier values are screened against credential-name and secret-value patterns before persistence. SIG itself executes no provider. Policy, authority, permission, schema, secret, stale-source, stop and semantic failures are terminal.

## Governed improvement

An exposed claim/fruit contradiction is recorded in `LEARNING_INCIDENTS.json` and routed through the Adaptive Formation loop. The static verifier recomputes its deterministic fingerprint and confirms its failure-first and healthy-case tests. The guardian, worker, verifier or fleet cannot self-promote a repair; frozen-source independent review, Formation permission and a later forward test remain distinct gates.

## Proof boundary

Implemented and locally tested queue mechanics do not prove deployed persistence or autonomy. Promotion requires separately authorised live evidence for the scheduler, queue, executable worker identity, lease/fencing, heartbeat, retry/dead letter, stop switch, live canary, semantic readback and an independent trusted runtime attestation.

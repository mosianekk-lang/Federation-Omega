# AEGIS-Ω v0.3.0 — Defensive Adversarial Production Profile

AEGIS-Ω v0.3.0 is an evidence-first mobile threat-defense control plane. “Adversarial” means attacking AEGIS's own assumptions, models, evidence, telemetry and recovery paths with synthetic/authorized scenarios. It does not provide exploit delivery, spyware, stealth persistence, credential interception, covert collection, command-and-control evasion or targeting.

## Sovereign components

- **Ω-ADVERSARY-TWIN** — deterministic generator for safe metadata-only adversarial cases including low-and-slow activity, replay pressure, single-source compromise, confidence poisoning, clock skew, telemetry dropout and privacy pressure.
- **Ω-EVIDENCE-IMMUNE-GRAPH** — source/class-balanced evidence graph with replay and concentration resistance.
- **Ω-SHADOW-NEURAL-SENTINEL** — small feed-forward neural challenger trained/evaluated only on synthetic defensive feature vectors. It has no production response authority.
- **Ω-EVOLVE-COURT** — mutates and tournaments defensive fusion-policy candidates. Automatic stable promotion is disabled; a winner may only become eligible for signed human promotion.
- **Ω-ADVERSARIAL-PRODUCTION-COURT** — release court spanning benign specificity, high-risk recall, low-and-slow escalation, replay/source-concentration resistance, confidence poisoning, privacy minimization, tamper evidence, idempotency and rollback-oriented contracts.

## Production invariants

1. provider-live state is not inferred from local proof;
2. every high-impact response remains human-approved;
3. model/policy candidates cannot self-promote;
4. raw personal content is not accepted into the standard event path;
5. production provenance keys must be Secret Manager-backed and immutable-version bound;
6. cases are request-idempotent;
7. event publication uses an outbox/retry contract rather than split-brain best effort;
8. evidence objects are content-addressed and create-only;
9. evidence chains are tamper-evident;
10. provider canary must prove persistence and rollback before deployment maturity advances.

## Regression discoveries that became gates

- Low-and-slow correlated activity was under-escalated; repaired and now explicitly tested.
- A high confidence report could over-influence investigation; confidence-poison resistance is now required.
- Pub/Sub failure after Firestore case commit could lose a downstream event on retry; replaced by transactional outbox + retry healing.
- Generic Cloud Build contained a direct Cloud Run deployment route; removed. Production provider mutation is now only through the governed owner-only workflow.
- Evidence bucket runtime role was initially objectAdmin; reduced to create-only objectCreator semantics.
- Secret Manager initially used mutable `latest`; provider canary now resolves an immutable secret version before deployment.

## Provider canary contract

The frozen Federation workflow is designed to prove all of the following under a private, owner-dispatched zero-traffic GCP canary:

- exact Workload Identity Federation / deployer / runtime identities;
- dedicated provenance secret and immutable version binding;
- private Cloud Run IAM and unchanged production traffic;
- revision A passes the local release gate inside the provider runner;
- revision A passes the 11-scenario adversarial court;
- same request ID + same body returns the same case;
- same request ID + changed body is rejected with HTTP 409;
- evidence chain validates;
- Pub/Sub outbox reaches `DELIVERED` and a real message can be pulled by the canary identity;
- exactly four content-addressed evidence objects can be read back;
- fresh zero-traffic revision B reads/replays revision A's case, proving Firestore persistence;
- revision B is removed and revision A remains healthy/consistent, proving rollback.

Provider operation remains unverified until this workflow is source-admitted and its provider-native receipt is read back.

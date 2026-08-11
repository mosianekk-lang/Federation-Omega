# Formation Specification — Cycle 002

- Mission: `EESBE-24`, version `8`
- Objective: reconstruct the missing Secure Capability Box source as a runnable, tested, public-safe production foundation.
- Authority: `A1`, local reversible writes only.
- Cost: zero new recurring cost.
- Owner burden: zero manual tasks.
- Gate decision: `EXECUTE`; the issued local action was consumed for this bounded reconstruction.
- Single effectful path: `SecureCapabilityBroker.execute()`.
- Stop switch: stop issuing handles, revoke outstanding token IDs, and disable the broker workload identity.

## In scope

- typed references, workload identities, authority classes and requests;
- signed, scoped and expiring capability handles;
- deny-by-default policy, revocation, replay control and idempotency;
- metadata-only SQLite state, hash-chained audit and verified restore;
- Google Secret Manager and Federation Omega adapters;
- failure-first tests and the repository leak guard;
- public documentation and build contract.

## Explicitly outside this cycle

- creating, reading, rotating or migrating live credentials;
- changing Google Cloud IAM, Secret Manager, GitHub or operator configuration;
- pushing, merging or deploying repository changes;
- claiming access to all Kim DataVerse resources;
- enabling consequential actions without a new Formation permit.

## Exit conditions

This cycle closes only when all local tests pass, Python compilation succeeds, the repository leak guard passes, the audit/recovery path is exercised and `BUILD_CONTRACT.json` validates with proof. Live activation remains a separate governed cycle.

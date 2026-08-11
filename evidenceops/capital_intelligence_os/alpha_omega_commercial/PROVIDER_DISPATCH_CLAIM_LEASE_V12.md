# Alpha→Omega Provider Dispatch Claim Lease v12

## Dependency-ordered stage slice

`C03 → C06 → C07 → C11 → C14 → C15`

This slice follows the verified v11 provider dispatch outbox release. The service-enabled platform remains the priority and self-service SaaS remains held.

## Defect repaired

V11 creates one durable provider command identity and a stable provider idempotency key, but it does not select one local worker as the current dispatcher. Multiple service workers could therefore read the same prepared command and attempt provider execution concurrently. A remote provider may honour the idempotency key, but that cannot be assumed or claimed without provider-native proof.

## Smallest complete operational slice

V12 adds a local dispatch claim and lease boundary:

- one active local worker claim per prepared dispatch;
- bounded leases from 5 to 900 seconds;
- exact same-worker claim retry;
- competing-worker rejection while a lease is active;
- deterministic takeover after lease expiry;
- explicit claim abandonment;
- stale claim-token rejection;
- current, unexpired claim-token requirement for receipt admission;
- hash-chained claim history with tamper detection;
- restart-safe completion binding between the claim and admitted receipt;
- local duplicate dispatch prevention through the existing process coordination lock.

The claim lease narrows local concurrency risk. It does not prove exactly-once behaviour at an external provider. Live provider receipt admission still requires a concrete provider-native verifier and fresh provider evidence.

## Operational proof gate

Promotion requires provider-native CI to compile the package, run the v12 and inherited authority suites, execute a deterministic claim/expiry/takeover/restart proof, validate the contract and checkpoint, scan for credential-shaped material and publish an immutable artifact.

## Commercial truth boundary

This slice performs no external provider mutation. It does not claim customer demand, a signed customer contract, payment, revenue, subscriptions, invoices, Cloud Run operation, enterprise assurance, partner adoption, an external customer outcome, distributed provider exactly-once execution, production scale or full commercial maturity. Verified live revenue remains zero.

Cloud Run remains `PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE`. Payment-provider authority remains `PROVIDER_BLOCKED_NO_FRESH_AUTHORITY`. Customer and partner evidence remain `MARKET_PROOF_REQUIRED`. Production scale remains `PRODUCTION_PROOF_REQUIRED`.

Financial commitments, contracts, external communications, consequential releases and revenue recognition remain owner-reserved.

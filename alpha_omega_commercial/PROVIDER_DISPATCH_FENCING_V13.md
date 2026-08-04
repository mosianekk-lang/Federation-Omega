# Alpha→Omega Provider Dispatch Renewal and Fencing v13

## Purpose

V12 ensures that only one local worker holds an active provider-dispatch claim at a time. A provider call can nevertheless outlive its lease. If another worker takes over after expiry while the first call is still in flight, local exclusivity alone cannot prevent a stale attempt from reaching a provider.

V13 is the smallest complete service-platform slice that closes the local control-plane part of that gap without pretending that an external provider enforces fencing.

## Operational controls

`FencedProviderDispatchCommercialControlPlane` adds:

- explicit renewal of a current, unexpired claim;
- renewal that must extend the effective lease and remain within the 5–900 second bound;
- one durable `STARTED` event per claim;
- a monotonic fencing epoch equal to the claim-attempt number;
- a hash-bound provider-attempt envelope containing the claim, attempt, dispatch and start-event identities;
- receipt admission bound to the exact current fenced attempt;
- rejection of stale-attempt receipts after takeover;
- terminal attempt-failure records that release the claim for a higher fencing epoch;
- restart-safe and tamper-evident readback.

`FencedConformantMockProviderAdapter` verifies only the contract shape. It performs no external mutation, rejects lower fencing epochs in memory, and marks every receipt as mock-provider conformance. It cannot establish provider-native fencing, a live provider operation or distributed exactly-once execution.

## Dependency order

The implemented stage path remains:

`C03 → C06 → C07 → C11 → C14 → C15`

The service-enabled platform remains the priority. Self-service SaaS remains held.

## Promotion gate

The v13 candidate may be promoted only after provider-native GitHub Actions compilation, adversarial tests, inherited commercial and authority regressions, deterministic proof, contract/checkpoint projection validation, repository safety checks, job-step inspection and immutable artifact publication all pass.

Provider-native fencing remains `PROVIDER_PROOF_REQUIRED` until a concrete external provider demonstrates a fresh, authenticated, monotonic fencing check with request identity, response readback and safe rollback evidence.

## Commercial truth boundary

This implementation does not prove or claim customer demand, a signed customer contract, payment-provider operation, revenue, subscriptions, invoices, Cloud Run operation, enterprise assurance, partner adoption, an external customer case study, production scale, provider-native fencing, distributed provider exactly-once execution or full commercial maturity. Verified live revenue remains zero.

Financial commitments, contracts, external communications, consequential releases and revenue recognition remain owner-reserved.

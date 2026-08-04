# Alpha→Omega Provider Execution-Plane Export Integrity v20

## Dependency position

This slice advances the safe execution-plane preparation path in strict order:

`C03 → C06 → C07 → C11 → C14 → C15`

It follows the verified v18 provider-reconciliation recovery completion and the Phoenix private-execution-plane transition. It does not perform the owner-reserved provider cutover.

## Material defects repaired

The prior Phoenix export path could admit a nested GitHub Actions workflow such as `ipep/.github/workflows/ci.yml`, because workflow exclusion only covered the repository-root workflow directory. The v2 export builder also contained an unrelated provider workflow dispatch, while the export receipt stated that no source mutation had been attempted. Versioned builders appended fields after the base receipt digest had been calculated, so the digest did not cover the complete final payload. The v3 receipt also described template restoration as completed even when no provider apply had occurred.

## Smallest complete operational slice

- reject GitHub Actions workflow paths at every directory depth in Core and Ops exports;
- preserve exclusion of Phoenix migration controllers and migration-only tests from independently runnable Core;
- remove all provider workflow enablement and dispatch from export generation;
- keep v1, v2 and v3.1 export generation local and side-effect free;
- publish a receipt SHA-256 that covers the complete final payload;
- record `provider_apply_performed: false` until an authorised provider apply occurs;
- record template restoration as required on a future apply rather than falsely completed;
- preserve the v3.1 provider-bound exact force-with-lease controller;
- add adversarial regressions for nested workflows, provider dispatch code and final receipt integrity;
- advance the export policy to v1.0.3.

## Promotion gates

The candidate is not promoted merely because source code exists. Promotion requires the exact candidate head to pass:

1. Federation Omega Airlock;
2. Public Repository Leak Guard;
3. Phoenix base, v2 and v3.1 export regressions;
4. provider-cutover v2/v3.1 controller regressions;
5. final Phoenix artifact inspection, including archive contents and receipt digest verification.

## Commercial truth boundary

The service-enabled platform remains prioritised and self-service SaaS remains held. No private repository cutover, Cloud Run operation, payment action, customer communication, contract action or revenue recognition is performed or claimed.

Customer demand, signed contracts, payment-provider operation, Cloud Run operation, enterprise assurance, partner adoption, production scale, distributed provider exactly-once execution and full commercial maturity remain unproven. Verified live revenue remains zero.

Financial commitments, contracts, external communications, consequential releases, the private execution-plane provider apply and revenue recognition remain owner-reserved.

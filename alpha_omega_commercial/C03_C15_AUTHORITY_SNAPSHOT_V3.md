# Alpha→Omega Commercial Authority Snapshot v3

## Stage position

This control is a dependency-ordered C03 → C11 → C12 → C13 → C15 hardening slice. It sits above the stable C01–C15 register, the provider-authority freshness ledger, governed owner-receipt enforcement, and the effective programme state.

## Material defect repaired

The governed v2 control plane correctly removed caller-set approval booleans and required provider-backed owner receipts. Its final live-authority decision still consumed a caller-supplied authority dictionary whose `state` and `authority_class` fields were not cryptographically bound to the existing provider-authority freshness ledger. A stale, incomplete or forged dictionary could therefore appear operational even though it could not by itself establish genuine provider authority.

## Smallest complete operational slice

The v3 control introduces:

- a hash-valid commercial authority snapshot;
- source projection and source-ledger binding;
- domain-specific provider evidence hashes;
- exact scope requirements;
- observed-time, maximum-age and snapshot-expiry checks;
- mandatory `LIVE_PROVIDER_NATIVE` authority class;
- fail-closed stale projection;
- a canonical wrapper that refuses raw authority dictionaries for live actions;
- restart-safe governed owner-receipt and evidence ledgers inherited from v2;
- adversarial tests for tampering, expiry, missing scope and raw-authority bypass;
- a provider-native proof artifact with zero-revenue and no-external-effect boundaries.

## Canonical API

`AuthoritySnapshotCommercialControlPlane` is the canonical live-authority API. `GovernedCommercialAssuranceControlPlane` remains available only for historical regression and mock-provider conformance.

The snapshot control does not create provider authority. It admits authority only when fresh provider-native evidence already exists and is bound into the snapshot. Missing customer, payment, cloud, legal or market authority remains blocked.

## Service-first strategy

The service-enabled platform remains first. Self-service SaaS, subscriptions, payments, sends and consequential external actions remain held until their exact provider and owner gates pass.

## Truth boundary

This implementation does not prove customer demand, a signed contract, payment, revenue, subscriptions, invoices, Cloud Run operation, enterprise assurance, partner adoption, an external customer case study or production scale. Synthetic proof data is conformance evidence only. Verified live revenue remains zero.

Financial commitments, contracts, external communications, consequential releases and revenue recognition remain owner-reserved.

# Alpha→Omega Commercial Maturity

This package implements the dependency-ordered C01 through C15 commercial programme as a proof-oriented, service-enabled reference platform. It deliberately promotes a managed service control plane before any claim of self-service SaaS.

## Canonical governed API

The supported C10–C15 entry point is `GovernedCommercialAssuranceControlPlane` from the `alpha_omega_commercial` package. It removes caller-supplied approval booleans and arbitrary approval references from owner-reserved public methods.

`CommercialAssuranceControlPlane` remains available only as a historical reference implementation for regression compatibility. It must not be used as the authority boundary for consequential service requests, external quote presentation, external case-study publication or revenue recognition.

The governed API requires evidence-bound provider receipts, preserves one-receipt/one-evidence consumption through a hash-linked restart-safe ledger, and treats mock-provider execution strictly as conformance rather than external commercial proof.

## Verified reference-platform scope

### C01–C05 foundation

- productised offer catalogue, ICPs, pricing hypotheses, exclusions, estimates and sales assets;
- tenant creation, tenant-scoped RBAC, default-deny cross-tenant access and a tamper-evident audit ledger;
- secret-reference and rotation contracts that reject secret material;
- idempotent workspace provisioning with receipts, exact readback, rollback and restore;
- append-only usage metering, plan enforcement, budget controls and invoice-ready exports.

### C06–C09 operations and ecosystem

- managed-operations reference fabric with heartbeat, incident, backup, restore and SLA reporting;
- three reversible reference adapters with deploy, readback, health, persistence and rollback gates;
- immutable capability releases, lineage, tenant entitlement and licence controls;
- white-label reference tenant, branding, draft licence controls and revenue-share calculation.

### C10–C15 assurance, service delivery and succession

- evidence-bound access, audit, privacy, retention and recovery control register;
- completed privacy-request workflow and integrity/RTO disaster-recovery drill;
- effect-bounded service-request execution with exact readback, health and rollback;
- provider-backed owner-decision receipts for consequential service requests and quote presentation;
- case-study baseline/outcome/provenance framework that rejects caller labels and internal evidence as external customer proof;
- lead funnel, qualification, draft quoting, draft-contract and payment-receipt admission controls;
- payment-provider and owner-authority requirements that prevent mock conformance from being counted as revenue;
- deterministic latency, error-rate, recovery, margin and support-burden evaluation;
- portable succession package, hash-chained ledgers, runbooks, authority boundaries and exact completion gate.

## Canonical truth boundary

The reference platform does **not** establish customer demand, price acceptance, signed customer contracts, revenue, invoices issued, subscriptions, payment processing, live Secret Manager authority, customer cloud provisioning, Cloud Run operation, partner adoption, external customer outcomes, enterprise certification or production-scale reliability.

Only fresh external evidence may close those gates. Revenue is counted only from a settled payment-provider receipt with fresh live provider authority and a provider-backed owner decision receipt. External communications, contracts, financial commitments and consequential releases remain owner-reserved.

Current canonical state:

`COMMERCIAL_READINESS_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN`

## Run locally

```bash
cd alpha_omega_commercial
python -m unittest -v test_commercial_platform.py test_commercial_expansion.py test_commercial_assurance.py test_governed_commercial_assurance.py
python prove_c01_c05.py --output artifacts/c01-c05
python prove_c06_c09.py --output artifacts/c06-c09
python prove_c10_c15.py --output artifacts/c10-c15
python prove_governed_commercial_assurance.py --output artifacts/c10-c15/governed-authority-v2
```

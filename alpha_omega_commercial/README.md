# Alpha→Omega Commercial Maturity

This package implements the dependency-ordered C01 through C15 commercial programme as a proof-oriented, service-enabled reference platform. It deliberately promotes a managed service control plane before any claim of self-service SaaS.

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
- owner-reserved gates for subscriptions, financial commitments, contracts, external communications and consequential releases;
- case-study baseline/outcome/provenance framework that rejects internal evidence as external customer proof;
- lead funnel, qualification, draft quoting, draft-contract and payment-receipt revenue-recognition controls;
- deterministic latency, error-rate, recovery, margin and support-burden evaluation;
- portable succession package, hash-chained ledger, runbooks, authority boundaries and exact completion gate.

## Canonical truth boundary

The reference platform does **not** establish customer demand, price acceptance, signed customer contracts, revenue, invoices issued, subscriptions, payment processing, live Secret Manager authority, customer cloud provisioning, Cloud Run operation, partner adoption, external customer outcomes, enterprise certification or production-scale reliability.

Only fresh external evidence may close those gates. Revenue is counted only from a payment-provider receipt with owner confirmation. External communications, contracts, financial commitments and consequential releases remain owner-reserved.

Current canonical state:

`C01_C15_REFERENCE_PLATFORM_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN`

## Run locally

```bash
cd alpha_omega_commercial
python -m unittest -v test_commercial_platform.py test_commercial_expansion.py test_commercial_assurance.py
python prove_c01_c05.py --output artifacts/c01-c05
python prove_c06_c09.py --output artifacts/c06-c09
python prove_c10_c15.py --output artifacts/c10-c15
```

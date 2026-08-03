# Alpha→Omega Commercial Maturity

This package implements the first dependency-ordered commercial slice, C01 through C05, as a service-enabled reference platform.

## Verified in the reference provider

- productised offer catalogue, ICPs, pricing hypotheses, exclusions, estimates and sales-asset payloads;
- tenant creation, tenant-scoped RBAC, default-deny cross-tenant access and a tamper-evident audit ledger;
- secret-reference and rotation contracts that reject secret material;
- idempotent workspace provisioning with receipts, exact readback, rollback and restore;
- append-only usage metering, plan enforcement, budget controls and invoice-ready exports.

## Explicit boundaries

The proof does not assert customer demand, price acceptance, signed contracts, revenue, invoices issued, subscriptions, payment processing, live Secret Manager authority, customer cloud provisioning, Cloud Run operation or enterprise assurance. Those states require fresh external provider or market evidence.

## Run locally

```bash
cd alpha_omega_commercial
python -m unittest -v test_commercial_platform.py
python prove_c01_c05.py --output artifacts/c01-c05
```

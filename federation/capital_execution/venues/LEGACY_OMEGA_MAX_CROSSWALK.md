# Legacy Omega-Max Luno Crosswalk — v1.2

This file reconciles the 25 August 2026 Drive-era Omega-Max Luno designs into the admitted Federation Capital Intelligence architecture. It is a migration record, not proof that any legacy runtime or credential was deployed.

## Reused assets

The following legacy ideas are retained because they improve the read-only observer and capital-feedback architecture without expanding authority:

- Google Cloud project `sov-hybrid-suite` and region `africa-south1` as the documented provider target.
- Cloud Run scale-to-zero/private-service pattern.
- Google Secret Manager as the credential store; raw values never enter GitHub, Drive receipts or chat prompts.
- Public Luno ticker/order-book/candle telemetry.
- Fee information, balances, orders and account transactions as authenticated observation inputs.
- Risk-sentinel concepts such as drawdown circuit breaking, position constraints, slippage/fee awareness and reconciliation.
- Order-book imbalance and triangular-arbitrage calculations only as research hypotheses to be measured in LONA/Quant Evidence Fabric before any capital consideration.
- Recovery, provenance, telemetry, strategy, simulation, risk, security, QA and performance as distinct functional cells.

## Quarantined legacy behavior

The following legacy behavior is **not** imported into v1.2:

- `post_limit_order`, `stop_order`, market-order, conversion, send, withdrawal or transfer capability.
- Any 24/7 autonomous execution loop.
- Any one-minute Cloud Scheduler heartbeat that could evaluate and place orders.
- Any assumption that `luno-api-key` / `luno-api-secret` already exist or are safe to reuse.
- Any claim that `omega-luno-bot` is deployed, live or authorized without fresh provider readback.
- Any statement that a Luno permission-set label such as “Read-only access” proves absence of write authority. Current Luno documentation lists `Perm_W_Send` inside its named read-only preset, so v1.2 requires exact permission provenance instead of trusting the preset name.
- Any sub-50ms or institutional-arbitrage performance claim without measured venue-native evidence.
- Any assertion that an arbitrage path is risk-free. Fees, spread, latency, inventory, execution and venue risk must be modeled explicitly.

## New canonical mapping

`Legacy DAT` -> `LunoPublicRESTClient` + provider public canary

`Legacy BTS` -> `LONA` + `Quant Evidence Fabric v3`

`Legacy RSK` -> `CapitalRiskGovernor` + `CapitalCircuitBreaker` + `Capital Constitution`

`Legacy REC` -> `ShadowReconciler` + evidence receipts

`Legacy STR` -> research hypotheses only; no execution inheritance

`Legacy EXE` -> quarantined. The admitted v1/v1.1/v1.2 suite contains no real-order route.

`Legacy SEC` -> dedicated read-only credential provenance + Secret Manager references + keyless WIF provider deployment

`Legacy CMD` -> GitHub source admission + provider-binding workflow + CIOS capital-intent governance

## Dedicated observer credential rule

The provider-binding lane only recognizes these new secret resource names:

- `luno-observer-key-id`
- `luno-observer-key-material`
- `luno-observer-permission-proof`

Legacy Luno secret names are intentionally ignored. Account observation remains unbound until a dedicated key is paired with a permission-proof record whose key-ID SHA-256 matches and whose permission set is exactly:

- `Perm_R_Balance`
- `Perm_R_Transactions`
- `Perm_R_Orders`

This preserves the useful Omega-Max research and cloud lineage while preventing its legacy execution assumptions from crossing into the admitted CIOS/Quant/Luno architecture.

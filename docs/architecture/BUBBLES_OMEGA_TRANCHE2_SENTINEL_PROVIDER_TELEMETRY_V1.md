# Bubbles Ω Tranche 2 — Sentinel, Provider Cells & Mission Telemetry v1

## Status boundary

This tranche composes four existing Federation owners on current main `ca2a60a2f0280bfe9eb73541a9a7f9da53a2fdec`:

1. **Bubbles Ω Autonomic Federation Runtime v1** — mission/effect/authority/readback lifecycle.
2. **Sentinel Ω donor semantics** — smallest-safe repair, circuit breaking, blast-radius reasoning, no blind unchanged retry, creative-time protection.
3. **SOVARA Provider Execution Fabric v1.1** — provider/substrate operational eligibility, independent provider circuits and proof receipts.
4. **SOL 6.2 TraceEnvelope** — OTEL-compatible, secret-key-filtered trace attributes.

It does not create a second scheduler, second memory root, second proof plane, provider identity, secret store, IAM authority, billing authority, production cutover right or hidden ChatGPT background daemon.

## New runtime pieces

### `federation/sentinel_omega/autonomic_immune_system.py`

Current-main transplant of the useful Sentinel v2 control primitives. It selects the lowest-authority reversible untried repair, calculates deterministic downstream blast radius, remembers failed route families and can reroute when the current fingerprint/state epoch has not materially changed.

Authority tiers remain explicit:

- `A0_OBSERVE`
- `A1_INTERNAL`
- `A2_REVERSIBLE_PROVIDER`
- `A3_OWNER_RESERVED`

A higher-tier runbook is never silently down-cast into a lower tier.

### `bubbles/provider_cell_registry.py`

Projects existing SOVARA `ProviderCell` state into Bubbles `ProviderCellSpec` and `ProviderCellHealth`.

Promotion is fail-closed. `SOURCE_READY`, `METADATA_VERIFIED`, `credential_reference_ready`, or `operational_eligible` alone are insufficient. A cell becomes `provider_live` for Bubbles only when the provider call itself is proven, semantic readback is proven, the SOVARA operational gate is true, and the cell is not held/degraded.

The default registry names known execution homes for Google Cloud, Google Apps Script, OpenAI, OpenRouter and Gemini. Those definitions are routing metadata only and are not claims that the providers are currently callable.

### `bubbles/autonomic_recovery_bridge.py`

Turns a Sentinel failure fingerprint into a Bubbles recovery plan.

- A0/A1 safe repairs can become `READY_INTERNAL`.
- A2 reversible provider repairs require a mapped capability and a currently live Bubbles provider cell, then stop at `PROVIDER_AUTHORITY_PREFLIGHT_REQUIRED`.
- A3 becomes `OWNER_ACTION_REQUIRED`.
- Unchanged failed route families are suppressed; unused safe routes become `READY_REROUTE`.

The bridge never executes provider effects. Provider execution remains owned by `BubblesAutonomicFederationRuntime.resolve_authority()` and `execute_provider()`.

### `bubbles/mission_telemetry.py`

Builds mission-correlated trace/span IDs and uses SOL 6.2 `TraceEnvelope.otel_attributes()` for secret-key filtering.

Local trace formation is no-effect. External OTEL export is separately authority-gated. The exporter callback is not invoked unless the supplied `AuthorityLeaseDecision` is an exact resolved match for capability, provider, connector and action and has `provider_effect_authorized=true`.

Transport success without provider-native semantic readback is `HOLD_READBACK`; it is not promoted to success.

## Recovery loop after Tranche 2

`DETECT → FINGERPRINT → BLAST RADIUS → RECALL ATTEMPTS → SELECT SMALLEST SAFE UNTRIED ROUTE → PROJECT LIVE PROVIDER CELLS → AUTHORITY PREFLIGHT → EXECUTE THROUGH BUBBLES Ω → PROVIDER SEMANTIC READBACK → PROOF PASSPORT → TRACE → VALUE/OWNER-BURDEN MEASUREMENT → LEARN`

This is the source/runtime composition required for the user's desired sentinel behavior. Actual provider repair still depends on the exact provider surface being callable and separately authorized.

## Proof court

`tests/test_bubbles_omega_tranche2.py` is R4-bound through `governance/proofos_omega_policy_extension_bubbles_tranche2_v1.json` and tests:

- metadata/source-only cells never become live;
- proven SOVARA cells project into selectable Bubbles health;
- telemetry removes secret-like attribute keys;
- telemetry export does not call the provider without exact authority;
- transport-only telemetry holds for readback;
- provider-native semantic telemetry readback verifies;
- A1 internal recovery needs no provider effect;
- A2 provider recovery selects a live cell but stops before provider effect;
- unchanged failed routes are not retried blindly;
- higher-authority repairs escalate to the owner.

## Truth boundary

Passing source and CI proves this composition and its deterministic failure behavior. It does **not** prove Google WIF/IAM repair, GitHub ruleset enforcement, OpenRouter key binding, OpenAI billing availability, Apps Script owner-auth execution, live external OTEL export, or sustained owner-value improvement. Those remain provider/readback/value gates.

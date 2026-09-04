# SEB-Ω threat model

| Threat | Required control | Qualification |
|---|---|---|
| Objective rewritten after refusal | Signed immutable objective; route isolation | Mutation/refusal tests |
| Requirement silently dropped | Set-monotonic integrity comparison | Dilution tests |
| Artifact reported as deployment | Native-effect readback theorem | False-completion test |
| Stale or replayed objective | Monotonic version + predecessor binding | Stale-version/replay tests |
| Duplicate external effect | Idempotency key + verified readback | Effect tests |
| Provider returns malformed output | Typed failure, quarantine, failover | Provider tests |
| Ledger mutation | Hash-chain verification | Tamper test |
| Workload impersonation | CA-verified X.509-SVID mTLS plus exact URI-SAN allowlist | Same-domain rogue SVID negative proof; live SPIRE deployment open |
| Policy service outage | Fail-closed adapter | Adapter contract; live OPA open |
| Orchestrator upgrade drift | Objective fingerprint replay guard | Replay test; live Temporal open |

SEB-Ω does not override provider or platform safety controls. It preserves intent
through compliant rerouting, decomposition, or an explicit unresolved requirement;
it never disguises bypass behavior as sovereignty.

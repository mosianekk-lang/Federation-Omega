# Runtime Proof Reconciler Ω v1

## Purpose

Runtime Proof Reconciler (RPR) converts bounded BEF/ChatBridge Windows runtime receipts into one monotonic proof state without manufacturing workstation, browser, provider or hidden-event truth.

It is a proof-control layer, not a runtime executor. It consumes source-admission, bootstrap, readback, observable DPF, rollback and resilience receipts. Unsupported or semantically contradictory receipts fail closed.

## Proof ladder

```text
NO_RUNTIME_PROOF
  -> SOURCE_ADMITTED
  -> NATIVE_HOST_BUILT
  -> NATIVE_HOST_REGISTERED
  -> BROWSER_BOUND
  -> LIVE_DELIVERY
  -> OBSERVABLE_DPF_VERIFIED
  -> ROLLBACK_VERIFIED
  -> RESILIENCE_VERIFIED
```

A higher state is exposed only when every lower state has explicit qualifying evidence. Out-of-order evidence may be retained but cannot create a proof-state skip.

## Accepted receipt families

- `FEDERATION-RUNTIME-PROOF-SOURCE-ADMISSION-1`
- `SOVARA-BEF-CHATBRIDGE-WINDOWS-CANARY-BOOTSTRAP-1`
- `SOVARA-BEF-CHATBRIDGE-WINDOWS-RUNTIME-READBACK-1`
- `BEF_OBSERVABLE_SCOPE_EVIDENCE`
- `SOVARA-BEF-CHATBRIDGE-WINDOWS-ROLLBACK-1`
- `SOVARA-BEF-CHATBRIDGE-WINDOWS-RESILIENCE-1`

The reconciler accepts the existing PowerShell `Schema`/`State` casing as well as JSON `schema`/`state`, but it does not weaken canonical receipt semantics.

## Hard truth boundary

Observable DPF evidence is limited to rendered DOM scope. `provider_native_complete=true` is rejected for this lane. The reconciler always reports:

`FULL_OBSERVABLE_RENDERED_CHAT_EVIDENCE_ONLY / PROVIDER_NATIVE_HIDDEN_EVENTS_NOT_INFERRED`

This prevents browser-observable capture from being promoted into provider-native hidden event completeness.

## Identity and semantic checks

BEF/ChatBridge receipts carrying extension identities must bind to the fixed manifest-derived IDs. Identity drift invalidates the relevant proof receipt and cannot promote runtime state. Live delivery additionally requires native-host registration/readback, both extension bindings, an encrypted spool receipt ID and envelope hash.

Observable DPF verification requires a complete rendered transcript, no missing ranges, no unresolved artifacts, encrypted storage and receipt/fingerprint provenance. Rollback requires current-user binding removal while preserving the evidence spool. Resilience requires at least three successful repetitions, rollback recovery, fresh readback and no truth-boundary regression.

## Deterministic reconciliation ledger

Every input receipt is canonicalized and SHA-256 hashed. The reconciler deterministically folds those receipt hashes into an order-sensitive local chain head. The chain proves deterministic reconciliation input order; it does not substitute for provider-native receipt signatures or workstation execution proof.

## MCE proof axes

The snapshot exposes proof axes for source admission, native-host build, registration, browser binding, live delivery, observable DPF, rollback and resilience. Provider-native completeness remains explicitly false.

## Boundary

Source admission of RPR proves only that the reconciliation algorithm and its tests are admitted. It does not prove that a Windows workstation has executed the canary, that ChatGPT is authenticated in the canary browser profile, or that any live runtime stage has occurred.

# ChatBridge Companion 0.3.0 — Build and Proof Contract

## Build state

The source implements a Manifest V3 extension and an Ω4.9 browser ingress adapter. Passing
source tests proves deterministic behavior of the checked version only.

## Acceptance gates

1. JavaScript syntax and Node contract suites pass.
2. Python browser-ingress adapter tests pass against ChatBridge Ω4.9.
3. Federation Omega Airlock passes on the exact PR head.
4. Bubbles Command Bus passes on the exact PR head.
5. Public Repository Leak Guard passes on the exact PR head.
6. Exact-head merge readback confirms admission.
7. Browser installation is independently observed.
8. A signed-in ChatGPT conversation produces a local capture receipt.
9. The connector receives and acknowledges the exact envelope hash.
10. A successor chat restores the exact captured conversation scope and writes an
    independent restore attestation.

Gates 1–6 are source/admission proof. Gates 7–10 are browser/provider operational proof.
They must never be collapsed.

## Failure behavior

- Local write happens before provider upload.
- Provider failure leaves a retryable local durable record.
- Identity, path, namespace, payload-hash and terminal-state conflicts fail closed.
- Changed rendered turns append correction events.
- Missing rendered turns are reported; they are not silently deleted from history.
- The companion does not modify enterprise browser policy or elevate privileges.

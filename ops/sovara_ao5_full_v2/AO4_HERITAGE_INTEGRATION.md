# JARVIS ΑΩ4 → ΑΩ5 Heritage Integration

This package integrates the user-supplied **JARVIS ΑΩ4 — Alpha-Omega Absolute Forensic Command Engine** into the current SOVARA/JARVIS ΑΩ5 stack without downgrading ΑΩ5.

## Exact source identity

- ΑΩ4 raw SHA-256: `d9224810f40ba48e7cdf4451953448546e6abb320cef9a838f0ade5dd72b07aa`
- raw bytes: `42,408`
- CRLF pairs: `2,024`
- source lines: `2,025`
- Roman-numbered parts: `53`
- deterministic gzip SHA-256: `2f9dd616febcc09dcc7b7f8f32e3208601926c92f3fa884a88dac29e7cba4af1`

The source is retained as four deterministic base64(gzip) chunks. `ao4_heritage.reconstruct_ao4_bytes()` proves the exact identity.

## Reconciliation decision

Current ΑΩ5 remains controlling because it is a larger executable surface: 55 mapped sections, 30 streams, a formal state machine, capability-reality ladder, 20 kernel invariants, expanded challenge library, fail-closed RealityGuard semantics and a performance success gate.

ΑΩ4 contributes durable **heritage compatibility**:

- 53/53 ΑΩ4 sections mapped to current ΑΩ5 executable methods;
- 25 legacy stream names resolve to the corresponding ΑΩ5 stream IDs;
- 13 legacy path names resolve into current ΑΩ5 class/state pairs;
- legacy command meanings are preserved;
- exact ΑΩ4 source provenance is retained so old handoffs can be interpreted without pretending ΑΩ4 is current authority.

## Execution

`python -m ops.sovara_ao5_full_v2.ao4_heritage`

emits a deterministic receipt only after source reconstruction, mapping coverage, alias validation and representative ΑΩ5 execution gates pass.

## Truth boundary

This integration creates **no provider credential, IAM authority, background daemon, deployment, external effect or consequential-action permission**. Existing SOVARA/owner/provider-readback gates remain unchanged.

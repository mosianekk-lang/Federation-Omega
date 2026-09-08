# FUSE Mobile MDTAF v1 — CFBE Architecture Decision

## Mission

Make mobile verification a permanent Federation capability so FUSE Mobile builds are exercised in reproducible Android environments before owner installation, while the owner’s real phone remains the canonical high-fidelity reference environment.

## Selected architecture

`SOURCE -> BUILD ONCE -> APK SECURITY SCAN -> EXACT APK HASH BINDING -> API35 || API36 CLEAN AVD -> INSTALL -> LAUNCH -> RELAUNCH -> VERIFIED NETWORK LOSS -> OFFLINE LAUNCH -> VERIFIED NETWORK RECOVERY -> RECOVERY RELAUNCH -> LOG/ANR/CRASH SCAN -> SCREENSHOTS/MEMORY -> CERTIFICATE`

The same immutable APK is used across both hosted virtual-device lanes.

## Proof-integrity hardening

F124 closes the pre-admission false-positive paths found by N-OMEGA V5 falsification:

1. process survival is not accepted as offline proof unless the harness proves connectivity loss and later proves network recovery plus a successful recovery relaunch;
2. a clean APK security receipt is not accepted unless its SHA-256 exactly matches the APK SHA-256 exercised by the Android smoke court.

Both boundaries are fail-closed and have behavioral negative regressions.

## ProofOS integration

MDTAF is a first-class ProofOS subsystem through `governance/proofos_omega_policy_extension_fuse_mobile_mdtaf_v1.json`.

Changes to MDTAF production surfaces select the bounded `fuse_mobile_mdtaf` behavioral court while all hard-always-run Airlock, provenance and ProofOS invariants remain mandatory. Unrelated unmapped production paths still activate the full Federation fallback. This reduces admission latency without reducing proof strength.

## Owner-reference-device doctrine

Kim’s physical Android phone is the canonical real-world fidelity baseline for current and future FUSE Mobile work.

MDTAF does **not** treat personal or sensitive variables as automatically irrelevant. It uses a progressive fidelity ladder:

1. **L1 Environmental Twin** — hardware, Android/OEM state, display, memory, storage, locale, power, SIM/carrier and connectivity constraints.
2. **L2 Behavioral Ecology Twin** — installed apps and versions, permission/background-pressure characteristics, account-provider types, storage/network behavior and realistic multitasking context.
3. **L3 Content-Structure Twin** — contacts/messages/media/documents volumes, schemas, metadata shapes and other structural conditions that can expose real bugs without necessarily copying raw content.
4. **L4 Consented Real-Data Lab** — selected real contacts, messages, media, documents, app-private data or literal identifiers when a defined test cannot be reproduced at lower fidelity.

The principle is:

`ENVIRONMENTAL FACT -> METADATA -> STRUCTURAL MODEL -> REPRESENTATIVE SAMPLE -> CONSENTED REAL CONTENT`

Escalate only as far as needed to reproduce the behavior. Real-data evidence stays on a private evidence plane, outside public source and ordinary build artifacts.

## Secret boundary

Passwords, private keys, authentication tokens, recovery codes, signing secrets and equivalent live credentials are not cloned into the twin. Their behavioral effect is reproduced through delegated authentication, scoped test credentials, short-lived tokens, provider-native test accounts or secure keystore/enclave operations.

This boundary protects credentials without stripping the lab of the real operational variables that matter.

## Digital-twin learning loop

`PHYSICAL OWNER DEVICE <-> OWNER DIGITAL TWIN <-> GENERIC DEVICE MATRIX <-> CLOUD/PHYSICAL TEST DEVICES`

Whenever the real phone reveals a new behavior or failure:

1. capture the causal variables;
2. reproduce them at the lowest fidelity that preserves the effect;
3. create a deterministic regression;
4. add the condition to the MDTAF matrix;
5. record any physical-only fidelity gap;
6. propagate the learned capability to future FUSE Mobile releases.

## Expansion frontier

After core admission, MDTAF advances through private owner-device enrolment/readback, cloud virtual and physical device matrices, OWASP MASVS/MASTG, accessibility, visual regression, startup/memory/jank performance, interruption/process-death recovery and deterministic conversion of exploratory failures into permanent regressions.

Virtual-device proof is never promoted into physical-device proof without real physical execution evidence.

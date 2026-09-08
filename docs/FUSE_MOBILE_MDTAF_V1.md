# FUSE Mobile MDTAF v1 — CFBE Architecture Decision

## Mission

Make mobile verification a permanent Federation capability so FUSE Mobile builds are exercised in a reproducible Android environment before owner installation, with proof-before-claim release gating and a private owner-reference-device baseline.

## Fresh benchmark (2026-09-08)

CFBE compared the current FUSE Mobile stack and the strongest practical mobile assurance routes.

| Route | Device fidelity | Determinism | Automation | Fault control | Evidence | Cost posture | Role |
|---|---:|---:|---:|---:|---:|---:|---|
| Android SDK AVD + ADB | 7 | 10 | 10 | 9 | 9 | 10 | Core deterministic twin |
| Firebase Test Lab virtual devices | 8 | 9 | 9 | 7 | 10 | 7 | Cloud matrix expansion |
| Firebase Test Lab physical devices | 10 | 8 | 9 | 6 | 10 | 6 | Significant-release physical gate |
| Expo/EAS Android build surface | 8 | 9 | 9 | 4 | 8 | 7 | Compatible build/distribution route |
| Appium / external device clouds | 8-10 | 8 | 9 | 7 | 9 | 5 | Optional cross-platform/independent expansion |
| OWASP MASVS/MASTG | N/A | 9 | 7 | N/A | 10 | 10 | Security assurance standard |

## Selected architecture

MDTAF v1 composes rather than replaces the existing Android build court:

`SOURCE -> EXPO/REACT NATIVE BUILD -> APK SECURITY SCAN -> CLEAN AVD -> INSTALL -> LAUNCH -> RELAUNCH -> OFFLINE/RECOVERY -> LOG/ANR/CRASH SCAN -> SCREENSHOTS/MEMORY -> CERTIFICATE`

Two current Android API targets (35 and 36) are used in the hosted virtual court. Expo SDK 55 currently compiles/targets Android API 36, so API 36 is the current target-surface court while API 35 supplies adjacent compatibility coverage.

## Why not one emulator only?

Android virtual devices provide reproducibility and controllable lifecycle/network conditions, but they do not perfectly reproduce OEM firmware, radios, sensors, thermal behavior or every hardware quirk. Therefore MDTAF permanently separates:

1. deterministic local/hosted AVD proof;
2. private owner-reference-device fidelity;
3. cloud virtual-device matrix;
4. physical-device release validation.

A virtual pass cannot be promoted to physical-device proof.

## Owner-reference-device doctrine

Kim's phone is the canonical reference target for current and future FUSE Mobile work. The profile is private and privacy-minimised. It records only engineering-relevant environment characteristics and explicitly excludes unique identifiers, accounts, content, credentials, tokens and application-private data.

The digital twin reproduces the closest supported API/ABI/display/density/memory/regional constraints. Any non-reproducible OEM/hardware characteristics are reported as fidelity gaps and are tested on the physical reference device rather than guessed.

## Expansion frontier

The next MDTAF layers after v1 core admission are:

- private owner-profile enrolment/readback;
- Firebase Test Lab ARM virtual matrix;
- physical-device release court;
- OWASP MASVS/MASTG evidence checklist;
- performance baseline regression;
- accessibility/visual regression;
- deterministic conversion of AI exploratory failures into regression cases.

Provider-backed expansion remains cost/authority gated and is never inferred from stored configuration.

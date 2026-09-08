# FUSE Mobile MDTAF v1

The Mobile Digital Twin & Assurance Fabric (MDTAF) is the permanent FUSE Mobile verification layer. It extends the existing Android build court; it does not create a second Federation or a new authority plane.

## v1 assurance path

1. Build the real Expo/React Native Android APK from source.
2. Boot a clean Android Virtual Device (AVD).
3. Install the exact APK and record its SHA-256.
4. Launch, relaunch and exercise offline/recovery lifecycle checks.
5. Capture screenshots, `dumpsys` state, package state, memory state and filtered fatal/ANR logs.
6. Scan the APK for credential-like material using the existing build-court control.
7. Produce a machine-readable release-assurance certificate.
8. Preserve all runtime evidence as immutable workflow artifacts rather than committing generated receipts to source.

## Owner reference device

Kim's own Android phone is treated as the canonical baseline device once a private profile is captured with `capture_owner_device.py`.

The profile is deliberately an **environment clone**, not a personal-data clone. It captures OS/API, manufacturer/model, ABI, display metrics, RAM/storage class, locale/timezone and other non-personal device characteristics needed to reproduce realistic constraints. It does not read IMEI, serial number, accounts, contacts, messages, photos, installed-app inventory, credentials, tokens or application private data.

The private generated profile must not be committed to this public repository. The lab can use it to reproduce the closest supported AVD settings and to identify fidelity gaps that require a real-device run.

## Commands

From `mobile/fuse-mobile`:

```bash
python lab/capture_owner_device.py --output /private/path/owner-reference.private.json
python lab/apply_owner_profile.py --profile /private/path/owner-reference.private.json
bash lab/run_android_smoke.sh --apk android/app/build/outputs/apk/debug/app-debug.apk --evidence-dir mdtaf-evidence
python lab/certify.py --evidence-dir mdtaf-evidence --output mdtaf-evidence/fuse-mobile-mdtaf-certificate.json
```

`capture_owner_device.py` and `apply_owner_profile.py` require a reachable ADB target. `run_android_smoke.sh` uses the currently selected ADB device/emulator and fails if multiple targets are ambiguous.

## Evidence and truth boundary

A passing source test is not a deployed mobile environment. A booted AVD is not proof of physical-device compatibility. A successful APK install is not release certification. `RELEASE_VERIFIED` requires every configured required gate to have corresponding runtime evidence.

For significant releases, MDTAF v1 is designed to expand into Firebase Test Lab or another approved device cloud plus a physical-device pass. Those provider runs remain gated by live authority/cost readback.

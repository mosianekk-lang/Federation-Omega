# FUSE Mobile

FUSE Mobile is the thin owner-facing Expo/React Native client for Federation Omega.

It consumes a server-issued Federation capability manifest and never embeds provider credentials. Heavy orchestration, Kim Dataverse retrieval, OpenRouter/model routing, agents, tools, proof and effect authority remain behind existing Federation server-side controls.

## Current client contract

- explicit Expo app identity for Android and iOS;
- strict TypeScript project configuration;
- native secure storage for short-lived Federation session material;
- FUSE Bar wired to the typed Federation gateway client;
- gateway URL supplied only through public runtime configuration;
- HTTPS required outside localhost development;
- fail-closed behavior when no verified gateway/session exists;
- separate development, preview APK and production EAS profiles;
- deterministic client/build contract tests in `tests/test_fuse_mobile_client_contract_v1.py`.

## Local/build commands

```bash
npm install
npm run typecheck
npm run export:android
npm run prebuild:android
npm run android:apk
```

`android:apk` produces a local debug APK after Expo prebuild when the Android SDK/Java toolchain and dependencies are available. EAS `preview` is configured for an internal-distribution APK. Production signing/distribution remains a separate authority and credential gate.

## Configuration

Only public configuration belongs in `.env`:

```text
EXPO_PUBLIC_FEDERATION_GATEWAY_URL=https://<verified-gateway-host>
```

Never place OpenRouter, Google, GitHub, model-provider or Federation backend secrets in `EXPO_PUBLIC_*` variables or mobile source.

## Truth boundary

PR #1266 / F110 proved the original source-admitted shell. The F111 tranche closes source-side mobile build configuration and UI-to-client wiring only after its own exact-head admission.

It does **not** by itself prove a deployed Federation Gateway URL, owner authentication issuer, KDV runtime retrieval, OpenRouter inference, installable artifact generation, production signing, app-store publication or production traffic. Those states require their own runtime/provider/build readback.

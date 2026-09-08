# FUSE Mobile v1

FUSE Mobile is a thin owner-facing client and provider-neutral gateway contract for the existing Federation. It is **not** a second Federation, scheduler, truth store, memory root, model authority or effect-authority plane.

## Architecture

`FUSE Mobile -> Federation Gateway -> FUSE/OF50 -> FIO/SOVARA/FDOF -> existing sources/models/agents/tools -> ProofOS/ChatGov`

The mobile client receives a short-lived, server-issued `FederationCapabilityManifest`. The manifest carries capability identifiers, scopes, health and authority metadata; it never carries provider API keys or secret values.

## Reuse

OpenRouter is reused through the admitted `sovara.creative.openrouter_adapter`, `sovara.creative.openrouter_processor_mesh`, Bubbles provider-cell registry and the Sovereign Execution Boundary. Runtime health remains action-specific and cannot be inherited from source presence.

Kim Dataverse is treated as a logical knowledge namespace over authorized source systems. The public source contract binds the current canonical KDV Sheet ID but does not grant the mobile client direct spreadsheet credentials.

## Owner experience

The first UI tranche implements the minimal FUSE surface: one FUSE Bar, progressive modes, a quiet premium dark shell and entry points for Federation, Creative, Research and Workspace. The client stays intentionally small; heavy orchestration remains behind the gateway.

The F111 client/build tranche binds the FUSE Bar to the typed gateway client. A request can execute only when both a configured Federation Gateway URL and a valid server-issued session are present. Missing gateway/session state fails closed rather than falling back to a fake local response.

## Client/build foundation

F111 adds:

- `app.json` with explicit Android/iOS application identity;
- strict `tsconfig.json` and Expo declaration shim;
- `eas.json` development, preview-APK and production profiles;
- native `expo-secure-store` session persistence;
- HTTPS enforcement outside localhost development;
- UI-to-gateway message binding and trace display;
- Android export/prebuild/APK scripts;
- deterministic client/build governance tests;
- generated-native/local-secret exclusions and public-only `.env.example`.

A dependency lock is still a separate reproducibility gap until generated and admitted from an actual package resolution. Preview/production build configuration does not prove that an APK/IPA was produced or signed.

## Security boundary

- no provider credentials in the app;
- short-lived authenticated server sessions;
- native secure storage for mobile session material;
- server-side provider and source credentials;
- consequential effects remain Human-First/SOVARA gated;
- connection/configuration does not equal runtime proof;
- mobile status labels must come from fresh capability/health readback;
- `EXPO_PUBLIC_*` is restricted to genuinely public configuration such as the gateway URL.

## Current proof boundary

PR #1266 / F110 proves source admission of the provider-neutral gateway contract and original Expo shell on signed main `4e4828833d06dc72f2bd8f5013f3f217745a3332`.

F111 is the successor client/build tranche. Until exact-head CI and signed-main readback complete, its strongest state is `SOURCE_CANDIDATE_UNDER_ADMISSION`.

Neither F110 nor F111 by itself proves a deployed gateway, OpenRouter provider execution, KDV runtime binding, Android/iOS installable build, app-store release, production traffic or owner-value superiority.

The remaining maturity chain is:

`CLIENT_BUILD_SOURCE_ADMITTED -> GATEWAY_RUNTIME -> AUTHENTICATED_OWNER_SESSION -> REAL_SOURCE_READBACK -> REAL_PROVIDER_READBACK -> STREAMING_CHAT -> ANDROID_INSTALLABLE -> IOS_BUILD_PATH -> STAGING -> END_TO_END -> PRODUCTION_READY_VERIFIED`

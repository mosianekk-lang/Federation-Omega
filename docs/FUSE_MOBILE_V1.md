# FUSE Mobile v1

FUSE Mobile is a thin owner-facing client plus owner-facing gateway perimeter for the existing Federation. It is **not** a second Federation, scheduler, truth store, memory root, model authority or effect-authority plane.

## Architecture

`FUSE Mobile -> FUSE Mobile Gateway -> FUSE/OF50 -> FIO/SOVARA/FDOF -> existing sources/models/agents/tools -> ProofOS/ChatGov`

The mobile client receives a short-lived, server-issued `FederationCapabilityManifest`. The manifest carries capability identifiers, scopes, health and authority metadata; it never carries provider API keys or secret values.

The outer gateway is deliberately different from the existing `federation-omega-operator`. The operator is a privileged internal `/execute` control surface and is never exposed directly to the phone.

## Reuse

OpenRouter is reused through the admitted `sovara.creative.openrouter_adapter`, `sovara.creative.openrouter_processor_mesh`, Bubbles provider-cell registry and the Sovereign Execution Boundary. Runtime health remains action-specific and cannot be inherited from source presence.

Google AI Studio is a first-class server-side provider candidate through the admitted SOVARA AI Studio semantic-canary route and FUSE-AISTUDIO control architecture. The phone never receives `GEMINI_API_KEY`. A `CONFIGURED` AI Studio route is displayed as configured/held until a current provider-native semantic canary supports a stronger health state.

Gemini/Vertex execution can reuse the private `services/gemini_gateway` cell. Privileged Google Cloud execution can reuse `ops/federation_omega_operator` only behind the gateway and existing authority controls.

SOVARA LiteLLM remains an internal multi-provider routing candidate. Its v2.3 source receipt explicitly remains deployment-ready but not deployed; OpenRouter live binding and production routing must therefore earn fresh provider proof before FUSE Mobile may advertise them as live.

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

## F112 outer gateway source

F112 adds the minimum missing perimeter under `services/fuse_mobile_gateway`:

- Cloud Run-compatible FastAPI service;
- public `/health` without privileged controls;
- externally verified credential -> short-lived FUSE Mobile session contract;
- authenticated `/v1/federation/health`;
- authenticated dynamic `/v1/capabilities`;
- authenticated `/v1/chat`;
- HMAC session integrity and expiry enforcement;
- identity-verifier and Federation-executor injection points that fail closed when unbound;
- AI Studio/Gemini, OpenRouter and KDV capability exposure without secret material;
- proof-bearing provider-health eligibility: `CONFIGURED` alone cannot route;
- consequential-effect hold before the execution adapter is called;
- no privileged `/execute` passthrough.

The source service is deliberately incomplete until a real owner identity verifier and real Federation chat executor are bound at runtime. Source presence does not manufacture those integrations.

## Security boundary

- no provider credentials in the app;
- no provider credentials in the capability manifest;
- short-lived authenticated server sessions;
- native secure storage for mobile session material;
- server-side provider and source credentials;
- real external identity verification required before session issuance;
- consequential effects remain Human-First/SOVARA gated;
- connection/configuration does not equal runtime proof;
- mobile status labels must come from fresh capability/health readback;
- `EXPO_PUBLIC_*` is restricted to genuinely public configuration such as the gateway URL;
- `federation-omega-operator` remains internal-only.

## Current proof boundary

PR #1266 / F110 proved source admission of the provider-neutral gateway contract and original Expo shell.

PR #1267 / F111 proved the client/build foundation on signed main `26296699d7b5f78c77d9cbdcc7bb83b44059af08`, tree `46db1cbd94245c3b8d5d1616fd8893b1b2a838be`, with exact-head Airlock/ProofOS, Bubbles and Leak Guard success. F111 is canonically released.

F112 is the outer-gateway source candidate. Until its own exact-head CI and signed-main readback complete, its strongest state is `GATEWAY_SOURCE_CANDIDATE_UNDER_ADMISSION`.

F110/F111/F112 source work does **not** by itself prove a deployed gateway, owner identity provider, Google AI Studio semantic execution, Gemini/Vertex inference, OpenRouter provider execution, KDV runtime binding, streaming chat, Android/iOS installable build, app-store release, production traffic or owner-value superiority.

The remaining maturity chain is:

`GATEWAY_SOURCE_ADMITTED -> GATEWAY_RUNTIME -> AUTHENTICATED_OWNER_SESSION -> REAL_SOURCE_READBACK -> REAL_PROVIDER_READBACK -> STREAMING_CHAT -> ANDROID_INSTALLABLE -> IOS_BUILD_PATH -> STAGING -> END_TO_END -> PRODUCTION_READY_VERIFIED`

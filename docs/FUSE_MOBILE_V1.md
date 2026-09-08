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

## Security boundary

- no provider credentials in the app;
- short-lived authenticated server sessions;
- server-side provider and source credentials;
- consequential effects remain Human-First/SOVARA gated;
- connection/configuration does not equal runtime proof;
- mobile status labels must come from fresh capability/health readback.

## Current proof boundary

This tranche proves source architecture and deterministic gateway routing only after its local/source CI courts pass. It does **not** prove a deployed gateway, OpenRouter provider execution, KDV runtime binding, Android/iOS installable build, app-store release, production traffic or owner-value superiority.

The next maturity chain is:

`SOURCE_ADMITTED -> GATEWAY_RUNTIME -> AUTHENTICATED_OWNER_SESSION -> REAL_SOURCE_READBACK -> REAL_PROVIDER_READBACK -> STREAMING_CHAT -> ANDROID_BUILD -> IOS_BUILD -> STAGING -> END_TO_END -> PRODUCTION_READY_VERIFIED`

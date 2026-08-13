# Bubbles Federation Governor Ω4

Ω4 scales the Ω3 chat governor across Federation Omega without copying a heavy governor into every chat.

## Architecture

- one Federation kernel
- project governors and matter walls
- thin chat shims (maximum 4 KiB)
- shared mission registry
- project-scoped evidence cache
- capability registry with minimum specialist formation
- federation-wide work fingerprinting and deduplication
- inheritance/bootstrap capsules
- federation health correlation for duplicate and idle executable missions
- shared performance metrics

## Reuse decision

`PROJECT + OBJECTIVE + PROOF_GAP + ACTION + TARGET + SOURCE_VERSION`

The project identifier is intentionally part of the fingerprint to prevent cross-matter contamination.

## Relationship to Ω3

Ω3 remains the mission-local execution governor. Ω4 adds Federation scope: project walls, shared registries, cross-chat reuse, inheritance and correlation.

## Scope boundary

Ω4 governs registered work routed through this layer. It does not claim platform-wide visibility into arbitrary chats or provider internals.

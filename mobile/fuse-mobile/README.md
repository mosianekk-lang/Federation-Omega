# FUSE Mobile

Minimal Expo client for the FUSE Mobile v1 source-admission tranche.

The client is intentionally thin: it consumes a server-issued Federation capability manifest and never embeds provider credentials. Heavy orchestration, Kim Dataverse retrieval, OpenRouter/model routing, agents, tools, proof and effect authority remain behind existing Federation server-side controls.

Current source lane: PR #1266 under F110 coordination. Production runtime, authenticated gateway, real provider/source readback and installable Android/iOS builds remain separate maturity gates.

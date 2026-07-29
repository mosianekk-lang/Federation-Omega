# PFRD-Ω Model-Independent Prevention Kernel v2.1.0

This directory stores the sealed deployment source for the PFRD-Ω external enforcement service.

## Integrity

The source archive is divided into bounded Base64 transport parts. CI concatenates the parts, reconstructs the exact ZIP, verifies its SHA-256 checksum, verifies every source file against `MANIFEST_SHA256.json`, then qualifies the local gateway, the distributed Docker/OPA topology, provider execution/readback, approval consumption, replay rejection and atomic release sealing.

## Current promotion boundary

- Source package: sealed
- Local external gateway: qualified
- Distributed Docker/OPA deployment: must pass GitHub qualification
- GHCR container: published only after qualification passes
- Live OpenAI model call: requires a securely configured runtime key
- Cloud Run production deployment: requires authenticated Google Cloud deployment and provider-native readback

No source record or CI success is treated as production deployment.

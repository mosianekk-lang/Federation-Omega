# SOVARA LiteLLM v2.3.0 — Converged Provider Admission

This release preserves the exact 33-alias, zero-dilution v2.3 source bundle and an additive provider-admission overlay.

- Base bundle SHA-256: `2dc95a249938604e3117d26e81da4afada96e3c836ab9dde3d80776187cf15bd`
- Provider-admission overlay SHA-256: `7d15c31e266a1424d982be82655b07c96afe29480ac2f921639215433204794f`
- Configuration SHA-256: `8cad48d954cd960b37b8c94559a19de244ffbd6d0ca1f7450dcec7b054d7d554`
- Google Drive folder: `1tRPIHXL4PZUAs5M4MhQ3W9I8oHjPd6K7`
- Base Drive bundle file: `1PDUZaxbnU4dsqd-VqCj24VkMff0EAPVa`

The push-to-main provider workflow authenticates through the existing repository-scoped Google WIF route, verifies symbolic Secret Manager references, performs direct provider canaries, builds a digest-pinned LiteLLM image, deploys a separate Cloud Run canary, promotes a separate production gateway only after semantic proof, and automatically restores the previous production revision on failure.

No credential value is committed to this repository. Runtime receipts are written under `deployments/sovara-litellm/v2.3.0/`.

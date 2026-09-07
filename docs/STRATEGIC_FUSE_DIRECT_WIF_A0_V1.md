# Strategic FUSE Direct WIF Vertex A0 v1

This is a subordinate, no-effect executor route for `GAP-STRATFUSE-002`.

It reuses the existing owner-only GitHub Actions WIF/ADC host and performs exactly two authenticated GET reads: Service Usage state for `aiplatform.googleapis.com` and the exact Vertex publisher-model metadata for `gemini-2.5-flash` in `global`.

It does not call `generateContent`, access a Gemini secret payload, mutate IAM/provider state, deploy Cloud Run, shift traffic, create a new scheduler/runtime/provider identity, or authorize spend.

A `VERTEX_A0_DIRECT_WIF_READBACK_VERIFIED` receipt proves only the A0 provider-read predicate for the exact target. Semantic Gemini execution, FSED runtime binding, durable recovery, soak and `COMPLETE_VERIFIED` remain separate maturity gates.

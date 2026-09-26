# FUSE LocalLLM Hybrid Intelligence Overlay v0.3.0

This overlay extends the immutable FUSE LocalLLM Desktop v0.2.2 Drive-custody baseline without altering its 21 source files.

## Adds

- SOVARA-aligned Gemini primary provider routing using Google Vertex AI.
- Local-private fallback through the existing FUSE LocalLLM OpenAI-compatible loopback API.
- Eight verified specialist roles: Alpha-Omega Reasoner, CFBE Critic, Creative Brief Compiler, DesignIR Validator, Route Ranker, Storyboard Continuity Critic, Provenance Analyst, Challenger Judge.
- Structured JSON provider receipts with provider/model/request/usage provenance.
- Automatic local-only routing for CONFIDENTIAL, LEGAL_EVIDENCE and SECRET data.
- Provider race with deterministic oracle support and no self-awarded winner when no oracle exists.
- Gemini council that preserves dissent rather than synthesizing false consensus.
- Fail-closed fallback: provider failure changes carrier, not mission identity or owner intent.

## Runtime contract

The core LocalLLM service remains loopback-only on port 8999. The provider fabric is installed beneath:

`%LOCALAPPDATA%\FUSE\LocalLLM\provider-fabric`

and exposed through:

`FUSE-LocalLLM-Hybrid.cmd`

Gemini calls use the current authenticated gcloud/ADC context and never persist access-token values. No API key is embedded in the package.

## Proof boundary

The provider route and 8/8 role + 8/8 adversarial holdout have been proven in the Federation estate. The matched 2x performance gate is **not** proven (measured 0.976554x), so this overlay does not claim hyper-performance.

The overlay does not grant Gemini FUSE authority, Windows effect permission, mission finality, or permission to send sensitive data externally.

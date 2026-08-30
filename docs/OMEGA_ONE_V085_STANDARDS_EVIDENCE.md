# Omega-One v0.8.5 standards evidence note

This note records the public-standard targets used by the branch-only interoperability candidate.

- MCP target: protocol version 2026-07-28. The release uses a stateless core; requests carry `MCP-Protocol-Version`, `Mcp-Method`, and `Mcp-Name`; Tasks are an extension rather than a core session primitive.
- A2A target: released 1.0.0 specification. Agent capabilities and extensions belong on the Agent Card; individual skills carry id/name/description/tags and optional input/output media modes.
- OpenTelemetry target: Semantic Conventions 1.44.0. Omega-One emits its own `omega.*` correlation attributes alongside standardized attributes such as `service.name` and `gen_ai.operation.name`.

These are translation targets only. External-standard compatibility does not grant provider credentials, execution authority, production deployment status, semantic readback, or owner-value maturity.

# FUSE Astra+ Communication Protocol Awareness v0.1

Canonical identity is semantic: `PROTO.*`. Historical implementation names and transports are adapters, not business logic.

## Purpose

The communication layer distinguishes **intent**, **semantic protocol**, **binding/transport**, **version**, **identity/auth**, **delivery semantics**, and **observability**. It fails closed on ambiguous or lossy negotiation rather than silently downgrading.

## Current protocol families

- `PROTO.MCP` — tool/context interoperability. Current preferred public contract: MCP `2026-07-28`, with stateless core and header-based routing.
- `PROTO.A2A` — agent-to-agent discovery/collaboration/task lifecycle. Preferred public contract: A2A `1.0`, with multiple bindings including JSON-RPC/HTTP, gRPC and HTTP/REST.
- `PROTO.AGUI` — agent-to-user event/state synchronization.
- `PROTO.CLOUDEVENTS` — vendor-neutral event envelope.
- `PROTO.JSONRPC`, `PROTO.GRPC`, `PROTO.SSE`, `PROTO.WEBSOCKET` — generic RPC/streaming bindings.
- `PROTO.OPENAPI` — synchronous HTTP API description.
- `PROTO.ASYNCAPI` — event-driven API description and protocol bindings.

## Awareness rules

1. Passive/declared detection only by default; no intrusive network scan.
2. Mission intent is compiled before protocol choice.
3. Protocol and transport are separate decisions.
4. Version/capability negotiation must be explicit.
5. Silent semantic downgrade fails closed.
6. Retry is allowed only for operations declared idempotent/replay-safe.
7. Exactly-once delivery is never assumed from transport alone; dedupe/idempotency belongs to the mission envelope.
8. Correlation, causation, mission ID, trace context and content identity survive protocol translation.
9. Translation through Ω-LINGUA must preserve effect semantics, not merely field shape.
10. Protocol support is not production interoperability until live semantic courts pass.

## Proof boundary

This package implements protocol recognition, intent selection, version negotiation and retry/downgrade rules. It does not claim live MCP/A2A/AG-UI interoperability until provider-native readback courts complete.

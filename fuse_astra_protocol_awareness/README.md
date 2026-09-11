# FUSE Astra+ Communication Protocol Awareness v0.2

Canonical identity is semantic: `PROTO.*`. Historical implementation names and transports are adapters, not business logic.

## Purpose

The communication layer distinguishes **intent**, **semantic protocol**, **binding/transport**, **version**, **schema**, **identity/auth**, **session semantics**, **delivery guarantees**, **flow control**, **replay/idempotency**, **drift**, and **observability**. It fails closed on ambiguous or lossy negotiation rather than silently downgrading.

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
11. Session state, resume, cancellation and deadlines are negotiated capabilities rather than inferred from transport.
12. Schema fingerprints are versioned evidence and drift invalidates affected compatibility claims.
13. Workload identity/auth binding must be explicit when the mission requires it.
14. Backpressure is part of protocol correctness; saturation must not become hidden message loss.
15. Route selection is based on semantic guarantees first and throughput preference second.

## Communications hypervisor

`hypervisor.py` adds a provider-neutral layer above concrete protocol bindings:

- `SchemaContract` produces deterministic schema fingerprints and compatibility judgments.
- `EndpointContract` models capabilities, auth schemes, session mode, delivery, idempotency, resume, deadlines and inflight capacity.
- `ProtocolHypervisor` refuses routes that weaken the mission's semantic or policy contract.
- `ReplayProtector` detects duplicate/out-of-order mission-local messages without claiming distributed exactly-once semantics.
- `FlowWindow` provides explicit backpressure.
- `ProtocolDriftDetector` detects version, transport, capability, auth and schema changes requiring re-verification.

A communication path is therefore not considered equivalent merely because bytes can be exchanged. Equivalent communication requires compatible meaning, effects, identity, delivery, session and proof semantics.

## Proof boundary

The package implements protocol recognition, intent selection, version negotiation, retry/downgrade rules and local protocol-hypervisor mechanics. It does not claim live MCP/A2A/AG-UI interoperability, distributed exactly-once delivery, or production protocol parity until provider-native/readback and independent semantic courts pass.
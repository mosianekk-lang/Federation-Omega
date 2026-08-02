# Project memory

## Canonical state

- Product: EvidenceOps Capability Heartbeat verified-v4 integration
- Base: Federation Omega `bbc122feb44e5be783067bde48cb373974f62c32`
- Runtime: Python standard library; local SQLite facade
- Maturity: `DURABLE_FOUNDATION_IMPLEMENTED_NOT_ATTACHED`
- Runtime ceiling: `A0`, recommendation-only
- Master authority: `VerifiedV4Authority`

## Decisions that must survive context loss

1. The verified-v4 foundation is the sole policy, scoring, inheritance, signing, receipt and respawn authority.
2. Existing engine, system, Bible, runtime, MCP, CLI, scheduler and surface catalogue paths are facades or scaffolding. Their existence cannot authorize ingress or prove liveness.
3. There is one caller-driven on-input recommendation path. Scheduled work is inventory-only and has zero recommendation authority.
4. Every envelope and registry record is `A0`; there is no effectful heartbeat path and no permit field that can widen it.
5. Owner, matter, classification, schema, adapter version, signing version and control generation inherit exactly or become stricter where the foundation permits.
6. Maximum propagation depth is three. Every forwarding hop requires the complete signed root-to-current lineage.
7. Registry binding includes node, key ID, signing version, secret-safe fingerprint and rotation/control generation. Static files never contain signing material.
8. Stop-generation fencing is mandatory. Never add a compatibility bypass.
9. Destination receipts bind the exact accepted envelope and a destination registration that is fresh at explicit verification time.
10. Respawn is semantic readback, not hash presence. It cross-binds policy, every fresh registry record, ledger, parent event, receipts, generation and false live-awareness flags.
11. Turn ingress carries no raw task, chat, message, evidence, document, transcript, personal, legal or credential content at any privacy tier.
12. Idempotency binds the complete canonical payload. Identical replay is stable; a reused operation identifier with changed content is a conflict.
13. Static catalogues, workflows, Bible policies and events are explicitly synthetic and never executable authority.
14. Catalogue presence, `EXECUTABLE_NOW`, `SESSION_CONNECTOR_AVAILABLE`, `SOURCE_IMPLEMENTED_NOT_HOSTED`, an unhosted API or an MCP tool declaration cannot authorize ingress.
15. Connector result summaries are never persisted; only hashes and controlled status codes survive.
16. Adapter remediation and scheduled heartbeat cycles are inventory-only. Do not restore route selection, retry advancement or automatic action.
17. JSON uses duplicate-key rejection; bounded local paths reject parent, dot, empty and symlink escape segments.
18. The runtime service and MCP adapter do not currently implement heartbeat contracts. Keep them as obligations until code, authentication tests and hosted readback exist.
19. Live master attachment, active-chat inventory, per-chat emitters, unsolicited injection and system-wide awareness remain false.
20. Preserve the 24-test legacy coverage map and the full verified-v4 foundation regression corpus when extending behavior.

## Safe extension

A new surface may be added to the synthetic catalogue for inventory. Ingress requires a separately registered foundation node, injected signer, fresh registration, complete lineage, destination receipt and an on-input caller. Provider API or MCP implementation is a later Formation-governed mission with current documentation, authentication, deployment and semantic readback.

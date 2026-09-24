# SOL 6.2 Complete FUSE Client Runtime

This service makes SOL 6.2 the owner-facing runtime instead of requiring the ChatGPT application.

## Ownership boundary

The existing FUSE Sovereign Plane is the primary orchestration, estate-resolution and route-election facade.

SOL 6.2 remains the transactional mission truth and verified-state-transition runtime beneath that plane. The Sovereign Plane may rank only routes that SOL has already classified as current, callable, authorized and privacy-safe; it cannot mint authority, provider effects, proof or completion.

The service reuses:
- FUSE Mobile Gateway for authenticated provider/model routing;
- FUSE Genesis Resident Executor v2 for durable execution wake/continuation;
- SOL 6.2 SQLite transactional truth spine for missions, client state, attempts, negative-route memory and proof;
- existing provider adapters rather than embedding provider credentials in the client.

The attachment hierarchy is:

`START:FUSE_ONE -> FUSE Sovereign Plane -> estate.resolve / route portfolio -> SOL 6.2 transactional truth -> FDOF/SICF effect fencing -> Genesis resident execution -> ProofOS/Reality Judge`.

It creates no second scheduler, mission database, proof root, authority root or Judge.

## Provider restriction rule

Provider-specific capacity or product restrictions such as context-window exhaustion, rate limits, quota exhaustion, unavailable models/tools or provider UI limitations are route-local. They cannot mutate the owner mission. The client runtime negative-caches the failing route, selects another qualified route, harvests a missing capability if necessary and persists continuation.

Authorization, privacy, legal, safety and high-impact effect gates remain fail-closed. The runtime reroutes around provider product limitations; it does not bypass authority or safety boundaries.

## Continuation

Immediate work is bounded per wake. Nonterminal work emits a typed SOL62_CLIENT_RESUME_PACKET_V1 and is enqueued to the existing Genesis resident executor. The estate clock remains external; no new scheduler is introduced.

Mission completion is only SOL 6.2 VERIFIED_REALITY: observed target state plus required proof.

## Sovereign Plane attachment

The source binding is `sol_61_runtime/sol_62_sovereign_plane_binding.py`.

It stamps every SOL client mission with a `SOL62_SOVEREIGN_MISSION_ENVELOPE_V1`, persists route-election receipts, and propagates the plane identity into durable resume packets. The adapter can reorder only routes already admitted by SOL hard gates. Unknown/failed external route resolution degrades to the deterministic SOL ordering and is route-local rather than mission-terminal.

Truth boundary: `SOVEREIGN_PLANE_BOUND != EXTERNAL_ESTATE_RESOLVER_LIVE != PROVIDER_EXECUTION != VERIFIED_REALITY`.

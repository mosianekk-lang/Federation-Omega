# FUSE Mobile Gateway

Thin owner-facing perimeter for FUSE Mobile. It is not a second Federation and does not replace FIO, SOVARA, FDOF, KDV, ProofOS, the private Gemini Gateway, OpenRouter/LiteLLM, or `federation-omega-operator`.

## Public mobile contract

- `GET /health` — source/runtime readiness without credentials.
- `POST /v1/session` — exchanges a credential only after an external identity verifier is bound; default source runtime fails closed.
- `GET /v1/federation/health` — authenticated compact health summary.
- `GET /v1/capabilities` — authenticated server-issued `FederationCapabilityManifest`.
- `POST /v1/chat` — authenticated request routed through FUSE/OF50/FIO; consequential effects remain held for owner/SOVARA approval.

The gateway deliberately has no privileged `/execute` passthrough. The existing `federation-omega-operator` remains an internal control surface.

## Provider architecture

Provider credentials are server-side only. The source-only manifest can advertise configured routes without pretending they are live:

- Google AI Studio / Gemini Developer API via the admitted SOVARA semantic-canary route;
- private SOVARA Gemini Gateway / Vertex AI;
- OpenRouter through the existing SOVARA/OpenRouter processor mesh;
- SOVARA LiteLLM when its deployment/runtime proof exists;
- KDV and other source adapters through server-side retrieval.

`CONFIGURED` is not a routing-eligible health state. Provider eligibility requires a proof-bearing state such as `RUNTIME_VERIFIED`, `VERIFIED_SCOPED`, `HOSTED_VERIFIED`, `BEHAVIOR_VERIFIED`, or `HEALTHY`.

## Authentication boundary

The gateway source supplies a short-lived HMAC session codec and an identity-verifier interface. It does not invent an owner identity provider. The production runtime must bind a real verifier and a session signing secret from a protected server-side secret store. Without them, `/v1/session` returns a held/unbound result.

The mobile client never receives provider secrets, Cloud Run admin tokens, service-account keys, OpenRouter keys, Gemini keys, or KDV credentials.

## Source lineage

The gateway implementation was built on F112 and carried forward under F113 because F112 expired before admission. F113 restacks the exact F112 gateway tree onto signed main `8776693d846117a22fcc1135e9c92a09e48050eb`, preserving the non-overlapping CANVA Ω-MAX delta. Exact lineage is recorded in `RESTACK_PROVENANCE.json`.

Until F113 exact-head courts and signed-main readback complete, the strongest state is `GATEWAY_SOURCE_CANDIDATE_UNDER_ADMISSION`.

## Truth boundary

Source admission of this service proves the perimeter contract only. It does not prove:

- a deployed Cloud Run revision;
- owner identity-provider verification;
- a live Google AI Studio semantic request;
- Gemini/Vertex execution;
- OpenRouter execution;
- KDV provider-native readback;
- streaming chat;
- installable Android/iOS artifacts;
- production traffic.

Each state requires its own provider/runtime/build readback.

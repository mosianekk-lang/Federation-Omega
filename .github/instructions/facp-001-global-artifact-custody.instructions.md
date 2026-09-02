---
applyTo: "**"
---

# FACP-001 — Global artifact custody and placement

Before creating, transforming or claiming completion of a material artifact, load `governance/federation_global_artifact_custody_policy_v1.json` and the current private canonical-state/route-authority projection.

Apply these rules to every current or future registered Federation chat, node, system, workstream and repository-integrated agent:

- GitHub is the canonical store for source code, tests, governance contracts and architecture files. Use a fresh purpose-specific branch and pull request; never mutate `main` directly.
- Resolve the owner-controlled canonical artifact vault through the private alias `FEDERATION_CONTROLLED_ARTIFACT_VAULT_CANONICAL`. Do not place exact private Drive identifiers in public source.
- Place qualification packets, evidence bundles, patches, manifests, logs, assurance records, provider receipts, rollback evidence and exported artifacts in the owning Drive work-package folder.
- Store artifact identity, version, digest, source epoch, generation anchor, proof state, lifecycle state and canonical pointer in the private Artifact Registry and Sync Bus/Kim Dataverse.
- Store full chronology and evidence gaps in the owning Local Bible. Store only the minimum necessary material summary and durable pointers in the Master Bible.
- Preserve provider-native runtime artifacts as distinct provider evidence. Copy them into Drive only when retention, cross-provider continuity or case preservation requires it.
- Treat `/mnt/data` and every session-local or chat-local sandbox as temporary construction storage. A sandbox link is not durable custody and cannot satisfy artifact completion.
- Assign one of `WORKING`, `CURRENT`, `SUPERSEDED`, `HISTORICAL` or `QUARANTINED`. Zero-byte, incomplete, corrupt or unverified artifacts are `QUARANTINED` and cannot be used as proof.
- Do not claim a material artifact task complete until the destination is resolved, upload or provider storage succeeds, the exact file/provider identity is read back, a digest and lifecycle state are recorded where available, the Artifact Registry and Bible captures are updated, and current/superseded relationships are reconciled.
- Preserve legal, employment, medical, family and other sensitive evidence inside the owning privacy wall. Only minimum necessary pointers may enter shared registries.
- Current registered nodes inherit FACP-001 through the private global capture-node and P0 dependency rule. Future nodes inherit at authorised bootstrap or their first registered material delta.

This policy does not create hidden access to closed chats, universal memory, background execution, provider authority, public-sharing authority, legal-filing authority, paid deployment authority or trust transfer. An unbootstrapped native chat remains unbound until its first authorised Federation registration or synchronization.

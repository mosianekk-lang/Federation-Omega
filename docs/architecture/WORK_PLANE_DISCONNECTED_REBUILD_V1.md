# WORK_PLANE_DISCONNECTED_REBUILD_V1

## Why Work Plane

The Self-Hosting R&D benefit census selected Work Plane as the first disconnected-rebuild target because its core runtime is already local and source-independent while durable hosted operation still has a Google Cloud Storage / Cloud Run adapter.

MODISA and RealityGuard are stronger offline reference implementations and should be reused. ChatBridge and FUSE-X remain provider-surface systems where external browser/X dependencies must not be hidden by an internal rebuild claim.

## Court

The court composes existing FUSE capabilities rather than creating new roots:

1. collect the exact Work Plane source/test/governance slice;
2. build a deterministic FULL snapshot with SOVARA Sovereign Backup;
3. verify archive SHA-256, CRC, manifest and every artifact;
4. restore the same archive into two empty temporary workspaces;
5. require exact file-set, size and SHA-256 equality;
6. install a Python socket-deny guard and prove it blocks connection creation;
7. compile the restored source;
8. run the existing Work Plane generation-CAS/recovery regression court from the restored copy;
9. corrupt one restored core file deliberately, restore it from the snapshot and require exact digest equality.

## Proof boundary

PASS proves that the selected **Work Plane core and its provider-neutral/in-memory durability semantics** can be reconstructed and tested from owner-controlled artifacts in a fresh disconnected Python workspace.

It does not prove live GCS access, Cloud Run deployment, Google identity, production traffic, persistent 24x7 service, cross-host disaster recovery, or owner value.

Those remain separate provider/runtime/value courts.

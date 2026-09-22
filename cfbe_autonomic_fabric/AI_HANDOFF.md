# AI handoff

Continue from mission CFBE-ACF-GENESIS-20260826.

Do not rename local source or repository publication as deployment. Preserve
the authority split in FORMATION_SPEC.md and the proof sequence in
cfbe_acf/proof.py. Run the full test suite and the MODISA build validator after
every change. Publish through a fresh branch based on the current main SHA and
never force-update the branch. Run hosted Airlock, Public Leak Guard and Bubbles
checks before considering merge or provider canaries.

The independent Genesis reviews blocked the first candidate. Their reproduced
defects were repaired in the current source: trusted consumed permits, immutable
execution contracts, effectfulness matching, fenced execution, UNKNOWN crash
holds, attested evidence-bound proof, application integrity, provenance restore,
secret-safe persistence, strict types and blocker lifecycle. Do not remove the
adversarial tests or reinterpret their local pass as production identity proof.

The closure remediation also removed caller-injected receipt verification,
scoped and reverified proof by mission/version/action, added canonical mission
supersession checks, a global cross-contract effect lease, strict JSON-container
validation, common provider-token detection, signed event/state checkpoints and
signed backup manifests. Integrity and authority keys remain runtime-only.

The final closure remediation made current-mission validation, permit
consumption, effect-lease acquisition and PENDING reservation one atomic write
transaction. It also binds checkpoint signatures to store and checkpoint IDs
and requires an independent monotonic anchor for health, backup and restore.

The local signed-file anchor was then removed after an independent reviewer
proved coordinated file-plus-database replay. Integrity-enabled stores now
require an independently configured expected store ID and a `TrustedAnchorStore`;
the supplied production-shaped adapter uses an external HTTPS atomic-CAS service.
The in-memory adapter is test-only. The external service itself is not deployed
or claimed by this package.

Genesis integrity provisioning is explicit and permitted only for a new empty
database when the external CAS has no record. Startup never auto-reseals missing
checkpoints. The bearer-authenticated CAS client disables all redirects.
Every governed mutation performs pre-write integrity verification inside the
SQLite write lock, preventing a legitimate follow-up write from blessing earlier
out-of-band tampering.

# Federation governed automatic-upgrade contract

RealityGuard 0.4 supplies one reusable `realityguard.upgrade.v1` decision contract. Federation hosts invoke it automatically at the end of every material `BUILD`, `FAILURE`, `RECOVERY`, `DEPLOYMENT` or `CANARY` cycle. Ordinary turns and unchanged observations do not open an upgrade path.

The contract reuses the current Federation registry and deduplicator, Alpha-Omega dependency ordering, action journaling, idempotency and uncertain-outcome reconciliation. It does not replace or duplicate those systems.

## Host sequence

1. Freeze a finite current capability manifest and its canonical hash.
2. Attest the exact target environment and provide current evidence references. Never inherit local, cloud-browser, account or deployment proof across surfaces.
3. Declare the desired outcome, changed source IDs, protected capabilities, proposed patch, failure and healthy-case tests, rollback, authority, cost and user burden.
4. Submit the material cycle to `realityguard upgrade`.
5. Obey the decision:
   - `NO_UPGRADE_REQUIRED` or `OBSERVE`: retain evidence; do not mutate.
   - `PATCH_EXISTING`: use the selected current component; do not fork a parallel engine.
   - `CREATE_CANDIDATE`: enter the governed competency lifecycle; do not promote.
   - `BLOCK_DUPLICATE_UPGRADE` or `BLOCK_UNSAFE_UPGRADE`: quarantine the candidate.
6. For an actionable decision, obtain and consume a separate single-use Formation permit immediately before the selected executor. The RealityGuard decision is not that permit.
7. Run the original-failure and healthy-case tests, execute rollback testing, invalidate every dependent artifact, repair in dependency order, and perform semantic readback.
8. Record a deduplicated learning receipt. Registration and later behavioral proof remain separate states.

## Meaning of automatic

Automatic means the integrated host invokes the decision at a material cycle boundary without waiting for another owner prompt. It does not mean a background daemon, silent provider-wide installation, autonomous authority expansion, foundation-model modification, or permission to bypass deployment and owner-acceptance gates.

`federation/REALITYGUARD_AUTO_UPGRADE_ADAPTER.v1.json` registers the source contract for every system in the current Federation canonical register. Entries marked `ADAPTER_REQUIRED` are an explicit integration queue, not a claim that those runtimes are already bound.

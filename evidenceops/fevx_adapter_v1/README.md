# EvidenceOps ↔ FEVX CSE Adapter v1

This package is the executable boundary between EvidenceOps and the federation-owned FEVX Cognitive Sovereignty Ecology.

## Placement

```text
Federation Omega
  └─ FEVX CSE (shared cognitive governance and assurance)
       └─ evidenceops_fevx_adapter_v1 (read-only case wall)
            └─ EvidenceOps (evidence, legal and forensic domain engine)
```

FEVX is not absorbed into the EvidenceOps evidence kernel. EvidenceOps supplies a typed, case-walled packet. FEVX returns a separate derived recommendation. Neither the adapter nor FEVX may alter original sources or the Verified Facts Register.

## Enforced boundaries

- A0/A1 internal authority only.
- One `matter_id` and one `case_wall_id` per packet.
- Recursive rejection of nested cross-case identifiers.
- No external send, filing, payment, publication, destructive action, disclosure, source mutation or verified-fact write.
- Derived outputs remain `HELD_FOR_EVIDENCEOPS_REVIEW`.
- Derived records are stored in a database with no source, document, evidence, chronology or fact tables.
- Repeat requests are idempotent.
- Ledger tampering is detected.
- Rollback and reapply are tested.
- Level 6 autonomy is not inherited or granted.

## Runtime

The verified reference implementation reconstructs the exact digest-pinned CSE v1.1 wheel for the base ten modules and imports the source-native CSE v2 frontier ten modules from `systems/fevx-frontier-v2`. The adapter therefore executes twenty modules when invoked from an authorised runtime.

The earlier synthetic provider canary proves its named integration controls. It does not prove legal correctness or a real case outcome.

Phoenix now treats this public repository as a quarantined source plane. Legacy adapter workflows must not be re-enabled or used to commit generated runtime receipts. Current or future execution belongs in the separate private execution plane or another authorised runtime, with proof retained as immutable artifacts or in the approved external append-only evidence store.

## Continuous learning integration

`learning_integration.py` translates every adapter terminal result and exception into the Federation learning fabric:

- successful runs record proof, value and reusability candidates;
- failed checks preserve evidence and activate repair and regression triggers;
- missing real-case accuracy remains an explicit `UNSUPPORTED_CLAIM` constraint;
- Level 6 ineligibility remains an `AUTHORITY` constraint;
- no learning event can mutate evidence, write verified facts, cross a case wall or create an external effect.

The runtime must supply an artifact or external-evidence workspace. Generated ledgers and trigger state must never be committed to canonical source.

## Commands

```bash
PYTHONPATH=".:systems/fevx-frontier-v2" \
python -m unittest discover -s evidenceops/fevx_adapter_v1/tests -v

python -m federation_learning \
  --workspace local-artifacts/evidenceops-fevx-learning \
  --policy governance/federation_learning_policy.json \
  verify
```

## Canonical source and evidence separation

Source contracts remain in the repository:

- Registration: `evidenceops/fevx_adapter_v1/registration.json`
- Policy: `evidenceops/fevx_adapter_v1/POLICY.yaml`
- Learning integration: `evidenceops/fevx_adapter_v1/learning_integration.py`
- Learning policy: `governance/federation_learning_policy.json`

Historical runtime records under `runtime/evidenceops_fevx_adapter/` are legacy evidence. New runtime results, learning ledgers, trigger-state snapshots and provider receipts belong in immutable workflow artifacts or the approved external evidence plane, not new source commits.

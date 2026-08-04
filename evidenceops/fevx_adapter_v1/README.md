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

The provider workflow reconstructs the exact digest-pinned CSE v1.1 wheel for the base ten modules and imports the source-native CSE v2 frontier ten modules from `systems/fevx-frontier-v2`. The provider canary therefore executes twenty modules.

The synthetic provider canary proves the integration controls. It does not prove legal correctness or a real case outcome.

## Commands

```bash
PYTHONPATH=".:systems/fevx-frontier-v2" \
python -m unittest discover -s evidenceops/fevx_adapter_v1/tests -v

PYTHONPATH=".:systems/fevx-frontier-v2" \
python evidenceops/fevx_adapter_v1/run_provider_canary.py \
  --repo-root . \
  --runtime-root runtime/evidenceops_fevx_adapter
```

## Canonical state

- Registration: `evidenceops/fevx_adapter_v1/registration.json`
- Policy: `evidenceops/fevx_adapter_v1/POLICY.yaml`
- Desired state: `runtime/evidenceops_fevx_adapter/state/desired_state.json`
- Actual state: `runtime/evidenceops_fevx_adapter/state/actual_state.json`
- Provider result: `runtime/evidenceops_fevx_adapter/results/latest.json`
- Provider proof chain: `runtime/evidenceops_fevx_adapter/proofs/`
- Workflow: `.github/workflows/evidenceops-fevx-adapter-v1.yml`

# Federation Omega Continuous Learning and Algorithm-Trigger Fabric v1

## Purpose

The fabric converts every material **success**, **failure**, **constraint**, **recovery** and **correction** into:

1. an append-only, hash-linked learning event;
2. a deterministic failure/constraint classification;
3. evidence-linked algorithm-trigger activations;
4. a current learning summary;
5. a verifiable artifact bundle.

## Separation of powers

The fabric observes and recommends internal responses. It cannot:

- exceed `A1_INTERNAL`;
- mutate source evidence or Verified Facts Registers;
- send, file, pay, publish or deploy;
- grant trusted autonomy;
- transfer trust between workflows;
- commit generated runtime ledgers into canonical source.

Runtime outputs belong in an immutable workflow artifact or an approved external append-only evidence store.

## Default triggers

| Event | Automatic internal trigger |
|---|---|
| Every failure | Preserve evidence, classify, select smallest repair, retest and read back |
| Repeated failure | Open circuit and require a materially different route |
| Every constraint | Register the constraint and discover the strongest safe fallback |
| Every success | Record proof, measure value and assess reusability |
| Success after failure | Bind a regression test and preserve before/after evidence |
| Repeated success | Create a route-confidence candidate without transferring trust |
| Correction | Propagate the correction and retest affected scope |
| Recovery | Verify repair, rollback and recovered-state readback |

## Artifact contract

A runtime invocation produces:

```text
learning_ledger.jsonl
algorithm_trigger_state.json
learning_summary.json
```

The ledger is append-only and hash-linked. Trigger state is derived and can be regenerated.

## CLI

```bash
python -m federation_learning \
  --workspace local-artifacts/federation-learning \
  --policy governance/federation_learning_policy.json \
  capture \
  --event-type FAILURE \
  --system-id EvidenceOps \
  --workflow-id MPMB298 \
  --mission-id CASE-INTELLIGENCE \
  --summary "Provider readback unavailable" \
  --category RUNTIME

python -m federation_learning \
  --workspace local-artifacts/federation-learning \
  --policy governance/federation_learning_policy.json \
  verify
```

## Phoenix compatibility

No workflow is enabled or broadened by this release. Source changes must enter through a branch and pull request. Continuous runtime capture must be invoked from the separate private execution plane or another authorised runtime and uploaded as immutable artifacts.

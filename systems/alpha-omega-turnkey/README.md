# Alpha→Omega Turnkey Build Engine

A Formation Innovation Engine derivative that converts a concept into a governed, decomposed, buildable, deployable and maintainable system plan.

## Operating modes

### Legacy sequential plan

`INTAKE → DISCOVERY → DECOMPOSITION → ARCHITECTURE → BUILD → TEST → DEPLOY → VERIFY → OPERATE → MAINTAIN`

The legacy mode remains available for compatibility.

### Progressive multi-path / multi-stream runtime

Version 1.1 adds a proof-bound runtime that:

- forms four materially different route families: verified reuse, compose/extend, materially new build and highest-information reversible experiment;
- evaluates eligible route families as separate parallel streams before the route tournament;
- decomposes the selected route into dependency-aware work units;
- executes independent A0/A1 streams concurrently through a bounded worker pool;
- serializes collision keys, shared-target writes, provider effects and consequential promotion;
- propagates failure and authority holds explicitly through downstream dependencies;
- opens a circuit after repeated failure fingerprints and requires a materially different route;
- writes deterministic checkpoints and a local hash-linked learning ledger;
- admits a capability to future reuse only after test, red-team and capability-assurance fan-in;
- replaces later rebuild work with proof-freshness verification and regression checks;
- reports work avoided immediately, but reports speedup only from complete matched capability cycles.

The runtime fans work out concurrently, then serializes result recording and canonical learning updates. This avoids conflicting writes while preserving real parallel execution.

## Quick start

Legacy local package:

```bash
python -m pip install -e .
alpha-omega examples/concept.json --workspace ./workspace --build
```

Progressive plan plus local safe-scope canary:

```bash
alpha-omega examples/progressive-multistream.json \
  --workspace ./progressive-workspace \
  --progressive \
  --simulate-safe \
  --max-parallel 8
```

The local canary exercises route formation, parallel waves, collision control, proof capture, learning, checkpointing and verified reuse. It performs no provider or external effect.

## Proof and authority boundary

A source file, plan, local package or local canary is not a provider deployment receipt. Provider promotion still requires:

- exact provider identity and action authority;
- provider deployment/execution receipt;
- semantic target readback;
- health and persistence checks;
- rollback proof;
- independent assurance for the promoted scope.

Unknown authority, missing proof and repeated unchanged failures fail closed. No raw credential value is stored in the progressive plan or learning ledger.

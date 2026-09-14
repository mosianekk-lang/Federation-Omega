# Formation specification — BCO-Prime successor v3.1

- Mission: `CFBE-BCO-V3-1-20260901`, version 1.
- Objective: extend sealed v3.0 into a separate signed-baseline, drift,
  regression and incremental-harvest release.
- Authority: A1 local internal; private persistence is separately gated.
- Cost and user burden: zero; `manualUserTasks: []`.
- Runtime: `ON_DEMAND_GOVERNED`.

## Terminal fruit

1. Sealed v2 and v3.0 hashes remain unchanged.
2. All inherited routes and tests remain passing.
3. Nine v3.1 operations pass the exhaustive verifier.
4. Baseline signature, trust-root, replay and tamper controls fail closed.
5. Partial, secret/licence, cancellation and regression states veto promotion.
6. Fresh extraction validates every package member and proof manifest.
7. MODISA and RealityGuard pass without granting deployment or promotion.

## Single effectful path

`SuccessorRegistryV31.execute` is the one dispatch surface. Its effects are
bounded local baseline reads, scanner reads, scoreboard append and
control-pointer selection. It has no provider, network or monitored-source
mutation route. Every repair candidate is declarative and non-executable.

## Cancellation and rollback

Mission-version and cancellation checks run before lock, compare, candidate and
commit. Cancellation performs no commit. Rollback changes only the local
control pointer to an exact verified baseline and preserves all evidence.

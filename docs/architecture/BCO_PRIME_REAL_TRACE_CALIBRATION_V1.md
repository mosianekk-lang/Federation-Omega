# BCΩ-PRIME real-trace calibration v1

This court tests whether a bounded scoring challenger predicts later opportunity
yield more accurately than the admitted BCΩ-PRIME radar profile.

## Temporal design

Each trace uses the final scope of a completed first-parent mission as its
feature snapshot. Its outcome window begins at the next mission and spans 20
later missions. Realized yield combines exact-file reuse, two-level scope reuse,
survival at the pinned source head, and absence of a related repair or revert.
The validator rejects any overlapping feature and outcome timestamps.

The oldest traces form training data. The newest 25 form an untouched
chronological holdout. A deterministic coordinate search sees training traces
only. Both training and holdout concordance must improve by at least 0.03, no
baseline-correct held-out pair may regress, and top-decile hard-regression rate
may not increase.

## Authority boundary

The court can emit only a shadow-profile candidate or a preserved negative
result. It never edits the live radar weights, dispatches work, creates provider
effects, expands authority, self-promotes, or assigns work to the owner.

## Run

```bash
python -m benchmarking.cfbe_omega.bco_prime_real_trace_calibration_v1 \
  --repo . --source-head "$(git rev-parse HEAD)"
python -m unittest tests.test_bco_prime_real_trace_calibration_v1
```

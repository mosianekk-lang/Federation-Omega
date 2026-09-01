# CFBE Value Foundry v1

Status: `SOURCE_IMPLEMENTED / PROVIDER_EFFECTS_HELD / STABLE_PROMOTION_FALSE`

## Purpose

Value Foundry v1 closes the gap between URI-shaped proof claims and admissible
evidence. It composes—not replaces—the Hyperleverage 100 control bindings,
Sentinel owner-value ingress and Bubbles owner-value/deployment court.

The flow is:

1. Resolve every proof reference through a caller-bound trusted receipt registry.
2. Verify exact evidence ID, subject, source head, record hash, payload hash,
   verifier allowlist, independent readback, status and receipt hash.
3. Compile matched prospective `BASELINE/BUBBLES` observations through the
   existing Sentinel adapter.
4. Evaluate owner value and runtime/deployment evidence through the existing
   Bubbles proof court.
5. Emit a deterministic foundry receipt. Even complete evidence reaches only
   `READY_FOR_SEPARATE_OWNER_PROMOTION_REVIEW`.

## Security and authority boundary

- A colon-shaped string is never admissible proof.
- The registry is a caller-supplied trust boundary; this source package does not
  authenticate a provider or create verifier authority.
- No metrics are inferred or manufactured.
- No provider call, deployment, IAM mutation, external effect or stable promotion
  occurs.
- Provider deployment, sustained owner value, market leadership and generalized
  superiority require separate empirical proof.

## Verification

```bash
python -m py_compile benchmarking/cfbe_omega/value_foundry_v1.py
python -m unittest -v tests.test_cfbe_value_foundry_v1
python -m unittest -v tests.test_federation_competitive_upgrade_fabric_v1
```

## CLI

```bash
python -m benchmarking.cfbe_omega.value_foundry_v1 \
  --input value_foundry_input.json \
  --output value_foundry_receipt.json
```

The input contains `champion_id`, `candidate_id`, `source_head_sha`, measured
observation records, optional runtime/deployment evidence, `evidence_registry`,
and `trusted_verifiers`. The output is an immutable deterministic decision
receipt with the promotion and effect boundaries explicit.

## Prospective Cohort 001

`prospective_observation_cohort_v1.py` registers the first ten-slot observation
cohort. Registration is deliberately empty: every slot requires a later real,
matched `BASELINE/BUBBLES` observation pair from its bound task oracle. Synthetic,
shadow, replayed or invented observations are prohibited and cannot count toward
owner value.

The canonical registry is
`cohorts/CFBE_VALUE_FOUNDRY_COHORT_001.json`. Its initial state is
`REGISTERED_AWAITING_PROSPECTIVE_OBSERVATIONS`, with all measurement counters at
zero and all value, deployment, effect and promotion flags false. Later records
must still pass Sentinel ingress, trusted-evidence resolution and the separate
owner-value deployment court.

## Passive observation collector

`passive_observation_collector_v1.py` provides the source-level connection from
eligible real directives to the next compatible empty Cohort 001 slot. It is a
callable in-process adapter, not a background watcher or deployed provider
runtime.

The collector:

1. requires an explicitly real, non-synthetic, non-shadow and non-replayed
   directive event;
2. resolves every directive proof through the existing trusted-evidence
   registry before binding the first compatible empty slot;
3. admits only explicitly real, measured `BASELINE/BUBBLES` observations whose
   directive, task class, oracle, pair, observation ID and source head match the
   binding and whose evidence receipts resolve;
4. deduplicates exact replays, rejects conflicting replays and preserves an
   immutable receipt-hashed overlay state; and
5. stops at `PAIR_READY_FOR_SEPARATE_FOUNDRY_EVALUATION` after a valid pair.

The registered empty overlay is
`cohorts/CFBE_VALUE_FOUNDRY_COLLECTOR_001.json`. It has zero bindings, zero
observations and zero ready pairs. Collection does not run automatically merely
because the source exists, and neither pair readiness nor source qualification
proves owner value, deployment, stable promotion or external effect.

```bash
python -m benchmarking.cfbe_omega.passive_observation_collector_v1 \
  --input collector_action.json \
  --output collector_state.json
python -m unittest -v tests.test_cfbe_passive_observation_collector_v1
```

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

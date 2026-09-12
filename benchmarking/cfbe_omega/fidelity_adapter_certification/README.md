# CFBE-Ω Fidelity Adapter Certification Wave 1

This package composes the admitted CFBE fidelity-isolation kernel and Bubbles work graph to run the same deterministic, effect-free court for GitHub, Google Drive, Gmail, and Canva. It adds no scheduler, credential broker, provider writer, or authority plane.

The profile contract contains only public-safe tool names, exact scopes, and connector-contract hashes. Live read evidence is supplied separately at runtime and is reduced to public-safe proof references before entering the scorecard.

## Run

```bash
python -m benchmarking.cfbe_omega.fidelity_adapter_certification \
  --observations /tmp/cfbe-wave1-observations.json \
  --output /tmp/cfbe-wave1-scorecard.json

python -m benchmarking.cfbe_omega.fidelity_adapter_certification.verify \
  /tmp/cfbe-wave1-scorecard.json \
  --output /tmp/cfbe-wave1-verification.json
```

Generated observations, scorecards, verification receipts, and heartbeats are runtime artifacts and must not be committed to canonical source.

## Result boundary

- `LOCAL_COURTS_4_OF_4_PASS` proves deterministic adapter fidelity only.
- `LIVE_READ_CANARIES_4_OF_4_AND_LOCAL_COURTS_4_OF_4_PASS` additionally proves the supplied read-only connector canaries at their recorded time.
- Every scorecard remains `executionState: NOT_EXECUTED`; it does not prove provider deployment, provider writes, stable promotion, or inherited authority.
- Rollback is deletion of generated runtime artifacts or reversal of the source branch. No provider state is changed by the court.

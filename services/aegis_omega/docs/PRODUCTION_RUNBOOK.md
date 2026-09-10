# Production Runbook

## Release gates
1. unit and regression tests pass
2. static/compile validation passes
3. benchmark harness completes
4. artifact digest generated
5. infrastructure plan reviewed
6. secrets created externally; never committed
7. Cloud Build produces immutable image
8. Cloud Run deploys with no public unauthenticated ingress
9. `/healthz` provider-native readback succeeds
10. authorized canary event produces a case and expected audit trail
11. rollback procedure is exercised

## Incident-safe defaults
- no raw personal content in normal telemetry
- no autonomous high-impact containment
- no model auto-promotion
- fail closed on `consent=false`
- preserve hashes and timestamps for evidence

## Rollback
Redeploy the previous immutable image digest, disable the current candidate model/config, and verify health/canary readback before closing the rollback.

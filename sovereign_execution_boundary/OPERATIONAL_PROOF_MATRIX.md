# Operational proof matrix

| Surface | Implemented | Locally tested | Live native proof | State |
|---|---:|---:|---:|---|
| Objective signature/supersession | yes | yes | n/a | VERIFIED_LOCAL |
| Anti-dilution comparison | yes | yes | n/a | VERIFIED_LOCAL |
| Completion theorem | yes | yes | n/a | VERIFIED_LOCAL |
| Provider failover/quarantine | yes | yes | mock only | PARTIAL |
| OpenRouter structured-output route | yes | no credential | no | OPEN_REQUIRED |
| OPA policy decision | adapter + Rego | contract only | no | OPEN_REQUIRED |
| Temporal durable replay | contract | contract only | no | OPEN_REQUIRED |
| SPIFFE/SPIRE identity | contract | contract only | no | OPEN_REQUIRED |
| Container runtime | definition | unavailable | no | OPEN_REQUIRED |
| Kubernetes deployment | manifests | schema not runtime | no | OPEN_REQUIRED |
| Production canary/rollback | specified | no | no | OPEN_REQUIRED |

Overall state: `HARDENED_BUILD_NOT_OPERATIONAL`. This label may change only after
every mandatory live row has provider-native readback and a proven rollback path.

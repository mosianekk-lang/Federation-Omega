# Omega-Max GitHub Operational Runtime

GitHub-native, proof-gated runtime providing:

- mutation-contract processing;
- digital-twin state readback;
- drift detection;
- repair canary execution;
- hash-chained proof records;
- exactly-once effect guards;
- heartbeat persistence;
- semantic target readback;
- real rollback drills.

The authority envelope is deliberately limited to reversible `A0`/`A1` JSON mutations under `runtime/omega-max/state`. It cannot send communications, alter provider IAM, access secrets, spend funds, or execute destructive external actions.

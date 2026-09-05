# AI Handoff

1. Read `README.md`, `BUILD_CONTRACT.json`, `FORMATION_SPEC.md` and `PROJECT_MEMORY.md`.
2. Run all tests and record the exact head/digest before integration.
3. Integrate only the Recovery Snapshot and Ledger Head first.
4. Use a new generation and five unique canary slots.
5. Promote only when duration and external-attempt median ratios are each at most 0.5, every proof succeeds, invariant failures are zero and harm signals are zero.
6. Treat any missing native metric as `UNKNOWN`, not zero.
7. Never claim deployment, production recovery or owner value from local tests.

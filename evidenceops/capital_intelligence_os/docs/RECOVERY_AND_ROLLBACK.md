# Recovery and Rollback

1. Freeze new writes to the affected packet.
2. Restore the last verified canonical-state JSON and receipt chain.
3. Re-run registry, route, lineage and PR-triage validation.
4. Re-run the end-to-end canary.
5. Read back the exact target state.
6. Preserve the failed state as evidence; never rewrite history.
7. Reopen only the affected gate.

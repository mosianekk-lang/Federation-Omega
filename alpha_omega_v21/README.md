# Alpha→Omega Autonomous Solution Foundry v2.1

Operational chain:

`DISCOVER → VALIDATE AUTHORITY → SNAPSHOT → BUILD → DEPLOY → EXECUTE → READ BACK → HEALTH → PERSISTENCE → ROLLBACK → RELEASE ARTIFACT → RECEIPT`

Included operational controls:
- deterministic release ZIP and SHA-256 manifest;
- heartbeat ledger;
- drift detection;
- failure classification;
- automatic repair selection;
- learning ledger;
- retirement controls;
- GitHub Actions artifact workflow.

Provider truth boundary:
- local release: operationally verified by tests;
- GitHub source/workflow: provider readback required after deployment;
- GitHub artifact run: only verified after Actions run evidence;
- Google Drive manifest: only verified after Drive write/readback;
- Cloud Run: provider-blocked without fresh cloud authority.

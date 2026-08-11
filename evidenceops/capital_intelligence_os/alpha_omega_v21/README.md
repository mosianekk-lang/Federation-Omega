# Alpha→Omega Autonomous Solution Foundry v2.2

Operational chain:

`DISCOVER → VALIDATE AUTHORITY → SNAPSHOT → BUILD → DEPLOY → EXECUTE → READ BACK → HEALTH → PERSISTENCE → ROLLBACK → RELEASE ARTIFACT → RECEIPT`

Maintenance chain:

`HEARTBEAT → DRIFT CHECK → FAILURE CLASSIFICATION → REPAIR ROUTING → LEARNING WRITE → RETIREMENT CHECK → FINAL HEARTBEAT → HASHED REPORT`

Included operational controls:
- deterministic release ZIP and SHA-256 manifest;
- executable maintenance heartbeat cycle;
- drift detection;
- failure classification;
- automatic repair selection;
- durable learning ledger;
- retirement controls;
- hashed maintenance report;
- GitHub Actions execution and artifact publication;
- connector-backed Google Drive manifest provider adapter with rollback receipt.

Run an operational release:

```bash
ao-foundry examples/concept.json --workspace ./workspace
```

Run one maintenance cycle:

```bash
ao-foundry examples/concept.json --workspace ./workspace --maintenance-cycle
```

Provider truth boundary:
- local release: operationally verified;
- GitHub CI, hosted release artifact and maintenance cycle: promoted only after provider-native run evidence;
- Google Drive manifest adapter: operationally verified for Drive-native document publication and reversible canary rollback;
- Google Drive binary ZIP publishing: provider-blocked at the current connector file-egress boundary;
- Cloud Run: provider-blocked without fresh cloud authority.

# Federation Omega Permanent Cloud Roadmap

Status: CONTROL_PLANE_DEPLOYMENT_IN_PROGRESS
Mission: FEDERATION-OMEGA-ROADMAP-DEPLOY v19
Owner: Kagiso Kim Mosiane
Policy: zero manual tasks; fail closed on missing authority; no capability dilution.

## Target architecture

One private Federation control plane coordinates provider-specific adapters without sharing credentials or confusing transport health with provider fruit.

- GitHub: source, release, workflow dispatch, immutable commit provenance.
- Google Cloud: Cloud Run services, Cloud Build, Artifact Registry, Secret Manager, Scheduler, Logging and rollback revisions.
- Google Drive/Docs/Sheets: governed evidence, command ledgers, lessons and future-work register.
- Gmail: authorized intake, notifications and evidence delivery; never a secret store.
- Apps Script: lightweight Drive/Workspace triggers; least privilege and bounded queues.
- OpenAI: reasoning/orchestration and MCP/Agents interfaces with typed tools and evaluations.
- Canva: derived reports and presentation surfaces; never the authoritative source.
- Formation: mission versioning, single-use permits, authority/cost boundaries and terminal stop.
- JARVIS Alpha-Omega: deadline-fit multi-path execution and route learning.

## Deployment programme

| Phase | Outcome | Hard proof gate | Automatic rollback/stop |
|---|---|---|---|
| 0. Identity convergence | Canonical project ID/number, runtime SA, deployer, Apps Script consumer and IAM map | Two independent provider reads agree | Stop on identity conflict |
| 1. Private control plane | Private MCP/operator endpoint and typed tool contract | Unauthenticated request denied; authenticated health and allowlist pass | Remove candidate tag / restore prior policy |
| 2. Reproducible lineage | Source hash → build ID → image digest → revision → traffic | Provider-native two-pass join, no stale cross-time match | Stop on missing source or digest |
| 3. Zero-traffic candidate | New revision deployed without serving production | Exact candidate digest/revision and previous allocation captured | Delete failed new service or restore exact prior traffic |
| 4. Semantic canary | Every provider action returns its required schema | Negative unknown-action test plus provider-specific read | Quarantine generic-handler collisions |
| 5. Controlled promotion | Candidate receives 100% only after all gates | Traffic sums to 100 and current revision matches attestation | Automatic exact traffic restoration |
| 6. Recovery and permanence | Tested backup, restore and scheduled verification | Immutable snapshot hash; bounded restore; two autonomous cycles | Circuit open after repeated failure |
| 7. Surface exploitation | Drive, Gmail, Apps Script, OpenAI, Canva and GitHub operate from one canonical state bundle | Source-linked receipts per surface; derived views reconcile | Isolate failing adapter, preserve core |
| 8. Adaptive improvement | Every success/failure updates route selection and future work | Learned fingerprint, latency, success rate, quarantine state | No reuse of quarantined route without two bounded successes |

## Current release gates

- [x] v0.2.1 package locally validated: 17 tools preserved; 34/34 integrated tests.
- [x] Deterministic archive and manifest verified.
- [x] Rollout design includes zero-traffic canary, two-pass attestation and traffic restoration.
- [x] Five-minute route-learning engine installed and forward-tested.
- [x] Machine-triggerable read-only auth canary deployed by this mission.
- [ ] Canonical project identity live-read and reconciled.
- [ ] Repository secret or keyless secret-broker authority proven.
- [ ] Live source/build/image/revision/traffic lineage attested.
- [ ] Private-access negative canary proven.
- [ ] Candidate deployment, promotion and rollback verified live.
- [ ] Two consecutive autonomous permanence cycles proven.

## Promotion law

A phase may advance only with provider-specific semantic fruit, a current mission permit, exact rollback state, independent readback and zero unresolved integrity errors. HTTP 200, queue DONE, a generated artifact or a generic health payload is not deployment proof.

## Continuous operation

Each cycle performs: observe → compile mission → invalidate stale actions → issue/consume one permit → execute minimum action → semantic readback → persist redacted receipt → learn → stop or recompile. Failures create quarantined routes and bounded future work; successes update preferred-route latency and regression tests.

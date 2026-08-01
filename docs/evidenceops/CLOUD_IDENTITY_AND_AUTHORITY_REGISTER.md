# EvidenceOps Cloud Identity and Authority Register

Status: ACTIVE_REPAIR / SOURCE_DERIVED / PROVIDER_READBACK_PENDING
Owner: Kim Kagiso Mosiane
Repository: mosianekk-lang/Federation-Omega

## Canonical Google Cloud estate

| Control | Expected value | Proof state |
|---|---|---|
| Project | sov-hybrid-suite | SOURCE CONSISTENT; provider readback pending |
| Project number | 257649435135 | SOURCE CONSISTENT; provider readback pending |
| Region | africa-south1 | SOURCE CONSISTENT; provider readback pending |
| WIF pool | github-federation-omega | SOURCE CONSISTENT; provider state unverified |
| WIF provider | github | SOURCE CONSISTENT; prior STS invalid_target |
| Trusted repository | mosianekk-lang/Federation-Omega | SOURCE CONSISTENT |
| Trusted ref | refs/heads/main | SOURCE CONSISTENT |
| Deployer identity | superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com | SOURCE CONSISTENT; existence unverified |
| Superior Logic runtime identity | superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com | SOURCE CONSISTENT; existence unverified |
| EvidenceOps MCP runtime identity | evidenceops-mcp-runtime@sov-hybrid-suite.iam.gserviceaccount.com | SOURCE PRESENT; existence unverified |

## Cloud Run services referenced by source

| Service | Purpose | Deployment state |
|---|---|---|
| architron9 | Superior Logic runtime | Historical service referenced; current version not deployed/proven |
| evidenceops-sovereign-runtime | Translator/mission runtime | CI canary defined; cloud deployment conditional and unverified |
| EvidenceOps MCP adapter | Remote MCP bridge | Deployment package exists; provider deployment unverified |
| IPEP audio worker | Audio processing vertical | Scaffold exists; production deployment unverified |

## Artifact and image resources

| Resource | Expected value | State |
|---|---|---|
| Artifact Registry | federation-omega | Source contract; live existence unverified |
| Superior Logic image | africa-south1-docker.pkg.dev/sov-hybrid-suite/federation-omega/architron9:<commit> | Build/deploy workflow defined |
| EvidenceOps repository | evidenceops | Setup script references separate MCP repository; live existence unverified |

## Secret and key resources referenced by source

| Secret reference | Consumer | State |
|---|---|---|
| fo-operator-admin-token | EvidenceOps MCP runtime | Secret contract only; version and access unverified |
| evidenceops-mcp-access-token | EvidenceOps MCP runtime | Secret contract only; version and access unverified |
| evidenceops-openai-runtime-key | AI/provider runtime | Required by incident containment; creation and binding unverified |
| KIM_CANONICAL_BACKEND_ID secret | Sovereign runtime | Required repository variable and secret; unverified |
| KIM_CANONICAL_RECEIPT_ID secret | Sovereign runtime | Required repository variable and secret; unverified |
| KIM_CANONICAL_STATUS secret | Sovereign runtime | Required repository variable and secret; unverified |
| KIM_DATAVERSE access-token secret | Optional Dataverse parity route | Optional and unverified |

## Required WIF mapping

- google.subject=assertion.sub
- attribute.repository=assertion.repository
- attribute.repository_owner=assertion.repository_owner
- attribute.ref=assertion.ref

Required condition:

`assertion.repository=='mosianekk-lang/Federation-Omega' && assertion.ref=='refs/heads/main'`

## Least-privilege bindings required

- roles/iam.workloadIdentityUser on the deployer service account for the exact repository principal set.
- roles/serviceusage.serviceUsageConsumer for the deployer.
- roles/run.developer and roles/run.invoker scoped to the required Cloud Run service.
- roles/artifactregistry.writer scoped to the required repository.
- roles/iam.serviceAccountUser on the selected runtime identity.
- roles/secretmanager.secretAccessor only on specifically named secrets for each runtime identity.
- roles/logging.logWriter for runtime service accounts.

## Repository variables required

- GCP_PROJECT_ID=sov-hybrid-suite
- GCP_REGION=africa-south1
- GCP_WIF_PROVIDER=<provider resource returned by provider-native verification>
- GCP_SERVICE_ACCOUNT=superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com
- GCP_RUNTIME_DEPLOY_ENABLED=false until provider-native verification and owner promotion decision

The WIF provider variable must not be populated from this source contract alone. It is applied only after `bootstrap_github_wif.sh --verify` returns `FEDOMEGA-WIF-CLOUD-VERIFIED`.

## Closure proof

This register becomes CLOUD_VERIFIED only when a provider-native inventory proves each identity and resource, the infrastructure workflow produces an artifact, and the artifact hashes and counts are independently read back.

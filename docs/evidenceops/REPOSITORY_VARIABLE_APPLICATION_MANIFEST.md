# EvidenceOps Repository Variable Application Manifest

Status: READY_NOT_APPLIED / PROVIDER_VERIFICATION_REQUIRED
Owner: Kim Kagiso Mosiane

## Rule

Only non-secret configuration belongs in GitHub repository variables. Secret values belong in Secret Manager or an approved encrypted runtime store.

## Shared variables

| Variable | Intended value | Application gate |
|---|---|---|
| GCP_PROJECT_ID | sov-hybrid-suite | Confirm project readback |
| GCP_PROJECT_NUMBER | 257649435135 | Confirm provider-native project number |
| GCP_REGION | africa-south1 | Confirm target resources are in this region |
| GCP_WIF_PROVIDER | Provider resource returned by verified WIF bootstrap | Apply only after FEDOMEGA-WIF-CLOUD-VERIFIED |
| GCP_SERVICE_ACCOUNT | superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com | Confirm service-account existence and WIF binding |
| GCP_ARTIFACT_REPOSITORY | federation-omega | Confirm repository exists in target region |

## Superior Logic variables

| Variable | Intended value | Application gate |
|---|---|---|
| SLRK_CLOUD_RUN_SERVICE | architron9 | Confirm service exists |
| SLRK_RUNTIME_SERVICE_ACCOUNT | superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com | Confirm identity and serviceAccountUser binding |

## Sovereign runtime variables

| Variable | Intended value | Application gate |
|---|---|---|
| GCP_RUNTIME_DEPLOY_ENABLED | false | Remain false until inventory and owner approval |
| KIM_CANONICAL_BACKEND_ID_SECRET_NAME | Provider-verified secret name | Confirm secret and runtime access |
| KIM_CANONICAL_RECEIPT_ID_SECRET_NAME | Provider-verified secret name | Confirm secret and runtime access |
| KIM_CANONICAL_STATUS_SECRET_NAME | Provider-verified secret name | Confirm secret and runtime access |
| KIM_DATAVERSE_URL | Optional non-secret endpoint | Apply only if Dataverse route is authorised |
| KIM_DATAVERSE_MISSION_TABLE | Optional table name | Apply only if Dataverse route is authorised |
| KIM_DATAVERSE_SECRET_NAME | Optional Secret Manager secret name | Confirm secret and runtime access |

## Application order

1. Verify project and WIF through the provider-native bootstrap.
2. Apply shared variables.
3. Run the read-only infrastructure inventory.
4. Confirm resource names from the inventory artifact.
5. Apply service-specific variables.
6. Keep deployment-enable variables false until authenticated canaries are authorised.
7. Record variable names and hashes of the manifest, never secret values.

## Prohibition

Do not populate GCP_WIF_PROVIDER from historical source repetition alone. Do not place OpenAI keys, bearer tokens, private evidence identifiers or secret versions in repository variables.

# NEXUS-CODEX Apps Script Deployer

This is the missing target-specific deployment module for
NEXUS-CODEX v3.1.1. It is designed for the existing ARCHITRON Apps Script
authority path and introduces no new credential, scheduler, or recurring cost.

## Locked release contract

| Field | Locked value |
| --- | --- |
| Project | `sov-hybrid-suite` (`257649435135`) |
| Region | `africa-south1` |
| Service | `nexus-codex-runtime` |
| Runtime service account | `fo-automation-agent@sov-hybrid-suite.iam.gserviceaccount.com` |
| Drive artifact | `1_r1qlRHeEcF7Xl-BSJpfWUWIRYs4C_Pm` |
| Artifact SHA-256 | `fabbdf9ec89c1ea4468515ba1659cc0019719c5bc5747084795148a354dc1518` |
| Staging bucket | `run-sources-sov-hybrid-suite-africa-south1` |
| Revision tag | `nexus-v311` |

## Execution contract

1. `nexusCodexPlanV1()` returns the immutable target and scope plan.
2. `nexusCodexStageAndSubmitV1()` verifies the Drive bytes, performs a
   generation-guarded upload, re-downloads and re-hashes the GCS object, reuses
   an existing matching regional build when present, and otherwise creates one
   build.
3. The build deploys a tagged revision with `--no-traffic`, verifies the service
   identity, runtime service account, ready revision, and release SHA marker,
   and performs tagged HTTP canaries.
4. Only a successful canary promotes the tag to 100%. A post-promotion failure
   restores the exact captured pre-deployment revision percentages when an
   earlier service existed.
5. `nexusCodexStatusV1()` provides read-only build and service proof without
   polling or creating a trigger.
6. `nexusCodexSubmitRollbackV1()` submits an idempotent rollback build from the
   persisted pre-deployment traffic map.

The module never logs OAuth tokens, request authorization headers, or
application secrets.

## Installation route

The existing Federation Omega Apps Authority Layer can install the single
`NexusCodexDeployer.gs` source file after taking a project snapshot. Merge the
three scopes in `appsscript.fragment.json` into the existing manifest without
removing existing scopes. The authority runner then invokes the plan and
one-shot deploy functions directly; no time trigger is required.

The effective Apps Script user must already hold `cloudbuild.builds.create` and
the bucket object permissions. The selected Cloud Build service account must
already hold the documented Cloud Run source deployment, Artifact Registry,
logging, storage, and service-account-use permissions. The adapter does not
expand IAM.

## Local verification

```sh
npm test
```

The deterministic tests cover integrity failure, idempotent reuse, provider
error handling, target confusion, rollback traffic construction, build
contract semantics, and secret-safe source behavior.

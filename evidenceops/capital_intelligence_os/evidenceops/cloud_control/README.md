# EvidenceOps Google Cloud Control Bootstrap

Run this from an authenticated Google Cloud Shell in the target project. It creates a keyless EvidenceOps operator identity, enables the control-plane APIs, grants discovery plus bounded runtime-management roles, creates the heartbeat event topic, binds existing private Cloud Run services when present, and produces a hashed capability inventory.

```bash
export EVIDENCEOPS_PROJECT_ID="sov-hybrid-suite"
export EVIDENCEOPS_REGION="africa-south1"
export EVIDENCEOPS_AUTHORITY_PROFILE="sovereign-full"
export EVIDENCEOPS_AUTHORITY_CONFIRMATION="AUTHORISE_EVIDENCEOPS_FULL_PROJECT_CONTROL_sov-hybrid-suite"
bash evidenceops/cloud_control/bootstrap_evidenceops_cloud.sh discover
bash evidenceops/cloud_control/bootstrap_evidenceops_cloud.sh bootstrap
bash evidenceops/cloud_control/bootstrap_evidenceops_cloud.sh deploy
bash evidenceops/cloud_control/bootstrap_evidenceops_cloud.sh verify
```

For keyless GitHub Actions access, set `EVIDENCEOPS_GITHUB_REPOSITORY` to the exact `owner/repository` before `bootstrap`. The provider condition restricts tokens to that repository.

The default `sovereign-full` profile grants the EvidenceOps operator the project Owner role after the exact confirmation string is supplied. This is full control of the selected Google Cloud project, including IAM and supported project resources. It does not automatically extend into other projects, folders, the organization or billing account; run a separately confirmed bootstrap at each required scope. Set the profile to `scoped` only when deliberately requesting reduced project authority.

The identity remains keyless: no JSON key is created or exported. Cloud Run service identity and GitHub Workload Identity Federation provide short-lived credentials without reducing the project role.

`deploy` publishes the Omega MCP control plane and the private Secure Capability Box. It binds a dedicated box identity to the exact Federation Omega admin-token secret, deploys the authenticated broker, and runs an issue/execute `STATUS` canary through the live operator. It also writes `chatgpt-activation.json`. The broader chat-integration mission remains open until the supported ChatGPT route itself is independently read back.

“Complete” requires the `verify` manifest plus one successful provider action and independent readback. Inventory alone proves discovery, not management.

`verify` now performs that proof automatically through the deployed Omega identity: MCP inventory readback, heartbeat publish plus Pub/Sub pull, a reversible topic-label mutation, exact rollback and final provider readback. Only after all four gates pass does the manifest promote `management_claim` to `PROJECT_OWNER_CLOUD_MANAGEMENT_HEARTBEAT_AND_ROLLBACK_READBACK_VERIFIED`.

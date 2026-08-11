# EvidenceOps MCP Adapter

Remote MCP bridge between ChatGPT/OpenAI clients and the existing Federation Omega Cloud Run operator.

## What is implemented

- authenticated remote `/mcp` endpoint;
- separate bearer secret for ChatGPT-to-MCP traffic;
- separate Secret Manager credential for MCP-to-operator traffic;
- Pro-compatible read-only `search`, `fetch`, `apps_script_list`, and `apps_script_get` tools;
- approval-gated `ingest_official_url`, `apps_script_backup`, and `apps_script_deploy` tools for clients/plans that support write actions;
- Cloud Run health endpoint and no-send status;
- Cloud Build deployment and least-privilege runtime service account;
- no credential values committed to GitHub.

## Deployment

1. Run `setup_gcp.sh` from an authenticated Cloud Shell.
2. Add a new random value to `evidenceops-mcp-access-token` in Secret Manager.
3. Confirm the existing `fo-operator-admin-token` has an active version.
4. Submit `cloudbuild.yaml`.
5. Read back `https://<service-url>/health`.
6. Register `https://<service-url>/mcp` in ChatGPT developer mode using Bearer authentication with the new MCP access token.
7. Scan tools and enable only the required actions.

## ChatGPT plan boundary

OpenAI currently permits Pro users to connect custom MCP apps for read/fetch access. Full write/modify MCP actions are available in Business and Enterprise/Edu developer mode. The server exposes both surfaces, but ChatGPT controls which actions can be enabled for the account/workspace.

## Security boundary

Do not grant Project Owner to this runtime. The runtime needs only Secret Manager access to the two named secrets and log-writing permission. The operator itself must enforce object/function authorisation and approval requirements. No email or filing action is exposed by this adapter.

## Completion truth

Code and deployment configuration are complete. Live binding is complete only after Cloud Run health readback and ChatGPT tool-scan confirmation. A screenshot or registry entry alone is not runtime proof.

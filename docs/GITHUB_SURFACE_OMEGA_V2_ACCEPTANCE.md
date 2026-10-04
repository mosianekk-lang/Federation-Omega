# GitHub Surface Omega v2 — Acceptance Court

Candidate source must remain source/CI only until every admission check is exact-head green.

## Mandatory candidate gates

- `python -m unittest discover -s tests -p 'test_github_control_plane.py' -v`
- Federation Omega Airlock / ProofOS
- Bubbles Command Bus
- Public Repository Leak Guard
- exact compare: base = current signed `main`; candidate 0 commits behind
- no scheduled trigger added
- no new repository writer
- no new unregistered OIDC workflow
- no provider/IAM/secret/deployment/traffic mutation

## Expected source behavior

Changed GitHub control surfaces fail closed on schedule, unregistered OIDC, `pull_request_target`, mutable Action refs, broad permissions, unsafe checkout credentials, unregistered agent privilege/MCP, and unregistered Copilot hooks.

The whole-estate scorecard is informational for legacy debt unless `strict_full_repository_scan` is separately promoted. Historical debt must be surfaced, not silently converted into a blocking migration without a dedicated convergence tranche.

## Provider gates that remain separate

- GitHub Main Airlock ruleset activation/readback (#146)
- direct-main negative canary
- code-scanning merge protection activation
- real build artifact + SBOM attestation and independent verification
- removal/admission of legacy GitHub cron workflows from `main`

A passing candidate must not claim any of those provider/runtime gates closed.

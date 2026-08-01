# EvidenceOps Legacy Workflow Retirement Register

Status: ACTIVE_CONTROL / DEPLOYMENT_INERT_PENDING_REVIEW
Owner: Kim Kagiso Mosiane

## Governing rule

Only workflows listed as CURRENT_AUTHORISED may perform cloud mutation. Historical workflows remain source references until individually reviewed, migrated to verified repository variables, protected by explicit owner gates, and re-proven against the current cloud identity register.

## Current authorised pathways

| Workflow | State | Mutation authority |
|---|---|---|
| evidenceops-infrastructure-inventory.yml | CURRENT / READ-ONLY | Inventory only after WIF verification |
| evidenceops-sovereign-runtime.yml | CURRENT / CONDITIONAL | Deployment disabled unless all repository-variable gates pass |
| deploy-cloud-run.yml | CURRENT / MANUAL / FAIL-CLOSED | Canary and optional promotion only after exact owner and WIF receipts |

## Deployment-inert legacy families

| Workflow family | Classification | Reason |
|---|---|---|
| nexus-* | LEGACY / SUPERSESSION_REVIEW | Historical recovery, preflight, diagnostic and deployment logic predating the current authority register |
| pfrd-omega-* | LEGACY / PRODUCT-SPECIFIC REVIEW | Separate historical recovery/canary path; no current production authority |
| live-thread-* | LEGACY / CONTINUITY-ONLY REVIEW | Historical live-thread deployment and key recovery path; not current platform deployment authority |

## Inertness rule

A legacy workflow is operationally inert unless all of the following are true:

1. it is expressly listed as CURRENT_AUTHORISED in this register;
2. it reads verified repository variables rather than stale hard-coded identities;
3. WIF verification returns FEDOMEGA-WIF-CLOUD-VERIFIED;
4. the affected service and rollback baseline are inventoried;
5. the user gives the exact workflow-specific approval token;
6. canary and authenticated health checks pass;
7. a receipt is preserved.

## Retirement actions

- Do not dispatch NEXUS, PFRD or live-thread mutation workflows during the current recovery mission.
- Harvest reusable code only through reviewed PR changes.
- Close or archive obsolete trigger PRs after supersession comparison.
- Remove scheduled or push-based mutation triggers before any legacy workflow can be re-authorised.
- Preserve historical receipts and source for provenance.

Maturity: LEGACY_PATHS_CLASSIFIED / MUTATION_NOT_AUTHORISED / SOURCE_PRESERVED

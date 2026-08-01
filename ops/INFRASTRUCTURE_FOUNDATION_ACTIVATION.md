# EvidenceOps Infrastructure Foundation Activation

This is the one authenticated Google Cloud bootstrap transaction required before the automated infrastructure inventory can run.

## Transaction

Run from an authenticated Google Cloud Shell with project `sov-hybrid-suite` selected:

```bash
set -euo pipefail

git clone https://github.com/mosianekk-lang/Federation-Omega.git
cd Federation-Omega
git fetch origin evidenceops/ai-ict-production-runtime-v1-4
git checkout evidenceops/ai-ict-production-runtime-v1-4

export PROJECT_ID=sov-hybrid-suite
export PROJECT_NUMBER=257649435135
export NEXUS_WIF_APPLY_APPROVAL=APPLY_NEXUS_OPERATOR_WIF_LEAST_PRIVILEGE

bash ops/bootstrap_nexus_operator_wif.sh --apply | tee /tmp/evidenceops-wif-apply.json
bash ops/bootstrap_nexus_operator_wif.sh --verify | tee /tmp/evidenceops-wif-verify.json

gh workflow run evidenceops-infrastructure-inventory.yml \
  --repo mosianekk-lang/Federation-Omega \
  --ref evidenceops/ai-ict-production-runtime-v1-4
```

## Required proof

The transaction is complete only when:

- the WIF pool state is `ACTIVE`;
- the provider state is `ACTIVE`;
- the deployer service account exists;
- the repository binding is present;
- the operator secret exists and the deployer can access it;
- the infrastructure inventory workflow produces `evidenceops-infrastructure-inventory`.

## Boundary

This transaction creates the missing authentication foundation only. It does not deploy the ICT runtime, create the database, create storage, or modify application security settings.

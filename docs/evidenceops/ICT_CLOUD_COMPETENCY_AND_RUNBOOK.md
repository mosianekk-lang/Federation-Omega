# EvidenceOps ICT Cloud Competency and Runbook

Status: ACTIVE TRAINING / PROVIDER EXECUTION PENDING
Owner and final authority: Kim Kagiso Mosiane

## Purpose

This runbook defines the minimum practical competence required to operate the EvidenceOps Google Cloud, GitHub Actions, Secret Manager, Cloud Run and incident-containment environment.

## Competency roles

### Cloud identity engineer
Must prove:
- authenticated project selection;
- project-number readback;
- WIF pool/provider inspection;
- exact attribute mapping and condition verification;
- service-account IAM inspection;
- least-privilege remediation;
- rollback commands;
- redacted receipt generation.

### DevOps engineer
Must prove:
- workflow source review;
- repository-variable validation;
- pull-request check interpretation;
- failed-job log analysis;
- artifact download and hash verification;
- branch and PR lifecycle control;
- no direct production promotion without gates.

### Runtime engineer
Must prove:
- Cloud Run service inspection;
- private service deployment;
- service-account binding;
- zero-traffic canary;
- authenticated health readback;
- traffic promotion and rollback;
- structured deployment receipt.

### Security engineer
Must prove:
- exposed-key containment;
- key revocation;
- Secret Manager version creation;
- runtime-only secret access;
- audit-log review;
- old-key rejection canary;
- incident closure evidence.

### Reliability engineer
Must prove:
- liveness/readiness distinction;
- queue and worker monitoring;
- failed deployment rollback;
- backup/restore test;
- OpenTelemetry or provider-native trace review;
- SLO and alert definition.

## WIF recovery runbook

1. Authenticate in an authorised Google Cloud administration surface.
2. Set project `sov-hybrid-suite` and read back project number.
3. Run `ops/bootstrap_github_wif.sh --plan`.
4. Review every missing control; perform no mutation from assumptions.
5. Confirm that `architron9` and `federation-omega` exist before applying the current bootstrap.
6. Apply only with `FEDOMEGA_WIF_APPLY_APPROVAL=APPLY_FEDOMEGA_WIF_LEAST_PRIVILEGE` after owner approval.
7. Run `ops/bootstrap_github_wif.sh --verify`.
8. Require receipt `FEDOMEGA-WIF-CLOUD-VERIFIED` and mutation_performed=false on verification.
9. Populate the four non-secret repository variables.
10. Rerun the infrastructure inventory workflow.
11. Download the inventory artifact and verify hashes/counts.
12. Update issue #52 and the cloud identity register.

## Secret Manager containment runbook

1. Treat plaintext OpenAI keys discovered in Gmail as compromised.
2. Create a dedicated EvidenceOps OpenAI project and replacement project key through the secure Platform flow.
3. Create secret `evidenceops-openai-runtime-key` in the approved Google Cloud project.
4. Add the replacement value as a new secret version without echoing it.
5. Grant accessor only to the selected runtime service account.
6. Bind the secret to a staging runtime.
7. Run a non-sensitive replacement-key canary.
8. Revoke the exposed keys.
9. Run the old-key rejection canary.
10. Record only redacted outcomes in issue #51.

## Cloud Run canary runbook

1. Require WIF verification receipt.
2. Build immutable image tagged by commit SHA.
3. Push to the approved Artifact Registry repository.
4. Deploy a tagged zero-traffic revision.
5. Verify latest created equals latest ready revision.
6. Obtain an identity token for the private URL.
7. Verify health contract, version and integrity fields.
8. Promote only with explicit owner input.
9. On failed post-promotion verification, restore the previous ready revision.
10. Preserve deployment receipt and image digest.

## EvidenceOps sovereign runtime dependencies

- Python 3.12 container runtime.
- Private Cloud Run service `evidenceops-sovereign-runtime`.
- Canonical backend identifier, receipt identifier and verified status supplied through Secret Manager.
- Optional Dataverse URL, table and access-token secret.
- Authenticated health readback.
- Repository variables enabling deployment only after WIF readiness.

## Failure classifications

- CONFIGURATION_EMPTY: required repository variable absent.
- WIF_TARGET_INVALID: provider resource rejected by STS.
- PROVIDER_UNVERIFIED: source contract exists but no provider readback.
- SECRET_UNBOUND: secret exists only as a requirement.
- DEPLOYMENT_UNVERIFIED: workflow/code exists without live service readback.
- CANARY_FAILED: revision deployed but health contract failed.
- PROMOTION_ROLLED_BACK: traffic restored after failed verification.

## Certification gate

A specialist is certified only after independently completing a read-only plan, supervised repair/canary, failure diagnosis, rollback exercise and receipt review. Documentation knowledge alone is insufficient.

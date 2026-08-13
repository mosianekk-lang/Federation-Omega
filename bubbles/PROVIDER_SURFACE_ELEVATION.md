# Bubbles Provider Surface Elevation — 13 August 2026

## Trigger evidence

User-supplied Google Cloud / Apps Script screenshots exposed provider-side evidence for four material Federation surfaces that were previously grouped under broad Google Cloud / Apps Script capability classes:

1. **Federation Omega Operator** — Cloud Run operator with public health/contract surface and token-gated `/execute` actions.
2. **ARCHON Admin Plane V5** — dedicated Cloud Run admin surface with historical capability-audit proof and a separate provider token.
3. **ARCHON Apps Script Translator** — script project `12CrTP0YUQbUpBvLklf_tInjN_k3L5qt3Tkp-M9pIO_O4Cs8dsYRH7kPO`, with screenshot deployment ID `AKfycbyaxovYOyaoMWFdsAZnbl2AIFU0PFY3hcGF-QRM1dmDqdtEHRFI7Ud7L_p7YCCVMG3J`.
4. **AFEME v4** — IAM-protected sovereign runtime reference.

The screenshot text itself is not treated as live IAM or execution proof. Provider/control records and fresh readback remain authoritative.

## New operating state

The Private Canonical Bridge now carries first-class specialist rows for all four surfaces, plus AI-liaison, handoff and capability-scorecard records. Source-side extensions are defined in `bubbles/platform_specialist_corps_extensions.py`.

## Read-only provider probe

`bubbles/provider_surface_probe.py` performs a no-effect discovery/readback chain:

- FO Operator public `/health` and contract read;
- FO Operator authenticated `STATUS` and `READ_CLOUD_RUN_SERVICE` only if a trusted token is already available through repository secret or authorised Secret Manager access;
- ARCHON Admin Plane public root/OpenAPI read;
- authenticated `capability_audit` only if a trusted token is already available;
- ARCHON Apps Script deployed `/exec` reachability/authentication-state probe;
- AFEME public probe and IAM identity-token read probe only if the existing Google identity route can mint a valid token.

The probe never calls a deployment action, never mutates IAM, never changes traffic, never changes Apps Script source/deployments/triggers/properties, and never records credential values.

## Main-only credential boundary

The Bubbles Command Bus workflow retains its existing PR/command behavior. A new `provider-surface-readback` job is restricted to an admitted `push` on `main`. Pull-request code does not receive the provider readback job. The job may request OIDC and use already-configured repository secrets only after source admission; its only effect is provider readback plus an immutable Actions artifact receipt.

## Apps Script correction

Service-account access is not promoted as an Apps Script API control path. The platform specialist explicitly forbids the assumption that sharing a script with a service account enables remote Apps Script API execution. The deployed web-app route and human OAuth/API-executable routes remain separate provider mechanisms.

## Maturity rule

No surface may be promoted to `BIDIRECTIONAL_VERIFIED` merely because the screenshot, Drive registry, endpoint URL, service account, secret name or workflow source exists. Promotion requires fresh semantic provider readback for the specific capability being claimed.

# SOVARA WIF R1-to-R4 Promotion Plan

## Decision

The route is currently **R1 — Defined**. The exact prior canary reached Google
STS, which returned `invalid_target`; Gemini was not invoked. This proves the
configured provider resource is syntactically complete, but it does not prove
that the pool/provider exists, is enabled, or is available to the configured
audience. Promotion is therefore blocked at the first live identity-control
gate, before service-account impersonation, Gemini, Cloud Run, or deployment.

This plan is fail-closed. A workflow may pass because it produced a valid,
sanitized diagnostic receipt, while the provider route remains at R1. A route
can advance only when the receipt itself proves the next gate.

## Airlock boundary

The exact-head repository Airlock classifies this public workflow as
`UNAUTHORISED_OIDC` and `WORKFLOW_NOT_ALLOWLISTED`. That is an intended policy
control, not a reason to weaken the Airlock: the repository is an execution-
quarantined public source plane and its OIDC allowlist is empty. This draft must
remain unmerged. R2 and later live identity work must move to the separately
authorized private execution plane; the public repository should retain only
reviewable code, tests, documentation, and sanitized external receipts.

## Readiness algorithm

| Level | Required proof | Automated exit test | Forbidden shortcut |
|---|---|---|---|
| R1 — Defined | Versioned provider resource, project/service-account alignment, pinned diagnostic workflow, tests, and sanitized receipt schema | Provider syntax and project alignment tests pass; an exact-head diagnostic receipt is present | Treating workflow completion, configuration text, or an unverified provider name as live capability |
| R2 — Implemented | Read-only inventory proves pool exists/enabled; provider exists/enabled; issuer is GitHub Actions; expected audience, attribute mapping, and attribute condition are present; service account exists/enabled; repository/ref subject is admitted | Inventory receipt satisfies every R2 predicate and the zero-effect STS exchange returns HTTP 200; neither signal may self-certify R2 alone | Creating/replacing a provider, broadening an attribute condition, adding IAM, or using a key merely to make the test pass |
| R3 — Tested | Two successful zero-effect STS exchanges on the same immutable head plus a negative repository/ref test that is denied | Two positive receipt hashes agree on schema, head and classification; negative case is denied; Airlock, Leak Guard, and regression tests pass | A single transient success, stale evidence, secret-bearing logs, or testing a different commit |
| R4 — Provider-bound | Pinned `google-github-actions/auth` completes service-account impersonation; credentials remain ephemeral; a bounded read-only identity call succeeds; then a separately authorized semantic Gemini canary verifies the requested model route | Exact-head auth receipt proves impersonation without exposing tokens; bounded canary returns its nonce and a sanitized response hash | Merge, deployment, traffic, billing, secret creation, long-lived keys, or production claims before the R4 receipt exists |

## Exact R1 to R2 readback contract

The next automation must run in the authorized private execution plane, perform
read-only inventory against the configured Google Cloud project, and emit a
receipt containing only booleans, stable state labels, resource-version hashes,
and the provider's enabled/disabled state. It must verify all of the following:

1. The workload identity pool exists and is enabled.
2. The named provider exists and is enabled inside that pool.
3. The issuer is `https://token.actions.githubusercontent.com`.
4. The configured audience is compatible with the provider resource used by
   the workflow.
5. Attribute mappings include the claims used by the attribute condition.
6. The condition admits the intended repository and intended ref only.
7. The service account exists, is enabled, and belongs to the configured
   project.

If read-only inventory is unavailable, the level remains R1. No compensating
write is authorized by this plan. A successful STS exchange is strong positive
evidence, but the diagnostic intentionally keeps `current_level` at R1 until the
independent provider and service-account readback is also bound to the receipt.

## R2 to R3 proof protocol

- Run the zero-effect exchange twice against one immutable commit SHA.
- Retain sanitized receipts as immutable GitHub Actions artifacts.
- Run a negative test from a deliberately non-admitted repository/ref identity;
  success of the negative exchange is a failure.
- Bind the positive and negative receipts to the workflow SHA and action-pin
  set.
- Reject evidence if any credential, OIDC token, access token, or arbitrary
  provider error description appears in logs or artifacts.

## R3 to R4 proof protocol

R4 requires separate authorization because it exercises service-account
impersonation and then the model route. Use the immutable
`google-github-actions/auth` action pin documented in the workflow review. The
first call after authentication must be read-only and identity-scoped. Only
after that proof succeeds may a bounded Gemini semantic canary run. The canary
must request a unique nonce, store only response length and SHA-256, and fail if
the nonce is absent.

## Automatic demotion rules

Immediately demote to R1 on `invalid_target`, missing/disabled pool or provider,
issuer/audience drift, or stale provider inventory. Demote to R2 on subject,
mapping, condition, or repeatability failure. Demote to R3 if service-account
impersonation or the semantic provider canary fails. Any credential exposure,
unapproved IAM change, unpinned workflow action, or receipt/head mismatch makes
the evidence inadmissible and blocks promotion.

# NEXUS optional-route hardening review

This branch quarantines the two push-trigger-capable NEXUS diagnostic workflows while preserving all manual preflight and recovery routes, historical receipts, source history and the canonical hash-locked release.

## Changes

- remove `.github/workflows/nexus-operator-auth-canary.yml` from active workflow scope;
- remove `.github/workflows/nexus-secret-access-diagnostic.yml` from active workflow scope;
- add `deployments/nexus/NEXUS_OPTIONAL_ROUTE_POLICY.md` with exact reactivation and proof gates.

## Reason

The latest 3 August 2026 receipt remains `BLOCKED_NO_TRUSTED_SECRET_ROUTE`; the configured WIF provider is `NOT_FOUND`; no deployment or runtime proof exists; and NEXUS-CODEX is not required for current Federation maturity. Re-running unchanged authentication probes creates noise and unnecessary write-capable workflow exposure.

## Safety

- no deployment;
- no cloud mutation;
- no credential access;
- no secret value recorded;
- no manual recovery workflow removed;
- Git history preserves every deleted workflow.

## Review decision

Keep this pull request in draft until repository checks and the final diff are verified. Merge only if the optional-route classification remains current and no active workload depends on either removed diagnostic workflow.

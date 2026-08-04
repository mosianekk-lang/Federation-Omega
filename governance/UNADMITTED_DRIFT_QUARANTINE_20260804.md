# Unadmitted Drift Quarantine — 2026-08-04

Status: `QUARANTINE_IN_PROGRESS`

Canonical admission checkpoint: `1305bf7ddd80f928b416565db6b5c926839aebb1`

Observed drift head: `1830f43d653f7136cfd5c3a5c097b82f8720b63f`

Thirteen commits reached `main` after the source-provenance sentinel checkpoint without an associated pull request. The drift introduced five workflow files, three source-committed runtime or inspection receipts, two trigger files and an unreviewed Federation Omega Phase-2 package.

The quarantine branch removes those additions from canonical source while preserving every commit in Git history for later reviewed recovery. The workflow removed during the drift window remains removed.

This marker is not proof that GitHub branch protection is active. Preventative enforcement still requires a provider ruleset that requires the `admission` check before `main` updates.

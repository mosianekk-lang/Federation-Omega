# CFBE–BCO-Prime release archive

This directory preserves the verified CFBE–BCO-Prime lineage without changing runtime authority.

- `VERSION_INDEX.json` is the canonical public accounting record.
- `archives/` contains the exact sealed v2.0.0, v3.0.0 and v3.1.0 packages.
- `superseded/` preserves RC1 and RC2 as audit evidence. RC1 is intentionally labelled as a failed thin-topology candidate; RC2 passed but was superseded by the final v3 package.
- v1 is source lineage inside the v2 archive; it did not have a separate sealed package.
- v4 remains evolving source on `main`, not a sealed successor archive.

Every archive passed path, duplicate-member, symlink, compression, credential-pattern and email-address preflight. Canonical releases were rerun from fresh private readback before this archive was prepared.

This archive grants no deployment, provider-effect, credential, scheduler, daemon or stable self-promotion authority. Runtime status remains `ON_DEMAND_GOVERNED`.

# FUSE Genesis External Truth Normalization v1

F329 inserts a typed normalization boundary between raw provider/runtime observations and FUSE effect, proof, currentness or terminality decisions.

## Rules

- Raw provider payload is provenance evidence, never control truth.
- Literal booleans are accepted by default; strings such as "false", "0", "success" and empty objects are not truthy shortcuts.
- Provider-specific string/status mappings require an explicit schema contract.
- Transport success is not semantic success.
- Observations require provider identity, operation identity, subject identity, source epoch, timezone-aware observation time, evidence hash and schema identity.
- Stale source epochs and expired observations classify STALE.
- Contradictory fresh receipts classify DISPUTED; last-write-wins is prohibited.
- Only a reconciled VERIFIED_TRUE may satisfy a hard positive proof/effect predicate.
- UNKNOWN, STALE, INVALID and DISPUTED remain nonterminal truth states.

F329 is source-only and grants no provider/effect authority.

# Superior Logic Heritage Revision Recovery v1

Status: `SOURCE_IMPLEMENTED / LOCAL_REGRESSION_PASS / PROVIDER_CANARY_REQUIRED`

## Purpose

Recover an exact historical Google Drive blob revision into a separate immutable heritage-vault object without overwriting the live/current package pointer.

The recovery path is intentionally separate from `google_workspace_adapter.py`, whose ordinary operating contract remains read-oriented. The heritage adapter uses Google Drive v3 through Application Default Credentials and requires an explicit mutation gate before it may pin or create provider objects.

## Admission sequence

1. Resolve the exact source file ID, revision ID, expected byte size and SHA-256 from the private Superior Logic Heritage Master Provenance Register.
2. Read the provider revision metadata.
3. If `keepForever` is already true, preserve that fact. If false, fail closed unless `FEDERATION_HERITAGE_REVISION_MUTATIONS=true` and the runtime identity actually has Drive write authority.
4. Set only `keepForever=true` for the exact revision and read the revision metadata back.
5. Retrieve the exact historical revision bytes.
6. Require exact expected size and SHA-256.
7. Search the target vault folder for the exact destination name.
8. Reuse an existing object only when a fresh byte download matches the expected size and SHA-256.
9. Otherwise create a new object; never overwrite a historical archive object.
10. Download the new vault object and verify the same size and SHA-256 again.
11. Persist the resulting receipt in the private Heritage Provenance Register / restore ledger.

## Authority and safety

- Source presence, code merge, ADC availability, or a registry row does not prove provider authority.
- `FEDERATION_HERITAGE_REVISION_MUTATIONS` defaults to false.
- The adapter never deletes or overwrites a vault object.
- A same-name object with different bytes fails closed.
- Provider credentials remain in the runtime identity / ADC path; no credential values are serialized.
- `keepForever` is treated as a sticky archival mutation. Use this path only for exact revisions already selected by the heritage recovery queue.
- Historical recovery grants no deployment, model, cloud, trading, legal, behavioral, or sibling-receiver authority.

## Local regression

`python -m unittest -v test_heritage_revision_adapter.py`

Current deterministic local result at admission: `7/7 PASS`.

## Provider canary required

The first provider canary must use one known historical Superior Logic revision and prove, in order:

`REVISION_METADATA_READ -> KEEP_FOREVER_READBACK -> REVISION_MEDIA_BYTES -> EXPECTED_SHA256 -> NEW_VAULT_OBJECT -> VAULT_BYTE_READBACK -> SAME_SHA256`.

Do not bulk-pin or recover all revisions until the first exact revision passes that sequence.

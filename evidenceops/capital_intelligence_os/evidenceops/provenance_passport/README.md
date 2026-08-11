# EvidenceOps Provenance Passport Toolkit

A dependency-free Python toolkit for building and validating ordered,
Merkle-backed provenance passports.

## What it proves

A successful validation proves that:

- the passport has the required structure;
- its ordered SHA-256 leaves reproduce the declared Merkle root;
- every supplied inclusion proof verifies;
- a V2 canonical JSON receipt, when present, verifies.

It does **not** prove that declared hashes match source bytes that were not
downloaded and re-hashed during the verification run.

## Commands

```bash
python -m evidenceops.provenance_passport.cli verify passport.json
python -m evidenceops.provenance_passport.cli verify-batch one.json two.json
python -m evidenceops.provenance_passport.cli build-records manifest.json output.json \
  --passport-id EPP-EXAMPLE-001
```

A record manifest has this shape:

```json
{
  "source": {
    "title": "Example ordered manifest",
    "contract": "EXAMPLE_V1"
  },
  "records": [
    {"record_id": "A", "value": 1},
    {"record_id": "B", "value": 2}
  ]
}
```

V2 receipts use SHA-256 over canonical JSON with the `receipt` field removed.
Legacy V1 receipts remain externally supplied because their original
canonicalisation scope was not declared.

## Security boundary

Do not commit private evidence records, source identifiers, credentials, or
matter data to a public repository. Use redacted or synthetic fixtures for
tests and keep real passports in an authorised private evidence store.

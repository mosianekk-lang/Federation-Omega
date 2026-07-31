# EvidenceOps Provenance Passport CLI

A deterministic standard-library implementation for building and verifying
multi-corpus provenance passports from precomputed SHA-256 record hashes.

It does **not** read source evidence bytes, upload private data, or claim legal
admissibility. It preserves integrity evidence that must still be interpreted
within the applicable evidentiary and custody framework.

## Manifest

```json
{
  "corpus_id": "MATTER-001-AUDIO",
  "records": [
    {"record_id": "audio-001", "sha256": "<64 lowercase hex>"}
  ]
}
```

## Commands

```bash
python -m evidenceops.provenance_passport.cli build manifest.json -o passport.json
python -m evidenceops.provenance_passport.cli verify passport.json
python -m evidenceops.provenance_passport.cli verify-many passport-a.json passport-b.json
```

The output contains a domain-separated Merkle root, one inclusion proof per
record, and a deterministic passport receipt.

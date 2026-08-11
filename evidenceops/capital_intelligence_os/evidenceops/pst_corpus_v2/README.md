# EvidenceOps PST Corpus v2

This module turns the 3.5 GB `MosianeKK@tut.ac.za.pst` mailbox into a verified and searchable EvidenceOps corpus.

## Why v2 exists

The July 24 v1 Cloud Run path successfully built and deployed jobs, but its publication design attempted to upload every EML and attachment individually to Google Drive. For a large mailbox, that creates excessive file cardinality and threatens the 24-hour completion target.

v2 publishes a compact evidence surface instead:

- control and verification records;
- CSV and JSONL occurrence indexes;
- a SQLite FTS5 search database;
- Drive-indexable text search packs;
- SHA-256 and CRC-verified ZIP64 raw evidence shards;
- parser and processing logs.

Every raw message and attachment remains preserved inside the retrieval shards. Individual EML and attachment files are not separately published to Drive.

## Canonical resources

- PST Drive ID: `1wRZyIhlFy5bECTccmfXHzWH5b4hTN7xN`
- Expected size: `3501253632` bytes
- Output vault: `12bvxf_uBKnNIYDJby2uJV_UdA30jZBK1`
- Google Cloud project: `sov-hybrid-suite`
- Region: `africa-south1`
- GCS working bucket: `mpmb298-evidence-archive`
- Runtime identity: `saiui-worker-runtime@sov-hybrid-suite.iam.gserviceaccount.com`
- Package Drive ID: `18PJ5jDIbG69pclgBYr3ehf9YD8WIS3uk`
- Package SHA-256: `ca28275cfb96bfb47c8a3cc88be3dce769d42e4183a39099260f16087736db4d`
- Apps Script deployer Drive ID: `1fXKafnrsAoGiC8CT-oDsql29cCT0Wgpv`

## Provider-independent GitHub lane

When WIF, Cloud Run deployment authority, or Apps Script timers are unavailable, `.github/workflows/evidenceops-pst-corpus-v2-extract.yml` runs the same reviewed extractor on a GitHub-hosted runner. It downloads the publicly shared, size-locked PST, produces the searchable corpus and raw retrieval shards, uploads short-lived workflow artifacts, and always commits a provider receipt to `deployment_receipts/evidenceops-pst-corpus-v2-latest.json`.

A GitHub artifact is an intermediate transport, not final completion. Its searchable files and raw shards must be transferred into the Evidence Operations Vault and independently verified there.

## Success rule

The mission is complete only when the independent verifier writes `00_CONTROL/COMPLETION.json` in the Drive corpus folder with `status: COMPLETE_VERIFIED` after re-downloading and reconciling every published object.

## 24-hour execution window

Start: `2026-08-04 01:48 SAST`  
Target gate: `2026-08-05 01:48 SAST`

The critical path is: extraction provider → compact Drive publication → independent verifier → completion readback.

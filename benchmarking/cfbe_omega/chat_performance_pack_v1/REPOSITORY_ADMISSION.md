# Federation repository admission

Source admission date: 2026-09-04
Base main: 3b47e77062242f224ab1d3eab993d53fd3f95147

This package is the tested, provider-neutral CFBE Chat Performance Pack v1.0.0. It adds producer-signed recovery snapshots, a fenced O(1) SQLite ledger head, bounded context capsules, a strict five-phase canary controller, evidence-aware scoring and stream admission.

Truth boundary: source registered on an isolated branch only. SQLite is a local/single-filesystem reference backend and must not be treated as multi-instance Cloud Run durability. Provider binding requires the existing Federation durable-store adapter or a new CAS/fencing adapter, a current operator allowlist, exact pre-change revision, provider-native readback and five matched canary phases. No workflow dispatch, deployment, traffic change, IAM change, secret creation or production promotion is performed by this admission.

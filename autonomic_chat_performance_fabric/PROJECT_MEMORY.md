# Project memory

The incident exposed repeated full-DOM scans, complete-ledger rewrites and 30-second
capture cadence in the existing companion. The selected remedy is a thin-client,
event-sourced and content-addressed fabric. This package is the first shadow-mode
implementation. Source, tests, registration, deployment and behavior remain distinct.

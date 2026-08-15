# Ω-TRUTHGRID deterministic enforcement layer

This package closes the gap between TruthGrid's declarative control rules and the
pre-mutation checks required to stop recurrence of the Genesis audit defect classes.
It is `A1_INTERNAL` and does not create provider authority or prove deployment.

## Foundation completion lock

TruthGrid is a foundational evidence-control mission for dependent Kim v TUT work.
While mandatory TruthGrid dependencies remain open, dependent workstreams such as
Section 188A merits, disciplinary charge analysis, Job Evaluation and PAIA/DHET may
only proceed as TruthGrid ingestion/revalidation work unless an explicit override is
present for a hard external deadline, legal preservation, safety or direct owner
instruction.

The mission is complete only when every mandatory completion gate passes.  Maturity
scores, architecture completeness, bounded usability, audit completion and partial
revalidation never substitute for corpus completion.

## Pre-mutation guards

`TruthGridGuard.validate_mutation()` plus `TruthGridWriterAdapter` fail closed on the
recurring defect classes:

1. raw byte/hash fields outside `INTEGRITY MANIFEST`;
2. positional update/delete/promotion without stable-key resolution;
3. Gmail connector `attachment_id` promoted to durable evidence identity;
4. stale target revision writes;
5. role/title/signatory representation promoted to authority without a qualifying
   appointment/delegation/authority source;
6. release/verified/complete vocabulary without execution receipt IDs;
7. malformed `RELEASE GATES` receipt rows not built from the named schema;
8. mutations whose named values do not bind to a freshly read live sheet schema,
   including unknown fields, duplicate or blank live headers, and incomplete APPEND
   rows that could shift values under equal-width positional serialization;
9. missing independent/provider readback plan.

The live schema reader must itself be provider-backed and current at execution time.
The adapter reorders values to the fresh header sequence before invoking the writer;
it does not allow a caller's dictionary insertion order to define sheet semantics.

These controls map directly to the open parent defect classes recorded in TruthGrid
Genesis work. They are preventive source behavior only until the exact operational
writer path has been independently exercised and read back.

## Completion gate

`TruthGridGuard.completion_gate()` uses a minimum-gate rule.  It returns true only
when global revalidation, P0, P1 and P2 are closed, no unresolved gaps or
undispositioned contradictions remain, Genesis parent audits and writer canaries pass,
and the dashboard is generated from the live matrix.

## Proof boundary

Source code and tests prove only deterministic source behavior.  Operational
promotion still requires the repository Airlock/PR checks and independent runtime or
provider readback on the exact writer path.  Presence of the adapter, a passing unit
test, or a successful proposal branch does not prove that production TruthGrid writes
use the adapter or that a parent Genesis defect has been repaired. The package may not
self-certify global TruthGrid trust restoration.

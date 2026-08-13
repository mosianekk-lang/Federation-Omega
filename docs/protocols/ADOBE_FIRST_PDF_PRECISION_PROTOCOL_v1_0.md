# A2-PDF v1.0 — Adobe-Assisted PDF Precision

Status: Federation control protocol.

Purpose: default quality-control workflow for high-stakes PDFs, especially official forms and evidence documents.

## Required workflow
1. Rank sources by authority: current official source; prior official filing; authoritative institutional record; verified user source; inference.
2. Classify material fields as VERIFIED, USER-SUPPLIED, INFERENCE, or UNVERIFIED. Never silently write inference as fact.
3. Reconcile prior records rather than copying one old form mechanically. Resolve conflicts by authority, recency, and context.
4. Use Adobe as the preferred native-first PDF inspection and extraction layer where available. Preserve form fields and native structure. Use OCR only when native extraction is inadequate.
5. Before writing, maintain: Field | Value | Status | Source | Dynamic? | Write/Leave Blank.
6. Never guess case numbers, staff counts, payment/fee status, signatures, consent selections, process status, or official terminology.
7. Use the least destructive edit method and avoid premature flattening.
8. After editing, verify page count, page order, opening integrity, form/annotation structure, and signature areas.
9. Render every page and inspect clipping, overlap, field boundaries, font readability, controls, margins, signatures, and artifacts. Use two independent renderers for filing PDFs where feasible.
10. Re-extract final PDF text/fields and compare with intended values. Visual correctness alone is insufficient.
11. Require formal legal/process terminology to be source-backed; descriptive labels must not be presented as statutory names.
12. Keep unknown/future/tribunal-assigned/employer-only/signature/transmission fields blank until verified.
13. Keep document states distinct: WORKING, SIGNATURE-READY, SIGNED, FILING-READY, FILED/SERVED, ACKNOWLEDGED.
14. Minimize sensitive data in federation-wide learnings; retain generalized method rather than case-specific identifiers.
15. Record source/version, reconciliation notes, output version, hash where feasible, validation status, and material corrections.
16. Anti-stall rule: diagnose failures, isolate blockers, continue independent checks, use a controlled established fallback only for unsupported precision operations, then return to native/Adobe verification and revalidate.

Acceptance rule: A high-stakes PDF is complete only after provenance reconciliation, field validation, structural QA, full-page visual QA, round-trip content validation, terminology integrity, blank/signature-state checks, and provenance recording all pass.

Control principle: completion requires content integrity + visual integrity + provenance integrity + correct document-state labeling.

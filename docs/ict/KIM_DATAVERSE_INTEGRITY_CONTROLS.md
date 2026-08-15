# Kim DataVerse Integrity Controls

Status: source contract / audit-derived / provider binding separately verified

This control set strengthens the existing Kim DataVerse estate map. It does not create a competing DataVerse and does not replace existing stable identifiers, receipts, attestations or private canonical pointers.

## Why this exists

The deep estate audit showed that the core identity graph is substantially sound, while mutable status projections can drift independently. It also exposed a forensic-analysis failure: a raw XLSX `<v>` payload was initially interpreted as a literal displayed value even though the cell was a shared-string cell. The failed finding was retracted and converted into a reusable format-aware decoding rule.

## Canonical controls

1. **Public schema manifest** — `config/kim-dataverse-schema-manifest-v1.json` records every observed KDV sheet, export identity, logical block summary and sheet role. Full field/type bindings stay in the private `KDV_SCHEMA_REGISTRY`.
2. **Projection contract** — `config/kim-dataverse-projection-contract-v1.json` separates source frontier, runtime-attestation frontier and provider-effect proof. A source SHA stored in KDV is an as-of observation, never permanent currentness.
3. **Consumer map** — `config/kim-dataverse-consumer-map-v1.json` records which systems consume mutable projections and which stronger evidence must be reconciled first.
4. **OOXML semantic decoder** — `evidenceops/kim_dataverse/xlsx_semantic.py` resolves shared-string indices and preserves OOXML type/style/formula metadata before audit interpretation.
5. **Typed writer wrapper** — `KDVTypedWriterAdapter` reuses the existing `TruthGridWriterAdapter`, adding schema normalisation before the already admitted live-schema → mutation → independent readback sequence.
6. **CAS projection rule** — mutable projection writers bind the expected source/revision immediately before write and fail closed when the provider has advanced.

## Export truth boundary

XLSX is a representation, not the provider-native canonical store. Excel limits worksheet names to 31 characters, so at least these Google Sheet names transform on export:

- `FEDERATION_ADVERSARIAL_VALIDATION` → `FEDERATION_ADVERSARIAL_VALIDATI`
- `CHATBRIDGE_CHECKPOINT_GENERATIONS` → `CHATBRIDGE_CHECKPOINT_GENERATIO`

Raw `<v>` contents must never be interpreted without the OOXML cell type. In a shared-string cell (`t="s"`), `<v>` is an index into `sharedStrings.xml`.

## Currentness rule

A durable record can say **verified as of X**. It cannot permanently prove **current now** in a high-churn source plane. Present-tense source claims therefore require a fresh provider read. Runtime attestations remain exact to the source version they actually tested and are never rewritten to follow later source.

## Migration posture

- preserve append-only evidence, receipts, lineage and historical attestations;
- normalise new writes first rather than destructively rewriting legacy history;
- progressively derive mutable current-state projections from stronger evidence;
- add provider-level validation where it cannot break legitimate append-only or dynamic state behavior;
- keep productionisation/maturity claims proof-gated.

# BCO-Prime Chat Forensics v2 architecture

## Outcome

V2 repairs the truth defects found in the v1 audit and exposes the harvested
capability layers through one deterministic registry. The canonical core and v1
extension are unchanged. The CFF engine is loaded only from an explicit local
path and can be bound to expected SHA-256 values.

## Components and boundaries

| Component | Responsibility | Effect boundary |
|---|---|---|
| strict contract layer | Canonicalize JSON, validate conversation identity, source records, booleans and hashes | no I/O |
| v1.1 truth repair | Source accounting, terminal lifecycle, contradictions, confidence, durability | no I/O |
| unified registry | Dispatch 100 core, 24 legacy, 2 meta and 8 CFF identifiers | no external effect |
| meta safe subset | Exact v1 strategy fitness, ranking and fallback algorithm | shadow decision support only |
| CFF adapter | Probe, hash-check and import the extracted engine | local module import |
| native audit route | Run the real CFF engine and validate its outputs | explicit local read/write only |
| CLI | List, run, audit and validate outputs | same authority as selected route |

Registry cardinality is 134. Availability is separate from registration:
unconfigured or hash-mismatched CFF routes remain registered but fail closed.
The full meta runtime is not counted as ready because three imported runtime
dependencies are absent.

## Typed inputs

An incident bundle requires:

- conversation.expected_id and conversation.observed_id, equal and non-empty;
- matching expected and observed titles when an expected title is supplied;
- sources, a list with unique source_id values;
- exact Boolean accessible and captured fields;
- a lowercase SHA-256 for every captured source;
- optional lifecycle observations, each an exact Boolean; and
- no request for publish, deploy, merge, registration, financial, approval, or
  other external effect.

Unsupported Python types, non-finite numbers, duplicate source IDs, captured
inaccessible sources, malformed hashes and identity collisions are rejected.
Serialization never uses default string coercion.

## Truth model

The lifecycle state machine emits WORKING, COMMITTED, FAILED_FINALIZATION,
ABORTED_USER, DISCONNECTED, or INDETERMINATE.

FINAL_RESPONSE_COMMIT_FAILURE is emitted only for FAILED_FINALIZATION. Other
incomplete evidence produces FINALIZATION_FAILURE_SUSPECTED. Backend cause stays
UNVERIFIED unless native backend evidence is later supplied.

Confidence is calculated from explicit signals and penalized for unresolved
contradictions. It is never promoted to high merely because two flags are true.
Methodology/tooling assets are excluded from incident-source counts.

Provider durability is PROVEN only when a pinned reference exists and every
artifact has a valid expected hash, equal observed hash, and
readback_verified=true.

## Native CFF output transaction

The native engine returns seven paths:

1. forensic audit JSON;
2. forensic audit Markdown;
3. exchange metrics CSV;
4. forensic dashboard HTML;
5. event ledger JSONL;
6. ChatBridge 1.1 capsule; and
7. transaction manifest JSON.

V2 requires every file to exist and be non-empty, hashes every file, validates
the ledger chain through the engine, and validates the ChatBridge schema,
14-section completeness and normalized self-hash. A missing or invalid file
keeps completion false.

## State and transactions

Pure registry calls are stateless and deterministic. A native audit follows:

CREATED -> PROCESSING -> OUTPUT_WRITTEN -> READBACK_VALIDATED -> COMPLETED

Failures transition to FAILED without external mutation. The caller may retry
with the same source and a new collision-safe prefix. Local output files are the
checkpoint; there is no hidden database, queue, scheduler or cache.

## Failure controls

| Failure | Control |
|---|---|
| invalid input | strict contract rejection before dispatch |
| authorization request | external-effect keys fail closed |
| timeout | no internal retry loop; caller controls process timeout |
| partial write | seven-file readback reports every missing/empty path |
| missing configuration | engine and dependency probes expose exact failure codes |
| external dependency failure | pure/core/legacy/meta-safe paths remain usable |
| duplicate message IDs | native CFF engine fails closed |
| engine drift | optional expected hashes block import |
| full meta dependency gap | only exact safe subset is exposed |

## Observability

- deterministic correlation ID from canonical incident input;
- input and receipt SHA-256 values;
- engine and dependency health probe;
- namespace, operation and output receipt;
- source-accounting and contradiction registers;
- seven-file output hashes and failure list;
- zero secret or raw credential echo; and
- explicit designed/implemented/tested/registered/authorized/ready/deployed/
  proven separation.

## Security and authority

V2 authorizes A1 local analysis only. It contains no network client, credential
broker, provider writer, messaging path, deployment hook, merge function or
registration effect. Native engine execution is constrained to paths supplied
by the local operator. External actions require a new Formation mission,
authority decision, permit and semantic readback.

## Verified evidence

- 27 selected legacy and v2 tests passed.
- 100 of 100 canonical core functions executed through the registry.
- 7 of 7 native CFF output files validated.
- The native JSONL event chain passed the engine validator.
- The generated ChatBridge 1.1 capsule passed schema, section and self-hash
  validation.
- Deterministic incident replay returned the same receipt.
- Missing engine and hash mismatch routes failed closed.

These results prove the local build and its bounded tests. They do not prove a
live deployment, cross-chat continuity, provider registration, or the original
incident's backend cause.

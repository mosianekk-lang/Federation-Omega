# BCO-Prime successor v3 architecture

## Outcome

V3 is an additive, standard-library-only local successor. It preserves the
sealed v2 behavior and its 100 canonical core identifiers, then adds a bounded
learning-and-harvesting plane that cannot mutate providers, execute generated
code or promote itself.

## Components

| Component | Responsibility | Effect boundary |
|---|---|---|
| SuccessorRegistry | One dispatch and receipt surface for v2 plus fourteen v3 operations | Local on-demand calls only |
| FlightRecorder | Append, verify, replay and checkpoint hash-chained JSONL events | Caller-selected contained local root |
| CapabilityRadar | Parse authorized local Python, JSON, JSONL, Markdown, text and CSV | Metadata only; raw source never emitted |
| Capability DNA | Preserve purpose, interface, pattern, dependencies, controls, proof, failure modes, provenance, licence and occurrence | Shadow metadata only |
| Opportunity compiler | Build an acyclic dependency graph and emit a declarative candidate package | Non-executable and quarantined |
| Shadow qualifier | Compare at least thirty paired cases, require uplift, rollback and an independent verifier | Never authorizes stable promotion |
| Adaptive intelligence | Derive reversible policy candidates from supplied telemetry | `LOCAL_SHADOW` evaluation only |
| Meta closure | Verify three genuine local dependencies by path and exact SHA-256 | Missing or mismatched inputs remain `BLOCKED_WITH_ROUTE` |

## Event and proof model

Every flight event carries mission, correlation and parent identifiers,
monotonic sequence, status, typed failure, start/end nanoseconds, derived
latency, prior hash and event hash. Replay first verifies the entire chain,
then reports status/failure/mission counts and missing-parent drift. A checkpoint
binds its event count and final event hash to the ledger SHA-256.

Capability harvesting separates `content_id` from `occurrence_id`: identical
redacted bytes are deduplicated as content while every authorized source
location remains represented. Each result binds tenant, matter and source
authority and emits no raw harvested content.

## Security and privacy

- paths must remain below a caller-selected root;
- symlinks, non-UTF-8 files, unsupported suffixes and configured size/count
  overruns are rejected or quarantined;
- common assignments and private-key blocks are redacted before hashing and
  extraction;
- SPDX and bounded text detection produce an explicit licence state;
- unknown/incompatible licences cannot compile;
- effect-key matching is punctuation- and case-normalized, closing snake_case
  and camelCase shadow escapes;
- candidate packages are declarative JSON and `executable=false`;
- no crawler, package installer, subprocess executor, network client or
  provider adapter exists in the successor modules.

## State and recovery

Runtime truth is `ON_DEMAND_GOVERNED`. Stop by terminating the invoking process;
there is no worker, lease, scheduler or recurring task. Roll back by stopping
v3 invocation and using unchanged v2. Preserve ledgers and proof receipts.
Adaptive rollback produces a candidate-bound receipt and returns to the stable
baseline; it does not delete evidence.

## Known boundary

The full meta runtime is intentionally not fabricated. Its closure operation
requires exact local artifacts for MISSION_IR, DURABLE_MISSION_RUNTIME and
PROOF_OS. Absence, missing files or hash mismatch returns
`BLOCKED_WITH_ROUTE`; the local safe subset stays ready.

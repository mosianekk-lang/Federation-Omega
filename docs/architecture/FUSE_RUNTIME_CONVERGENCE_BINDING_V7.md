# FUSE Runtime Convergence Binding v7 — FRCB-007

Status: SOURCE CANDIDATE / STACKED ON FRCB-006 / AUTHORITATIVE F130 SNAPSHOT BINDING

## Mission

FRCB v7 closes the remaining evidence-provenance seam before terminal truth.

Earlier FRCB stages progressively establish:

1. AAREK producer invocation;
2. OH50 producer invocation;
3. Formation foundry-cycle evidence;
4. Alpha-Omega local BUILD evidence;
5. FDOF route/fence activation;
6. provider execution plus provider-native semantic readback.

V7 converts the current durable mission estate into the existing F130
`MissionRuntimeSnapshot` so callers no longer provide terminal tasks, proof bindings,
or objective-satisfaction booleans as the evidentiary root.

F130 remains the terminal authority.

## Authoritative inputs

The snapshot compiler consumes only current evidence from existing Federation owners:

- `DurableMissionRuntimeV1`
- verified `ConvergenceLedger`
- current `MissionProjection`
- current `MissionProofPassport`
- the verified FRCB v6 provider-execution/readback receipt

No second mission store or proof root is introduced.

## Durable → F130 mapping

Every durable work item becomes an F130 runtime task.

- `VERIFIED` becomes `DONE` only when result references exist.
- `VERIFIED` with no result references becomes `BLOCKED`.
- `SUPERSEDED` / `CANCELLED` become non-required `DONE`.
- `RUNNING` remains `RUNNING`.
- dependency-ready work becomes `READY`.
- held or non-ready planned work remains `BLOCKED`.

Every required `DONE` task emitted by the compiler must have at least one current
`ProofBinding`. The compiler refuses to emit a required proof-free DONE task.

Pending durable requests are projected as synthetic required blocked tasks, so a
current unresolved dependency cannot disappear merely because the caller omitted it.

## Synthetic authoritative tasks

V7 also materializes current proof for:

- durable ledger integrity;
- FRCB v6 convergence;
- mission projection closure;
- MissionProofPassport completion.

The projection-closure and passport tasks remain blocked unless their own current
conditions are satisfied.

## Objective satisfaction

`MissionRuntimeSnapshot.objective_satisfied` is derived. It is true only when:

- the durable projection is closable;
- no compiler integrity gap exists;
- the MissionProofPassport is complete;
- the passport ledger head matches the current verified durable ledger;
- no pending durable request exists;
- V6 provider execution is verified;
- V6 provider semantic readback is verified.

The compiler accepts no caller-supplied objective-satisfaction Boolean.

## Epoch and replay resistance

The compiler creates an evidence epoch from:

- mission identity;
- current durable ledger head;
- mission event count;
- ledger tail;
- projection digest;
- V6 receipt digest.

Every compiler-created F130 proof uses that epoch for both `bound_epoch` and
`current_epoch`.

More importantly, V7 does not rely on that string alone for replay protection.

### Two-phase authoritative terminal route

Prepare:

`current durable state → compile snapshot → F130 PREPARE_TERMINAL`

The V7 prepare receipt binds:

- authoritative compiler receipt digest;
- current ledger head;
- projection SHA-256;
- evidence epoch;
- F130 prepare receipt.

Commit:

`re-read durable state → recompile snapshot → compare with prepare → F130 COMMIT`

If the ledger, projection, passport evidence, V6 receipt, work state, proof state,
pending requests, or any other compiler input changes, the authoritative compiler
receipt changes and V7 fails closed **before** F130 commit.

A stale caller cannot preserve an old snapshot merely by replaying its old object.

## Why closable is used rather than requiring pre-existing mission closure

The snapshot compiler requires the current durable projection to be `closable`, not
already `CLOSED_VERIFIED`.

Requiring the durable mission to be closed before F130 terminal preparation would
create a second terminal event ahead of the actual terminal authority. F130 remains
the final two-phase terminal court.

A later projection may record the F130 completion receipt after commit without
becoming a competing terminal authority.

## Truth boundary

A green V7 source court establishes that:

- snapshot truth is compiled from the durable mission estate;
- required DONE tasks are proof-bound;
- pending durable dependencies remain visible;
- objective satisfaction is derived;
- provider execution/readback is inherited only from verified V6 evidence;
- state drift between PREPARE and COMMIT is detected before F130 commit.

V7 source admission does not by itself prove:

- a production mission has actually reached terminal closure;
- an arbitrary external provider effect occurred;
- native ChatGPT response emission is mechanically intercepted.

Whole-mission `COMPLETE_VERIFIED` is legal only after the existing F130
`PREPARE_TERMINAL → current-state recompile → compare-and-swap → COMMIT` path succeeds.

## Convergence chain

```text
AAREK
  ↓
OH50
  ↓
Formation Foundry
  ↓
Alpha-Omega BUILD
  ↓
FDOF route + fence
  ↓
provider execution + native semantic readback
  ↓
durable mission ledger + MissionProofPassport
  ↓
FRCB v7 authoritative snapshot compiler
  ↓
F130 PREPARE_TERMINAL
  ↓
recompile current durable state
  ↓
authoritative snapshot comparison
  ↓
F130 COMMIT
  ↓
COMPLETE_VERIFIED
```

## No-False-Finality interaction

A V7 snapshot receipt is not completion. Even an F130 PREPARE receipt is not
completion. Only the existing F130 terminal COMMIT may produce
`COMPLETE_VERIFIED`.

Therefore:

`V7 GREEN != MISSION DONE`
`F130 PREPARED != TERMINAL`
`F130 COMPLETE_VERIFIED == terminal success only when the commit receipt is current`

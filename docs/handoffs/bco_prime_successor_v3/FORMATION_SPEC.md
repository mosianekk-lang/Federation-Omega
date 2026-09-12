# Formation specification — BCO-Prime successor v3

## Mission

- Mission ID: CFBE-BCO-AUTOPILOT-20260901
- Mission version: 1
- Goal: complete the isolated successor with flight recording, authorized
  harvesting, Capability DNA, shadow compilation and bounded adaptation.
- Authority ceiling: A1 local internal, plus one final private-library write
  after local proof.
- Cost ceiling: zero.
- Runtime: ON_DEMAND_GOVERNED.
- `manualUserTasks: []`
- `ownerActionRequired: false`

## Requirements

| ID | Required fruit | Release gate |
|---|---|---|
| A1 | Complete isolated successor | Code and docs present |
| A2 | Preserve sealed v2 and canonical 100 | Hash and route sweep |
| A3 | Independent proof | Fresh extraction suite |
| A4 | Fail-closed authority/privacy/licence | Adversarial tests |
| A5 | Truthful full-meta boundary | `BLOCKED_WITH_ROUTE` without pins |
| A6 | Hash-bound continuity | Source, proof and package manifests |
| A7 | Private persistence only after proof | Provider readback receipt |
| A8 | Zero owner orchestration | No manual task or approval dependency |

## Single effectful path

The canonical runtime path is `SuccessorRegistry.execute`. Its only mutations
are bounded local ledger/checkpoint writes below the configured workspace.
Harvest, graph, compile, qualification, adaptation and closure outputs are pure
receipts. No provider effect, deployment, registration, package installation,
external message or stable self-promotion is authorized.

## Cancellation and recovery

Terminate the invoking process. No background work survives. Resume by
verifying the package/source manifest and ledger chain, rerunning the suite and
continuing within the same authority. Rollback selects unchanged v2 and retains
all evidence.

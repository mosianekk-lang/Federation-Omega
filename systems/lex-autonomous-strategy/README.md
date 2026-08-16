# LEX Autonomous Strategy Engine (LASE)

`LASE` turns Lex Advocate's **ACCESS BEFORE ASK** and **LEX-10X Predictive Strategy** doctrines into an executable, stateful legal-strategy runtime.

It is a Formation Innovation Engine + Alpha→Omega derivative and follows the Federation Omega proof/authority contracts.

## Objective

Operate continuously on a matter state with minimal owner burden:

`RESTORE → RETRIEVE → VERIFY → MODEL → FORECAST → RED-TEAM → PRIORITISE → PREPARE → LEARN → REPEAT`

The engine may autonomously perform A0/A1-internal work: retrieval planning, source selection, case-state reconciliation, unknown mapping, evidence-gap prioritisation, ten-step scenario simulation, adversarial/neutral-bench analysis, decision-DAG updates, pre-mortems, fallback design, draft preparation, and learning extraction.

Consequential outward legal actions remain owner-reserved and must pass the existing Lex external-action firewall / exact-target execution-lease route.

## Core invariants

1. **ACCESS BEFORE ASK** — never ask the owner for information until authorised accessible sources and recovery routes have been exhausted.
2. **RETRIEVE BEFORE RECONSTRUCT** — current primary/provider state outranks remembered or derivative state.
3. **SOURCE BEFORE CLAIM** — facts, inferences, allegations and legal arguments remain distinct.
4. **TEN-STEP LOOKAHEAD** — consequential recommendations require a minimum ten-node forward tree.
5. **THREE OPPONENT LANES** — model most-likely, strongest, and surprise/high-impact opponent responses.
6. **TRIBUNAL TWIN** — simulate neutral and hostile decision-maker responses before promotion.
7. **EVIDENCE AHEAD** — identify future rebuttal evidence before the anticipated opponent move occurs.
8. **OPTION VALUE** — prefer reversible routes that preserve remedies and reduce future lock-in.
9. **NO SILENT ROUTE MERGE** — case/forum/cause-of-action walls remain explicit.
10. **LEARN FROM OUTCOMES, NOT BACKCASTS** — forecasts are recorded before outcomes and calibrated afterward.
11. **FAILURES BECOME BUILDS** — unresolved capability gaps become AO-CRA engineering builds rather than manual-owner defaults.
12. **OWNER RESERVED EFFECT** — external filing, sending, service, admission, settlement acceptance, destructive mutation and other consequential effects are held.

## Executable cycle

```text
BOOTSTRAP
  ├─ load matter checkpoint + case theory card
  ├─ load source/corpus registries and prior learning
  └─ load current law/procedure freshness requirements

ACCESS-BEFORE-ASK RESOLVER
  ├─ inventory currently accessible sources
  ├─ generate source-specific retrieval routes
  ├─ score information gain / authority / cost / latency
  ├─ execute or emit retrieval packets for available adapters
  └─ ask_owner_allowed only after exhaustion proof

CASE TWIN
  ├─ verified facts / disputed facts / unknowns
  ├─ legal elements + burdens + forum
  ├─ opponent model
  ├─ neutral/hostile tribunal model
  ├─ remedy stack
  └─ cross-lane risks

LEX-10X FORECAST
  1. objective
  2. legal/procedural gate
  3. immediate opponent response
  4. opponent second-order pivot
  5. tribunal response
  6. future evidence dependency
  7. collateral/cross-lane consequence
  8. countermove/fallback
  9. worst-case/recovery
  10. pivot/stop trigger

FORMATION / ALPHA→OMEGA
  ├─ generate competing routes
  ├─ reuse before rebuild
  ├─ select minimum complete high-option-value route
  ├─ red-team / counterfactual / failure-injection
  └─ emit plan, proof gates and action packets

LEARNING
  ├─ append forecast snapshot before event
  ├─ compare predicted vs actual branch after event
  ├─ emit SUCCESS / FAILURE / CONSTRAINT / CORRECTION / RECOVERY
  ├─ update route confidence only with measured evidence
  └─ promote only reversible, non-authority-expanding parameters
```

## Runtime states

- `READ_ONLY_AUTONOMOUS` — default. Retrieval/model/strategy/learning only.
- `PREPARE_ONLY` — may generate internal draft/action packets, but no external effect.
- `OWNER_APPROVAL_REQUIRED` — consequential packet ready for exact-target approval.
- `HELD_CAPABILITY_GAP` — missing capability has an AO-CRA build record and workaround.
- `CIRCUIT_OPEN` — repeated failure blocks unchanged retries and requires a materially different route.

## Input / output

Input is a JSON matter packet. See `examples/mpmb1435.json`.

Output includes:

- `access_resolution`
- `ask_owner_allowed`
- `case_twin`
- `forecast_tree`
- `route_tournament`
- `selected_strategy`
- `future_evidence_queue`
- `action_queue`
- `learning_events`
- `ao_cra_builds`
- `truth_boundary`

## Local run

```bash
PYTHONPATH=systems/lex-autonomous-strategy/src \
python -m lex_strategy examples/mpmb1435.json --workspace ./local-artifacts/lex-strategy
```

The local runtime is deterministic and external-effect-free. Provider adapters and scheduled/background execution require their own runtime/readback proof before any `LIVE` or `DEPLOYED` claim.

# AEGIS-Ω — SOL 6.2 + Formation + Alpha→Omega + bounded AI-bot fusion

## Status

`LOCAL_VERIFIED_ORCHESTRATION_PROFILE` — this profile does not claim provider deployment or background agents.

## Operating composition

AEGIS adopts SOL 6.2 as the state-transition/proof spine. Mission closure means **target state + valid proof**, not a worker saying "done". Effectful operations require fresh identity, one-use action authority, idempotency, fencing, provider readback, semantic/attestation proof, rollback semantics and an atomic state/audit transition.

Formation Engine supplies four mandatory route families before material execution:

1. strongest reuse/optimise route;
2. strongest compose/extend route;
3. strongest materially different/clean-slate route;
4. highest-information reversible experiment.

Alpha→Omega compiles the selected route into transitions, dependencies, interfaces, tests, rollback, evidence and acceptance criteria.

SLOS-style bounded parallelism is applied only to `NO_EFFECT` and `READ_ONLY` lanes. Conflict domains prevent shared-target races. Provider calls and mutations never join speculative parallel races; they are serialized behind SOL 6.2 authority and FDOF fencing.

## AI-bot roles

The runtime defines logical worker roles rather than pretending invisible agents exist:

- HARVEST_BOT — market capability/evidence harvest;
- EVIDENCE_BOT — provenance and proof reconciliation;
- RED_TEAM_BOT — adversarial/false-completion challenge;
- TEST_BOT — deterministic and regression courts;
- PRIVACY_BOT — minimization, consent and leakage challenge;
- PROVIDER_BOT — provider-read/canary lane, always separately gated;
- BENCHMARK_BOT — matched baseline and 10× court;
- SYNTHESIS_BOT — FUSE/adapter compilation;
- FDOF_BOT — fresh source-fence/currentness readback.

A bot role is a schedulable logical unit. It gains no credentials, authority, provider access or independent truth status by being called a bot.

## Current AEGIS route tournament

Selected route: `compose-sol62-formation-slos-fuse`.

Safe parallel lanes include CFBE harvest, red team, proof court, privacy review, FUSE adapter compilation, FDOF currentness and local blind-benchmark preparation. Provider/GitHub/GCP mutations remain held until their exact SOL 6.2/FDOF gates pass.

## Safety and authority invariants

- no spyware/exploit delivery, stealth persistence, credential interception, covert collection/exfiltration, C2 evasion or targeting;
- no raw secret logging or persistence;
- no provider-effect claim from source/configuration;
- no `MUTATING` lane in the safe bot swarm;
- no provider-call lane without fresh provider identity, authority, cost and privacy gates;
- no GitHub/GCP mutation without owned FDOF fence;
- no stable promotion from execution authority alone;
- no market-superiority claim without comparable empirical baselines.

## Federation source anchors loaded for this profile

- signed main during load: `c251ed8994739c00fa72b089042223a9635af05d`;
- `sol_61_runtime/SOL_6_2_ARCHITECTURE.md`;
- `sol_61_runtime/SOL_6_2_PROGRAMME.json`;
- `sol_61_runtime/sol_62.py`;
- `sol_61_runtime/sol_62_frontier_primitives.py`;
- `superior_logic/parallel_runtime.py`;
- FUSE P0 SOL 6.2 state-migration candidate in canonical Drive.

This AEGIS profile is an adapter/control composition. It does not fork SOL 6.2 into a second sovereign runtime.

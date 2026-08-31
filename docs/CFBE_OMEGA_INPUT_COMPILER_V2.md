# CFBE Ω INPUT COMPILER v2

Status: SOURCE CANDIDATE — execution/runtime/promotion remain separate proof gates.

## Mission

Turn the ordinary ChatGPT input box into a high-leverage Federation mission interface for an owner who should not need to know the internal technical vocabulary, tool topology, agent graph, provider APIs, testing strategy or orchestration mechanics.

The owner states intent. The compiler supplies missing expert structure and emits a validated `MissionIR` for the existing Bubbles / Formation / CFBE execution fabric.

## Non-goals

This component is deliberately **not**:

- a second scheduler;
- a provider executor;
- an authority service;
- a hidden background agent;
- a replacement for MissionIR;
- a replacement for Bubbles, Omega-One, CFBE, SOVARA, ProofOS or Sentinel;
- autonomous foundation-model retraining.

It is a thin intent-to-mission compiler.

## Input contract

The user may type technically incomplete natural language, including:

- `n`
- `fix`
- `better`
- `investigate ...`
- `build ...`
- `do all`
- `is this the best?`
- or a free-form desired result.

The compiler classifies the request into one of:

`CONTINUE | FIX | IMPROVE | INVESTIGATE | BUILD | EXECUTE_ALL | CHALLENGE | GENERAL`

Then it supplies:

1. root intent;
2. desired result;
3. success criteria;
4. inferred expert workstreams;
5. capability hints;
6. effect/authority classification;
7. proof requirements;
8. a validated provider-neutral `MissionIR`;
9. a truth boundary;
10. an owner-burden policy.

## Operating principle

> The user communicates at the level of intent. The Federation operates at the level of expert execution.

The compiler must not punish missing technical vocabulary by asking the owner to design the solution.

Preferred flow:

`OWNER INPUT → INTENT MODEL → MISSIONIR → BUBBLES / FORMATION → OMEGA-ONE WORK GRAPH → CFBE ROUTE CHALLENGE → PROOFOS / JARVIS / REALITYGUARD → SOVARA EFFECT GATE → READBACK`

Only the components actually required by the mission should activate.

## Shorthand semantics

### `n`

Continue the active verified mission through the highest-value safe executable path. Do not merely repeat status. If no active verified mission is supplied, fail closed to an explicit clarification signal instead of inventing context.

### `fix`

Preserve evidence → identify root cause → apply minimum safe repair → regression test → reduce recurrence.

### `better`

Baseline incumbent → challenge with materially different alternatives → CFBE benchmark → retain only proof-adjusted improvement.

### `investigate`

Define evidence frontier → retrieve material sources → reconstruct truth/timeline/model → challenge alternatives → state confidence and gaps.

### `build`

Infer requirements safely → check reuse → design the smallest sufficient implementation → build → test → verify maturity.

### `do all`

Execute all currently safe, authorized, materially useful work in dependency-optimal order. It does **not** grant external authority.

### `is this the best?`

Run champion/challenger reasoning against the incumbent and identify the strongest current proof-adjusted route.

## Intent learning

“Learn from me” is implemented as **working-policy adaptation**, not a false claim that the underlying model retrains itself.

Callers may supply explicit verified context:

- active mission/objective;
- known constraints;
- preferred behaviours;
- rejected behaviours;
- blockers;
- available capabilities;
- domain/source/privacy/rights state.

The compiler incorporates that state into the mission contract and deterministic digest. Durable preference/episodic memory remains the responsibility of the existing Bubbles digital-twin/living-state fabric.

## Authority firewall

The compiler never converts intent into authority.

Examples such as sending email, publication, court/regulatory filing, deletion, production merge/deploy, purchase/trading, IAM/credentials or billing are classified as consequential effects and require explicit exact-effect authority plus receiver/provider readback.

Reversible internal branch/draft/fixture work is classified as bounded effect and still requires an existing bounded route authority.

`MissionIR.truth_boundary` remains authoritative: compilation does not authorize provider, financial or publication effects.

## Proof contract

Every compiled mission requires at minimum:

- source/artifact provenance;
- claim state matching observed maturity;
- explicit terminal result or blocker.

Effectful missions additionally require receiver-specific readback.

## Owner-burden contract

`NO_AVOIDABLE_OWNER_WORK`

Ask the owner only for a fact, authority or irreducible choice that materially changes the outcome. Missing engineering vocabulary is not such a gate.

## Initial regression court

The v2 test court proves:

- `n` reuses verified active mission state;
- `n` without active context fails closed;
- repair expands to root-cause + recurrence prevention;
- improvement activates CFBE challenger semantics;
- build supplies engineering capabilities automatically;
- `do all` does not grant external authority;
- consequential send operations remain owner/effect gated;
- reversible branch creation remains route-authority gated;
- deterministic inputs produce deterministic digests;
- empty input fails closed;
- the compiler does not claim hidden execution or autonomous model retraining.

## Maturity boundary

Source presence means only that the compiler exists in repository source. It is not equivalent to:

- being wired into every ChatGPT input automatically;
- provider deployment;
- always-on runtime;
- empirically lower owner burden;
- improved mission quality;
- Federation-wide stable promotion.

Those claims require independent integration, runtime and value evidence.

# SOVARA Sovereign Intelligence Court v2

## Canonical user experience

The intended ChatGPT-facing command is:

```text
SOVARA — external model review

<PASTE CODE>
```

The chat is a client terminal. It is not the system of record and is not the primary runtime.

## Architecture

1. Chat-native MCP ingress receives the code and objective.
2. Durable Mission Control creates a mission ID, hashes the source, records checkpoints, and owns resumability.
3. Provider-independent intelligence mesh selects current external providers dynamically; no single provider is mandatory.
4. Sovereign local intelligence mesh provides local/open-weight and deterministic-analysis lanes when external providers are partial or unavailable.
5. Adversarial Intelligence Court performs independent blind review, disagreement extraction, and a second challenge round.
6. SLOS Decision Court applies JARVIS ΑΩ5, Ω-Scientist, CFBE, regression and zero-dilution gates.
7. Provenance/Recovery Plane seals receipts and preserves exact mission state for restart or handoff.

## Sovereignty law

External models are intelligence suppliers only. They cannot redefine the mission, change acceptance criteria, promote source, weaken safeguards, or inherit another provider's authority.

Platform refusal, policy boundary, timeout, outage, context exhaustion, or UI failure is recorded as a provider/platform boundary event. It may degrade or reroute a lane, but it must not silently terminate unrelated executable work or dilute the mission.

This is resilience against platform dependence, not a mechanism for bypassing provider or platform safeguards.

## Degradation model

- `FULL`: external + local + deterministic + all courts available.
- `DEGRADED_EXTERNAL_PARTIAL`: some external provider lanes unavailable; remaining external/local/deterministic lanes continue.
- `DEGRADED_LOCAL_ONLY`: external providers unavailable; local/open-weight + deterministic lanes continue.
- `DEGRADED_DETERMINISTIC_ONLY`: model inference unavailable; static analysis/tests continue.
- `CHECKPOINT_ONLY`: no safe execution lane available; exact mission state is sealed for resumption.

## Critical runtime rule

GitHub Actions is CI/admission/canary infrastructure, not the production SOVARA runtime. The production path is a persistent SOVARA service reachable over MCP/HTTPS.

## Promotion rule

All external model outputs are `PROPOSAL_ONLY`. A challenger may advance only through SLOS adjudication, explicit zero-dilution checks, regression tests, and the applicable release/recovery gates.

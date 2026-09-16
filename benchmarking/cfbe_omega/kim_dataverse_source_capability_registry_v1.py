from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceCapability:
    capability_id: str
    owner_layer: str
    function: str
    operational_claim: bool


CAPABILITIES = (
    SourceCapability("objective-ecology", "CFBE", "portfolio objective/dependency prioritization", False),
    SourceCapability("resource-economy", "CFBE", "bounded resource allocation", False),
    SourceCapability("autonomy-debt", "CFBE", "owner-as-scheduler debt detection and repair planning", False),
    SourceCapability("owner-interruption-firewall", "SOL/CFBE", "separate irreducible owner boundaries from maintenance", False),
    SourceCapability("autonomic-event-router", "Federation", "route mission/maintenance/recovery/evolution events", False),
    SourceCapability("dynamic-organization", "Bubbles", "ephemeral mission-specific work-cell topology", False),
    SourceCapability("institutional-twin", "Federation", "proof-state capability projection", False),
    SourceCapability("entropy-controller", "CFBE", "merge/role/policy/retire review pressure", False),
    SourceCapability("constitutional-evolution", "SOL/ProofOS", "strict amendment shadow qualification", False),
    SourceCapability("capability-market", "CFBE", "fitness-based retain/challenge/review pressure", False),
    SourceCapability("causal-value-learning", "CFBE", "matched strategy outcomes and causal hypotheses", False),
    SourceCapability("persistent-carrier-contract", "SOL", "qualify durable no-chat execution carriers", False),
    SourceCapability("provider-event-semantics", "SOVARA", "wait/wake/handoff proof separation", False),
    SourceCapability("cross-provider-counterfactual", "SOVARA", "provider-loss route simulation", False),
    SourceCapability("value-retention", "CFBE", "retain capabilities only with observed value", False),
    SourceCapability("negative-knowledge-diffusion", "Failure-Win", "diffuse verified repair genes within semantic scope", False),
    SourceCapability("level7-qualification", "ProofOS", "fail-closed empirical maturity evaluation", False),
    SourceCapability("level8-frontier", "CFBE", "multi-timescale and information-value planning", False),
    SourceCapability("level9-frontier", "CFBE", "authority-neutral falsifiable frontier experiments", False),
)


def source_capability_registry() -> tuple[SourceCapability, ...]:
    return CAPABILITIES

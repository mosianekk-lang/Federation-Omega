from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


class AuthorityDomain(str, Enum):
    MISSION_SEMANTICS = "MISSION_SEMANTICS"
    STRATEGIC_COGNITION = "STRATEGIC_COGNITION"
    TRANSACTION_EXECUTION = "TRANSACTION_EXECUTION"
    PROVIDER_EFFECTS = "PROVIDER_EFFECTS"
    TERMINAL_TRUTH = "TERMINAL_TRUTH"
    ASSURANCE = "ASSURANCE"
    DURABLE_FEDERATION_STATE = "DURABLE_FEDERATION_STATE"


@dataclass(frozen=True)
class AuthorityOwner:
    domain: AuthorityDomain
    owner: str
    description: str


DEFAULT_AUTHORITY_GRAPH: tuple[AuthorityOwner, ...] = (
    AuthorityOwner(AuthorityDomain.MISSION_SEMANTICS, "SLOS", "Owner objective, mission meaning and non-dilution contract"),
    AuthorityOwner(AuthorityDomain.STRATEGIC_COGNITION, "SLOS", "Forest/Horizon, algorithms, reasoning and policy cognition"),
    AuthorityOwner(AuthorityDomain.TRANSACTION_EXECUTION, "SOL_6_2_KERNEL", "Idempotency, fencing, transactional effects and proof-bound state transitions"),
    AuthorityOwner(AuthorityDomain.PROVIDER_EFFECTS, "SOVARA", "Provider credentials, effect admission, provider execution and rollback"),
    AuthorityOwner(AuthorityDomain.TERMINAL_TRUTH, "SLOS_TERMINAL_TRUTH", "Completion state compiled from independently verified reality"),
    AuthorityOwner(AuthorityDomain.ASSURANCE, "PROOFOS_EVIDENCEOPS_JFRIE", "Independent source/change/evidence assurance courts"),
    AuthorityOwner(AuthorityDomain.DURABLE_FEDERATION_STATE, "FEDERATION_STATE_ROOT", "Canonical durable Federation state and projections"),
)


class ConstitutionalConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class MissionIntentContract:
    mission_id: str
    objective: str
    source_version: str
    initial_state: Mapping[str, Any]
    target_state: Mapping[str, Any]
    constraints: tuple[str, ...] = ()
    success_proofs: tuple[Mapping[str, Any], ...] = ()


class ConstitutionalConvergence:
    """Single-authority graph binding SLOS, SOL 6.2 and SOVARA.

    SLOS owns mission meaning. SOL 6.2 is explicitly a transactional kernel,
    never a second sovereign mission OS. SOVARA owns provider effects. The
    adapter mirrors only the minimum transaction projection required for crash-
    safe execution and never treats that projection as independent mission truth.
    """

    def __init__(self, authority_graph: tuple[AuthorityOwner, ...] = DEFAULT_AUTHORITY_GRAPH):
        self.authority_graph = tuple(authority_graph)
        self._validate_authority_graph()

    def _validate_authority_graph(self) -> None:
        seen: dict[AuthorityDomain, str] = {}
        for item in self.authority_graph:
            previous = seen.get(item.domain)
            if previous and previous != item.owner:
                raise ConstitutionalConflict(
                    f"duplicate constitutional authority for {item.domain.value}: {previous} vs {item.owner}"
                )
            seen[item.domain] = item.owner
        missing = set(AuthorityDomain).difference(seen)
        if missing:
            raise ConstitutionalConflict(
                "missing constitutional authority domains: "
                + ",".join(sorted(item.value for item in missing))
            )
        if seen[AuthorityDomain.MISSION_SEMANTICS] != "SLOS":
            raise ConstitutionalConflict("SLOS must remain mission-semantic sovereign")
        if seen[AuthorityDomain.TRANSACTION_EXECUTION] != "SOL_6_2_KERNEL":
            raise ConstitutionalConflict("SOL 6.2 must be bound as the transaction kernel")
        if seen[AuthorityDomain.PROVIDER_EFFECTS] != "SOVARA":
            raise ConstitutionalConflict("SOVARA must remain provider-effect sovereign")

    def owner_for(self, domain: AuthorityDomain | str) -> str:
        target = domain if isinstance(domain, AuthorityDomain) else AuthorityDomain(str(domain))
        return next(item.owner for item in self.authority_graph if item.domain is target)

    def compile_mission(
        self,
        *,
        mission_id: str,
        objective: str,
        source_version: str,
        initial_state: Mapping[str, Any],
        target_state: Mapping[str, Any],
        constraints: tuple[str, ...] = (),
        success_proofs: tuple[Mapping[str, Any], ...] = (),
    ) -> MissionIntentContract:
        if not mission_id.strip() or not objective.strip() or not source_version.strip():
            raise ValueError("mission_id, objective and source_version are required")
        if dict(initial_state) == dict(target_state):
            raise ValueError("target state must materially differ from initial state")
        return MissionIntentContract(
            mission_id=mission_id,
            objective=objective,
            source_version=source_version,
            initial_state=dict(initial_state),
            target_state=dict(target_state),
            constraints=tuple(constraints),
            success_proofs=tuple(dict(item) for item in success_proofs),
        )

    @staticmethod
    def build_transaction_kernel(root: str | Path):
        from sol_61_runtime.sol_62_frontier_primitives import GatewayPolicy, WorkloadIdentityPolicy
        from sol_61_runtime.sol_62_strict_runtime import Sol62StrictRuntime

        return Sol62StrictRuntime(
            Path(root),
            gateway_policy=GatewayPolicy("slos-sol62-gateway", "sol-6.2"),
            identity_policy=WorkloadIdentityPolicy(
                allowed_issuers={"https://token.actions.githubusercontent.com"},
                audience="sol-runtime",
                subject_prefix="repo:mosianekk-lang/Federation-Omega:",
                max_ttl_seconds=600,
            ),
        )

    @staticmethod
    def project_mission_to_kernel(contract: MissionIntentContract):
        from sol_61_runtime.sol_62_runtime import MissionSpec

        return MissionSpec(
            mission_id=contract.mission_id,
            objective=contract.objective,
            initial_state=dict(contract.initial_state),
            target_state=dict(contract.target_state),
            success_proofs=tuple(dict(item) for item in contract.success_proofs),
            constraints=tuple(contract.constraints),
            version=1,
        )

    def architecture_receipt(self) -> dict[str, Any]:
        return {
            "schema": "SLOS_SOL62_CONSTITUTIONAL_CONVERGENCE_V1",
            "state": "SOURCE_ENFORCED",
            "mission_semantic_owner": self.owner_for(AuthorityDomain.MISSION_SEMANTICS),
            "transaction_kernel_owner": self.owner_for(AuthorityDomain.TRANSACTION_EXECUTION),
            "provider_effect_owner": self.owner_for(AuthorityDomain.PROVIDER_EFFECTS),
            "duplicate_sovereign_mission_plane": False,
            "sol62_role": "TRANSACTION_KERNEL",
            "sovara_role": "PROVIDER_EFFECT_PLANE",
            "provider_authority_inherited": False,
        }


__all__ = [
    "AuthorityDomain",
    "AuthorityOwner",
    "ConstitutionalConflict",
    "ConstitutionalConvergence",
    "DEFAULT_AUTHORITY_GRAPH",
    "MissionIntentContract",
]

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ao_harmonic_v3.failure_win_v2 import (
    FailureEventType,
    FailureObservation,
    FailureToOperationalWinKernelV2,
    FailureWinRequest,
    FailureWinResult,
    RecoveryRoute,
)
from ao_harmonic_v3.models import PerformanceVector
from formation_omega.powerhouse import FormationOmega, ReleaseGate, SurfaceReadback

RECOVERY_FORMATION_COMPATIBILITY_VERSION = "1.0.0"


class RecoveryFormationCompatibility:
    """Read-only C3 compatibility facade for Ω-AUTOFIX and Modisa.

    This facade composes existing Failure-Win and Formation primitives. It does
    not bind provider runtime, move source, retire either doctrine, or expand
    authority.
    """

    CONTRACT_FILE = "ao_harmonic_forest_first_c3_recovery_formation_contract_v1.json"
    ALTERNATE_ROUTE_ID = "c3-shared-materially-different-route"

    def __init__(self, *, governance_dir: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[1]
        path = (governance_dir or (root / "governance")) / self.CONTRACT_FILE
        self.contract: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def observation(receiver_id: str) -> FailureObservation:
        return FailureObservation(
            event_id=f"C3-{receiver_id}-RECOVERY-SHADOW",
            event_type=FailureEventType.FAILURE,
            system_id=receiver_id,
            objective="preserve mission progress after a bounded recovery-route failure",
            claim="the failed route cannot be retried unchanged before readback and reroute",
            observed_fruit="bounded route failure with no provider effect",
            desired_outcome="continue the objective through a materially different reversible route",
            failure_code="C3_SHARED_RECOVERY_ROUTE_FAILURE",
            failed_route_id="c3-failed-incumbent-route",
            material=True,
            recent_route_history=("c3-failed-incumbent-route",),
        )

    @staticmethod
    def incumbent() -> PerformanceVector:
        return PerformanceVector(quality=8, reliability=8, proof=8, speed=2, owner_burden=1)

    @staticmethod
    def candidate() -> PerformanceVector:
        return PerformanceVector(
            quality=8,
            reliability=8,
            proof=8,
            speed=5,
            owner_time_recovered=3,
            recovery_gain=3,
            owner_burden=0,
        )

    def evaluate_receiver(
        self,
        receiver_id: str,
        *,
        materially_different: bool = True,
        rollback_available: bool = True,
    ) -> FailureWinResult:
        route = RecoveryRoute(
            route_id=self.ALTERNATE_ROUTE_ID,
            route_type="REROUTE",
            performance=self.candidate(),
            rollback_available=rollback_available,
            materially_different=materially_different,
            proof_strength=1.0,
            reversibility=1.0 if rollback_available else 0.0,
            strategic_value=1.0,
            expected_value=2.0,
        )
        return FailureToOperationalWinKernelV2().evaluate(
            FailureWinRequest(
                observation=self.observation(receiver_id),
                incumbent=self.incumbent(),
                routes=(route,),
            )
        )

    @classmethod
    def portable_fingerprint(cls, receiver_id: str) -> str:
        return FailureToOperationalWinKernelV2.portable_fingerprint(cls.observation(receiver_id))

    @classmethod
    def local_fingerprint(cls, receiver_id: str) -> str:
        return FailureToOperationalWinKernelV2.fingerprint(cls.observation(receiver_id))

    @staticmethod
    def normalized_receipt(result: FailureWinResult) -> dict[str, Any]:
        return {
            "portable_fingerprint": result.portable_fingerprint,
            "state": result.state.value,
            "action": result.action.value,
            "selected_route_ids": list(result.selected_route_ids),
            "vector_gate_passed": result.vector_gate_passed,
            "missing_proof_nodes": list(result.proof_graph.missing_nodes),
            "proof_graph_complete": result.proof_graph.complete,
        }

    @staticmethod
    def formation_release(*, semantic_match: bool, rollback_ready: bool) -> bool:
        readback = SurfaceReadback(
            surface="C3_SOURCE_SHADOW",
            expected_semantics="objective-preserving reversible recovery",
            observed_semantics=(
                "objective-preserving reversible recovery" if semantic_match else "different semantics"
            ),
            authority_verified=True,
            target_verified=True,
            version_verified=True,
            rollback_ready=rollback_ready,
        )
        gate = ReleaseGate(
            proof_ok=True,
            legal_accuracy_ok=True,
            privacy_ok=True,
            target_authority_ok=True,
            version_ok=True,
            semantic_readback_ok=readback.semantically_verified,
            rollback_ok=rollback_ready,
        )
        return FormationOmega.release_allowed(gate)

    def source_truth_boundary(self) -> dict[str, bool]:
        boundary = self.contract["truth_boundary"]
        return {key: bool(value) for key, value in boundary.items() if isinstance(value, bool)}


__all__ = ["RECOVERY_FORMATION_COMPATIBILITY_VERSION", "RecoveryFormationCompatibility"]

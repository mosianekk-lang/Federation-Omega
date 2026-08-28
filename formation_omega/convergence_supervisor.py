"""Formation Ω Convergence Supervisor v1.

Thin orchestration layer over existing MCE/JARVIS/Autonomous Maturation primitives.
It does not create provider authority or perform mutations. It compiles proof-bound
execution permits that external adapters may honor only after fresh-state verification.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from typing import Any, Iterable, Mapping

from ao_harmonic_v3.jarvis_ao5 import FailureEvent
from evidenceops.caseforge.autonomous_maturation import AutonomousMaturationController, MaturationGap
from evidenceops.caseforge.federation_evolution_program import EvolutionStage
from formation_omega.mission_convergence import FailureResolver
from formation_omega.source_convergence import (
    AdmissionPlan,
    AdmissionState,
    ChangeCapsule,
    SourceConvergenceClass,
    SourceConvergenceDecision,
    classify_convergence,
    reanchor_manifest,
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha256(value: Any) -> str:
    payload = value if isinstance(value, str) else _canonical_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


class SupervisorAction(str, Enum):
    REANCHOR_EXACT_BLOBS = "REANCHOR_EXACT_BLOBS"
    RUN_REQUIRED_CHECKS = "RUN_REQUIRED_CHECKS"
    RECHECK_CURRENT_MAIN = "RECHECK_CURRENT_MAIN"
    MERGE_EXPECTED_HEAD = "MERGE_EXPECTED_HEAD"
    READBACK_SIGNED_MAIN = "READBACK_SIGNED_MAIN"
    RECLASSIFY_FRESH_MAIN = "RECLASSIFY_FRESH_MAIN"
    RECONCILE_SEMANTIC_CONFLICT = "RECONCILE_SEMANTIC_CONFLICT"
    HOLD_OWNER_BOUNDARY = "HOLD_OWNER_BOUNDARY"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class ProviderSnapshot:
    """Bounded provider truth used as a read-before-write fence."""

    main_sha: str
    candidate_head_sha: str
    current_blobs: Mapping[str, str | None]
    check_results: Mapping[str, bool]
    evidence_refs: tuple[str, ...]
    snapshot_sha256: str

    @classmethod
    def create(
        cls,
        *,
        main_sha: str,
        candidate_head_sha: str,
        current_blobs: Mapping[str, str | None],
        check_results: Mapping[str, bool] | None = None,
        evidence_refs: Iterable[str] = (),
    ) -> "ProviderSnapshot":
        main_sha = str(main_sha).strip()
        candidate_head_sha = str(candidate_head_sha).strip()
        if not main_sha or not candidate_head_sha:
            raise ValueError("main_sha and candidate_head_sha are required")
        blobs = dict(sorted((str(path), blob) for path, blob in current_blobs.items()))
        checks = dict(sorted((str(name), bool(value)) for name, value in (check_results or {}).items()))
        refs = _clean(evidence_refs)
        body = {
            "main_sha": main_sha,
            "candidate_head_sha": candidate_head_sha,
            "current_blobs": blobs,
            "check_results": checks,
            "evidence_refs": refs,
        }
        return cls(snapshot_sha256=_sha256(body), **body)

    @property
    def passed_checks(self) -> tuple[str, ...]:
        return tuple(sorted(name for name, passed in self.check_results.items() if passed))


@dataclass(frozen=True)
class ExecutionPermit:
    """A no-effect permit binding a future source mutation to exact provider state."""

    permit_id: str
    mission_id: str
    change_id: str
    action: SupervisorAction
    expected_main_sha: str
    expected_candidate_head_sha: str
    expected_snapshot_sha256: str
    allowed_paths: tuple[str, ...]
    required_checks: tuple[str, ...]
    external_effect: bool = False
    authority_created: bool = False

    @classmethod
    def create(
        cls,
        *,
        mission_id: str,
        change_id: str,
        action: SupervisorAction,
        snapshot: ProviderSnapshot,
        allowed_paths: Iterable[str] = (),
        required_checks: Iterable[str] = (),
    ) -> "ExecutionPermit":
        normalized_action = SupervisorAction(action)
        allowed = _clean(allowed_paths)
        checks = _clean(required_checks)
        body = {
            "mission_id": mission_id,
            "change_id": change_id,
            "action": normalized_action.value,
            "expected_main_sha": snapshot.main_sha,
            "expected_candidate_head_sha": snapshot.candidate_head_sha,
            "expected_snapshot_sha256": snapshot.snapshot_sha256,
            "allowed_paths": allowed,
            "required_checks": checks,
        }
        return cls(
            permit_id="MCE-PERMIT-" + _sha256(body)[:24].upper(),
            mission_id=mission_id,
            change_id=change_id,
            action=normalized_action,
            expected_main_sha=snapshot.main_sha,
            expected_candidate_head_sha=snapshot.candidate_head_sha,
            expected_snapshot_sha256=snapshot.snapshot_sha256,
            allowed_paths=allowed,
            required_checks=checks,
        )

    def assert_fresh(self, observed: ProviderSnapshot) -> None:
        if observed.main_sha != self.expected_main_sha:
            raise RuntimeError("STALE_MAIN_RECLASSIFY_REQUIRED")
        if observed.candidate_head_sha != self.expected_candidate_head_sha:
            raise RuntimeError("STALE_CANDIDATE_HEAD_RECLASSIFY_REQUIRED")
        if observed.snapshot_sha256 != self.expected_snapshot_sha256:
            raise RuntimeError("PROVIDER_SNAPSHOT_DRIFT_RECLASSIFY_REQUIRED")


@dataclass(frozen=True)
class FailureLearningBundle:
    failure_event: FailureEvent
    resolver: FailureResolver
    maturation_gap: MaturationGap
    maturation_transaction: Mapping[str, Any]
    continuity_checkpoint: Mapping[str, Any]


@dataclass(frozen=True)
class SupervisorDecision:
    mission_id: str
    change_id: str
    action: SupervisorAction
    convergence: SourceConvergenceDecision
    admission: AdmissionPlan | None
    permit: ExecutionPermit | None
    overlay_manifest: Mapping[str, str | None]
    reason_codes: tuple[str, ...]
    capability_chain: tuple[str, ...]
    failure_learning: FailureLearningBundle | None = None

    @property
    def source_mutation_ready(self) -> bool:
        return self.action in {
            SupervisorAction.REANCHOR_EXACT_BLOBS,
            SupervisorAction.MERGE_EXPECTED_HEAD,
        } and self.permit is not None


class ConvergenceSupervisor:
    """Composes existing Federation capabilities into one stale-safe admission loop."""

    CAPABILITY_CHAIN = (
        "MCE_CHANGE_CAPSULE",
        "MCE_SOURCE_CONVERGENCE",
        "JARVIS_AO5_FAILURE_ESCALATION",
        "FAILURE_WIN_RESOLVER_MEMORY",
        "AUTONOMOUS_MATURATION_GAP_RANKING",
        "FEDERATION_EXECUTION_CONTINUITY_CHECKPOINT",
        "GITHUB_EXACT_HEAD_ADMISSION",
        "INDEPENDENT_READBACK",
    )

    def __init__(self, maturation: AutonomousMaturationController | None = None) -> None:
        self.maturation = maturation or AutonomousMaturationController()

    @staticmethod
    def _failure_learning(
        *,
        capsule: ChangeCapsule,
        snapshot: ProviderSnapshot,
        failure_class: str,
        observed_state: str,
        expected_state: str,
        root_cause: str,
        repair: str,
        regression_test: str,
        recurrence_count: int,
    ) -> FailureLearningBundle:
        recurrence_count = max(1, int(recurrence_count))
        fingerprint = f"{failure_class}|{capsule.change_id}|{expected_state}|{root_cause}"
        failure = FailureEvent(
            failure_id="FAIL-" + _sha256(fingerprint)[:20].upper(),
            failure_class=failure_class,
            observed_state=observed_state,
            expected_state=expected_state,
            root_cause=root_cause,
            available_signal=snapshot.snapshot_sha256,
            detector_that_should_have_fired="CONVERGENCE_SUPERVISOR_FRESHNESS_FENCE",
            repair=repair,
            regression_test=regression_test,
            recurrence_count=recurrence_count,
        )
        resolver = FailureResolver.create(
            fingerprint=fingerprint,
            exact_gap=observed_state,
            diagnosis=root_cause,
            immediate_workaround="Preserve the Change Capsule and reclassify only the fresh provider delta.",
            permanent_fix=repair,
            alternate_route="Use exact blob overlay only when MCE classifies the delta as lossless; otherwise reconcile the overlapping path.",
            retry_condition="A fresh provider snapshot exists with exact main/head/blob identities.",
            proof_test=regression_test,
            closure_test="The same fingerprint completes without stale-state restart or semantic dilution.",
            evidence_refs=snapshot.evidence_refs or (snapshot.snapshot_sha256,),
        )
        gap = MaturationGap(
            gap_id="GAP-" + _sha256(fingerprint)[:20].upper(),
            system_id="FORMATION_OMEGA",
            stage=EvolutionStage.SELF_HEALING_ROUTE_ENGINE,
            description=f"Prevent recurrence of {failure_class} during source admission.",
            mission_value_gain=0.95,
            failure_recurrence_reduction=0.98,
            owner_burden_reduction=0.90,
            proof_strength_gain=0.90,
            resilience_gain=0.95,
            capability_reuse_gain=0.90,
            reversibility=1.0,
            cost=0.10,
            risk=0.10,
            evidence_refs=snapshot.evidence_refs or (snapshot.snapshot_sha256,),
        )
        ranked = AutonomousMaturationController.rank_gaps((gap,))
        transaction = AutonomousMaturationController.compile_transaction(
            system_id="FORMATION_OMEGA",
            gap=ranked[0],
            candidate=None,
            expected_state_epoch=snapshot.snapshot_sha256,
            checkpoint_state=failure.required_response,
            provider_receipt_refs=snapshot.evidence_refs,
        )
        checkpoint = AutonomousMaturationController.continuity_checkpoint(
            system_id="FORMATION_OMEGA",
            transaction=transaction,
            last_proven_state=expected_state,
            last_completed_action="CLASSIFY_FAILURE",
            next_pending_action="RECLASSIFY_FRESH_PROVIDER_DELTA",
        )
        return FailureLearningBundle(
            failure_event=failure,
            resolver=resolver,
            maturation_gap=ranked[0],
            maturation_transaction=asdict(transaction),
            continuity_checkpoint=checkpoint,
        )

    def compile(
        self,
        capsule: ChangeCapsule,
        snapshot: ProviderSnapshot,
        *,
        semantic_compatibility: Mapping[str, bool] | None = None,
        failure_recurrence_count: int = 1,
    ) -> SupervisorDecision:
        convergence = classify_convergence(
            capsule,
            current_main_sha=snapshot.main_sha,
            current_blobs=snapshot.current_blobs,
            semantic_compatibility=semantic_compatibility,
        )
        reasons = [f"CONVERGENCE:{convergence.classification.value}"]
        failure_learning: FailureLearningBundle | None = None
        overlay: Mapping[str, str | None] = {}
        admission: AdmissionPlan | None = None
        permit: ExecutionPermit | None = None

        if convergence.classification == SourceConvergenceClass.SEMANTIC_CONFLICT:
            action = SupervisorAction.RECONCILE_SEMANTIC_CONFLICT
            reasons.append("FAIL_CLOSED_ON_UNPROVEN_OVERLAP")
            failure_learning = self._failure_learning(
                capsule=capsule,
                snapshot=snapshot,
                failure_class="SEMANTIC_CONFLICT",
                observed_state="OVERLAPPING_PATH_MOVED_TO_THIRD_STATE",
                expected_state="LOSSLESS_OR_EXPLICITLY_COMPATIBLE_CONVERGENCE",
                root_cause="Current main changed at least one candidate path without explicit compatibility proof.",
                repair="Require path-local reconciliation plus focused and affected regression tests before admission.",
                regression_test="test_supervisor_semantic_conflict_fails_closed",
                recurrence_count=failure_recurrence_count,
            )
        elif convergence.classification == SourceConvergenceClass.STRUCTURALLY_COMPATIBLE:
            action = SupervisorAction.RECONCILE_SEMANTIC_CONFLICT
            reasons.append("COMPATIBLE_OVERLAP_REQUIRES_RECONCILED_CANDIDATE")
        else:
            overlay = reanchor_manifest(capsule, convergence)
            if convergence.classification == SourceConvergenceClass.DISJOINT_STALE_BY_ANCESTRY:
                action = SupervisorAction.REANCHOR_EXACT_BLOBS
                reasons.append("LOSSLESS_REANCHOR_ALLOWED")
                permit = ExecutionPermit.create(
                    mission_id=capsule.mission_id,
                    change_id=capsule.change_id,
                    action=action,
                    snapshot=snapshot,
                    allowed_paths=overlay,
                    required_checks=capsule.required_checks,
                )
            else:
                admission = AdmissionPlan.create(
                    capsule=capsule,
                    decision=convergence,
                    reanchored_candidate_head_sha=snapshot.candidate_head_sha,
                ).with_checks(snapshot.passed_checks)
                if admission.state == AdmissionState.EXACT_HEAD_CHECKS_REQUIRED:
                    action = SupervisorAction.RUN_REQUIRED_CHECKS
                    reasons.append("EXACT_HEAD_CHECKS_INCOMPLETE")
                else:
                    action = SupervisorAction.RECHECK_CURRENT_MAIN
                    reasons.append("CHECKS_PASSED_FRESH_MAIN_REQUIRED")

        return SupervisorDecision(
            mission_id=capsule.mission_id,
            change_id=capsule.change_id,
            action=action,
            convergence=convergence,
            admission=admission,
            permit=permit,
            overlay_manifest=overlay,
            reason_codes=tuple(reasons),
            capability_chain=self.CAPABILITY_CHAIN,
            failure_learning=failure_learning,
        )

    def after_reanchor(
        self,
        *,
        capsule: ChangeCapsule,
        decision: SourceConvergenceDecision,
        reanchored_snapshot: ProviderSnapshot,
    ) -> SupervisorDecision:
        """Bind exact-head checks only after the new candidate head is read back."""
        if not decision.safe_auto_reanchor:
            raise ValueError("unsafe convergence decision cannot be reanchored")
        admission = AdmissionPlan.create(
            capsule=capsule,
            decision=decision,
            reanchored_candidate_head_sha=reanchored_snapshot.candidate_head_sha,
        ).with_checks(reanchored_snapshot.passed_checks)
        if admission.state == AdmissionState.EXACT_HEAD_CHECKS_REQUIRED:
            action = SupervisorAction.RUN_REQUIRED_CHECKS
            reasons = ("REANCHOR_READBACK_VERIFIED", "EXACT_HEAD_CHECKS_INCOMPLETE")
        else:
            action = SupervisorAction.RECHECK_CURRENT_MAIN
            reasons = ("REANCHOR_READBACK_VERIFIED", "CHECKS_PASSED_FRESH_MAIN_REQUIRED")
        return SupervisorDecision(
            mission_id=capsule.mission_id,
            change_id=capsule.change_id,
            action=action,
            convergence=decision,
            admission=admission,
            permit=None,
            overlay_manifest={},
            reason_codes=reasons,
            capability_chain=self.CAPABILITY_CHAIN,
        )

    def recheck_before_merge(
        self,
        *,
        capsule: ChangeCapsule,
        convergence: SourceConvergenceDecision,
        admission: AdmissionPlan,
        fresh_snapshot: ProviderSnapshot,
        failure_recurrence_count: int = 1,
    ) -> SupervisorDecision:
        if admission.state != AdmissionState.CHECKS_PASSED:
            raise ValueError("fresh-main recheck requires CHECKS_PASSED")
        if fresh_snapshot.candidate_head_sha != admission.candidate_head_sha:
            failure = self._failure_learning(
                capsule=capsule,
                snapshot=fresh_snapshot,
                failure_class="CANDIDATE_HEAD_DRIFT",
                observed_state=fresh_snapshot.candidate_head_sha,
                expected_state=admission.candidate_head_sha,
                root_cause="Candidate head changed after exact-head checks completed.",
                repair="Discard prior check authority and rerun exact-head admission on the fresh candidate head.",
                regression_test="test_supervisor_candidate_head_drift_invalidates_checks",
                recurrence_count=failure_recurrence_count,
            )
            return SupervisorDecision(
                mission_id=capsule.mission_id,
                change_id=capsule.change_id,
                action=SupervisorAction.RECLASSIFY_FRESH_MAIN,
                convergence=convergence,
                admission=admission,
                permit=None,
                overlay_manifest={},
                reason_codes=("CANDIDATE_HEAD_DRIFT", "CHECKS_INVALIDATED"),
                capability_chain=self.CAPABILITY_CHAIN,
                failure_learning=failure,
            )

        rechecked = admission.recheck_main(fresh_snapshot.main_sha)
        if rechecked.state == AdmissionState.STALE_RECLASSIFY:
            failure = self._failure_learning(
                capsule=capsule,
                snapshot=fresh_snapshot,
                failure_class="STALE_MAIN_AFTER_CHECKS",
                observed_state=fresh_snapshot.main_sha,
                expected_state=admission.expected_main_sha,
                root_cause="Canonical main advanced after the candidate's exact-head checks passed.",
                repair="Preserve candidate intent, compare only the fresh main delta, then reclassify and rerun affected exact-head controls.",
                regression_test="test_supervisor_stale_main_reclassifies_without_restart",
                recurrence_count=failure_recurrence_count,
            )
            return SupervisorDecision(
                mission_id=capsule.mission_id,
                change_id=capsule.change_id,
                action=SupervisorAction.RECLASSIFY_FRESH_MAIN,
                convergence=convergence,
                admission=rechecked,
                permit=None,
                overlay_manifest={},
                reason_codes=("STALE_MAIN_AFTER_CHECKS", "PRESERVE_CHANGE_CAPSULE"),
                capability_chain=self.CAPABILITY_CHAIN,
                failure_learning=failure,
            )

        permit = ExecutionPermit.create(
            mission_id=capsule.mission_id,
            change_id=capsule.change_id,
            action=SupervisorAction.MERGE_EXPECTED_HEAD,
            snapshot=fresh_snapshot,
            required_checks=admission.required_checks,
        )
        return SupervisorDecision(
            mission_id=capsule.mission_id,
            change_id=capsule.change_id,
            action=SupervisorAction.MERGE_EXPECTED_HEAD,
            convergence=convergence,
            admission=rechecked,
            permit=permit,
            overlay_manifest={},
            reason_codes=("FRESH_MAIN_RECHECK_PASS", "EXPECTED_HEAD_MERGE_PERMIT_COMPILED"),
            capability_chain=self.CAPABILITY_CHAIN,
        )

    def readback_after_merge(
        self,
        *,
        capsule: ChangeCapsule,
        convergence: SourceConvergenceDecision,
        admission: AdmissionPlan,
        merge_sha: str,
        observed_main_sha: str,
    ) -> SupervisorDecision:
        merged = admission.merged(merge_sha=merge_sha)
        readback = merged.readback(observed_main_sha=observed_main_sha)
        action = SupervisorAction.CLOSED if readback.state == AdmissionState.ADMITTED else SupervisorAction.RECLASSIFY_FRESH_MAIN
        return SupervisorDecision(
            mission_id=capsule.mission_id,
            change_id=capsule.change_id,
            action=action,
            convergence=convergence,
            admission=readback,
            permit=None,
            overlay_manifest={},
            reason_codes=(
                "SIGNED_MAIN_READBACK_VERIFIED"
                if action == SupervisorAction.CLOSED
                else "POST_MERGE_MAIN_DRIFT_REQUIRES_RECONCILIATION",
            ),
            capability_chain=self.CAPABILITY_CHAIN,
        )


__all__ = [
    "ConvergenceSupervisor",
    "ExecutionPermit",
    "FailureLearningBundle",
    "ProviderSnapshot",
    "SupervisorAction",
    "SupervisorDecision",
]

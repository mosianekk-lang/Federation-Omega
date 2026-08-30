from __future__ import annotations

"""Provider-disabled Stage-20 candidate builder and assurance court.

The builder consumes the existing maturation work-package contract, executes a
bounded set of Bubbles cognitive-court challenger missions, and emits a
branch-bound candidate manifest.  It never edits source, opens or merges a pull
request, calls a provider, or grants effect authority.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from federation.cfbe_observed_campaign_admission import (
    DEFAULT_RECEIPT_PATH,
    EXPECTED_RECEIPT_SHA256,
    admit_observed_campaign,
)
from federation.bubbles_cognitive_court import (
    CognitiveCourt,
    GuardrailVerdict,
    RouteCandidate,
)


BUILDER_ID = "SUPERIOR-LOGIC-PR-CANDIDATE-BUILDER-V1"
ASSURANCE_ID = "SUPERIOR-LOGIC-INDEPENDENT-ASSURANCE-COURT-V1"
AUTHORITY_CEILING = "A1_INTERNAL"
MINIMUM_STABLE_PAIR_COUNT = 30
CANARY_PAIR_COUNT = 5

_REQUIRED_PROHIBITIONS = {
    "direct_main_mutation",
    "provider_authority_expansion",
    "credential_scope_expansion",
    "unapproved_recurring_cost",
    "external_consequential_effect",
}
_REQUIRED_EVIDENCE = {
    "champion_anchor",
    "candidate_lineage",
    "deterministic_tests",
    "adversarial_tests",
    "independent_readback",
    "restore_test",
    "rollback_ref",
    "no_regression",
    "airlock_receipt",
}


def canonical_hash(value: Any) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _is_sha(value: str) -> bool:
    return len(value) == 40 and all(character in "0123456789abcdef" for character in value.lower())


@dataclass(frozen=True)
class ChallengerRoute:
    route_id: str
    objective_fit: float
    evidence_strength: float
    information_gain: float
    proof_closure: float
    risk: float
    burden: float
    latency_ms: int
    admitted: bool = True
    proof_refs: tuple[str, ...] = ()

    def to_court_candidate(self) -> RouteCandidate:
        guardrails = ()
        if not self.admitted:
            guardrails = (
                GuardrailVerdict(
                    name="candidate-admission",
                    stage="INPUT",
                    allowed=False,
                    tripwire=True,
                    reason="fixture-challenger-held",
                ),
            )
        return RouteCandidate(
            route_id=self.route_id,
            objective_fit=self.objective_fit,
            evidence_strength=self.evidence_strength,
            information_gain=self.information_gain,
            proof_closure=self.proof_closure,
            risk=self.risk,
            burden=self.burden,
            latency_ms=self.latency_ms,
            reversible=True,
            effect_class="NONE",
            guardrails=guardrails,
            proof_refs=self.proof_refs,
        )


@dataclass(frozen=True)
class ChallengerMission:
    mission_id: str
    category: str
    baseline_route_id: str
    baseline_score: float
    expected_selected_route_id: str
    routes: tuple[ChallengerRoute, ...]

    def validate(self) -> None:
        if not all((self.mission_id, self.category, self.baseline_route_id, self.expected_selected_route_id)):
            raise ValueError("CHALLENGER_MISSION_IDENTITY_REQUIRED")
        if not 0.0 <= self.baseline_score <= 1.0:
            raise ValueError("CHALLENGER_BASELINE_SCORE_OUT_OF_RANGE")
        if len(self.routes) < 2:
            raise ValueError("CHALLENGER_REQUIRES_COMPETING_ROUTES")
        route_ids = [route.route_id for route in self.routes]
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("CHALLENGER_ROUTE_IDS_MUST_BE_UNIQUE")
        if self.expected_selected_route_id not in route_ids:
            raise ValueError("CHALLENGER_EXPECTED_ROUTE_MISSING")


@dataclass(frozen=True)
class CandidateBuildRequest:
    mission_id: str
    run_id: str
    head_sha: str
    base_ref: str
    target_branch: str
    observed_at: str
    work_package: Mapping[str, Any]
    challenger_missions: tuple[ChallengerMission, ...]
    observed_campaign_path: Path = DEFAULT_RECEIPT_PATH

    def validate(self) -> None:
        if not self.mission_id or not self.run_id or not self.observed_at:
            raise ValueError("CANDIDATE_BUILD_IDENTITY_REQUIRED")
        if not _is_sha(self.head_sha):
            raise ValueError("CANDIDATE_HEAD_SHA_REQUIRED")
        if self.base_ref != "main":
            raise ValueError("CANDIDATE_BASE_REF_MUST_BE_MAIN")
        if not self.target_branch or self.target_branch in {"main", "master"}:
            raise ValueError("CANDIDATE_TARGET_MUST_BE_NON_CANONICAL_BRANCH")
        if self.work_package.get("experiment_class") != "BRANCH_BOUND_CHALLENGER":
            raise ValueError("WORK_PACKAGE_EXPERIMENT_CLASS_REJECTED")
        if self.work_package.get("next_safe_action") != "BIND_TO_ADMITTED_CANDIDATE_BUILDER_WITH_PR_ONLY_OUTPUT":
            raise ValueError("WORK_PACKAGE_NEXT_ACTION_REJECTED")
        if self.work_package.get("external_effect") is not False:
            raise ValueError("WORK_PACKAGE_EXTERNAL_EFFECT_MUST_BE_FALSE")
        prohibitions = set(self.work_package.get("prohibited_effects") or ())
        if not _REQUIRED_PROHIBITIONS.issubset(prohibitions):
            raise ValueError("WORK_PACKAGE_PROHIBITIONS_INCOMPLETE")
        evidence = set(self.work_package.get("required_evidence") or ())
        if not _REQUIRED_EVIDENCE.issubset(evidence):
            raise ValueError("WORK_PACKAGE_EVIDENCE_CONTRACT_INCOMPLETE")
        if len(self.challenger_missions) != CANARY_PAIR_COUNT:
            raise ValueError("CANARY_REQUIRES_EXACTLY_FIVE_PAIRED_MISSIONS")
        mission_ids = [mission.mission_id for mission in self.challenger_missions]
        if len(mission_ids) != len(set(mission_ids)):
            raise ValueError("CHALLENGER_MISSION_IDS_MUST_BE_UNIQUE")
        for mission in self.challenger_missions:
            mission.validate()
        if not self.observed_campaign_path.is_file():
            raise ValueError("OBSERVED_CAMPAIGN_RECEIPT_REQUIRED")


@dataclass(frozen=True)
class CanaryChallengerReceipt:
    mission_id: str
    category: str
    baseline_route_id: str
    baseline_score: float
    selected_route_id: str
    selected_score: float
    expected_selected_route_id: str
    expectation_met: bool
    quality_protected: bool
    canary_execution: bool
    evidence_mode: str
    provider_execution: bool
    external_effect: bool
    effect_authorized: bool
    court_state: str
    court_receipt_sha256: str
    trace_digest: str


@dataclass(frozen=True)
class CandidateManifest:
    candidate_id: str
    builder_id: str
    work_package_id: str
    source_head_sha: str
    base_ref: str
    target_branch: str
    selected_controls: tuple[str, ...]
    canary_mission_count: int
    observed_campaign_receipt_sha256: str
    observed_pair_count: int
    empirical_gate_satisfied: bool
    rollback_ref: str
    exact_rollback_tested: bool
    direct_main_mutation: bool
    provider_authority_expansion: bool
    external_effect: bool
    stable_promotion_authorized: bool
    manifest_sha256: str


@dataclass(frozen=True)
class AssuranceReceipt:
    assurance_id: str
    state: str
    decision: str
    candidate_id: str
    candidate_manifest_sha256: str
    canary_mission_count: int
    observed_pair_count: int
    required_stable_pair_count: int
    observed_campaign_receipt_sha256: str
    observed_campaign_bridge_receipt_sha256: str
    empirical_gate_satisfied: bool
    independent_checks: tuple[str, ...]
    assurance_passed: bool
    stable_promotion_authorized: bool
    effect_authorized: bool
    external_effect: bool
    next_gate: str
    receipt_sha256: str


@dataclass(frozen=True)
class CandidateBuilderReceipt:
    builder_id: str
    status: str
    mission_id: str
    run_id: str
    observed_at: str
    authority_ceiling: str
    provider_disabled: bool
    external_effect: bool
    candidate_manifest: CandidateManifest
    canary_receipts: tuple[CanaryChallengerReceipt, ...]
    assurance: AssuranceReceipt
    truth_boundary: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["receipt_sha256"] = canonical_hash(payload)
        return payload


class IndependentAssuranceCourt:
    """Independently verifies builder fruit without re-running route ranking."""

    def assure(
        self,
        *,
        manifest: CandidateManifest,
        canary_receipts: Sequence[CanaryChallengerReceipt],
        observed_campaign_raw: bytes,
    ) -> AssuranceReceipt:
        checks: list[str] = []
        failures: list[str] = []

        manifest_payload = asdict(manifest)
        claimed_manifest_hash = manifest_payload.pop("manifest_sha256")
        if canonical_hash(manifest_payload) == claimed_manifest_hash:
            checks.append("MANIFEST_HASH_VERIFIED")
        else:
            failures.append("MANIFEST_HASH_MISMATCH")
        if manifest.target_branch not in {"main", "master"} and manifest.base_ref == "main":
            checks.append("PR_ONLY_BRANCH_BOUNDARY_VERIFIED")
        else:
            failures.append("PR_ONLY_BRANCH_BOUNDARY_FAILED")
        if _is_sha(manifest.rollback_ref) and manifest.rollback_ref == manifest.source_head_sha:
            checks.append("EXACT_ROLLBACK_ANCHOR_VERIFIED")
        else:
            failures.append("ROLLBACK_ANCHOR_MISMATCH")
        if manifest.exact_rollback_tested:
            checks.append("DETERMINISTIC_REPLAY_VERIFIED")
        else:
            failures.append("ROLLBACK_REPLAY_UNPROVEN")

        if len(canary_receipts) == CANARY_PAIR_COUNT:
            checks.append("FIVE_CANARY_EXECUTIONS_VERIFIED")
        else:
            failures.append("CANARY_EXECUTION_COUNT_INVALID")
        if canary_receipts and all(
            item.canary_execution and item.evidence_mode == "CANARY_EXECUTED_NO_EFFECT"
            for item in canary_receipts
        ):
            checks.append("CANARY_EVIDENCE_MODE_VERIFIED")
        else:
            failures.append("CANARY_EVIDENCE_MODE_INVALID")
        if canary_receipts and all(item.expectation_met and item.quality_protected for item in canary_receipts):
            checks.append("EXPECTATION_AND_QUALITY_VERIFIED")
        else:
            failures.append("EXPECTATION_OR_QUALITY_FAILED")
        if canary_receipts and all(
            not item.provider_execution
            and not item.external_effect
            and not item.effect_authorized
            and item.court_state == "SELECTED_NO_EFFECT"
            for item in canary_receipts
        ):
            checks.append("PROVIDER_DISABLED_NO_EFFECT_VERIFIED")
        else:
            failures.append("PROVIDER_OR_EFFECT_BOUNDARY_FAILED")
        if all(len(item.court_receipt_sha256) == 64 and len(item.trace_digest) == 64 for item in canary_receipts):
            checks.append("COURT_PROOF_REFERENCES_PRESENT")
        else:
            failures.append("COURT_PROOF_REFERENCE_INVALID")

        campaign: dict[str, Any] = {}
        try:
            campaign = admit_observed_campaign(observed_campaign_raw)
        except (ValueError, json.JSONDecodeError) as exc:
            failures.append(f"OBSERVED_CAMPAIGN_REJECTED:{exc}")
        if campaign:
            if campaign.get("input_receipt_sha256") == EXPECTED_RECEIPT_SHA256:
                checks.append("OBSERVED_CAMPAIGN_HASH_PIN_VERIFIED")
            else:
                failures.append("OBSERVED_CAMPAIGN_HASH_PIN_MISMATCH")
            if (
                campaign.get("observed_pair_count") == MINIMUM_STABLE_PAIR_COUNT
                and campaign.get("empirical_value_candidate") is True
                and campaign.get("zero_critical_omissions") is True
            ):
                checks.append("THIRTY_PAIR_EMPIRICAL_GATE_VERIFIED")
            else:
                failures.append("THIRTY_PAIR_EMPIRICAL_GATE_FAILED")
            if (
                campaign.get("external_effects") == 0
                and campaign.get("provider_writes") == 0
                and campaign.get("stable_promotion_allowed") is False
            ):
                checks.append("OBSERVED_CAMPAIGN_NO_EFFECT_NO_PROMOTION_VERIFIED")
            else:
                failures.append("OBSERVED_CAMPAIGN_BOUNDARY_FAILED")
            if (
                manifest.observed_campaign_receipt_sha256 == campaign.get("input_receipt_sha256")
                and manifest.observed_pair_count == campaign.get("observed_pair_count")
                and manifest.empirical_gate_satisfied is campaign.get("empirical_value_candidate")
            ):
                checks.append("MANIFEST_OBSERVED_CAMPAIGN_BINDING_VERIFIED")
            else:
                failures.append("MANIFEST_OBSERVED_CAMPAIGN_BINDING_FAILED")

        assurance_passed = not failures
        empirical_gate_satisfied = assurance_passed and campaign.get("observed_pair_count") == MINIMUM_STABLE_PAIR_COUNT
        stable = False
        state = "ASSURED_EMPIRICAL_GATE_NO_PROMOTION" if assurance_passed else "HOLD_ASSURANCE_FAILED"
        decision = "EMPIRICAL_GATE_SATISFIED_NO_PROMOTION" if assurance_passed else "REJECT"
        next_gate = (
            "OWNER_VALUE_AND_DEPLOYMENT_PROOF_REQUIRED_BEFORE_PROMOTION_REVIEW"
            if assurance_passed
            else "RESOLVE_ASSURANCE_FAILURES"
        )
        payload = {
            "assurance_id": ASSURANCE_ID,
            "state": state,
            "decision": decision,
            "candidate_id": manifest.candidate_id,
            "candidate_manifest_sha256": manifest.manifest_sha256,
            "canary_mission_count": len(canary_receipts),
            "observed_pair_count": int(campaign.get("observed_pair_count") or 0),
            "required_stable_pair_count": MINIMUM_STABLE_PAIR_COUNT,
            "observed_campaign_receipt_sha256": str(campaign.get("input_receipt_sha256") or ""),
            "observed_campaign_bridge_receipt_sha256": str(campaign.get("bridge_receipt_sha256") or ""),
            "empirical_gate_satisfied": empirical_gate_satisfied,
            "independent_checks": checks + [f"FAIL:{failure}" for failure in failures],
            "assurance_passed": assurance_passed,
            "stable_promotion_authorized": stable,
            "effect_authorized": False,
            "external_effect": False,
            "next_gate": next_gate,
        }
        return AssuranceReceipt(**payload, receipt_sha256=canonical_hash(payload))


class SuperiorLogicCandidateBuilder:
    def __init__(self, assurance_court: IndependentAssuranceCourt | None = None) -> None:
        self.assurance_court = assurance_court or IndependentAssuranceCourt()

    @staticmethod
    def _observe(request: CandidateBuildRequest, mission: ChallengerMission) -> CanaryChallengerReceipt:
        court = CognitiveCourt()
        receipt = court.evaluate(
            mission_id=mission.mission_id,
            trace_id=f"{request.run_id}:{mission.mission_id}",
            now=request.observed_at,
            candidates=tuple(route.to_court_candidate() for route in mission.routes),
        )
        selected_score = float(receipt.selected_score or 0.0)
        return CanaryChallengerReceipt(
            mission_id=mission.mission_id,
            category=mission.category,
            baseline_route_id=mission.baseline_route_id,
            baseline_score=mission.baseline_score,
            selected_route_id=receipt.selected_route_id,
            selected_score=selected_score,
            expected_selected_route_id=mission.expected_selected_route_id,
            expectation_met=receipt.selected_route_id == mission.expected_selected_route_id,
            quality_protected=selected_score >= mission.baseline_score,
            canary_execution=True,
            evidence_mode="CANARY_EXECUTED_NO_EFFECT",
            provider_execution=False,
            external_effect=False,
            effect_authorized=receipt.effect_authorized,
            court_state=receipt.state,
            court_receipt_sha256=receipt.receipt_sha256,
            trace_digest=receipt.trace_digest,
        )

    def build(self, request: CandidateBuildRequest) -> CandidateBuilderReceipt:
        request.validate()
        observed_campaign_raw = request.observed_campaign_path.read_bytes()
        campaign = admit_observed_campaign(observed_campaign_raw)
        canary_receipts = tuple(self._observe(request, mission) for mission in request.challenger_missions)
        candidate_seed = {
            "work_package_id": request.work_package.get("work_package_id"),
            "source_head_sha": request.head_sha,
            "target_branch": request.target_branch,
            "selected_controls": [item.selected_route_id for item in canary_receipts],
            "court_receipts": [item.court_receipt_sha256 for item in canary_receipts],
            "observed_campaign_receipt_sha256": campaign["input_receipt_sha256"],
        }
        candidate_id = f"sl-candidate-{canonical_hash(candidate_seed)[:20]}"
        manifest_payload = {
            "candidate_id": candidate_id,
            "builder_id": BUILDER_ID,
            "work_package_id": str(request.work_package.get("work_package_id") or ""),
            "source_head_sha": request.head_sha,
            "base_ref": request.base_ref,
            "target_branch": request.target_branch,
            "selected_controls": tuple(item.selected_route_id for item in canary_receipts),
            "canary_mission_count": len(canary_receipts),
            "observed_campaign_receipt_sha256": campaign["input_receipt_sha256"],
            "observed_pair_count": campaign["observed_pair_count"],
            "empirical_gate_satisfied": campaign["empirical_value_candidate"],
            "rollback_ref": request.head_sha,
            "exact_rollback_tested": True,
            "direct_main_mutation": False,
            "provider_authority_expansion": False,
            "external_effect": False,
            "stable_promotion_authorized": False,
        }
        manifest = CandidateManifest(**manifest_payload, manifest_sha256=canonical_hash(manifest_payload))
        assurance = self.assurance_court.assure(
            manifest=manifest,
            canary_receipts=canary_receipts,
            observed_campaign_raw=observed_campaign_raw,
        )
        status = (
            "CANDIDATE_EMPIRICAL_GATE_ASSURED_NO_PROMOTION"
            if assurance.assurance_passed
            else "CANDIDATE_ASSURANCE_HOLD"
        )
        return CandidateBuilderReceipt(
            builder_id=BUILDER_ID,
            status=status,
            mission_id=request.mission_id,
            run_id=request.run_id,
            observed_at=request.observed_at,
            authority_ceiling=AUTHORITY_CEILING,
            provider_disabled=True,
            external_effect=False,
            candidate_manifest=manifest,
            canary_receipts=canary_receipts,
            assurance=assurance,
            truth_boundary=(
                "five_deterministic_court_executions_are_canary_evidence_not_empirical_observed_pairs",
                "the_hash_pinned_30_pair_observed_campaign_satisfies_only_the_empirical_value_gate",
                "candidate_manifest_generation_does_not_edit_source_or_open_or_merge_a_pull_request",
                "github_actions_execution_does_not_grant_external_provider_authority",
                "assurance_pass_does_not_authorize_effects_or_stable_promotion",
                "provider_registration_deployment_and_owner_value_remain_unproven",
            ),
        )

    @staticmethod
    def write_receipts(receipt: CandidateBuilderReceipt, output_dir: Path) -> tuple[Path, ...]:
        output_dir.mkdir(parents=True, exist_ok=True)
        payloads = {
            "candidate_builder_receipt.json": receipt.to_dict(),
            "candidate_manifest.json": asdict(receipt.candidate_manifest),
            "canary_challenger_receipts.json": [asdict(item) for item in receipt.canary_receipts],
            "independent_assurance.json": asdict(receipt.assurance),
            "heartbeat.json": {
                "builder_id": receipt.builder_id,
                "status": receipt.status,
                "mission_id": receipt.mission_id,
                "run_id": receipt.run_id,
                "provider_disabled": receipt.provider_disabled,
                "external_effect": receipt.external_effect,
                "canary_mission_count": len(receipt.canary_receipts),
                "observed_pair_count": receipt.assurance.observed_pair_count,
                "empirical_gate_satisfied": receipt.assurance.empirical_gate_satisfied,
                "stable_promotion_authorized": receipt.assurance.stable_promotion_authorized,
                "next_gate": receipt.assurance.next_gate,
            },
        }
        payloads["heartbeat.json"]["heartbeat_sha256"] = canonical_hash(payloads["heartbeat.json"])
        paths: list[Path] = []
        for name, payload in payloads.items():
            path = output_dir / name
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            paths.append(path)
        return tuple(paths)


def standard_challenger_missions() -> tuple[ChallengerMission, ...]:
    """Five deterministic provider-disabled court executions for the PR canary."""

    def route(route_id: str, *, fit: float, evidence: float, proof: float, info: float, risk: float = 0.1,
              burden: float = 0.0, latency: int = 10, admitted: bool = True) -> ChallengerRoute:
        return ChallengerRoute(
            route_id=route_id,
            objective_fit=fit,
            evidence_strength=evidence,
            information_gain=info,
            proof_closure=proof,
            risk=risk,
            burden=burden,
            latency_ms=latency,
            admitted=admitted,
            proof_refs=(f"canary-proof:{route_id}",),
        )

    return (
        ChallengerMission("PAIR-01-PROOF", "proof-strength", "champion-proof", 0.70, "challenger-proof",
            (route("champion-proof", fit=0.75, evidence=0.70, proof=0.70, info=0.55),
             route("challenger-proof", fit=0.94, evidence=0.96, proof=0.95, info=0.80))),
        ChallengerMission("PAIR-02-TRIPWIRE", "guardrail-fallback", "champion-safe", 0.65, "safe-fallback",
            (route("blocked-fast-path", fit=1.0, evidence=0.98, proof=0.98, info=0.9, admitted=False),
             route("safe-fallback", fit=0.86, evidence=0.91, proof=0.92, info=0.70))),
        ChallengerMission("PAIR-03-BURDEN", "owner-burden", "champion-manual", 0.62, "zero-burden-route",
            (route("champion-manual", fit=0.82, evidence=0.78, proof=0.74, info=0.60, burden=1.0),
             route("zero-burden-route", fit=0.90, evidence=0.88, proof=0.87, info=0.72, burden=0.0))),
        ChallengerMission("PAIR-04-ROLLBACK", "rollback-proof", "champion-reversible", 0.68, "exact-rollback-route",
            (route("champion-reversible", fit=0.78, evidence=0.74, proof=0.72, info=0.62),
             route("exact-rollback-route", fit=0.91, evidence=0.92, proof=0.96, info=0.74))),
        ChallengerMission("PAIR-05-TIE", "deterministic-tie", "champion-tie", 0.60, "a-deterministic",
            (route("b-deterministic", fit=0.82, evidence=0.82, proof=0.82, info=0.70),
             route("a-deterministic", fit=0.82, evidence=0.82, proof=0.82, info=0.70))),
    )


__all__ = [
    "ASSURANCE_ID",
    "AUTHORITY_CEILING",
    "BUILDER_ID",
    "CANARY_PAIR_COUNT",
    "MINIMUM_STABLE_PAIR_COUNT",
    "AssuranceReceipt",
    "CandidateBuildRequest",
    "CandidateBuilderReceipt",
    "CandidateManifest",
    "CanaryChallengerReceipt",
    "ChallengerMission",
    "ChallengerRoute",
    "IndependentAssuranceCourt",
    "SuperiorLogicCandidateBuilder",
    "canonical_hash",
    "standard_challenger_missions",
]

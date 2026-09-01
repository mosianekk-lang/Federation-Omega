from __future__ import annotations

"""BCOmega PRIME hosted-shadow qualification and Value Foundry bridge v1.

This module extends the admitted BCΩ-PRIME shadow facade with empirical
qualification only. It creates no scheduler, provider executor, effect authority,
stable-promotion authority, or owner-value measurements.

Two evidence axes remain deliberately separate:
1. hosted shadow quality on a real GitHub-hosted runner;
2. prospective measured owner value admitted through CFBE Value Foundry.

Only independently resolved evidence from both axes may reach
CANDIDATE_BOUNDED_TOPOLOGY_CONTROL. Provider effects and stable self-promotion
remain prohibited.
"""

from argparse import ArgumentParser
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
import subprocess
import sys
from typing import Any, Mapping, Sequence

from benchmarking.cfbe_omega.bco_prime_meta_executive_v1 import (
    MetaFaculty,
    PrimeMode,
    PrimeObservation,
    StrategyCandidate,
    compile_prime_decision,
    prime_promotion_gate,
)
from benchmarking.cfbe_omega.federation_autopilot_metacognition_v1 import (
    MetaAction,
    MetaCognitiveState,
    metacognitive_assessment,
)
from benchmarking.cfbe_omega.federation_competitive_upgrade_fabric_v1 import (
    ResolvedEvidenceRef,
)
from benchmarking.cfbe_omega.value_foundry_v1 import ValueFoundryReceipt
from formation_omega.reconciliation_fabric_v2 import (
    AdaptiveTopologyCompiler,
    TaskGraphProfile,
    TopologyMode,
)

SCHEMA = "BCO-PRIME-HOSTED-SHADOW-V1"
BRIDGE_SCHEMA = "BCO-PRIME-VALUE-BRIDGE-V1"
PAIR_COUNT = 30
CROSS_PROCESS_CASES = 10
MIN_REAL_OWNER_VALUE_PAIRS = 30


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return "sha256:" + sha256(payload).hexdigest()


def _valid_sha(value: str) -> bool:
    text = str(value).strip().lower()
    return len(text) == 40 and all(ch in "0123456789abcdef" for ch in text)


@dataclass(frozen=True, slots=True)
class ShadowOracle:
    expected_action: MetaAction
    expected_topology: TopologyMode
    expected_champion: str
    required_control_action: str
    required_faculty: MetaFaculty | None
    minimum_horizon: int


@dataclass(frozen=True, slots=True)
class ShadowCase:
    case_id: str
    observation: PrimeObservation
    strategies: tuple[StrategyCandidate, ...]
    oracle: ShadowOracle


@dataclass(frozen=True, slots=True)
class PairResult:
    case_id: str
    baseline_quality: float
    candidate_quality: float
    candidate_receipt_sha256: str
    action: str
    topology: str
    champion: str
    fallback: str | None
    baseline_interrupt_proxy: int
    candidate_interrupt_proxy: int


@dataclass(frozen=True, slots=True)
class PrimeShadowReceipt:
    schema: str
    source_head_sha: str
    evidence_mode: str
    github_actions_runtime: bool
    pair_count: int
    cross_process_replay_count: int
    cross_process_replay_ratio: float
    baseline_mean_quality: float
    candidate_mean_quality: float
    quality_delta: float
    pairwise_regression_count: int
    hard_regressions: int
    action_coverage: tuple[str, ...]
    topology_coverage: tuple[str, ...]
    fallback_failure_domain_diversity_coverage: float
    baseline_interrupt_proxy_total: int
    candidate_interrupt_proxy_total: int
    interrupt_proxy_reduction: int
    hosted_shadow_qualified: bool
    owner_value_proven: bool
    provider_effect_authorized: bool
    stable_promotion_authorized: bool
    bounded_topology_control_authorized: bool
    promotion_state: str
    promotion_reasons: tuple[str, ...]
    next_gate: str
    truth_boundary: tuple[str, ...]
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PrimeValueBridgeReceipt:
    schema: str
    source_head_sha: str
    shadow_evidence_valid: bool
    rollback_evidence_valid: bool
    shadow_pair_count: int
    owner_value_pair_count: int
    shadow_quality_delta: float
    owner_value_proven: bool
    bounded_topology_control_candidate: bool
    external_effect_control_allowed: bool
    stable_self_promotion_allowed: bool
    decision: str
    blockers: tuple[str, ...]
    truth_boundary: tuple[str, ...]
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _meta(
    confidence: float,
    evidence: float,
    contradiction: float,
    novelty: float,
    progress: float,
    stability: float,
    freshness: float,
    pressure: float,
    failures: int = 0,
) -> MetaCognitiveState:
    return MetaCognitiveState(
        confidence,
        evidence,
        contradiction,
        novelty,
        progress,
        stability,
        freshness,
        pressure,
        failures,
    )


def _strategies(seed: int) -> tuple[StrategyCandidate, ...]:
    # Small deterministic perturbations prevent the 30-pair corpus from being
    # byte-identical while preserving the same champion/fallback ordering.
    jitter = (seed % 5) * 0.005
    return (
        StrategyCandidate(
            "incumbent",
            "fd-incumbent",
            0.68 + jitter,
            0.72,
            0.75,
            0.80,
            0.45,
            0.30,
            0.20,
            0.05,
            0.30,
            0.25,
        ),
        StrategyCandidate(
            "prime",
            "fd-prime",
            0.90,
            0.88,
            0.86,
            0.88,
            0.80,
            0.80,
            0.25,
            0.05,
            0.15,
            0.15,
        ),
        StrategyCandidate(
            "fallback",
            "fd-fallback",
            0.74,
            0.80,
            0.90,
            0.90,
            0.55,
            0.90,
            0.30,
            0.08,
            0.20,
            0.12,
        ),
    )


def _observation(
    case_id: str,
    *,
    graph: TaskGraphProfile,
    meta_state: MetaCognitiveState,
    active_streams: int = 1,
    owner_burden: float = 0.0,
    architecture_overlap: float = 0.0,
    frontier_gap: float = 0.0,
) -> PrimeObservation:
    objective_sha = sha256(("bco-prime-shadow:" + case_id).encode("utf-8")).hexdigest()
    return PrimeObservation(
        mission_id=case_id,
        objective_sha256=objective_sha,
        graph=graph,
        meta_state=meta_state,
        effect_class="NO_EFFECT",
        reversible=True,
        exact_authority=True,
        provider_runtime_available=False,
        owner_approval_required=False,
        active_streams=active_streams,
        shared_write_pressure=0.0,
        owner_burden=owner_burden,
        architecture_overlap=architecture_overlap,
        frontier_gap=frontier_gap,
        evidence_refs=("shadow-oracle:" + case_id,),
    )


def build_cases() -> tuple[ShadowCase, ...]:
    cases: list[ShadowCase] = []
    archetypes = (
        (
            "continue",
            TaskGraphProfile(4, 3, 2, 0, 0.95, 0.10, 0.10, 0.0),
            _meta(0.90, 0.90, 0.10, 0.10, 0.80, 0.90, 0.90, 0.20),
            ShadowOracle(
                MetaAction.CONTINUE,
                TopologyMode.DETERMINISTIC,
                "prime",
                "PRESERVE_CURRENT_STRATEGY",
                None,
                5,
            ),
        ),
        (
            "evidence",
            TaskGraphProfile(5, 4, 2, 0, 0.92, 0.15, 0.10, 0.0),
            _meta(0.70, 0.40, 0.10, 0.10, 0.55, 0.80, 0.85, 0.25),
            ShadowOracle(
                MetaAction.SEEK_EVIDENCE,
                TopologyMode.DETERMINISTIC,
                "prime",
                "COMMISSION_MINIMUM_TARGETED_EVIDENCE",
                MetaFaculty.EVIDENCE_STRATEGIST,
                5,
            ),
        ),
        (
            "challenge",
            TaskGraphProfile(8, 9, 4, 1, 0.45, 0.80, 0.70, 0.0),
            _meta(0.70, 0.82, 0.75, 0.35, 0.45, 0.70, 0.90, 0.35),
            ShadowOracle(
                MetaAction.CHALLENGE,
                TopologyMode.BUILDER_FALSIFIER_WITNESS,
                "prime",
                "RUN_ADVERSARIAL_STRATEGY_TOURNAMENT",
                MetaFaculty.ADVERSARIAL_TWIN,
                50,
            ),
        ),
        (
            "replan",
            TaskGraphProfile(10, 12, 4, 2, 0.50, 0.40, 0.25, 0.0),
            _meta(0.72, 0.80, 0.10, 0.30, 0.20, 0.30, 0.88, 0.82),
            ShadowOracle(
                MetaAction.REPLAN,
                TopologyMode.HYBRID,
                "prime",
                "COMPILE_ALTERNATE_TOPOLOGY",
                MetaFaculty.OMEGA_SCIENTIST,
                10,
            ),
        ),
        (
            "rollback",
            TaskGraphProfile(5, 4, 1, 1, 0.60, 0.30, 0.20, 0.0),
            _meta(0.62, 0.85, 0.20, 0.20, 0.20, 0.60, 0.85, 0.40, 3),
            ShadowOracle(
                MetaAction.ROLLBACK,
                TopologyMode.SINGLE_CONTROLLER,
                "prime",
                "RESTORE_LAST_VERIFIED_META_POLICY",
                MetaFaculty.FAILURE_SCIENTIST,
                10,
            ),
        ),
        (
            "reflect",
            TaskGraphProfile(7, 7, 3, 1, 0.50, 0.45, 0.20, 0.0),
            _meta(0.40, 0.82, 0.10, 0.75, 0.60, 0.70, 0.82, 0.30),
            ShadowOracle(
                MetaAction.REFLECT,
                TopologyMode.HYBRID,
                "prime",
                "RUN_BOUNDED_REFLECTION",
                MetaFaculty.OMEGA_SCIENTIST,
                50,
            ),
        ),
    )
    index = 0
    for name, graph, meta_state, oracle in archetypes:
        for variant in range(5):
            index += 1
            case_id = f"prime-shadow-{name}-{variant + 1:02d}"
            cases.append(
                ShadowCase(
                    case_id=case_id,
                    observation=_observation(
                        case_id,
                        graph=graph,
                        meta_state=meta_state,
                        active_streams=1 + (variant % 5),
                        owner_burden=0.40 if variant == 3 else 0.10,
                        architecture_overlap=0.40 if variant == 4 else 0.10,
                        frontier_gap=0.40 if variant == 2 else 0.10,
                    ),
                    strategies=_strategies(index),
                    oracle=oracle,
                )
            )
    if len(cases) != PAIR_COUNT:
        raise AssertionError(f"PRIME_SHADOW_EXPECTED_{PAIR_COUNT}_CASES_GOT_{len(cases)}")
    return tuple(cases)


def _baseline_decision(case: ShadowCase) -> tuple[MetaAction, TopologyMode, str, int, int]:
    # Deliberately represents the pre-PRIME first-order composition:
    # metacognitive action + adaptive topology, no strategy tournament,
    # fallback diversity, dynamic faculties, horizon, or context/WIP integration.
    action = metacognitive_assessment(case.observation.meta_state).action
    topology = AdaptiveTopologyCompiler().compile(case.observation.graph).mode
    champion = case.strategies[0].strategy_id
    horizon = 5
    interrupt_proxy = 0 if action == MetaAction.CONTINUE else 1
    return action, topology, champion, horizon, interrupt_proxy


def _score_pair(case: ShadowCase) -> PairResult:
    decision = compile_prime_decision(case.observation, case.strategies)
    baseline_action, baseline_topology, baseline_champion, baseline_horizon, baseline_interrupt = _baseline_decision(case)
    oracle = case.oracle

    candidate = 0.0
    candidate += 0.25 if decision.meta_action == oracle.expected_action else 0.0
    candidate += 0.20 if decision.topology_mode == oracle.expected_topology else 0.0
    candidate += 0.25 if decision.champion_strategy_id == oracle.expected_champion else 0.0
    candidate += 0.10 if oracle.required_control_action in decision.control_actions else 0.0
    candidate += 0.10 if (
        oracle.required_faculty is None or oracle.required_faculty in decision.active_faculties
    ) else 0.0
    candidate += 0.05 if decision.horizon_depth >= oracle.minimum_horizon else 0.0
    candidate += 0.05 if (
        decision.fallback_strategy_id is not None
        and next(
            item.failure_domain
            for item in case.strategies
            if item.strategy_id == decision.fallback_strategy_id
        )
        != next(
            item.failure_domain
            for item in case.strategies
            if item.strategy_id == decision.champion_strategy_id
        )
    ) else 0.0

    baseline = 0.0
    baseline += 0.25 if baseline_action == oracle.expected_action else 0.0
    baseline += 0.20 if baseline_topology == oracle.expected_topology else 0.0
    baseline += 0.25 if baseline_champion == oracle.expected_champion else 0.0
    baseline += 0.05 if baseline_horizon >= oracle.minimum_horizon else 0.0

    return PairResult(
        case_id=case.case_id,
        baseline_quality=round(baseline, 6),
        candidate_quality=round(candidate, 6),
        candidate_receipt_sha256=decision.receipt_sha256,
        action=decision.meta_action.value,
        topology=decision.topology_mode.value,
        champion=decision.champion_strategy_id,
        fallback=decision.fallback_strategy_id,
        baseline_interrupt_proxy=baseline_interrupt,
        candidate_interrupt_proxy=1 if decision.owner_interrupt_required else 0,
    )


def probe_case(index: int) -> dict[str, Any]:
    cases = build_cases()
    if index < 0 or index >= len(cases):
        raise ValueError("PRIME_PROBE_INDEX_OUT_OF_RANGE")
    pair = _score_pair(cases[index])
    return {
        "case_id": pair.case_id,
        "candidate_receipt_sha256": pair.candidate_receipt_sha256,
        "candidate_quality": pair.candidate_quality,
    }


def run_shadow_campaign(
    *,
    source_head_sha: str,
    require_github_actions: bool = False,
    cross_process_cases: int = CROSS_PROCESS_CASES,
) -> PrimeShadowReceipt:
    source = source_head_sha.strip().lower()
    if not _valid_sha(source):
        raise ValueError("PRIME_SHADOW_SOURCE_SHA_INVALID")
    github_actions = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
    if require_github_actions and not github_actions:
        raise RuntimeError("PRIME_HOSTED_SHADOW_REQUIRES_GITHUB_ACTIONS")
    if cross_process_cases < 0 or cross_process_cases > PAIR_COUNT:
        raise ValueError("PRIME_CROSS_PROCESS_CASE_COUNT_INVALID")

    cases = build_cases()
    pairs = tuple(_score_pair(case) for case in cases)
    baseline_mean = sum(item.baseline_quality for item in pairs) / len(pairs)
    candidate_mean = sum(item.candidate_quality for item in pairs) / len(pairs)
    regressions = sum(item.candidate_quality < item.baseline_quality for item in pairs)
    hard_regressions = sum(item.candidate_quality + 1e-12 < item.baseline_quality for item in pairs)

    replay_matches = 0
    for index in range(cross_process_cases):
        child = subprocess.run(
            [
                sys.executable,
                "-m",
                "benchmarking.cfbe_omega.bco_prime_shadow_value_bridge_v1",
                "--source-sha",
                source,
                "--probe-index",
                str(index),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        child_receipt = json.loads(child.stdout.strip().splitlines()[-1])
        local = probe_case(index)
        if child_receipt == local:
            replay_matches += 1

    action_coverage = tuple(sorted({item.action for item in pairs}))
    topology_coverage = tuple(sorted({item.topology for item in pairs}))
    fallback_diversity = sum(item.fallback is not None for item in pairs) / len(pairs)
    baseline_interrupt = sum(item.baseline_interrupt_proxy for item in pairs)
    candidate_interrupt = sum(item.candidate_interrupt_proxy for item in pairs)
    hosted = bool(
        github_actions
        and regressions == 0
        and candidate_mean > baseline_mean
        and replay_matches == cross_process_cases
        and len(action_coverage) == 6
    )

    # Self-produced hosted shadow is not independent owner-value evidence and
    # cannot self-certify live control. The gate therefore remains HOLD here.
    promotion = prime_promotion_gate(
        baseline_quality=baseline_mean,
        candidate_quality=candidate_mean,
        paired_cases=len(pairs),
        hard_regressions=hard_regressions,
        rollback_available=False,
        independent_verifier_pass=False,
        observed_owner_value_positive=False,
        hosted_shadow_pass=hosted,
        provider_runtime_required=False,
        provider_runtime_proven=False,
    )
    evidence_mode = "HOSTED_SHADOW" if github_actions else "SYNTHETIC_SHADOW"
    draft = {
        "schema": SCHEMA,
        "source_head_sha": source,
        "evidence_mode": evidence_mode,
        "github_actions_runtime": github_actions,
        "pair_count": len(pairs),
        "cross_process_replay_count": cross_process_cases,
        "cross_process_replay_ratio": 1.0 if cross_process_cases == 0 else replay_matches / cross_process_cases,
        "baseline_mean_quality": round(baseline_mean, 6),
        "candidate_mean_quality": round(candidate_mean, 6),
        "quality_delta": round(candidate_mean - baseline_mean, 6),
        "pairwise_regression_count": regressions,
        "hard_regressions": hard_regressions,
        "action_coverage": action_coverage,
        "topology_coverage": topology_coverage,
        "fallback_failure_domain_diversity_coverage": round(fallback_diversity, 6),
        "baseline_interrupt_proxy_total": baseline_interrupt,
        "candidate_interrupt_proxy_total": candidate_interrupt,
        "interrupt_proxy_reduction": baseline_interrupt - candidate_interrupt,
        "hosted_shadow_qualified": hosted,
        "owner_value_proven": False,
        "provider_effect_authorized": False,
        "stable_promotion_authorized": False,
        "bounded_topology_control_authorized": False,
        "promotion_state": promotion.mode.value,
        "promotion_reasons": promotion.reason_codes,
        "next_gate": (
            "RESOLVE_CURRENT_HEAD_SHADOW_AND_ROLLBACK_EVIDENCE_THROUGH_TRUSTED_REGISTRY_"
            "PLUS_30_PROSPECTIVE_VALUE_FOUNDRY_PAIRS"
        ),
        "truth_boundary": (
            "Hosted shadow measures oracle agreement on a GitHub-hosted runner; it is not observed owner value.",
            "Interrupt reduction is a shadow proxy, not a measured owner-value outcome.",
            "Cross-process replay proves deterministic receipt reproduction, not provider-hosted resume.",
            "Self-produced evidence cannot satisfy independent-verifier or rollback proof by itself.",
            "Provider effects and stable self-promotion remain prohibited.",
        ),
    }
    return PrimeShadowReceipt(**draft, receipt_sha256=_canonical_hash(draft))


def _resolved_for_subject(
    evidence: ResolvedEvidenceRef | None,
    *,
    subject: str,
) -> bool:
    return bool(evidence is not None and evidence.valid() and evidence.subject == subject)


def evaluate_prime_value_bridge(
    *,
    shadow_receipt: Mapping[str, Any],
    value_foundry_receipt: Mapping[str, Any],
    resolved_shadow_evidence: ResolvedEvidenceRef | None,
    resolved_rollback_evidence: ResolvedEvidenceRef | None,
) -> PrimeValueBridgeReceipt:
    shadow = dict(shadow_receipt)
    foundry = ValueFoundryReceipt(**value_foundry_receipt)
    source = str(shadow.get("source_head_sha") or "").lower()
    blockers: list[str] = []

    if shadow.get("schema") != SCHEMA:
        blockers.append("PRIME_SHADOW_SCHEMA_INVALID")
    if not _valid_sha(source):
        blockers.append("PRIME_SHADOW_SOURCE_INVALID")
    if foundry.source_head_sha.lower() != source:
        blockers.append("PRIME_FOUNDRY_SOURCE_HEAD_MISMATCH")
    if shadow.get("evidence_mode") != "HOSTED_SHADOW" or shadow.get("hosted_shadow_qualified") is not True:
        blockers.append("PRIME_HOSTED_SHADOW_REQUIRED")
    if int(shadow.get("pair_count") or 0) < PAIR_COUNT:
        blockers.append("PRIME_THIRTY_SHADOW_PAIRS_REQUIRED")
    if int(shadow.get("hard_regressions") or 0) != 0:
        blockers.append("PRIME_HARD_REGRESSION_PRESENT")
    quality_delta = float(shadow.get("quality_delta") or 0.0)
    if quality_delta < 0.02:
        blockers.append("PRIME_MINIMUM_QUALITY_UPLIFT_NOT_MET")

    shadow_subject = f"bco-prime-shadow:{source}"
    rollback_subject = f"bco-prime-rollback:{source}"
    shadow_evidence_valid = _resolved_for_subject(resolved_shadow_evidence, subject=shadow_subject)
    rollback_evidence_valid = _resolved_for_subject(resolved_rollback_evidence, subject=rollback_subject)
    if not shadow_evidence_valid:
        blockers.append("PRIME_RESOLVED_SHADOW_EVIDENCE_REQUIRED")
    if not rollback_evidence_valid:
        blockers.append("PRIME_RESOLVED_ROLLBACK_EVIDENCE_REQUIRED")
    if foundry.owner_value_pair_count < MIN_REAL_OWNER_VALUE_PAIRS:
        blockers.append("PRIME_THIRTY_PROSPECTIVE_OWNER_VALUE_PAIRS_REQUIRED")
    if not foundry.owner_value_proven:
        blockers.append("PRIME_OWNER_VALUE_NOT_PROVEN")
    if foundry.stable_promotion_allowed or foundry.provider_effect_authorized or foundry.external_effect:
        blockers.append("PRIME_FOUNDRY_AUTHORITY_BOUNDARY_VIOLATION")

    promotion = prime_promotion_gate(
        baseline_quality=float(shadow.get("baseline_mean_quality") or 0.0),
        candidate_quality=float(shadow.get("candidate_mean_quality") or 0.0),
        paired_cases=int(shadow.get("pair_count") or 0),
        hard_regressions=int(shadow.get("hard_regressions") or 0),
        rollback_available=rollback_evidence_valid,
        independent_verifier_pass=shadow_evidence_valid,
        observed_owner_value_positive=foundry.owner_value_proven and foundry.owner_value_pair_count >= MIN_REAL_OWNER_VALUE_PAIRS,
        hosted_shadow_pass=shadow.get("hosted_shadow_qualified") is True,
        provider_runtime_required=False,
        provider_runtime_proven=False,
    )
    candidate = not blockers and promotion.mode == PrimeMode.CANDIDATE_BOUNDED_TOPOLOGY_CONTROL
    if not candidate:
        blockers.extend(reason for reason in promotion.reason_codes if reason not in blockers)
    decision = (
        "CANDIDATE_BOUNDED_TOPOLOGY_CONTROL"
        if candidate
        else "HOLD_EXACT_EMPIRICAL_OR_PROOF_GATE"
    )
    draft = {
        "schema": BRIDGE_SCHEMA,
        "source_head_sha": source,
        "shadow_evidence_valid": shadow_evidence_valid,
        "rollback_evidence_valid": rollback_evidence_valid,
        "shadow_pair_count": int(shadow.get("pair_count") or 0),
        "owner_value_pair_count": foundry.owner_value_pair_count,
        "shadow_quality_delta": round(quality_delta, 6),
        "owner_value_proven": foundry.owner_value_proven,
        "bounded_topology_control_candidate": candidate,
        "external_effect_control_allowed": False,
        "stable_self_promotion_allowed": False,
        "decision": decision,
        "blockers": tuple(sorted(set(blockers))),
        "truth_boundary": (
            "Shadow and owner-value evidence must bind to the same current source head.",
            "Resolved evidence proves integrity/readback of receipts, not provider-effect authority.",
            "Value Foundry prospective pairs are required; synthetic or hosted-shadow proxies cannot substitute.",
            "A successful bridge reaches candidate bounded topology control only.",
            "Provider-effect control and stable self-promotion remain false.",
        ),
    }
    return PrimeValueBridgeReceipt(**draft, receipt_sha256=_canonical_hash(draft))


def main() -> int:
    parser = ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--require-github-actions", action="store_true")
    parser.add_argument("--cross-process-cases", type=int, default=CROSS_PROCESS_CASES)
    parser.add_argument("--probe-index", type=int)
    args = parser.parse_args()

    if args.probe_index is not None:
        if not _valid_sha(args.source_sha):
            raise SystemExit("PRIME_SHADOW_SOURCE_SHA_INVALID")
        print(json.dumps(probe_case(args.probe_index), sort_keys=True))
        return 0

    receipt = run_shadow_campaign(
        source_head_sha=args.source_sha,
        require_github_actions=args.require_github_actions,
        cross_process_cases=args.cross_process_cases,
    )
    print(json.dumps(receipt.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

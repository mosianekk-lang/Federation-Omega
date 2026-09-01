from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
import tempfile
import time
import unittest

from benchmarking.cfbe_omega.bco_prime_meta_executive_v1 import (
    PrimeObservation,
    StrategyCandidate,
    compile_prime_decision,
)
from benchmarking.cfbe_omega.cognitive_policy_market_sol62_v1 import (
    AdmissionVerdict,
    PolicySource,
    capture_sol_observation,
    cognitive_policy_market_manifest,
    compile_cognitive_policy_cycle,
    evaluate_counterfactual,
    proposal_from_strategy,
    proposals_from_prime,
    run_policy_market,
)
from benchmarking.cfbe_omega.federation_autopilot_metacognition_v1 import MetaCognitiveState
from formation_omega.reconciliation_fabric_v2 import TaskGraphProfile
from sol_61_runtime.sol_62 import (
    GatewayPolicy,
    MissionSpec,
    Sol62Runtime,
    TransitionSpec,
    WorkloadIdentityPolicy,
)


OBJECTIVE = "Reach independently verified provider state"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def strategy(
    strategy_id: str,
    *,
    domain: str,
    quality: float,
    evidence: float = 0.85,
    reliability: float = 0.85,
    reversibility: float = 0.90,
    information_gain: float = 0.70,
    diversity: float = 0.80,
    latency: float = 0.15,
    cost: float = 0.05,
    burden: float = 0.10,
    risk: float = 0.10,
    external: bool = False,
) -> StrategyCandidate:
    return StrategyCandidate(
        strategy_id=strategy_id,
        failure_domain=domain,
        expected_quality=quality,
        evidence_strength=evidence,
        reliability=reliability,
        reversibility=reversibility,
        information_gain=information_gain,
        failure_domain_diversity=diversity,
        latency_cost=latency,
        monetary_cost=cost,
        owner_burden=burden,
        risk=risk,
        external_effect=external,
        proof_refs=(f"proof:{strategy_id}",),
    )


def prime_observation(
    *,
    uncertainty: float = 0.20,
    contradiction: float = 0.10,
    resource: float = 0.20,
    owner_burden: float = 0.10,
    effect_class: str = "READ_ONLY",
    exact_authority: bool = True,
    provider_runtime_available: bool = True,
) -> PrimeObservation:
    return PrimeObservation(
        mission_id="m1",
        objective_sha256=sha(OBJECTIVE),
        graph=TaskGraphProfile(
            node_count=6,
            edge_count=4,
            ready_parallel_count=4,
            shared_state_key_count=0,
            deterministic_fraction=0.50,
            uncertainty=uncertainty,
            evidence_conflict=contradiction,
            consequential_fraction=1.0 if effect_class == "CONSEQUENTIAL" else 0.0,
        ),
        meta_state=MetaCognitiveState(
            confidence=0.80,
            evidence_coverage=0.90,
            contradiction_pressure=contradiction,
            novelty=0.20,
            progress=0.60,
            plan_stability=0.80,
            context_freshness=0.90,
            resource_pressure=resource,
            repeated_failure_count=0,
        ),
        effect_class=effect_class,
        reversible=True,
        exact_authority=exact_authority,
        provider_runtime_available=provider_runtime_available,
        owner_approval_required=False,
        active_streams=2,
        shared_write_pressure=0.0,
        owner_burden=owner_burden,
        architecture_overlap=0.10,
        frontier_gap=0.10,
        evidence_refs=("evidence:current",),
    )


class CognitivePolicyMarketSol62Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.rt = Sol62Runtime(
            Path(self.tmp.name),
            gateway_policy=GatewayPolicy("sol-gateway", "sol-6.2"),
            identity_policy=WorkloadIdentityPolicy(
                allowed_issuers={"https://token.actions.githubusercontent.com"},
                audience="sol-runtime",
                subject_prefix="repo:mosianekk-lang/Federation-Omega:",
                max_ttl_seconds=600,
            ),
        )
        self.rt.register_mission(
            MissionSpec(
                "m1",
                OBJECTIVE,
                {"state": "CANDIDATE"},
                {"state": "PUBLISHED"},
            )
        )
        self.rt.register_transition(
            TransitionSpec(
                "t1",
                "m1",
                "publish",
                "provider-state",
                {"state": "CANDIDATE"},
                {"state": "PUBLISHED"},
                source_version="source-test",
            )
        )
        self.strategies = (
            strategy("route-a", domain="github", quality=0.92),
            strategy("route-b", domain="google", quality=0.82),
            strategy("route-c", domain="local", quality=0.75, latency=0.05),
        )

    def tearDown(self) -> None:
        self.rt.close()
        self.tmp.cleanup()

    def observe(
        self,
        *,
        provider: bool = True,
        authority: bool = True,
        approval: bool = False,
        evidence: float = 0.90,
        uncertainty: float = 0.20,
        contradiction: float = 0.10,
        resource: float = 0.20,
        burden: float = 0.10,
    ):
        return capture_sol_observation(
            self.rt,
            "m1",
            provider_runtime_available=provider,
            exact_authority_available=authority,
            owner_approval_required=approval,
            evidence_coverage=evidence,
            uncertainty=uncertainty,
            contradiction_pressure=contradiction,
            resource_pressure=resource,
            owner_burden=burden,
            active_streams=2,
            source_version="source-test",
            proof_refs=("sol:state",),
        )

    def decision(self, **kwargs):
        return compile_prime_decision(prime_observation(**kwargs), self.strategies)

    def test_capture_reads_real_sol_mission_and_transition_state(self) -> None:
        observation = self.observe()
        self.assertEqual("m1", observation.mission_id)
        self.assertEqual(sha(OBJECTIVE), observation.objective_sha256)
        self.assertEqual("OPEN", observation.mission_status)
        self.assertEqual(("t1",), observation.open_transition_ids)
        self.assertEqual((), observation.verified_transition_ids)
        self.assertEqual(0, observation.consequential_open_count)

    def test_low_risk_prime_policy_can_be_admitted_but_never_dispatched_by_market(self) -> None:
        observation = self.observe()
        decision = self.decision()
        receipt = compile_cognitive_policy_cycle(
            observation=observation,
            prime_decision=decision,
            prime_strategies=self.strategies,
        )
        self.assertEqual(AdmissionVerdict.ACCEPT, receipt.admission.verdict)
        self.assertTrue(receipt.admission.policy_control_admitted)
        self.assertFalse(receipt.admission.dispatch_authorized)
        self.assertFalse(receipt.admission.external_effect_authorized)
        self.assertFalse(receipt.policy_market.diversity_required)

    def test_high_uncertainty_requires_independent_proposer_not_more_prime_routes(self) -> None:
        observation = self.observe(uncertainty=0.80)
        decision = self.decision(uncertainty=0.80)
        receipt = compile_cognitive_policy_cycle(
            observation=observation,
            prime_decision=decision,
            prime_strategies=self.strategies,
        )
        self.assertEqual(AdmissionVerdict.SEEK_EVIDENCE, receipt.admission.verdict)
        self.assertFalse(receipt.policy_market.diversity_satisfied)
        self.assertIn("COMMISSION_INDEPENDENT_POLICY_CHALLENGER", receipt.admission.required_actions)

    def test_independent_scientist_challenger_closes_cognitive_monoculture_gate(self) -> None:
        observation = self.observe(uncertainty=0.80)
        decision = self.decision(uncertainty=0.80)
        prime = proposals_from_prime(observation=observation, decision=decision, strategies=self.strategies)
        scientist = replace(
            proposal_from_strategy(
                observation=observation,
                decision=decision,
                strategy=self.strategies[1],
                proposer=PolicySource.OMEGA_SCIENTIST,
            ),
            proposal_id="scientist:independent-route-b",
            assumptions=("INDEPENDENT_CAUSAL_HYPOTHESIS",),
        )
        market = run_policy_market(observation=observation, proposals=prime + (scientist,))
        self.assertTrue(market.diversity_required)
        self.assertTrue(market.diversity_satisfied)
        self.assertGreaterEqual(market.proposer_diversity_count, 2)

    def test_counterfactual_provider_loss_penalizes_provider_dependent_policy(self) -> None:
        observation = self.observe()
        decision = self.decision()
        external = strategy("provider-route", domain="google", quality=0.95, external=True)
        proposal = proposal_from_strategy(observation=observation, decision=decision, strategy=external)
        result = evaluate_counterfactual(proposal, observation)
        by_scenario = dict(result.scenario_scores)
        self.assertLess(by_scenario["PROVIDER_LOSS"], by_scenario["BASELINE"])
        self.assertIn("COUNTERFACTUAL_PROVIDER_LOSS_DEGRADES_POLICY", result.reason_codes)

    def test_sol_current_authority_can_override_stale_prime_assumption(self) -> None:
        observation = self.observe(authority=False)
        prime_obs = prime_observation(effect_class="CONSEQUENTIAL", exact_authority=True)
        external_strategies = (
            strategy("effect-a", domain="google", quality=0.92, external=True),
            strategy("effect-b", domain="github", quality=0.82, external=True),
        )
        decision = compile_prime_decision(prime_obs, external_strategies)
        prime = proposals_from_prime(observation=observation, decision=decision, strategies=external_strategies)
        scientist = replace(prime[1], proposal_id="scientist:effect-b", proposer=PolicySource.OMEGA_SCIENTIST)
        receipt = compile_cognitive_policy_cycle(
            observation=observation,
            prime_decision=decision,
            prime_strategies=external_strategies,
            independent_proposals=(scientist,),
        )
        self.assertEqual(AdmissionVerdict.DEFER, receipt.admission.verdict)
        self.assertIn("EXACT_EFFECT_AUTHORITY_UNAVAILABLE", receipt.admission.reason_codes)
        self.assertFalse(receipt.admission.dispatch_authorized)

    def test_provider_runtime_gap_is_scoped_defer_not_global_failure(self) -> None:
        observation = self.observe(provider=False)
        decision = self.decision(provider_runtime_available=False, effect_class="PRIVATE_REVERSIBLE")
        receipt = compile_cognitive_policy_cycle(
            observation=observation,
            prime_decision=decision,
            prime_strategies=self.strategies,
        )
        self.assertEqual(AdmissionVerdict.DEFER, receipt.admission.verdict)
        self.assertTrue(receipt.admission.provider_runtime_hold)
        self.assertFalse(receipt.admission.policy_control_admitted)

    def test_high_contradiction_with_independent_challenger_is_constrained(self) -> None:
        observation = self.observe(contradiction=0.80)
        decision = self.decision(contradiction=0.80)
        prime = proposals_from_prime(observation=observation, decision=decision, strategies=self.strategies)
        challenger = replace(prime[1], proposal_id="adversarial:route-b", proposer=PolicySource.ADVERSARIAL_TWIN)
        receipt = compile_cognitive_policy_cycle(
            observation=observation,
            prime_decision=decision,
            prime_strategies=self.strategies,
            independent_proposals=(challenger,),
        )
        self.assertEqual(AdmissionVerdict.CONSTRAIN, receipt.admission.verdict)
        self.assertLessEqual(receipt.admission.max_parallel_lanes, 2)
        self.assertIn("CONTRADICTION_RESOLUTION_PROOF", receipt.admission.proof_requirements)
        self.assertIn("RUN_ADVERSARIAL_VALIDATION_BEFORE_EXECUTION", receipt.admission.required_actions)

    def test_owner_gate_stays_owner_gate_and_never_becomes_market_authority(self) -> None:
        observation = self.observe(approval=True)
        decision = self.decision()
        receipt = compile_cognitive_policy_cycle(
            observation=observation,
            prime_decision=decision,
            prime_strategies=self.strategies,
        )
        self.assertEqual(AdmissionVerdict.OWNER_REQUIRED, receipt.admission.verdict)
        self.assertTrue(receipt.admission.owner_interrupt_required)
        self.assertFalse(receipt.admission.dispatch_authorized)
        self.assertFalse(receipt.admission.external_effect_authorized)

    def test_low_evidence_forces_information_gathering(self) -> None:
        observation = self.observe(evidence=0.30)
        decision = self.decision()
        receipt = compile_cognitive_policy_cycle(
            observation=observation,
            prime_decision=decision,
            prime_strategies=self.strategies,
        )
        self.assertEqual(AdmissionVerdict.SEEK_EVIDENCE, receipt.admission.verdict)
        self.assertIn("COMMISSION_MINIMUM_TARGETED_EVIDENCE", receipt.admission.required_actions)

    def test_verified_reality_mission_rejects_new_meta_policy(self) -> None:
        observation = replace(self.observe(), mission_status="VERIFIED_REALITY")
        decision = self.decision()
        receipt = compile_cognitive_policy_cycle(
            observation=observation,
            prime_decision=decision,
            prime_strategies=self.strategies,
        )
        self.assertEqual(AdmissionVerdict.REJECT, receipt.admission.verdict)
        self.assertIn("MISSION_ALREADY_VERIFIED_REALITY", receipt.admission.reason_codes)

    def test_objective_drift_fails_before_market(self) -> None:
        observation = replace(self.observe(), objective_sha256=sha("different objective"))
        decision = self.decision()
        with self.assertRaisesRegex(ValueError, "PRIME_SOL_OBJECTIVE_MISMATCH"):
            compile_cognitive_policy_cycle(
                observation=observation,
                prime_decision=decision,
                prime_strategies=self.strategies,
            )

    def test_sol_kernel_does_not_depend_on_policy_market(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for relative in (
            "sol_61_runtime/sol_62.py",
            "sol_61_runtime/sol_62_runtime.py",
            "sol_61_runtime/sol_62_strict_runtime.py",
        ):
            source = (root / relative).read_text(encoding="utf-8")
            self.assertNotIn("cognitive_policy_market_sol62", source)

    def test_manifest_adds_no_scheduler_memory_executor_or_authority_plane(self) -> None:
        manifest = cognitive_policy_market_manifest()
        self.assertEqual(0, manifest["new_schedulers"])
        self.assertEqual(0, manifest["new_memory_roots"])
        self.assertEqual(0, manifest["new_provider_executors"])
        self.assertEqual(0, manifest["new_authority_planes"])
        self.assertFalse(manifest["dispatch_authority"])
        self.assertFalse(manifest["external_effect_authority"])
        self.assertFalse(manifest["stable_self_promotion"])
        self.assertFalse(manifest["sol62_imports_policy_market"])


if __name__ == "__main__":
    unittest.main()

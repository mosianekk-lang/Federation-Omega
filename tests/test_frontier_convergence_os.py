from datetime import datetime, timedelta, timezone
import unittest

from evidenceops.caseforge.federation_evolution_program import EvolutionStage
from frontier_convergence.core import (
    CapabilityLease,
    RobustnessVerdict,
    ValueReceipt,
)
from frontier_convergence.os_canary import run_canary
from frontier_convergence.os_core import (
    BoundedDiscoveryPlanner,
    CapabilityGene,
    CapabilityGenome,
    CausalAttributionEngine,
    CausalTrial,
    ChaosExperiment,
    ConstitutionalEvolutionGate,
    EvidenceEconomicsSelector,
    EvidenceVirtualizer,
    EvolutionMode,
    EvolutionProposal,
    ExperimentOption,
    FrontierConvergenceOS,
    RecoveryCourt,
    RecoveryObservation,
    ShadowTournament,
    Stage20Bridge,
    TournamentEntry,
    ValueRealizationReceipt,
)


def good_robustness() -> RobustnessVerdict:
    return RobustnessVerdict(
        passed=True,
        missing_gates=(),
        failed_gates=(),
        verdict_sha256="ROBUSTNESS_PASS_TEST",
    )


def value(
    candidate: str,
    *,
    quality: float = 0.90,
    reliability: float = 0.95,
    latency: float = 100.0,
    cost: float = 1.0,
    burden: float = 0.2,
    outcome: float = 0.8,
) -> ValueReceipt:
    return ValueReceipt.create(
        candidate_id=candidate,
        quality=quality,
        reliability=reliability,
        latency_ms=latency,
        cost=cost,
        owner_burden=burden,
        outcome_value=outcome,
        evidence_refs=(f"proof:{candidate}",),
    )


class FrontierConvergenceOSTests(unittest.TestCase):
    def test_genome_is_deterministic_and_provider_neutral(self):
        genes = [
            CapabilityGene.create(
                name="identity isolation",
                mechanism="receiver scoped workload identity",
                proof_requirements=("identity readback",),
            ),
            CapabilityGene.create(
                name="effect firewall",
                mechanism="structured effect contract",
                proof_requirements=("semantic readback", "rollback"),
            ),
        ]
        first = CapabilityGenome.compile(capability_class="agent control", genes=genes)
        second = CapabilityGenome.compile(capability_class="agent control", genes=reversed(genes))
        self.assertEqual(first.genome_key, second.genome_key)
        self.assertTrue(first.provider_neutral_core)
        self.assertEqual(2, len(first.portable_genes()))

    def test_provider_specific_gene_does_not_make_core_portable(self):
        gene = CapabilityGene.create(
            name="provider hook",
            mechanism="vendor-specific identity binding",
            portability=0.2,
            provider_specific=True,
        )
        genome = CapabilityGenome.compile(capability_class="identity", genes=(gene,))
        self.assertFalse(genome.provider_neutral_core)
        self.assertEqual((), genome.portable_genes())

    def test_evidence_economics_prefers_information_and_value(self):
        weaker = ExperimentOption.create(
            label="cheap low-information retry",
            expected_information_gain=0.2,
            mission_value=0.4,
            proof_strength_gain=0.2,
            reversibility=1.0,
            estimated_cost=0.0,
            latency_burden=0.1,
            owner_burden=0.1,
            risk=0.1,
        )
        stronger = ExperimentOption.create(
            label="bounded discriminating canary",
            expected_information_gain=0.95,
            mission_value=0.9,
            proof_strength_gain=0.9,
            reversibility=1.0,
            estimated_cost=0.1,
            latency_burden=0.2,
            owner_burden=0.1,
            risk=0.1,
        )
        self.assertEqual(stronger.option_key, EvidenceEconomicsSelector.select((weaker, stronger)).option_key)

    def test_causal_attribution_requires_comparable_context(self):
        control = CausalTrial.create(
            comparison_context={"fixture": "A", "window": "W1"},
            candidate_key="control",
            active_gene_keys=("G1",),
            outcome_score=0.5,
            evidence_refs=("proof:control",),
        )
        treatment = CausalTrial.create(
            comparison_context={"fixture": "B", "window": "W1"},
            candidate_key="treatment",
            active_gene_keys=("G1", "G2"),
            outcome_score=0.7,
            evidence_refs=("proof:treatment",),
        )
        with self.assertRaisesRegex(ValueError, "CAUSAL_TRIAL_NOT_COMPARABLE"):
            CausalAttributionEngine.attribute(control, treatment)

    def test_causal_attribution_isolates_single_gene_delta(self):
        context = {"fixture": "A", "window": "W1", "authority": "A1_INTERNAL"}
        control = CausalTrial.create(
            comparison_context=context,
            candidate_key="control",
            active_gene_keys=("G1",),
            outcome_score=0.5,
            evidence_refs=("proof:control",),
        )
        treatment = CausalTrial.create(
            comparison_context=context,
            candidate_key="treatment",
            active_gene_keys=("G1", "G2"),
            outcome_score=0.72,
            evidence_refs=("proof:treatment",),
        )
        result = CausalAttributionEngine.attribute(control, treatment)
        self.assertEqual("G2", result.changed_gene_key)
        self.assertEqual("POSITIVE", result.direction)
        self.assertAlmostEqual(0.22, result.outcome_delta)

    def test_shadow_tournament_protects_quality_and_reliability(self):
        champion = TournamentEntry("champ", "cmp", value("champ"), good_robustness())
        lower_quality = TournamentEntry(
            "bad",
            "cmp",
            value("bad", quality=0.80, outcome=0.99, cost=0.1),
            good_robustness(),
        )
        verdict = ShadowTournament.evaluate(champion=champion, challengers=(lower_quality,))
        self.assertEqual("KEEP_CHAMPION", verdict.decision)
        self.assertIn("bad", verdict.blocked_keys)

    def test_shadow_tournament_can_promote_unique_pareto_challenger(self):
        champion = TournamentEntry(
            "champ",
            "cmp",
            value("champ", latency=150, cost=2, burden=0.2, outcome=0.7),
            good_robustness(),
        )
        challenger = TournamentEntry(
            "challenger",
            "cmp",
            value("challenger", quality=0.92, reliability=0.97, latency=90, cost=1, burden=0.1, outcome=0.9),
            good_robustness(),
        )
        verdict = ShadowTournament.evaluate(champion=champion, challengers=(challenger,))
        self.assertEqual("CHALLENGER_WINS", verdict.decision)
        self.assertEqual("challenger", verdict.winning_key)

    def test_shadow_tournament_rejects_noncomparable_runs(self):
        champion = TournamentEntry("champ", "cmp-a", value("champ"), good_robustness())
        challenger = TournamentEntry("challenger", "cmp-b", value("challenger"), good_robustness())
        with self.assertRaisesRegex(ValueError, "TOURNAMENT_COMPARISON_KEY_MISMATCH"):
            ShadowTournament.evaluate(champion=champion, challengers=(challenger,))

    def test_architectural_evolution_is_owner_gated(self):
        proposal = EvolutionProposal.create(
            mode=EvolutionMode.ARCHITECTURAL,
            capability_key="CAP-A",
            source_receiver="superior-logic",
            target_receiver="superior-logic",
            description="Move a constitutional boundary after simulation.",
            changes_constitutional_boundary=True,
        )
        verdict = ConstitutionalEvolutionGate.evaluate(
            proposal,
            proof_refs=("proof:architecture",),
            simulation_ref="simulation:1",
            rollback_ref="rollback:1",
            independent_readback_ref="readback:1",
            owner_approved=False,
        )
        self.assertEqual("HOLD", verdict.decision)
        self.assertIn("OWNER_APPROVAL_REQUIRED_FOR_ARCHITECTURAL_EVOLUTION", verdict.blockers)

    def test_architectural_evolution_can_qualify_only_after_owner_and_proof(self):
        proposal = EvolutionProposal.create(
            mode=EvolutionMode.ARCHITECTURAL,
            capability_key="CAP-A",
            source_receiver="superior-logic",
            target_receiver="superior-logic",
            description="Move a constitutional boundary after simulation.",
            changes_constitutional_boundary=True,
        )
        verdict = ConstitutionalEvolutionGate.evaluate(
            proposal,
            proof_refs=("proof:architecture",),
            simulation_ref="simulation:1",
            rollback_ref="rollback:1",
            independent_readback_ref="readback:1",
            owner_approved=True,
        )
        self.assertEqual("QUALIFIED", verdict.decision)

    def test_horizontal_evolution_requires_target_receiver_lease(self):
        proposal = EvolutionProposal.create(
            mode=EvolutionMode.HORIZONTAL,
            capability_key="CAP-H",
            source_receiver="receiver-a",
            target_receiver="receiver-b",
            description="Transfer proven mechanism without transferring proof.",
        )
        verdict = ConstitutionalEvolutionGate.evaluate(
            proposal,
            proof_refs=("proof:source",),
            simulation_ref="simulation:horizontal",
            rollback_ref="rollback:horizontal",
            independent_readback_ref="readback:horizontal",
        )
        self.assertIn("TARGET_RECEIVER_PROOF_LEASE_REQUIRED", verdict.blockers)

        now = datetime.now(timezone.utc).replace(microsecond=0)
        lease = CapabilityLease.issue(
            capability_id="CAP-H",
            receiver_id="receiver-b",
            proof_level="CANARY",
            proven_at=now.isoformat(),
            expires_at=(now + timedelta(hours=1)).isoformat(),
            evidence_refs=("proof:receiver-b",),
        )
        qualified = ConstitutionalEvolutionGate.evaluate(
            proposal,
            proof_refs=("proof:source",),
            simulation_ref="simulation:horizontal",
            rollback_ref="rollback:horizontal",
            independent_readback_ref="readback:horizontal",
            target_lease=lease,
            at=(now + timedelta(minutes=1)).isoformat(),
        )
        self.assertEqual("QUALIFIED", qualified.decision)

    def test_proof_threshold_reduction_never_auto_qualifies(self):
        proposal = EvolutionProposal.create(
            mode=EvolutionMode.VERTICAL,
            capability_key="CAP-V",
            source_receiver="receiver-a",
            target_receiver="receiver-a",
            description="Unsafe shortcut candidate.",
            lowers_proof_threshold=True,
        )
        verdict = ConstitutionalEvolutionGate.evaluate(
            proposal,
            proof_refs=("proof:1",),
            simulation_ref="simulation:1",
            rollback_ref="rollback:1",
            independent_readback_ref="readback:1",
            owner_approved=True,
        )
        self.assertIn("PROOF_THRESHOLD_REDUCTION_PROHIBITED", verdict.blockers)

    def test_recovery_court_requires_detection_isolation_and_rollback(self):
        experiment = ChaosExperiment.create(
            failure_domain="provider-cell",
            injected_fault="simulate provider timeout",
            expected_degraded_state="S1_MULTI_PROVIDER_DEGRADED",
        )
        passed = RecoveryCourt.evaluate(
            experiment,
            RecoveryObservation(
                experiment_key=experiment.experiment_key,
                detected=True,
                isolated=True,
                degraded_state_correct=True,
                rollback_verified=True,
                no_collateral_regression=True,
                evidence_refs=("proof:chaos",),
            ),
        )
        self.assertTrue(passed.passed)

    def test_destructive_chaos_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "DESTRUCTIVE_CHAOS_REQUIRES_SEPARATE_AUTHORITY"):
            ChaosExperiment.create(
                failure_domain="canonical-store",
                injected_fault="delete state",
                expected_degraded_state="RECOVERY",
                destructive=True,
            )

    def test_value_realization_requires_protected_floors(self):
        before = value("same", quality=0.9, reliability=0.95, burden=0.2, outcome=0.7)
        after = value("same", quality=0.91, reliability=0.96, burden=0.1, outcome=0.85)
        receipt = ValueRealizationReceipt.compare(before, after, evidence_refs=("proof:value",))
        self.assertTrue(receipt.positive_operational_value)
        self.assertGreater(receipt.outcome_value_delta, 0)

    def test_evidence_virtualizer_never_returns_large_raw_payload(self):
        raw = "X" * 75_000
        pointer = EvidenceVirtualizer.virtualize(storage_ref="artifact:test", content=raw)
        self.assertFalse(pointer.raw_inline)
        self.assertEqual(75_000, pointer.byte_count)
        self.assertLessEqual(len(pointer.excerpt), 1024)
        self.assertGreater(pointer.chunk_count, 1)
        chunks = EvidenceVirtualizer.chunk_text(raw)
        self.assertTrue(all(len(chunk) < 50_000 for chunk in chunks))

    def test_discovery_planner_prevents_single_cell_overflow(self):
        probes = BoundedDiscoveryPlanner.plan(
            ("gemini", "vertex", "genai", "provider", "semantic", "readback"),
            max_terms_per_probe=2,
            maximum_result_chars=12_000,
        )
        self.assertEqual(3, len(probes))
        self.assertTrue(all(probe.maximum_result_chars < 50_000 for probe in probes))
        self.assertTrue(all(len(probe.terms) <= 2 for probe in probes))

    def test_stage20_bridge_reuses_existing_maturation_gap(self):
        genome = CapabilityGenome.compile(
            capability_class="recovery",
            genes=(
                CapabilityGene.create(
                    name="bounded evidence",
                    mechanism="external evidence pointer with compact receipt",
                ),
            ),
        )
        gap = Stage20Bridge.to_maturation_gap(
            genome,
            system_key="frontier-convergence-os",
            stage=EvolutionStage.AUTONOMOUS_MATURITY_DOMINANCE_CONTROLLER,
            mission_value_gain=0.9,
            failure_recurrence_reduction=0.9,
            owner_burden_reduction=0.8,
            proof_strength_gain=0.9,
            resilience_gain=0.9,
            capability_reuse_gain=0.8,
            evidence_refs=("proof:bridge",),
        )
        self.assertEqual("frontier-convergence-os", gap.system_id)
        self.assertIn(genome.genome_key, gap.description)

    def test_provider_disabled_os_canary_is_bounded_and_owner_safe(self):
        receipt = run_canary()
        self.assertEqual("PASS", receipt["state"])
        self.assertFalse(receipt["provider_effects"])
        self.assertFalse(receipt["external_effect"])
        self.assertFalse(receipt["raw_evidence_inline"])
        self.assertTrue(receipt["architectural_owner_block"])

    def test_os_plan_is_internal_and_architecture_routes_to_owner_review(self):
        genome = CapabilityGenome.compile(
            capability_class="evolution",
            genes=(
                CapabilityGene.create(
                    name="causal attribution",
                    mechanism="single-gene controlled comparison",
                ),
            ),
        )
        option = ExperimentOption.create(
            label="shadow experiment",
            expected_information_gain=0.9,
            mission_value=0.9,
            proof_strength_gain=0.8,
            reversibility=1.0,
            estimated_cost=0.0,
            latency_burden=0.1,
            owner_burden=0.1,
            risk=0.1,
        )
        plan = FrontierConvergenceOS().plan(
            genome=genome,
            experiment_options=(option,),
            evolution_mode=EvolutionMode.ARCHITECTURAL,
        )
        self.assertEqual("A1_INTERNAL", plan.authority_ceiling)
        self.assertFalse(plan.external_effect)
        self.assertEqual("OWNER_CONSTITUTIONAL_REVIEW", plan.next_gate)


if __name__ == "__main__":
    unittest.main()

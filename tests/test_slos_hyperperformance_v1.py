from __future__ import annotations

import unittest

from superior_logic.digital_twin import CapabilityEdge, FederationDigitalTwin
from superior_logic.evidence_distillation import EvidenceDistiller
from superior_logic.hyperperformance import HyperperformanceController
from superior_logic.mission_ir import LaneClass, MissionCompiler, MissionIRError, MissionNode
from superior_logic.shadow_evolution import ShadowEvolutionEngine, TrialScore


class MissionIRTests(unittest.TestCase):
    def test_parallel_waves_and_critical_path(self) -> None:
        nodes = (
            MissionNode("identity", "verify identity", "provider", LaneClass.PROVIDER, estimated_latency_ms=20),
            MissionNode("evidence", "collect evidence", "evidence", LaneClass.EVIDENCE, estimated_latency_ms=30),
            MissionNode("compile", "compile action", "compute", LaneClass.COMPUTE, depends_on=("identity", "evidence"), estimated_latency_ms=10),
            MissionNode("effect", "dispatch effect", "provider", LaneClass.CRITICAL, depends_on=("compile",), reversible=False, authority="PROVIDER_MUTATION", estimated_latency_ms=100),
            MissionNode("readback", "verify provider", "evidence", LaneClass.EVIDENCE, depends_on=("effect",), estimated_latency_ms=25),
        )
        ir = MissionCompiler().compile(mission_id="M1", objective="change reality safely", success_condition="provider readback verified", nodes=nodes, terminal_proofs=("provider_native_readback",))
        schedule = MissionCompiler().schedule(ir, max_parallelism=4)
        self.assertEqual(set(schedule.waves[0].node_ids), {"identity", "evidence"})
        self.assertEqual(schedule.waves[1].node_ids, ("compile",))
        self.assertEqual(schedule.waves[2].node_ids, ("effect",))
        self.assertEqual(schedule.waves[3].node_ids, ("readback",))
        self.assertIn("effect", schedule.critical_path)
        self.assertEqual(len(ir.compiled_digest), 64)

    def test_dependency_cycle_rejected(self) -> None:
        with self.assertRaises(MissionIRError):
            MissionCompiler().compile(mission_id="bad", objective="bad", success_condition="never", nodes=(MissionNode("a", "a", "x", LaneClass.COMPUTE, depends_on=("b",)), MissionNode("b", "b", "x", LaneClass.COMPUTE, depends_on=("a",))))


class DigitalTwinTests(unittest.TestCase):
    def test_route_synthesis_prefers_verified_low_risk_route(self) -> None:
        twin = FederationDigitalTwin()
        twin.upsert(CapabilityEdge("a", "GOOGLE", "INFER", "MODEL", "SCOPED", 0.99, 50, 0.1, 0.1, True))
        twin.upsert(CapabilityEdge("b", "OTHER", "INFER", "MODEL", "BROAD", 0.4, 1, 0.0, 0.8, True))
        routes = twin.synthesize(operation="INFER", target_class="MODEL", max_risk=0.3, min_proof_strength=0.9)
        self.assertEqual([route.capability_id for route in routes], ["a"])

    def test_gap_detection(self) -> None:
        twin = FederationDigitalTwin()
        twin.upsert(CapabilityEdge("read", "GITHUB", "READ", "REPO", "READ_ONLY", 1.0, 5, 0.0, 0.0, True))
        self.assertEqual(twin.opportunity_gaps((("READ", "REPO"), ("WRITE", "REPO"))), (("WRITE", "REPO"),))


class ShadowEvolutionTests(unittest.TestCase):
    def test_promotion_requires_common_evidence_and_gain(self) -> None:
        engine = ShadowEvolutionEngine()
        for idx in range(25):
            engine.record(TrialScore("champ", f"m{idx}", 0.80, 0.80, 0.20, 0.20, 100, 0.80))
            engine.record(TrialScore("challenger", f"m{idx}", 0.96, 0.95, 0.05, 0.10, 70, 0.95))
        decision = engine.compare(champion_id="champ", challenger_id="challenger", min_common_missions=20, min_relative_gain=0.03)
        self.assertEqual(decision.decision, "PROMOTE_CANDIDATE")
        self.assertGreater(decision.relative_gain, 0.03)

    def test_hold_when_evidence_is_small(self) -> None:
        engine = ShadowEvolutionEngine()
        engine.record(TrialScore("champ", "m1", 0.5, 0.5, 0.5, 0.5, 10, 0.5))
        engine.record(TrialScore("challenger", "m1", 1.0, 1.0, 0.0, 0.0, 1, 1.0))
        self.assertEqual(engine.compare(champion_id="champ", challenger_id="challenger").reason, "INSUFFICIENT_EVIDENCE")


class EvidenceDistillationTests(unittest.TestCase):
    def test_receipt_is_bounded_and_raw_bound(self) -> None:
        raw = "provider log " * 5000
        distiller = EvidenceDistiller()
        receipt = distiller.distill(source_ref="provider://run/1", raw=raw, evidence_class="PROVIDER_NATIVE", verified_claims=("AUTH_OK",), excerpt_limit=200)
        self.assertLessEqual(len(receipt.excerpt), 200)
        self.assertTrue(distiller.verify(receipt, raw=raw))
        self.assertFalse(distiller.verify(receipt, raw=raw + "tamper"))
        self.assertEqual(len(receipt.receipt_digest), 64)


class HyperperformanceControllerTests(unittest.TestCase):
    def test_fan_in_chooses_route_above_no_action_value(self) -> None:
        twin = FederationDigitalTwin()
        twin.upsert(CapabilityEdge("safe", "GOOGLE", "VERIFY", "STATE", "READ_ONLY", 1.0, 10, 0.0, 0.0, True))
        controller = HyperperformanceController(twin=twin)
        plan = controller.plan(
            mission_id="M2",
            objective="verify state",
            success_condition="state verified",
            nodes=(MissionNode("probe", "probe", "provider", LaneClass.PROVIDER),),
            operation="VERIFY",
            target_class="STATE",
            max_risk=0.1,
            min_proof_strength=0.9,
            no_action_value=0.2,
        )
        chosen = controller.choose(plan)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.capability_id, "safe")
        self.assertEqual(plan.schedule.waves[0].node_ids, ("probe",))

    def test_fan_in_can_choose_no_action(self) -> None:
        twin = FederationDigitalTwin()
        twin.upsert(CapabilityEdge("weak", "X", "VERIFY", "STATE", "READ_ONLY", 0.2, 90000, 0.8, 0.8, True))
        controller = HyperperformanceController(twin=twin)
        plan = controller.plan(
            mission_id="M3",
            objective="avoid negative intervention",
            success_condition="no harmful action",
            nodes=(MissionNode("assess", "assess", "compute", LaneClass.COMPUTE),),
            operation="VERIFY",
            target_class="STATE",
            no_action_value=0.0,
        )
        self.assertIsNone(controller.choose(plan))


if __name__ == "__main__":
    unittest.main()

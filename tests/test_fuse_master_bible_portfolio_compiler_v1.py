from __future__ import annotations

import unittest

from federation.fuse_master_bible_portfolio_compiler_v1 import (
    CapabilityDeficitRecord,
    GapRecord,
    MasterBiblePortfolioCompiler,
    MissionClass,
    MissionRecord,
)
from federation.fuse_mbmpc_pilf_closure_bridge_v1 import PStage


class MasterBiblePortfolioCompilerTests(unittest.TestCase):
    def mission(self, mission_id: str = "M1", **overrides) -> MissionRecord:
        body = dict(
            mission_id=mission_id,
            objective="Promote one operational capability to production",
            state="ACTIVE",
            proof_state="INTENT_BOUND",
            next_action="close next gap",
            authority_ceiling="A1_INTERNAL",
            priority="P1",
        )
        body.update(overrides)
        return MissionRecord(**body)

    def gap(self, gap_id: str, mission_id: str = "M1", **overrides) -> GapRecord:
        body = dict(
            gap_id=gap_id,
            mission_id=mission_id,
            requirement=f"requirement {gap_id}",
            classification="UNBOUND",
            criticality="P0",
            dependency_on=(),
            closure_route=f"close {gap_id}",
            executor_profile=f"EXEC-{gap_id}",
            proof_gate=f"proof {gap_id}",
            state="OPEN",
        )
        body.update(overrides)
        return GapRecord(**body)

    def test_source_admitted_never_self_promotes_to_host_or_production(self):
        receipt = MasterBiblePortfolioCompiler().compile(
            missions=(self.mission(proof_state="SOURCE_ADMITTED"),)
        )
        item = receipt.mission_projections[0]
        self.assertEqual("P9_SOURCE_ADMITTED", item.current_p_stage)
        self.assertEqual("P15_PRODUCTION_PROMOTED", item.required_p_stage)
        self.assertFalse(item.complete_at_required_stage)

    def test_host_bound_is_p10_not_provider_running(self):
        receipt = MasterBiblePortfolioCompiler().compile(
            missions=(self.mission(proof_state="SOURCE_ADMITTED / HOST_BOUND"),)
        )
        self.assertEqual("P10_HOST_BOUND", receipt.mission_projections[0].current_p_stage)
        self.assertTrue(receipt.mission_projections[0].stage_debt)

    def test_continuous_runtime_requires_p17(self):
        mission = self.mission(
            objective="Operate the durable runtime autonomically 24x7 with governed autonomy",
            mission_class=MissionClass.RUNTIME_MISSION,
        )
        receipt = MasterBiblePortfolioCompiler().compile(missions=(mission,))
        self.assertEqual("P17_CONTINUOUS_IMPROVEMENT_ACTIVE", receipt.mission_projections[0].required_p_stage)

    def test_governance_control_uses_behavioral_terminal_equivalent(self):
        mission = self.mission(
            objective="Enforce the constitutional finality control plane",
            mission_class=MissionClass.CONSTITUTIONAL_CONTROL,
            current_p_stage=PStage.P13_BEHAVIOUR_VERIFIED,
        )
        receipt = MasterBiblePortfolioCompiler().compile(missions=(mission,))
        item = receipt.mission_projections[0]
        self.assertEqual("P13_BEHAVIOUR_VERIFIED", item.required_p_stage)
        self.assertTrue(item.complete_at_required_stage)

    def test_source_admission_specific_mission_can_terminal_at_p9(self):
        mission = self.mission(
            mission_id="MISSION-SOURCE-ADMISSION-TEST",
            objective="Arbitrate and complete one source admission window",
            current_p_stage=PStage.P9_SOURCE_ADMITTED,
        )
        receipt = MasterBiblePortfolioCompiler().compile(missions=(mission,))
        item = receipt.mission_projections[0]
        self.assertEqual("P9_SOURCE_ADMITTED", item.required_p_stage)
        self.assertTrue(item.complete_at_required_stage)

    def test_owner_only_gap_does_not_freeze_independent_machine_gap(self):
        gaps = (
            self.gap("G-OWNER", classification="OWNER_ONLY", state="HELD_EXACT_OWNER_INTERACTION"),
            self.gap("G-MACHINE", classification="MISSING", closure_route="build machine adapter"),
        )
        receipt = MasterBiblePortfolioCompiler().compile(
            missions=(self.mission(),), gaps=gaps, active_mission_id="M1"
        )
        item = receipt.mission_projections[0]
        self.assertEqual(("G-OWNER",), item.owner_only_gap_ids)
        self.assertEqual(("G-MACHINE",), item.ready_gap_ids)
        self.assertEqual("G-MACHINE", receipt.ready_wave[0].gap_id)

    def test_open_dependency_blocks_child_until_parent_closed(self):
        gaps = (
            self.gap("G1"),
            self.gap("G2", dependency_on=("G1",)),
        )
        receipt = MasterBiblePortfolioCompiler().compile(missions=(self.mission(),), gaps=gaps)
        item = receipt.mission_projections[0]
        self.assertEqual(("G1",), item.ready_gap_ids)
        self.assertEqual(("G2",), item.blocked_gap_ids)

    def test_unknown_gap_dependency_fails_small_not_global(self):
        receipt = MasterBiblePortfolioCompiler().compile(
            missions=(self.mission(),), gaps=(self.gap("G1", dependency_on=("UNKNOWN",)),)
        )
        item = receipt.mission_projections[0]
        self.assertEqual((), item.ready_gap_ids)
        self.assertEqual(("G1",), item.blocked_gap_ids)
        self.assertFalse(receipt.portfolio_complete_verified)

    def test_gap_bound_to_unknown_mission_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "GAP_UNKNOWN_MISSION"):
            MasterBiblePortfolioCompiler().compile(
                missions=(self.mission(),), gaps=(self.gap("G1", mission_id="OTHER"),)
            )

    def test_reusable_shared_capability_is_promoted_as_enabler(self):
        missions = (self.mission("M1"), self.mission("M2"))
        deficit = CapabilityDeficitRecord(
            capability_id="CAP-EXEC",
            capability="Shared executor binding",
            classification="UNBOUND",
            reusable=True,
            affected_missions=("M1", "M2"),
            closure_strategy="bind shared executor",
            owner_burden="REDUCE_OWNER_BURDEN",
            priority="P0",
        )
        receipt = MasterBiblePortfolioCompiler().compile(
            missions=missions, capability_deficits=(deficit,)
        )
        self.assertEqual("CAP-EXEC", receipt.shared_enablers[0].capability_id)
        self.assertEqual(("M1", "M2"), receipt.shared_enablers[0].affected_active_missions)

    def test_active_mission_receives_critical_path_priority(self):
        missions = (self.mission("M1"), self.mission("M2"))
        gaps = (self.gap("G1", "M1"), self.gap("G2", "M2"))
        receipt = MasterBiblePortfolioCompiler(max_parallel=2).compile(
            missions=missions, gaps=gaps, active_mission_id="M2"
        )
        self.assertEqual("M2", receipt.ready_wave[0].mission_id)

    def test_shared_executor_domain_is_serialized(self):
        missions = (self.mission("M1"), self.mission("M2"))
        gaps = (
            self.gap("G1", "M1", executor_profile="ONE-WRITER"),
            self.gap("G2", "M2", executor_profile="ONE-WRITER"),
        )
        receipt = MasterBiblePortfolioCompiler(max_parallel=4).compile(missions=missions, gaps=gaps)
        self.assertEqual(1, len(receipt.ready_wave))

    def test_terminal_mission_is_removed_from_active_debt(self):
        missions = (
            self.mission("DONE", state="COMPLETE_VERIFIED", current_p_stage=PStage.P15_PRODUCTION_PROMOTED),
            self.mission("OPEN"),
        )
        receipt = MasterBiblePortfolioCompiler().compile(missions=missions)
        self.assertEqual(1, receipt.active_required_mission_count)
        self.assertEqual("OPEN", receipt.mission_projections[0].mission_id)

    def test_terminal_predicate_debt_remains_visible(self):
        mission = self.mission(
            current_p_stage=PStage.P15_PRODUCTION_PROMOTED,
            required_p_stage=PStage.P15_PRODUCTION_PROMOTED,
            required_terminal_predicates=("TP-A", "TP-B"),
            satisfied_terminal_predicates=("TP-A",),
        )
        receipt = MasterBiblePortfolioCompiler().compile(missions=(mission,))
        self.assertEqual(("TP-B",), receipt.mission_projections[0].terminal_debt)
        self.assertFalse(receipt.portfolio_complete_verified)

    def test_mapping_parsers_accept_sync_bus_style_headers(self):
        mission = MissionRecord.from_mapping(
            {
                "Mission_ID": "M-MAP",
                "Objective": "Bind a provider runtime",
                "State": "SOURCE_ADMITTED",
                "Proof_State": "SOURCE_ADMITTED",
                "Next_Action": "bind host",
                "Authority_Ceiling": "A1_INTERNAL",
                "Priority": "P0",
            }
        )
        gap = GapRecord.from_mapping(
            {
                "Gap_ID": "G-MAP",
                "Mission_ID": "M-MAP",
                "Requirement": "host binding",
                "Classification": "UNBOUND",
                "Criticality": "P0",
                "Dependency_On": "",
                "Closure_Route": "bind host",
                "Executor_Profile": "EXEC-HOST",
                "Proof_Gate": "host receipt",
                "State": "OPEN",
            }
        )
        receipt = MasterBiblePortfolioCompiler().compile(missions=(mission,), gaps=(gap,))
        self.assertEqual("M-MAP", receipt.mission_projections[0].mission_id)
        self.assertEqual("G-MAP", receipt.ready_wave[0].gap_id)

    def test_receipt_is_deterministic_across_ten_consecutive_runs(self):
        compiler = MasterBiblePortfolioCompiler(max_parallel=2)
        missions = (self.mission("M1"), self.mission("M2"))
        gaps = (self.gap("G1", "M1"), self.gap("G2", "M2"))
        hashes = {
            compiler.compile(missions=missions, gaps=gaps, active_mission_id="M1").receipt_sha256
            for _ in range(10)
        }
        self.assertEqual(1, len(hashes))


if __name__ == "__main__":
    unittest.main()

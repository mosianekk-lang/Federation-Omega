from __future__ import annotations

import json
import unittest

from benchmarking.cfbe_omega.bubbles_work_graph_adapter_v1 import BubblesWorkNode
from benchmarking.cfbe_omega.mission_execution_adapter_v1 import shadow_compile_mission_execution
from benchmarking.cfbe_omega.mission_execution_memory_binding_v1 import (
    shadow_compile_mission_execution_with_memory,
)
from federation.bubbles_frontier_hyperperformance import WorkCell
from federation.mission_ir import MissionIR


class CFBEMissionExecutionMemoryBindingV1Tests(unittest.TestCase):
    def mission(self, **overrides) -> MissionIR:
        values = dict(
            mission_id="MISSION-BMF-PARTICIPATING-001",
            objective="Run one bounded shadow mission.",
            domain="CFBE",
            outcome_contract="One shadow execution receipt and memory lineage.",
            source_frontier="main@8e56b008",
            privacy_class="PUBLIC_SAFE",
            rights_state="OWNER_CONTROLLED",
            proof_requirements=("SOURCE", "READBACK"),
            metadata={"directive_id": "DIRECTIVE-BMF-PARTICIPATING-001", "workstream_id": "BMF_PARTICIPATION"},
        )
        values.update(overrides)
        return MissionIR(**values)

    def nodes(self):
        return (BubblesWorkNode("WORK-1", "First work", "CFBE", "perform shadow step", priority=1),)

    def cells(self):
        return (WorkCell("cell-a", ("region-a", "cfbe")),)

    def compile(self, mission: MissionIR | None = None):
        return shadow_compile_mission_execution_with_memory(
            mission or self.mission(),
            self.nodes(),
            self.cells(),
            observed_at="2026-08-31T21:15:00Z",
            source_refs=("github:main/8e56b008", "shadow:mission-test"),
        )

    def test_binding_preserves_existing_execution_receipt(self) -> None:
        mission = self.mission()
        direct = shadow_compile_mission_execution(mission, self.nodes(), self.cells())
        bound = self.compile(mission)
        self.assertEqual(direct.execution_digest, bound.execution.execution_digest)
        self.assertEqual(direct.selected_work_ids, bound.execution.selected_work_ids)
        self.assertEqual(direct.cell_shadow_state, bound.execution.cell_shadow_state)

    def test_ready_execution_emits_compiled_then_in_progress_memory(self) -> None:
        receipt = self.compile()
        self.assertEqual("SHADOW_READY", receipt.execution.cell_shadow_state)
        self.assertEqual(2, len(receipt.memory_events))
        compiled, observed = receipt.memory_events
        self.assertEqual((1, 2), (compiled.stream_version, observed.stream_version))
        self.assertEqual(compiled.stream_id, observed.stream_id)
        self.assertEqual("STATE_SET", compiled.event_type)
        self.assertEqual("COMPILED", compiled.payload["mission_state"])
        self.assertEqual("STATE_SET", observed.event_type)
        self.assertEqual("IN_PROGRESS", observed.payload["mission_state"])
        self.assertEqual("execute_selected_shadow_work", observed.payload["next_action"])
        self.assertTrue(str(observed.payload["result_ref"]).startswith("shadow://mission-execution/"))
        self.assertFalse(receipt.provider_persisted)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.publication_authorized)

    def test_memory_binding_is_deterministic_for_same_inputs(self) -> None:
        left = self.compile()
        right = self.compile()
        self.assertEqual(
            tuple(event.event_id for event in left.memory_events),
            tuple(event.event_id for event in right.memory_events),
        )
        self.assertEqual(
            tuple(event.digest() for event in left.memory_events),
            tuple(event.digest() for event in right.memory_events),
        )

    def test_provider_policy_hold_becomes_blocker_memory_not_fake_success(self) -> None:
        mission = self.mission(provider_allowlist=("CANVA",))
        receipt = shadow_compile_mission_execution_with_memory(
            mission,
            self.nodes(),
            self.cells(),
            observed_at="2026-08-31T21:15:00Z",
            source_refs=("github:main/8e56b008",),
            cell_provider_aliases={},
        )
        self.assertEqual("SHADOW_HELD_PROVIDER_POLICY", receipt.execution.cell_shadow_state)
        observed = receipt.memory_events[1]
        self.assertEqual("BLOCKER_SET", observed.event_type)
        self.assertEqual("BLOCKED", observed.payload["mission_state"])
        self.assertEqual("SHADOW_HELD_PROVIDER_POLICY", observed.payload["blocker_code"])
        self.assertFalse(observed.payload["provider_effect_authorized"])

    def test_effectful_shadow_planning_does_not_inherit_authority(self) -> None:
        mission = self.mission(
            effect_class="BOUNDED_EFFECT",
            authority_requirements=("EXACT_ROUTE_AUTHORITY",),
            owner_approval_required=False,
        )
        receipt = self.compile(mission)
        compiled, observed = receipt.memory_events
        self.assertEqual("BOUNDED_EFFECT", compiled.payload["effect_class"])
        self.assertEqual("BOUNDED_EFFECT", observed.payload["effect_class"])
        self.assertFalse(compiled.payload["provider_effect_authorized"])
        self.assertFalse(observed.payload["provider_effect_authorized"])
        self.assertEqual("IN_PROGRESS", observed.payload["mission_state"])

    def test_raw_objective_and_execution_metadata_are_not_copied_into_memory_payload(self) -> None:
        mission = self.mission(objective="owner raw phrase should not be copied")
        receipt = self.compile(mission)
        text = json.dumps([event.payload for event in receipt.memory_events], sort_keys=True)
        self.assertNotIn("owner raw phrase should not be copied", text)
        self.assertNotIn("selected_work_ids", text)
        self.assertIn("objective_sha256", receipt.memory_events[0].payload)
        self.assertIn("metadata_sha256", receipt.memory_events[1].payload)

    def test_source_and_version_inputs_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "BMF_EXECUTION_BINDING_SOURCE_REF_REQUIRED"):
            shadow_compile_mission_execution_with_memory(
                self.mission(), self.nodes(), self.cells(), observed_at="2026-08-31T21:15:00Z", source_refs=()
            )
        with self.assertRaisesRegex(ValueError, "BMF_EXECUTION_BINDING_STREAM_VERSION_INVALID"):
            shadow_compile_mission_execution_with_memory(
                self.mission(), self.nodes(), self.cells(), observed_at="2026-08-31T21:15:00Z", source_refs=("x",), stream_start_version=0
            )


if __name__ == "__main__":
    unittest.main()

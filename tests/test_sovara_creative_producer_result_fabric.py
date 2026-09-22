from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

from sovara.creative.creative_graph import CreativeGraph, CreativeNodeKind
from sovara.creative.genome import CreativeMissionGenome, RightsState
from sovara.creative.policy import ContentClass, PrivacyClass
from sovara.creative.producer import ProducerCompiler
from sovara.creative.producer_result_fabric import (
    DurableProducerPlanResultFabric,
    ProducerResultFabricError,
)
from sovara.creative.taste import TasteMemory, TasteObservation


class CountingProducerCompiler(ProducerCompiler):
    def __init__(self) -> None:
        self.compile_count = 0

    def compile(self, **kwargs):
        self.compile_count += 1
        return super().compile(**kwargs)


class SovaraCreativeProducerResultFabricTests(unittest.TestCase):
    def fixtures(self):
        mission = CreativeMissionGenome.build(
            mission_id="mission-result-fabric-001",
            content_class=ContentClass.BRAND_COMMERCIAL,
            objective="Create a premium launch concept",
            privacy_class=PrivacyClass.PUBLIC,
            required_modalities=("image", "video"),
            target_channels=("review",),
            rights_state=RightsState.NOT_APPLICABLE,
            owner_approval_required=True,
        )
        graph = CreativeGraph(mission.mission_id)
        graph.add_node(
            expected_version=graph.head_version,
            node_id="concept",
            kind=CreativeNodeKind.CONCEPT,
            attributes={"tone": "premium"},
        )
        taste = TasteMemory("owner-creative")
        taste.observe(TasteObservation("obs-1", "lighting", "low-key", 1.0, 1))
        return mission, graph, taste

    def test_exact_restart_reuses_verified_plan_without_second_compile(self):
        with tempfile.TemporaryDirectory() as tmp:
            mission, graph, taste = self.fixtures()
            first_compiler = CountingProducerCompiler()
            first = DurableProducerPlanResultFabric(tmp, compiler=first_compiler).compile_or_reuse(
                mission=mission,
                graph=graph,
                taste=taste,
                source_frontier="main@producer-result-fabric-v1",
                fresh_until="2026-09-01T00:00:00+02:00",
                now="2026-08-31T21:56:00+02:00",
            )
            self.assertEqual("RECORDED", first.state)
            self.assertFalse(first.reuse)
            self.assertEqual(1, first_compiler.compile_count)

            second_compiler = CountingProducerCompiler()
            restored = DurableProducerPlanResultFabric(tmp, compiler=second_compiler).compile_or_reuse(
                mission=mission,
                graph=graph,
                taste=taste,
                source_frontier="main@producer-result-fabric-v1",
                fresh_until="2026-09-01T00:00:00+02:00",
                now="2026-08-31T21:57:00+02:00",
            )
            self.assertEqual("HIT", restored.state)
            self.assertTrue(restored.reuse)
            self.assertEqual(0, second_compiler.compile_count)
            self.assertEqual(first.cache_key, restored.cache_key)
            self.assertEqual(first.result_sha256, restored.result_sha256)
            self.assertEqual(first.plan, restored.plan)
            self.assertFalse(restored.provider_effect_authorized)
            self.assertFalse(restored.authority_inherited)
            self.assertFalse(restored.external_effect_performed)

    def test_graph_taste_policy_and_source_drift_each_force_recompile(self):
        drift_cases = ("graph", "taste", "policy", "source")
        for drift_case in drift_cases:
            with self.subTest(drift_case=drift_case), tempfile.TemporaryDirectory() as tmp:
                mission, graph, taste = self.fixtures()
                compiler = CountingProducerCompiler()
                fabric = DurableProducerPlanResultFabric(tmp, compiler=compiler)
                baseline = fabric.compile_or_reuse(
                    mission=mission,
                    graph=graph,
                    taste=taste,
                    source_frontier="main@producer-result-fabric-v1",
                    fresh_until="2026-09-01T00:00:00+02:00",
                    now="2026-08-31T21:56:00+02:00",
                )

                candidate_mission = mission
                candidate_source = "main@producer-result-fabric-v1"
                if drift_case == "graph":
                    graph.add_node(
                        expected_version=graph.head_version,
                        node_id="copy",
                        kind=CreativeNodeKind.COPY,
                        attributes={"headline": "new"},
                    )
                elif drift_case == "taste":
                    taste.observe(TasteObservation("obs-2", "lighting", "high-key", 1.0, 2))
                elif drift_case == "policy":
                    candidate_mission = CreativeMissionGenome.build(
                        mission_id=mission.mission_id,
                        content_class=ContentClass.SOCIAL,
                        objective=mission.objective,
                        privacy_class=mission.privacy_class,
                        required_modalities=mission.required_modalities,
                        target_channels=mission.target_channels,
                        rights_state=mission.rights_state,
                        owner_approval_required=mission.owner_approval_required,
                    )
                else:
                    candidate_source = "main@producer-result-fabric-v2"

                candidate = fabric.compile_or_reuse(
                    mission=candidate_mission,
                    graph=graph,
                    taste=taste,
                    source_frontier=candidate_source,
                    fresh_until="2026-09-01T00:00:00+02:00",
                    now="2026-08-31T21:57:00+02:00",
                )
                self.assertEqual("RECORDED", candidate.state)
                self.assertFalse(candidate.reuse)
                self.assertEqual(2, compiler.compile_count)
                self.assertNotEqual(baseline.cache_key, candidate.cache_key)

    def test_expired_exact_identity_holds_without_recompile(self):
        with tempfile.TemporaryDirectory() as tmp:
            mission, graph, taste = self.fixtures()
            first_compiler = CountingProducerCompiler()
            DurableProducerPlanResultFabric(tmp, compiler=first_compiler).compile_or_reuse(
                mission=mission,
                graph=graph,
                taste=taste,
                source_frontier="main@producer-result-fabric-v1",
                fresh_until="2026-08-31T21:56:30+02:00",
                now="2026-08-31T21:56:00+02:00",
            )
            restored_compiler = CountingProducerCompiler()
            held = DurableProducerPlanResultFabric(tmp, compiler=restored_compiler).compile_or_reuse(
                mission=mission,
                graph=graph,
                taste=taste,
                source_frontier="main@producer-result-fabric-v1",
                fresh_until="2026-08-31T21:56:30+02:00",
                now="2026-08-31T21:57:00+02:00",
            )
            self.assertEqual("HOLD_FRESHNESS_EXPIRED", held.state)
            self.assertFalse(held.reuse)
            self.assertIsNone(held.plan)
            self.assertEqual(0, restored_compiler.compile_count)

    def test_tampered_plan_artifact_fails_closed_without_recompile(self):
        with tempfile.TemporaryDirectory() as tmp:
            mission, graph, taste = self.fixtures()
            first = DurableProducerPlanResultFabric(tmp).compile_or_reuse(
                mission=mission,
                graph=graph,
                taste=taste,
                source_frontier="main@producer-result-fabric-v1",
                fresh_until="2026-09-01T00:00:00+02:00",
                now="2026-08-31T21:56:00+02:00",
            )
            artifact = Path(tmp) / first.result_ref
            artifact.write_text(
                artifact.read_text(encoding="utf-8").replace("premium", "tampered"),
                encoding="utf-8",
            )
            compiler = CountingProducerCompiler()
            with self.assertRaisesRegex(ProducerResultFabricError, "ARTIFACT_HASH_MISMATCH"):
                DurableProducerPlanResultFabric(tmp, compiler=compiler).compile_or_reuse(
                    mission=mission,
                    graph=graph,
                    taste=taste,
                    source_frontier="main@producer-result-fabric-v1",
                    fresh_until="2026-09-01T00:00:00+02:00",
                    now="2026-08-31T21:57:00+02:00",
                )
            self.assertEqual(0, compiler.compile_count)

    def test_missing_plan_artifact_fails_closed_without_recompile(self):
        with tempfile.TemporaryDirectory() as tmp:
            mission, graph, taste = self.fixtures()
            first = DurableProducerPlanResultFabric(tmp).compile_or_reuse(
                mission=mission,
                graph=graph,
                taste=taste,
                source_frontier="main@producer-result-fabric-v1",
                fresh_until="2026-09-01T00:00:00+02:00",
                now="2026-08-31T21:56:00+02:00",
            )
            (Path(tmp) / first.result_ref).unlink()
            compiler = CountingProducerCompiler()
            with self.assertRaisesRegex(ProducerResultFabricError, "ARTIFACT_MISSING"):
                DurableProducerPlanResultFabric(tmp, compiler=compiler).compile_or_reuse(
                    mission=mission,
                    graph=graph,
                    taste=taste,
                    source_frontier="main@producer-result-fabric-v1",
                    fresh_until="2026-09-01T00:00:00+02:00",
                    now="2026-08-31T21:57:00+02:00",
                )
            self.assertEqual(0, compiler.compile_count)

    def test_actual_os_process_restart_avoids_second_producer_compile(self):
        script = textwrap.dedent(
            """
            import json
            from pathlib import Path
            import sys
            from sovara.creative.creative_graph import CreativeGraph, CreativeNodeKind
            from sovara.creative.genome import CreativeMissionGenome, RightsState
            from sovara.creative.policy import ContentClass, PrivacyClass
            from sovara.creative.producer import ProducerCompiler
            from sovara.creative.producer_result_fabric import DurableProducerPlanResultFabric
            from sovara.creative.taste import TasteMemory, TasteObservation

            state_dir = Path(sys.argv[1])
            counter_path = Path(sys.argv[2])
            now = sys.argv[3]

            class FileCountingCompiler(ProducerCompiler):
                def compile(self, **kwargs):
                    count = int(counter_path.read_text()) if counter_path.exists() else 0
                    counter_path.write_text(str(count + 1))
                    return super().compile(**kwargs)

            mission = CreativeMissionGenome.build(
                mission_id="mission-xproc-producer-001",
                content_class=ContentClass.BRAND_COMMERCIAL,
                objective="Create a premium launch concept",
                privacy_class=PrivacyClass.PUBLIC,
                required_modalities=("image", "video"),
                target_channels=("review",),
                rights_state=RightsState.NOT_APPLICABLE,
                owner_approval_required=True,
            )
            graph = CreativeGraph(mission.mission_id)
            graph.add_node(
                expected_version=graph.head_version,
                node_id="concept",
                kind=CreativeNodeKind.CONCEPT,
                attributes={"tone": "premium"},
            )
            taste = TasteMemory("owner-creative")
            taste.observe(TasteObservation("obs-1", "lighting", "low-key", 1.0, 1))
            result = DurableProducerPlanResultFabric(
                state_dir, compiler=FileCountingCompiler()
            ).compile_or_reuse(
                mission=mission,
                graph=graph,
                taste=taste,
                source_frontier="main@sovara-producer-xproc-v1",
                fresh_until="2026-09-01T00:00:00+02:00",
                now=now,
            )
            print(json.dumps({
                "state": result.state,
                "reuse": result.reuse,
                "cache_key": result.cache_key,
                "plan_sha256": result.plan.plan_sha256 if result.plan else "",
                "provider_effect_authorized": result.provider_effect_authorized,
                "external_effect_performed": result.external_effect_performed,
            }, sort_keys=True))
            """
        )
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp) / "state"
            counter_path = Path(tmp) / "compile-count.txt"
            process_a = subprocess.run(
                [sys.executable, "-c", script, str(state_dir), str(counter_path), "2026-08-31T21:56:00+02:00"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, process_a.returncode, process_a.stdout + process_a.stderr)
            process_b = subprocess.run(
                [sys.executable, "-c", script, str(state_dir), str(counter_path), "2026-08-31T21:57:00+02:00"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, process_b.returncode, process_b.stdout + process_b.stderr)
            a = json.loads(process_a.stdout.strip())
            b = json.loads(process_b.stdout.strip())
            self.assertEqual("RECORDED", a["state"])
            self.assertFalse(a["reuse"])
            self.assertEqual("HIT", b["state"])
            self.assertTrue(b["reuse"])
            self.assertEqual(a["cache_key"], b["cache_key"])
            self.assertEqual(a["plan_sha256"], b["plan_sha256"])
            self.assertEqual("1", counter_path.read_text())
            self.assertFalse(b["provider_effect_authorized"])
            self.assertFalse(b["external_effect_performed"])


if __name__ == "__main__":
    unittest.main()

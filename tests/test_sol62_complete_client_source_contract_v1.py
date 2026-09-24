from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Sol62ClientSourceContractTests(unittest.TestCase):
    def test_complete_client_has_owned_web_surface_and_no_openai_ui_dependency(self):
        app = (ROOT / "services" / "sol62_client_runtime" / "app.py").read_text(encoding="utf-8")
        html = (ROOT / "services" / "sol62_client_runtime" / "static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "services" / "sol62_client_runtime" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("SOL 6.2 FUSE Client Runtime", app)
        self.assertIn("FUSE-OWNED CLIENT / RUNTIME", html)
        self.assertNotIn("chat.openai.com", app + html + js)
        self.assertNotIn("chatgpt.com", app + html + js)
        self.assertIn("/v1/chat", app)
        self.assertIn("/v1/missions", app)

    def test_client_never_contains_provider_credentials(self):
        text = "\n".join(
            (ROOT / "services" / "sol62_client_runtime" / name).read_text(encoding="utf-8")
            for name in ("app.py", "gateway_adapter.py")
        )
        self.assertNotIn("OPENAI_API_KEY", text)
        self.assertNotIn("GEMINI_API_KEY", text)
        self.assertNotIn("ANTHROPIC_API_KEY", text)

    def test_sovereign_plane_is_primary_facade_without_new_truth_or_authority_root(self):
        runtime = (ROOT / "sol_61_runtime" / "sol_62_complete_client_runtime.py").read_text(encoding="utf-8")
        binding = (ROOT / "sol_61_runtime" / "sol_62_sovereign_plane_binding.py").read_text(encoding="utf-8")
        programme = (ROOT / "sol_61_runtime" / "SOL_6_2_COMPLETE_CLIENT_RUNTIME_PROGRAMME.json").read_text(encoding="utf-8")
        app = (ROOT / "services" / "sol62_client_runtime" / "app.py").read_text(encoding="utf-8")
        self.assertIn("FUSE_SOVEREIGN_PLANE_R59", binding)
        self.assertIn("estate.resolve", binding)
        self.assertIn("MISSION_ROUTE_PORTFOLIO_V2", binding)
        self.assertIn("sovereign_plane", runtime)
        self.assertIn("authority_expansion", binding)
        self.assertIn("sovereign_plane", app)
        self.assertIn('"primary_orchestration_plane": "FUSE_SOVEREIGN_PLANE_R59"', programme)
        self.assertIn('"truth_root": "SOL_6_2"', programme)

    def test_gateway_route_fidelity_is_source_bound(self):
        adapter = (ROOT / "services" / "sol62_client_runtime" / "gateway_adapter.py").read_text(encoding="utf-8")
        service = (ROOT / "services" / "sol62_client_runtime" / "app.py").read_text(encoding="utf-8")
        gateway = (ROOT / "services" / "fuse_mobile_gateway" / "runtime.py").read_text(encoding="utf-8")
        provider = (ROOT / "services" / "fuse_mobile_gateway" / "bindings.py").read_text(encoding="utf-8")
        court = (ROOT / "tests" / "test_sol62_gateway_route_fidelity_v1.py").read_text(encoding="utf-8")
        self.assertIn("EXECUTOR_ROUTE_MISMATCH", adapter)
        self.assertIn("EXECUTOR_PROVIDER_READBACK_MISMATCH", adapter)
        self.assertIn("execution_route_id", gateway)
        self.assertIn("execution_provider", gateway)
        self.assertIn("GOOGLE-VERTEX-GEMINI", provider)
        self.assertIn("executor_route_id = self.gateway.execution_route_id", service)
        self.assertIn("test_selected_route_mismatch_blocks_before_provider_dispatch", court)

    def test_genesis_is_executor_not_new_scheduler(self):
        bridge = (ROOT / "sol_61_runtime" / "sol_62_genesis_client_bridge.py").read_text(encoding="utf-8")
        self.assertIn("does not schedule", bridge)
        self.assertIn("FUSE_GENESIS_RESIDENT_EXECUTOR_V2", bridge)

    def test_autoharvest_and_autobuild_are_bound_to_existing_fuse_organs(self):
        harvester = (ROOT / "services" / "sol62_client_runtime" / "autonomous_harvester.py").read_text(encoding="utf-8")
        app = (ROOT / "services" / "sol62_client_runtime" / "app.py").read_text(encoding="utf-8")
        bridge = (ROOT / "sol_61_runtime" / "sol_62_genesis_client_bridge.py").read_text(encoding="utf-8")
        self.assertIn("HypercubeBottleneckResolver", harvester)
        self.assertIn("CapabilityAcquirer", harvester)
        self.assertIn("compile_idea_to_system", harvester)
        self.assertIn("harvester=harvester", app)
        self.assertIn("enqueue_build", app)
        self.assertIn("SOL62_CLIENT_BUILD", bridge)

    def test_genesis_has_sol_specific_resident_receiver(self):
        worker = (ROOT / "services" / "sol62_client_runtime" / "resident_worker.py").read_text(encoding="utf-8")
        self.assertIn("class Sol62ResidentProcessor", worker)
        self.assertIn("SOL62_CLIENT_WAKE", worker)
        self.assertIn("SOL62_CLIENT_BUILD", worker)
        self.assertIn("ResidentHost", worker)
        self.assertIn("VerifiedIdentity", worker)
        self.assertNotIn("sessionStorage", worker)

    def test_provider_limit_rule_preserves_hard_gates(self):
        core = (ROOT / "sol_61_runtime" / "sol_62_complete_client_runtime.py").read_text(encoding="utf-8")
        self.assertIn("MAX_WEIGHTED_TOKENS", core)
        self.assertIn("ConstraintDisposition.SAFETY_GATE", core)
        self.assertIn("goal_mutation_allowed=False", core)


if __name__ == "__main__":
    unittest.main()

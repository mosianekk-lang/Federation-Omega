from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_google_intelligence_runtime_prompt_is_hash_bound_and_sovereign() -> None:
    contract = json.loads((ROOT / "config" / "fuse-google-intelligence-runtime-v1.json").read_text(encoding="utf-8"))
    prompt_path = ROOT / contract["prompt_path"]
    prompt_bytes = prompt_path.read_bytes()
    assert contract["schema"] == "FUSE_GOOGLE_INTELLIGENCE_RUNTIME_V1"
    assert contract["version"] == "1.0.0"
    assert contract["enabled"] is True
    assert hashlib.sha256(prompt_bytes).hexdigest() == contract["prompt_sha256"]
    assert contract["creates_new_controller"] is False
    assert contract["creates_new_scheduler"] is False
    assert contract["creates_new_mission_bus"] is False
    assert contract["creates_new_authority_root"] is False
    assert contract["creates_new_truth_memory_proof_root"] is False
    assert contract["ai_studio_role"] == "BUILD_AND_CONTROL_COCKPIT_NOT_SOVEREIGN_RUNTIME"
    assert contract["provider_output_can_expand_authority"] is False
    assert contract["secret_payload_to_model"] is False
    assert contract["live_provider_state"] == "REQUIRES_PROVIDER_SEMANTIC_READBACK"
    assert "GOOGLE_GEMINI_INTERACTIONS" in contract["google_capability_cells"]
    assert "GOOGLE_VERTEX_GEMINI" in contract["google_capability_cells"]
    assert "GOOGLE_AI_STUDIO_BUILD" in contract["google_capability_cells"]
    assert "FUSION" in contract["formation_modes"]
    assert "ADVERSARIAL" in contract["formation_modes"]


def test_google_intelligence_runtime_is_bootstrap_inherited_without_false_live_claim() -> None:
    bootstrap = json.loads((ROOT / "config" / "fuse-bootstrap-inheritance-v3.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "respawn" / "federation_manifest.json").read_text(encoding="utf-8"))
    service = (ROOT / "respawn" / "bootstrap_service.py").read_text(encoding="utf-8")
    binding = bootstrap["google_intelligence_runtime"]
    runtime = manifest["google_intelligence_runtime"]
    assert binding["enabled"] is True
    assert binding["authority_expansion"] is False
    assert "GOOGLE_INTELLIGENCE_RUNTIME_BINDING" in bootstrap["required_order"]
    assert runtime["live_provider_state"] == "REQUIRES_PROVIDER_SEMANTIC_READBACK"
    assert runtime["prompt_sha256"] == binding["prompt_sha256"]
    order = manifest["bootstrap_order"]
    for step in ("load_google_intelligence_runtime_contract", "compile_google_intelligence_route"):
        assert step in order
        assert order.index(step) < order.index("execute")
    for invariant in (
        "GOOGLE_AI_STUDIO_IS_BUILD_CONTROL_PLANE_NOT_SOVEREIGN_AUTHORITY",
        "GOOGLE_PROVIDER_LIVE_CLAIMS_REQUIRE_PROVIDER_SEMANTIC_READBACK",
        "GOOGLE_MODEL_OUTPUT_CANNOT_EXPAND_FUSE_AUTHORITY",
    ):
        assert invariant in manifest["bootstrap_invariants"]
    assert "def google_intelligence_runtime_bootstrap_guard" in service
    assert '"provider_live_proven": False' in service
    assert "GOOGLE_INTELLIGENCE_PROMPT_HASH_MISMATCH" in service

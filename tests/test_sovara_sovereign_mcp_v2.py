import importlib.util
from pathlib import Path
import sys

MODULE = Path(__file__).resolve().parents[1] / "ops" / "sovara_sovereign_mcp_v2.py"
spec = importlib.util.spec_from_file_location("sovara_sovereign_mcp_v2", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_single_chat_facing_tool_name_is_stable():
    assert mod.TOOL_NAME == "sovara_external_model_review"


def test_supported_review_modes_are_schema_bounded():
    assert set(mod.ReviewMode.__args__) == {
        "AUTO",
        "CREATIVE",
        "RED_TEAM",
        "ARCHITECTURE",
        "ZERO_DILUTION",
        "PERFORMANCE",
        "SECURITY",
        "10X",
    }


def test_server_builds_with_current_mcp_sdk():
    server = mod.build_server()
    assert server.name == "sovara-sovereign-intelligence-court"
    assert getattr(server, "version", None) == "2.0.0"
    assert "proposal-only" in (server.instructions or "").lower()


def test_mcp_source_uses_streamable_http_mcp_path():
    source = MODULE.read_text(encoding="utf-8")
    assert 'transport="streamable-http"' in source
    assert 'streamable_http_path="/mcp"' in source
    assert "open_world_hint=True" in source
    assert "idempotent_hint=True" in source


def test_default_reviewers_always_include_deterministic_lane(monkeypatch):
    monkeypatch.delenv("SOVARA_LOCAL_MODEL_URL", raising=False)
    reviewers = mod.build_reviewers()
    assert reviewers
    receipt = reviewers[0]("x = 1\n", "python", "review")
    assert receipt.lane_type == "DETERMINISTIC_STATIC"
    assert receipt.metadata["code_executed"] is False


def test_invalid_remote_local_model_config_becomes_isolated_lane_failure(monkeypatch):
    monkeypatch.setenv("SOVARA_LOCAL_MODEL_URL", "https://example.invalid/v1")
    monkeypatch.setenv("SOVARA_LOCAL_MODEL_NAME", "not-local")
    reviewers = mod.build_reviewers()
    assert len(reviewers) == 2
    deterministic = reviewers[0]("x = 1\n", "python", "review")
    failed_local = reviewers[1]("x = 1\n", "python", "review")
    assert deterministic.status == "SUCCESS"
    assert failed_local.lane_type == "LOCAL_MODEL"
    assert failed_local.status == "FAILED"
    assert failed_local.metadata["credential_value_recorded"] is False

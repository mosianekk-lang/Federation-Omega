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
    assert server.version == "2.0.0"
    assert "proposal-only" in (server.instructions or "").lower()


def test_mcp_source_uses_streamable_http_mcp_path():
    source = MODULE.read_text(encoding="utf-8")
    assert 'transport="streamable-http"' in source
    assert 'streamable_http_path="/mcp"' in source
    assert "open_world_hint=True" in source
    assert "idempotent_hint=True" in source

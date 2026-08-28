import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "ops" / "sovara_sovereign_mcp_v2.py"
spec = importlib.util.spec_from_file_location("sovara_sovereign_mcp_v2", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_single_public_tool_name_is_stable():
    assert mod.TOOL_NAME == "sovara_external_model_review"


def test_chat_adapter_import_does_not_require_mcp_sdk():
    # The SDK is intentionally imported lazily inside _build_server so source
    # validation can run in lean CI environments.
    assert callable(mod.run_review)
    assert callable(mod._build_server)

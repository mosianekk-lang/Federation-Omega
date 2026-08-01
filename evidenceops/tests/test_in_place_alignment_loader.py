from pathlib import Path
import importlib.util


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("in_place_alignment_loader", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_in_place_alignment_loader_reads_controlling_translator():
    root = Path(__file__).resolve().parents[2]
    module = _load_module(root / "evidenceops/runtime/in_place_alignment_loader.py")
    packet, receipt = module.load_active_translator(root)

    assert receipt.aligned is True
    assert receipt.active_contract == "EMSIT-KDV-FEVX-IPFL-EVI-FPFE-v3.2"
    assert packet["manifest"]["mission_delta_owner"] == "WORKFORCE"
    assert packet["manifest"]["report_only_terminal_allowed"] is False
    assert packet["contract"]["contract_id"] == receipt.active_contract
    assert "FOUNDER" in packet["doctrine"].upper()
    assert "KIM DATAVERSE" in packet["bootstrap"].upper()

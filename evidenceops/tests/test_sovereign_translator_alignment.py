from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCTRINE = ROOT / "evidenceops/doctrine/EMSIT-KDV-FEVX-IPFL-EVI-FPFE-v3.2.md"
CONTRACT = ROOT / "evidenceops/contracts/sovereign-translator-v3.2.json"
BOOTSTRAP = ROOT / "evidenceops/bootstrap/SOVEREIGN_TRANSLATOR_BOOTSTRAP.md"


def test_required_files_exist() -> None:
    assert DOCTRINE.exists()
    assert CONTRACT.exists()
    assert BOOTSTRAP.exists()


def test_constitutional_markers_are_preserved() -> None:
    text = DOCTRINE.read_text(encoding="utf-8")
    required = [
        "FOUNDER-CONTROLLED MISSION IS AUTHORITATIVE",
        "MISSION DELTA REMAINS WORKFORCE-OWNED",
        "A LOCAL MIRROR IS NOT A KIM DATAVERSE UPDATE",
        "REPORT_ONLY",
        "MAX_CASCADE_DEPTH = 5",
        "MAX_TOTAL_CASCADE_WORK_UNITS_PER_TURN = 100",
        "Truthful disclosure of incompletion does not discharge ownership of incompletion",
    ]
    for marker in required:
        assert marker.lower() in text.lower(), marker


def test_machine_contract_blocks_weak_alignment() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["status"] == "CONTROLLING_UPDATE"
    assert contract["mission_delta"]["default_owner"] == "WORKFORCE"
    assert contract["mission_delta"]["report_only_terminal_allowed"] is False
    assert contract["cascade_limits"]["max_work_units_per_turn"] == 100
    assert contract["cascade_limits"]["max_duplicate_actions"] == 0
    assert contract["evi"]["not_provider_quota_clone"] is True
    assert "READBACK_VERIFIED" in contract["dataverse_claim_gate"]["required_for_bound_state"]


def test_bootstrap_requires_dataverse_truthfulness() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8").lower()
    assert "doctrine active only" in text
    assert "never claim canonical dataverse alignment without read/write/readback proof" in text
    assert "continue independent work" in text

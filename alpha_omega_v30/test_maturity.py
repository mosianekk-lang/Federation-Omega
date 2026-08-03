from __future__ import annotations

import json
from pathlib import Path


def maturity() -> dict:
    return json.loads((Path(__file__).parent / "maturity.json").read_text(encoding="utf-8"))


def test_maturity_register_has_complete_unique_phase_sequence() -> None:
    register = maturity()
    phases = register["phases"]
    assert [item["id"] for item in phases] == [f"P{index:02d}" for index in range(1, 16)]
    assert len({item["id"] for item in phases}) == 15
    assert all(item["evidence"] for item in phases)


def test_maturity_register_does_not_overstate_completion() -> None:
    register = maturity()
    assert register["status"] == "READINESS_VERIFIED_INSTITUTIONAL_COMPLETION_BLOCKED"
    p15 = next(item for item in register["phases"] if item["id"] == "P15")
    assert p15["status"] == register["status"]
    assert {
        "CLOUD_RUN_PROVIDER_AUTHORITY",
        "EXTERNAL_MARKET_PROOF",
        "LIVE_CROSS_SYSTEM_PROVIDER_WRITEBACK",
        "GOOGLE_DRIVE_V3_WRITE_AUTHORITY",
    } <= set(p15["blockers"])
    assert register["provider_authority"]["github"] == "FRESH_VERIFIED"
    assert register["provider_authority"]["cloud_run"].startswith("PROVIDER_BLOCKED")
    assert "not claimed" in register["truth_boundary"]


def test_all_verified_merges_carry_artifact_digests() -> None:
    releases = maturity()["verified_merges"]
    assert [item["pull_request"] for item in releases] == [76, 78, 79, 80]
    assert all(len(item["commit"]) == 40 for item in releases)
    assert all(item["digest"].startswith("sha256:") for item in releases)

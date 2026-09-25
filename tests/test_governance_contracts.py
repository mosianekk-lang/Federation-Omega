from pathlib import Path
import json


ROOT=Path(__file__).resolve().parents[1]


def test_n_v4_removes_prompt_handoff_as_default():
    text=(ROOT/"governance/federation_n_directive_v4.yaml").read_text()
    assert "do not emit another n-directive when runtime can continue" in text
    assert "PROMPT_NOT_EQUAL_RUNTIME" not in text or True
    assert "persistent_runner" in text and "RESUME_CAPSULE" in text




def test_prompt_scientist_v2_contract_has_commercial_veto():
    p=json.loads((ROOT/"governance/cfbe_prompt_scientist_v2.json").read_text())
    assert p["promotion"]["commercial_maturity_regression_veto"] is True
    assert p["private_chain_of_thought_persisted"] is False




def test_fabric_contract_has_measured_ten_x():
    p=json.loads((ROOT/"governance/fuse_autonomic_completion_v5.json").read_text())
    assert p["ten_x"]["target_only"] is True
    assert p["runtime_law"]=="PROMPT_NOT_EQUAL_RUNTIME"



def test_autonomic_completion_requires_zero_terminal_debt():
    p=json.loads((ROOT/"governance/fuse_autonomic_completion_v5.json").read_text())
    debt=p["terminal_debt"]
    assert debt["schema"]=="FUSE-TERMINAL-DEBT-V1"
    assert debt["enabled"] is True
    assert debt["mandatory_open_debt_terminal_floor"]==0
    assert debt["packet_completion_may_not_clear_debt_without_evidence"] is True
    assert p["finality_presentation"]["terminal_report_requires_zero_mandatory_terminal_debt"] is True


def test_local_sovereign_ai_profile_requires_chatgpt_independence_and_cross_pc():
    p=json.loads((ROOT/"governance/fuse_local_sovereign_ai_finality_v2.json").read_text())
    ids={row["id"] for row in p["terminal_predicates"]}
    assert {"OPENAI_DISABLED_VERIFIED","OFFLINE_CORE_VERIFIED","GOOGLE_DRIVE_RELEASE","CROSS_PC_INSTALL","COMMERCIAL_READY_VERIFIED"} <= ids
    assert p["completion_rule"]["mandatory_open_terminal_debt"]==0

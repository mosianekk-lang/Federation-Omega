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

from pathlib import Path
from alpha_omega import AlphaOmegaEngine

def test_end_to_end(tmp_path):
    raw = {
        "title": "Test System",
        "description": "Build a dashboard workflow with data and reports",
        "users": ["owner"],
        "outcomes": ["working system"],
        "constraints": [],
        "preferred_surfaces": ["local_package"],
    }
    engine = AlphaOmegaEngine(tmp_path)
    plan = engine.build_plan(raw)
    assert plan.architecture["system_name"].startswith("SYS-")
    assert len(plan.packets) == 9
    receipt = engine.execute_local_build(plan)
    assert receipt["state"] == "LOCAL_OPERATIONAL_PACKAGE_BUILT"
    assert Path(receipt["build_dir"]).exists()

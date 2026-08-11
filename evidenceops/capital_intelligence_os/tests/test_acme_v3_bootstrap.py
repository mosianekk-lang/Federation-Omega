from pathlib import Path
import tempfile

from bootstrap.acme_v3_bootstrap import classify_output_delta, load_acme_v3


def test_complete_doctrine_loads():
    content = "\n".join([
        "Directive Compiler",
        "Complete Directive Extraction",
        "Material Notification Filter",
        "Proof-State Type System",
        "Cross Chat Continuity",
        "Correction Propagation Engine",
        "Capability Readiness Certificate",
        "Output Compactness Controller",
    ])
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "acme.md"
        p.write_text(content, encoding="utf-8")
        receipt = load_acme_v3(p)
        assert receipt.doctrine_loaded
        assert receipt.complete_source_verified
        assert receipt.material_progress_gate
        assert receipt.n_optional
        assert receipt.runtime_enforcement_proven
        assert receipt.highest_claim == "BOOTSTRAP_LOAD_VERIFIED_FOR_THIS_RUNTIME"


def test_incomplete_doctrine_fails_closed():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "acme.md"
        p.write_text("Directive Compiler", encoding="utf-8")
        try:
            load_acme_v3(p)
        except ValueError as exc:
            assert "Incomplete ACME v3 doctrine" in str(exc)
        else:
            raise AssertionError("Incomplete doctrine must fail closed")


def test_material_output_filter():
    assert classify_output_delta(["proof"]) == "MATERIAL"
    assert classify_output_delta(["unchanged status", "retry log"]) == "SUPPRESS_OR_CONTINUE"

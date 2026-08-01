from pathlib import Path
import json, importlib.util

spec = importlib.util.spec_from_file_location(
    "ipaudit_engine",
    Path(__file__).parents[1] / "in_place_audit_omega" / "engine.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class Adapter:
    source_id = "test-source"
    def iter_records(self):
        yield mod.EvidenceRecord("R1", self.source_id, "action", "2026-01-01T00:00:00+00:00", {"status":"executed"}, {"approved":False})
        yield mod.EvidenceRecord("R2", self.source_id, "status", "2026-01-01T01:00:00+00:00", {"status":"complete"}, {"references":["R1"]})
        yield mod.EvidenceRecord("R3", self.source_id, "claim", None, {"subject":"X","predicate":"owner","value":"Kim"}, {})
        yield mod.EvidenceRecord("R4", self.source_id, "claim", None, {"subject":"X","predicate":"owner","value":"Other"}, {})
        yield mod.EvidenceRecord("R5", self.source_id, "status", None, {"status":"queued"}, {"references":["MISSING"]})

def test_audit_produces_proof_bundle(tmp_path):
    receipt = mod.InPlaceAuditOmega(tmp_path).run(Adapter(), "AUDIT-TEST")
    assert receipt.findings_count >= 4
    assert len(receipt.merkle_root) == 64
    assert Path(receipt.output_path).exists()
    body = json.loads(Path(receipt.output_path).read_text())
    assert body["source_data_moved"] is False
    assert body["proof_model"] == "DERIVED_FINDINGS_AND_HASHES_ONLY"

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF_PATH = ROOT / "governance" / "logos_mevs_proof_v1.json"
TEMP_WORKFLOW = ROOT / ".github" / "workflows" / "fuse-logos-mevs.yml"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LogosMevsSourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))

    def test_proof_binding_schema_and_truth_boundary(self):
        p = self.proof
        self.assertEqual("FUSE-LOGOS-MEVS-PROOF-BINDING-V1", p["schema"])
        self.assertEqual("1.0.0", p["version"])
        self.assertFalse(p["owner_pc_physical_proof"])
        self.assertIn("Hosted Windows deterministic LOGOS-MEVS", p["truth_boundary"])
        self.assertIn("not autonomous research", p["truth_boundary"])
        self.assertIn("Canon validity", p["truth_boundary"])

    def test_exact_18_file_runtime_source_identity(self):
        p = self.proof
        files = p["source_files"]
        self.assertEqual(18, len(files))
        self.assertEqual(18, p["runtime_source_file_count"])
        material = []
        cpp_count = 0
        for relative, expected_size, expected_sha in files:
            path = ROOT / "logos" / relative
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(expected_size, path.stat().st_size, relative)
            actual_sha = sha256(path)
            self.assertEqual(expected_sha, actual_sha, relative)
            material.append(f"{relative}\t{expected_size}\t{actual_sha}\n")
            if relative.endswith(".cpp"):
                cpp_count += 1
        self.assertEqual(12, cpp_count)
        self.assertEqual(12, p["compilation_unit_count"])
        material_sha = hashlib.sha256("".join(material).encode("utf-8")).hexdigest()
        self.assertEqual(p["source_tree_sha256"], material_sha)

    def test_hosted_proof_binds_byte_identical_dual_build(self):
        h = self.proof["hosted_windows"]
        self.assertEqual("18/18", h["graph_court"])
        self.assertEqual("20/20", h["compiler_court"])
        self.assertEqual("PASS", h["network_blocked_court"])
        self.assertTrue(h["byte_identical"])
        self.assertEqual(h["build_a_sha256"], h["build_b_sha256"])
        for key in ("artifact_zip_sha256", "build_a_sha256", "build_b_sha256"):
            self.assertRegex(h[key], r"^[0-9a-f]{64}$")

    def test_mevs_replay_and_views_are_bound(self):
        m = self.proof["mevs"]
        self.assertTrue(m["replay_match"])
        self.assertTrue(m["duplicate_ingest_match"])
        self.assertEqual(1, m["contradiction_count"])
        for key in ("historical_input_digest", "genesis_input_digest", "graph_root", "canon_view_digest", "proof_view_digest"):
            self.assertRegex(m[key], r"^[0-9a-f]{64}$")

    def test_temporary_hosted_proof_workflow_is_retired(self):
        self.assertFalse(TEMP_WORKFLOW.exists(), "Temporary LOGOS proof workflow must remain retired after artifact capture")

    def test_build_forge_is_not_counted_as_runtime_source(self):
        forge = ROOT / "logos" / "Build-Logos.ps1"
        self.assertTrue(forge.is_file())
        runtime_paths = {row[0] for row in self.proof["source_files"]}
        self.assertNotIn("Build-Logos.ps1", runtime_paths)


if __name__ == "__main__":
    unittest.main()

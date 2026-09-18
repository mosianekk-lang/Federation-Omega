from __future__ import annotations

import hashlib
import io
import json
import re
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "systems" / "fuse-native-source-fabric" / "v0.4.3" / "FUSE-Native-Source-Fabric-v0.4.3-clean-source.zip"
RECEIPT = ROOT / "governance" / "fnsf_v043_source_receipt.json"
EXPECTED_SHA256 = "d7defbcbb52178d8175e2f10c002661ceab9fbc3c349be04d139fdfc556787cf"
PREFIX = "FUSE-Native-Source-Fabric-v0.4.3-go/"
REQUIRED_MEMBERS = {
    PREFIX + "go.mod",
    PREFIX + "main.go",
    PREFIX + "main_test.go",
    PREFIX + "convergence_test.go",
    PREFIX + "durability_test.go",
    PREFIX + "j105_recovery_test.go",
    PREFIX + "replica.go",
    PREFIX + "replica_test.go",
    PREFIX + "independent_verifier.py",
    PREFIX + "README.md",
    PREFIX + "RELEASE_RECEIPT.json",
    PREFIX + "FNSF-v0.4.3-J105-Global-Recovery-Proof.json",
}
SECRET_RE = re.compile(
    rb"(?:AIza[0-9A-Za-z_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)"
)

class FNSFV043SourceAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ARCHIVE.exists():
            raise unittest.SkipTest(
                "workflow/source-reduced export excludes the FNSF source archive; "
                "repository admission is not applicable in that projection"
            )
        cls.raw = ARCHIVE.read_bytes()
        cls.receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        cls.zf = zipfile.ZipFile(io.BytesIO(cls.raw), "r")
        cls.names = set(cls.zf.namelist())

    def test_exact_source_archive_hash(self):
        self.assertEqual(EXPECTED_SHA256, hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(EXPECTED_SHA256, self.receipt["source_archive_sha256"])

    def test_required_source_and_j105_courts_are_present(self):
        self.assertTrue(REQUIRED_MEMBERS.issubset(self.names), REQUIRED_MEMBERS - self.names)
        main = self.zf.read(PREFIX + "main.go").decode("utf-8")
        j105 = self.zf.read(PREFIX + "j105_recovery_test.go").decode("utf-8")
        self.assertIn("recoverAdmissionTransactionsLocked", main)
        self.assertIn("global admission fence", main)
        self.assertIn("RecoverAdmissionTransactions", main)
        self.assertIn("TestJ105CrossCandidatePrecommitCrashGloballyFencedBeforeUnrelatedAdmission", j105)
        self.assertIn("TestJ105CrossCandidateCommittedCrashFinalizedBeforeUnrelatedAdmission", j105)

    def test_internal_proof_identity_is_v043_j105(self):
        proof = json.loads(self.zf.read(PREFIX + "FNSF-v0.4.3-J105-Global-Recovery-Proof.json"))
        self.assertEqual("FNSF_V043_J105_GLOBAL_RECOVERY_REPAIR_PROOF_V1", proof["schema"])
        self.assertEqual("0.4.3", proof["version"])
        self.assertIn("independent Reality Judge J105 re-court still required", proof["proof_boundaries"])
        self.assertEqual("TC-20260918T184839+0200-FNSF-V043-J105-INDEPENDENT-ACK-J111", self.receipt["independent_judge_receipt"])

    def test_no_external_effect_or_runtime_promotion_is_smuggled_into_receipt(self):
        self.assertEqual("SOURCE_CANDIDATE", self.receipt["maturity"])
        for key in (
            "dispatch_authorized",
            "provider_effect_authorized",
            "physical_windows_proven",
            "production_activation_authorized",
            "provider_native_cas_proven",
            "go_live_proven",
            "owner_value_proven",
        ):
            self.assertIs(self.receipt[key], False, key)

    def test_archive_has_no_secret_like_material_and_no_symlinks(self):
        for info in self.zf.infolist():
            mode = (info.external_attr >> 16) & 0o170000
            self.assertNotEqual(0o120000, mode, info.filename)
            if info.is_dir():
                continue
            data = self.zf.read(info.filename)
            self.assertIsNone(SECRET_RE.search(data), info.filename)

if __name__ == "__main__":
    unittest.main()

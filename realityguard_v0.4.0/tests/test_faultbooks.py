import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from realityguard.faultbooks import FaultbookManager, event_hash, verify_event_stream
from realityguard.schema import InputError


def write_ledger(path: Path, contents=("first", "second")) -> list[dict]:
    rows, previous = [], "GENESIS"
    for index, content in enumerate(contents, start=1):
        row = {"event_id": f"F-E{index:04d}", "event_type": "FAULT", "content": content, "prev_hash": previous}
        row["event_hash"] = event_hash(row)
        rows.append(row)
        previous = row["event_hash"]
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return rows


def metadata(**changes):
    value = {
        "schema_version": "realityguard.faultbook-import.v1",
        "faultbook_id": "FAULTBOOK-1",
        "title": "Authorization continuity fault",
        "status": "SYSTEMIC_OPEN",
        "faults": [{"fault_id": "F-01", "title": "Redundant authorization pause", "classification": "AUTHORIZATION_CONTINUITY", "status": "OPEN", "root_mechanism": "written authorization not applied at execution"}],
        "open_regression_tests": ["FT-01"],
        "artifacts": [],
        "consumers": [
            {"consumer_id": "current-invocation", "surface": "ChatGPT", "state": "VERIFIED_INVOCATION", "proof_refs": ["test:import"]},
            {"consumer_id": "historical-chats", "surface": "ChatGPT", "state": "ADAPTER_REQUIRED", "proof_refs": [], "notes": "not addressable"},
        ],
    }
    value.update(changes)
    return value


class FaultbookManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ledger = self.root / "faults.jsonl"
        self.rows = write_ledger(self.ledger)
        self.manager = FaultbookManager(self.root / "registry.json")

    def tearDown(self):
        self.temp.cleanup()

    def test_import_verifies_and_preserves_complete_event_stream(self):
        receipt = self.manager.import_faultbook(self.ledger, metadata())
        registry = json.loads((self.root / "registry.json").read_text())
        self.assertEqual(2, receipt["event_count"])
        self.assertEqual(self.rows, registry["faultbooks"]["FAULTBOOK-1"]["ledger"]["events"])

    def test_duplicate_import_is_idempotent(self):
        first = self.manager.import_faultbook(self.ledger, metadata())
        before = (self.root / "registry.json").read_bytes()
        second = self.manager.import_faultbook(self.ledger, metadata())
        self.assertFalse(first["duplicate_suppressed"])
        self.assertTrue(second["duplicate_suppressed"])
        self.assertEqual(before, (self.root / "registry.json").read_bytes())

    def test_duplicate_source_allows_verified_consumer_metadata_refresh(self):
        self.manager.import_faultbook(self.ledger, metadata())
        updated = metadata(consumers=[
            {"consumer_id": "current-invocation", "surface": "ChatGPT", "state": "VERIFIED_INVOCATION", "proof_refs": ["test:import"]},
            {"consumer_id": "historical-chats", "surface": "ChatGPT", "state": "ADAPTER_REQUIRED", "proof_refs": []},
            {"consumer_id": "library-registry", "surface": "ChatGPT Library", "state": "VERIFIED_SOURCE", "proof_refs": ["library:version-1"]},
        ])
        receipt = self.manager.import_faultbook(self.ledger, updated)
        self.assertTrue(receipt["duplicate_suppressed"])
        self.assertTrue(receipt["registry_written"])
        self.assertEqual("VERIFIED_SOURCE", receipt["consumer_states"]["library-registry"])

    def test_tampered_event_is_rejected(self):
        self.rows[1]["content"] = "tampered"
        self.ledger.write_text("".join(json.dumps(row) + "\n" for row in self.rows))
        with self.assertRaisesRegex(InputError, "hash mismatch"):
            verify_event_stream(self.ledger)

    def test_parent_chain_mismatch_is_rejected(self):
        self.rows[1]["prev_hash"] = "wrong"
        self.rows[1]["event_hash"] = event_hash(self.rows[1])
        self.ledger.write_text("".join(json.dumps(row) + "\n" for row in self.rows))
        with self.assertRaisesRegex(InputError, "parent mismatch"):
            verify_event_stream(self.ledger)

    def test_duplicate_event_id_is_rejected(self):
        self.rows[1]["event_id"] = self.rows[0]["event_id"]
        self.rows[1]["event_hash"] = event_hash(self.rows[1])
        self.ledger.write_text("".join(json.dumps(row) + "\n" for row in self.rows))
        with self.assertRaisesRegex(InputError, "duplicate"):
            verify_event_stream(self.ledger)

    def test_changed_source_preserves_prior_revision(self):
        self.manager.import_faultbook(self.ledger, metadata())
        write_ledger(self.ledger, ("first", "second", "fork-preserved"))
        self.manager.import_faultbook(self.ledger, metadata())
        record = json.loads((self.root / "registry.json").read_text())["faultbooks"]["FAULTBOOK-1"]
        self.assertEqual(1, len(record["revisions"]))
        self.assertEqual(3, record["ledger"]["event_count"])

    def test_open_tests_prevent_closed_faultbook(self):
        with self.assertRaisesRegex(InputError, "cannot be CLOSED"):
            self.manager.import_faultbook(self.ledger, metadata(status="CLOSED"))

    def test_unreachable_consumers_block_universal_sync_claim(self):
        self.manager.import_faultbook(self.ledger, metadata())
        manifest = self.manager.public_manifest()
        self.assertFalse(manifest["universal_sync_claim_allowed"])
        states = {item["consumer_id"]: item["state"] for item in manifest["consumers"]}
        self.assertEqual("ADAPTER_REQUIRED", states["historical-chats"])

    def test_host_bound_requires_current_semantic_readback(self):
        bad = metadata(consumers=[{"consumer_id": "host", "surface": "ChatGPT", "state": "VERIFIED_HOST_BOUND", "proof_refs": ["receipt:x"]}])
        with self.assertRaisesRegex(InputError, "current_invocation"):
            self.manager.import_faultbook(self.ledger, bad)

    def test_public_manifest_excludes_private_content_and_storage_refs(self):
        secret = self.root / "private.docx"
        secret.write_bytes(b"private")
        digest = hashlib.sha256(b"private").hexdigest()
        data = metadata(
            artifacts=[{"kind": "DOCX", "sha256": digest, "local_path": str(secret), "storage_ref": "private-id"}],
            consumers=[{"consumer_id": "library", "surface": "Library", "state": "VERIFIED_SOURCE", "proof_refs": ["libfile_private-proof-id"]}],
        )
        self.manager.import_faultbook(self.ledger, data)
        encoded = json.dumps(self.manager.public_manifest())
        self.assertNotIn("private-id", encoded)
        self.assertNotIn("first", encoded)
        self.assertNotIn(str(secret), encoded)
        self.assertNotIn("libfile_private-proof-id", encoded)
        self.assertFalse(self.manager.public_manifest()["privacy"]["consumer_proof_refs_included"])

    def test_registry_verifier_detects_fingerprint_tampering(self):
        self.manager.import_faultbook(self.ledger, metadata())
        value = json.loads((self.root / "registry.json").read_text())
        value["faultbooks"]["FAULTBOOK-1"]["faults"][0]["fingerprint"] = "bad"
        (self.root / "registry.json").write_text(json.dumps(value))
        result = self.manager.verify()
        self.assertFalse(result["valid"])
        self.assertTrue(any("fault-fingerprint" in item for item in result["failures"]))

    def test_expected_ledger_digest_mismatch_is_rejected(self):
        with self.assertRaisesRegex(InputError, "digest mismatch"):
            self.manager.import_faultbook(self.ledger, metadata(expected_ledger_sha256="0" * 64))


if __name__ == "__main__":
    unittest.main()

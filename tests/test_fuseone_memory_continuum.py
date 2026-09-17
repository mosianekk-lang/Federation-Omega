import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from federation_consolidation.fuseone_memory_continuum import (
    MemoryStore, MemoryObject, MemoryKind, Canonicality, SecurityClass,
    ContextRelation, PresentTruthCut, ContinuationCapsule, RecoveryManifest,
    MemoryConflict, migrate_memory_dict, SCHEMA_VERSION
)


class MemoryContinuumTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db = self.tmp / "memory_store"
        self.store = MemoryStore(self.db)
        self.intent = MemoryObject(
            memory_id="INTENT:FUSE-ONE",
            object_kind=MemoryKind.INTENT,
            payload={"objective": "Build sovereign FUSE-One memory"},
            canonicality=Canonicality.AUTHORITATIVE,
            source_refs=("owner-directive",),
            intent_ids=("INTENT:FUSE-ONE",),
        )
        self.store.append(self.intent)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_01_append_is_idempotent_and_versioned(self):
        r1 = self.store.append(self.intent)
        self.assertTrue(r1["reused"])
        updated = MemoryObject(
            memory_id="INTENT:FUSE-ONE", object_kind=MemoryKind.INTENT,
            payload={"objective": "Build sovereign FUSE-One memory", "stage": "OMEGA1"},
            canonicality=Canonicality.AUTHORITATIVE, source_refs=("owner-directive",), intent_ids=("INTENT:FUSE-ONE",)
        )
        r2 = self.store.append(updated)
        self.assertEqual(r2["version"], 2)
        self.assertEqual(self.store.latest("INTENT:FUSE-ONE").payload["stage"], "OMEGA1")

    def test_02_graph_relation(self):
        rel = ContextRelation("INTENT:FUSE-ONE", "contains", "SYSTEM:FMC", ("proof:1",))
        self.store.add_relation(rel)
        rows = self.store.relations_for("INTENT:FUSE-ONE")
        self.assertEqual(rows[0]["predicate"], "contains")

    def test_03_process_restart_recovery(self):
        reopened = MemoryStore(self.db)
        self.assertEqual(reopened.latest("INTENT:FUSE-ONE").content_hash, self.intent.content_hash)

    def test_04_index_loss_and_rebuild(self):
        self.store.rebuild_indexes()
        self.assertIn("INTENT:FUSE-ONE", self.store.search("sovereign"))
        (self.db / "indexes" / "keyword-v1.json").unlink()
        self.assertEqual(self.store.search("sovereign"), [])
        self.store.rebuild_indexes()
        self.assertIn("INTENT:FUSE-ONE", self.store.search("sovereign"))

    def test_05_export_import_cold_restore(self):
        export = self.tmp / "memory.jsonl"
        h = self.store.export_jsonl(export)
        self.assertEqual(len(h), 64)
        restored = MemoryStore.import_jsonl(export, self.tmp / "restored_store")
        self.assertEqual(restored.latest("INTENT:FUSE-ONE").content_hash, self.intent.content_hash)

    def test_06_secret_leak_redacted(self):
        obj = MemoryObject(
            memory_id="AUTH:TEST", object_kind=MemoryKind.AUTHORITY,
            payload={"secret_value": "TOPSECRET", "secret_ref": "vault://alpha"},
            security_class=SecurityClass.CONFIDENTIAL,
        )
        self.store.append(obj)
        export = self.tmp / "secret.jsonl"
        self.store.export_jsonl(export, max_security=SecurityClass.CONFIDENTIAL)
        text = export.read_text()
        self.assertNotIn("TOPSECRET", text)
        self.assertIn("vault://alpha", text)

    def test_07_context_projection_minimum_scope(self):
        project_obj = MemoryObject(
            memory_id="DECISION:1", object_kind=MemoryKind.DECISION,
            payload={"decision": "browser under fuse-one"}, project_ids=("P1",), intent_ids=("INTENT:FUSE-ONE",), security_class=SecurityClass.INTERNAL
        )
        private_obj = MemoryObject(
            memory_id="DECISION:2", object_kind=MemoryKind.DECISION,
            payload={"decision": "sovereign secret"}, project_ids=("P2",), intent_ids=("INTENT:OTHER",), security_class=SecurityClass.SOVEREIGN
        )
        self.store.append(project_obj); self.store.append(private_obj)
        projection = self.store.context_projection(intent_ids=("INTENT:FUSE-ONE",), max_security=SecurityClass.INTERNAL)
        ids = {x["memory_id"] for x in projection}
        self.assertIn("DECISION:1", ids)
        self.assertNotIn("DECISION:2", ids)

    def test_08_orphan_detection_and_replication(self):
        self.assertIn("INTENT:FUSE-ONE", self.store.orphaned())
        self.store.register_replica("INTENT:FUSE-ONE", "LOCAL", "sqlite://memory", self.intent.content_hash)
        self.store.register_replica("INTENT:FUSE-ONE", "DRIVE", "gdrive://artifact", self.intent.content_hash)
        self.assertNotIn("INTENT:FUSE-ONE", self.store.orphaned())

    def test_09_fork_detection(self):
        self.store.put_checkpoint("CAPSULE:X", "CONTINUATION_CAPSULE", {"a": 1})
        with self.assertRaises(MemoryConflict):
            self.store.put_checkpoint("CAPSULE:X", "CONTINUATION_CAPSULE", {"a": 2})

    def test_10_present_truth_cut(self):
        cut = PresentTruthCut("FPTC:1", "2026-09-13T01:00:00+02:00", "abc", "tree", "F253:ACTIVE", "MB:79", "KDV:checkpoint", "ART:checkpoint", active_intents=("INTENT:FUSE-ONE",))
        digest = self.store.create_present_truth_cut(cut)
        cp = self.store.get_checkpoint("FPTC:1")
        self.assertEqual(cp["content_hash"], digest)

    def test_11_continuation_capsule_and_manifest(self):
        cap = ContinuationCapsule("CAPSULE:1", "INTENT:FUSE-ONE", ("SYSTEM:FMC",), ("DECISION:1",), ("CLAIM:1",), ("CLAIM:2",), (), ("main:abc",), ("ART:1",), ("AUTH:A1",), ("OPP:1",), "run recovery court", "FPTC:1")
        cap_hash = self.store.create_capsule(cap)
        man = RecoveryManifest("MANIFEST:1", cap.capsule_id, ("FFCL:1",), ("INTENT:FUSE-ONE",), ("git:abc",), ("KDV:1",), ("ARTVAULT:1",), "FPTC:1", ("LOCAL", "DRIVE"), ("keyword-v1", "graph-v1", "temporal-v1", "vector-rebuildable"), ("verify hashes", "restore canonical memory", "rebuild indexes", "verify present truth"))
        man_hash = self.store.create_manifest(man)
        self.assertEqual(len(cap_hash), 64); self.assertEqual(len(man_hash), 64)

    def test_12_stale_history_block(self):
        obj = MemoryObject(
            memory_id="CLAIM:RUNTIME", object_kind=MemoryKind.CLAIM,
            payload={"claim": "provider works"}, canonicality=Canonicality.AUTHORITATIVE,
            currentness_ttl_seconds=1, last_verified_at="2000-01-01T00:00:00+00:00"
        )
        self.store.append(obj)
        self.assertEqual(self.store.currentness_status("CLAIM:RUNTIME"), "STALE")

    def test_13_schema_migration(self):
        old = {"memory_id": "FACT:OLD", "object_kind": "FACT", "payload": {"x": 1}, "schema_version": "FMC-MEMORY-0.9"}
        new = migrate_memory_dict(old)
        self.assertEqual(new["schema_version"], SCHEMA_VERSION)
        obj = MemoryObject.from_dict(new)
        self.assertEqual(obj.memory_id, "FACT:OLD")

    def test_14_corrections_append_not_rewrite(self):
        first = MemoryObject(memory_id="FACT:X", object_kind=MemoryKind.FACT, payload={"value": "A"}, canonicality=Canonicality.AUTHORITATIVE)
        second = MemoryObject(memory_id="FACT:X", object_kind=MemoryKind.FACT, payload={"value": "B"}, canonicality=Canonicality.AUTHORITATIVE, supersedes=(first.content_hash,))
        self.store.append(first); self.store.append(second)
        self.assertEqual(self.store.version_count("FACT:X"), 2)

    def test_15_ephemeral_not_exported(self):
        ep = MemoryObject(memory_id="EVENT:TEMP", object_kind=MemoryKind.EVENT, payload={"tmp": True}, security_class=SecurityClass.EPHEMERAL)
        self.store.append(ep)
        export = self.tmp / "ephemeral.jsonl"
        self.store.export_jsonl(export)
        self.assertNotIn("EVENT:TEMP", export.read_text())

    def test_16_cross_provider_restore_is_provider_neutral(self):
        # No provider-native memory exists in the exported record; two consumers can receive the same projection.
        export = self.tmp / "provider-neutral.jsonl"; self.store.export_jsonl(export)
        restored = MemoryStore.import_jsonl(export, self.tmp / "providerB_store")
        a = self.store.context_projection(intent_ids=("INTENT:FUSE-ONE",))
        b = restored.context_projection(intent_ids=("INTENT:FUSE-ONE",))
        self.assertEqual([x["memory_id"] for x in a], [x["memory_id"] for x in b])

    def test_17_source_admission_module_is_provider_neutral_stdlib(self):
        # The canonical memory kernel must not acquire a hidden provider SDK/network dependency at source admission.
        import federation_consolidation.fuseone_memory_continuum as module
        source = Path(module.__file__).read_text(encoding="utf-8").lower()
        forbidden = ("import requests", "from requests", "import openai", "from openai", "google.cloud", "boto3", "anthropic")
        self.assertFalse(any(token in source for token in forbidden))


if __name__ == "__main__":
    unittest.main(verbosity=2)

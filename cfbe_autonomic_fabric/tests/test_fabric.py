from __future__ import annotations

import json
import hashlib
import sqlite3
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib import error as urlerror

from cfbe_acf.anchor import HttpCasTrustedAnchorStore, MemoryTrustedAnchorStore
from cfbe_acf.authority import FormationPermitAuthority
from cfbe_acf.compiler import IntentCompiler
from cfbe_acf.models import CloudEvent, ProviderDescriptor
from cfbe_acf.proof import ProofKernel
from cfbe_acf.reconciler import Reconciler
from cfbe_acf.resolver import CapabilityResolver
from cfbe_acf.runtime import DeterministicObservationAdapter, FabricRuntime
from cfbe_acf.store import FabricStore
from cfbe_acf.twin import EstateTwin
from cfbe_acf.util import canonical_json, digest_json


ROOT = Path(__file__).resolve().parents[1]
FORMATION_KEY = b"formation-test-key-32-bytes-minimum!!"
JARVIS_KEY = b"jarvis-test-key-32-bytes-minimum!!!!!"
INTEGRITY_KEY = b"integrity-test-key-32-bytes-minimum!!"
INTEGRITY_AUTHORITY = "sentinel-integrity-test"
INTEGRITY_STORE_ID = "STORE-cfbe-test-fixture"


def load_example(name: str):
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


class CountingAdapter:
    def __init__(self, provider_id: str, *, effectful: bool, delay: float = 0.0, secret=False):
        self.provider_id = provider_id
        self.effectful = effectful
        self.delay = delay
        self.secret = secret
        self.calls = 0
        self.active = 0
        self.max_concurrent = 0
        self._lock = threading.Lock()

    def execute(self, action, payload, *, dry_run, idempotency_key):
        with self._lock:
            self.calls += 1
            self.active += 1
            self.max_concurrent = max(self.max_concurrent, self.active)
        try:
            if self.delay:
                time.sleep(self.delay)
            if self.secret:
                return {"access_token": "plaintext-secret"}
            return {
                "provider_id": self.provider_id,
                "action": action,
                "external_mutation_performed": self.effectful and not dry_run,
                "semantic_result": {"ok": True},
            }
        finally:
            with self._lock:
                self.active -= 1


class FakeHttpResponse:
    def __init__(self, status: int, value: dict):
        self.status = status
        self._body = canonical_json(value).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size: int):
        return self._body[:size]


class TrustedAnchorClientTests(unittest.TestCase):
    def test_http_cas_client_requires_https_and_performs_expected_version_cas(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            HttpCasTrustedAnchorStore(
                "http://anchor.invalid", bearer_token="anchor-token-long-enough"
            )
        previous = {
            "checkpoint_id": 1,
            "event_count": 0,
            "event_chain_root": "0" * 64,
            "state_root": "1" * 64,
            "observed_at": "2026-08-26T18:00:00Z",
            "authority_id": INTEGRITY_AUTHORITY,
        }
        current = {**previous, "checkpoint_id": 2, "state_root": "2" * 64}
        responses = [
            FakeHttpResponse(200, {"anchor": previous}),
            FakeHttpResponse(200, {"anchor": current}),
        ]
        client = HttpCasTrustedAnchorStore(
            "https://anchor.example", bearer_token="anchor-token-long-enough"
        )
        with patch.object(client._opener, "open", side_effect=responses) as mocked:
            client.commit(INTEGRITY_STORE_ID, current)
        self.assertEqual(mocked.call_count, 2)
        put_request = mocked.call_args_list[1].args[0]
        payload = json.loads(put_request.data)
        self.assertEqual(payload["expected_checkpoint_id"], 1)
        self.assertEqual(payload["anchor"], current)
        self.assertEqual(put_request.get_header("Authorization"), "Bearer anchor-token-long-enough")

    def test_unanchored_store_cannot_report_ready_or_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            health = FabricRuntime(FabricStore(Path(temp) / "unanchored.sqlite")).health()
        self.assertEqual(health["state"], "DEGRADED_LOCAL")
        self.assertEqual(health["store"]["integrity_anchor"], "UNCONFIGURED")
        self.assertFalse(health["completion_claim_allowed"])

    def test_anchor_redirects_are_rejected_without_a_second_request(self):
        client = HttpCasTrustedAnchorStore(
            "https://anchor.example", bearer_token="anchor-token-long-enough"
        )
        redirect = urlerror.HTTPError(
            "https://anchor.example/anchors/store",
            302,
            "redirect",
            {"Location": "http://attacker.invalid/capture"},
            None,
        )
        with patch.object(client._opener, "open", side_effect=redirect) as mocked:
            with self.assertRaisesRegex(ConnectionError, "redirects"):
                client.read("store")
        self.assertEqual(mocked.call_count, 1)


class StoreAndTwinTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "fabric.sqlite"
        self.anchor_store = MemoryTrustedAnchorStore()
        self.store = FabricStore(
            self.db,
            integrity_key=INTEGRITY_KEY,
            integrity_authority_id=INTEGRITY_AUTHORITY,
            anchor_store=self.anchor_store,
            expected_store_id=INTEGRITY_STORE_ID,
        )
        self.store.provision_integrity()

    def tearDown(self):
        self.temp.cleanup()

    def test_snapshot_is_atomic_and_integrity_checked(self):
        result = EstateTwin(self.store).ingest(load_example("estate_snapshot.json"))
        self.assertEqual(result["integrity"]["state"], "OK")
        self.assertEqual(result["counts"]["assets"], 13)
        bad = load_example("estate_snapshot.json")
        bad["edges"][0]["target_id"] = "missing-node"
        with self.assertRaisesRegex(ValueError, "edge endpoint"):
            self.store.apply_snapshot(bad)
        self.assertEqual(self.store.integrity_check()["counts"]["assets"], 13)

    def test_event_idempotency_and_collision_detection(self):
        event = CloudEvent(id="evt-1", source="urn:test:source", type="org.cfbe.test.v1", data={"ok": True})
        first = self.store.append_event(event)
        self.assertFalse(first["reused"])
        self.assertTrue(self.store.append_event(event)["reused"])
        changed = CloudEvent(
            id="evt-1", source="urn:test:source", type="org.cfbe.test.v1",
            data={"ok": False}, traceparent=event.traceparent, time=event.time,
        )
        with self.assertRaisesRegex(ValueError, "collision"):
            self.store.append_event(changed)

    def test_event_secret_and_reserved_extension_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "sensitive material"):
            CloudEvent(id="evt-secret", source="urn:test", type="test", data={"password": "x"})
        with self.assertRaisesRegex(ValueError, "reserved"):
            CloudEvent(
                id="evt-extension", source="urn:test", type="test", data={"ok": True},
                extensions={"source": "relative"},
            )
        with self.assertRaisesRegex(ValueError, "non-JSON"):
            CloudEvent(
                id="evt-tuple", source="urn:test", type="test",
                data={"items": ({"password": "x"},)},
            )
        with self.assertRaisesRegex(ValueError, "sensitive material"):
            CloudEvent(
                id="evt-token", source="urn:test", type="test",
                data={"note": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"},
            )

    def test_application_tampering_fails_integrity_and_readback(self):
        EstateTwin(self.store).ingest(load_example("estate_snapshot.json"))
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE assets SET document='{}' WHERE id='cfbe-omega'")
        self.assertEqual(self.store.integrity_check()["state"], "FAILED")
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.store.snapshot()

    def test_self_consistent_rewrite_and_event_deletion_break_signed_anchor(self):
        EstateTwin(self.store).ingest(load_example("estate_snapshot.json"))
        event = CloudEvent(id="evt-anchor", source="urn:test", type="test", data={"ok": True})
        self.store.append_event(event)
        attacker = {"id": "cfbe-omega", "state": "attacker"}
        with sqlite3.connect(self.db) as con:
            con.execute(
                "UPDATE assets SET document=?,content_hash=? WHERE id='cfbe-omega'",
                (canonical_json(attacker), digest_json(attacker)),
            )
            con.execute("DELETE FROM events WHERE id='evt-anchor'")
        integrity = self.store.integrity_check()
        self.assertEqual(integrity["state"], "FAILED")
        self.assertIn("anchored_state_root_mismatch", integrity["application_issues"])

    def test_backup_restore_round_trip_has_provenance(self):
        EstateTwin(self.store).ingest(load_example("estate_snapshot.json"))
        backup = Path(self.temp.name) / "backup.sqlite"
        result = self.store.backup(backup)
        self.assertEqual(result["integrity"]["state"], "OK")
        self.assertTrue(Path(result["manifest"]).is_file())
        restored = FabricStore.restore(
            backup,
            Path(self.temp.name) / "restored.sqlite",
            integrity_key=INTEGRITY_KEY,
            integrity_authority_id=INTEGRITY_AUTHORITY,
            anchor_store=self.anchor_store,
            expected_store_id=INTEGRITY_STORE_ID,
        )
        self.assertEqual(restored.integrity_check()["counts"]["assets"], 13)

    def test_missing_or_tampered_backup_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            FabricStore.restore(
                Path(self.temp.name) / "missing.sqlite",
                self.db,
                integrity_key=INTEGRITY_KEY,
                integrity_authority_id=INTEGRITY_AUTHORITY,
                anchor_store=self.anchor_store,
                expected_store_id=INTEGRITY_STORE_ID,
            )
        EstateTwin(self.store).ingest(load_example("estate_snapshot.json"))
        backup = Path(self.temp.name) / "backup.sqlite"
        self.store.backup(backup)
        with backup.open("ab") as handle:
            handle.write(b"tamper")
        manifest_path = Path(str(backup) + ".manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["database_sha256"] = hashlib.sha256(backup.read_bytes()).hexdigest()
        manifest_path.write_text(canonical_json(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "signature"):
            FabricStore.restore(
                backup,
                Path(self.temp.name) / "bad.sqlite",
                integrity_key=INTEGRITY_KEY,
                integrity_authority_id=INTEGRITY_AUTHORITY,
                anchor_store=self.anchor_store,
                expected_store_id=INTEGRITY_STORE_ID,
            )

    def test_external_anchor_detects_checkpoint_and_event_rollback(self):
        self.store.append_event(
            CloudEvent(id="evt-rollback", source="urn:test", type="test", data={"ok": True})
        )
        with sqlite3.connect(self.db) as con:
            latest = con.execute("SELECT MAX(id) FROM integrity_checkpoints").fetchone()[0]
            con.execute("DELETE FROM events WHERE id='evt-rollback'")
            con.execute("DELETE FROM integrity_checkpoints WHERE id=?", (latest,))
        integrity = self.store.integrity_check()
        self.assertEqual(integrity["state"], "FAILED")
        self.assertIn("external_trusted_anchor_mismatch", integrity["application_issues"])

    def test_missing_all_checkpoints_cannot_be_automatically_resealed(self):
        EstateTwin(self.store).ingest(load_example("estate_snapshot.json"))
        with sqlite3.connect(self.db) as con:
            attacker = {"id": "cfbe-omega", "state": "attacker"}
            con.execute(
                "UPDATE assets SET document=?,content_hash=? WHERE id='cfbe-omega'",
                (canonical_json(attacker), digest_json(attacker)),
            )
            con.execute("DELETE FROM integrity_checkpoints")
        self.store.initialize()
        integrity = self.store.integrity_check()
        self.assertEqual(integrity["state"], "FAILED")
        self.assertIn("integrity_checkpoint_missing", integrity["application_issues"])
        with self.assertRaisesRegex(PermissionError, "pre-write integrity|prior checkpoint"):
            self.store.seal_integrity_checkpoint()

    def test_tampered_state_cannot_be_blessed_by_a_later_legitimate_write(self):
        EstateTwin(self.store).ingest(load_example("estate_snapshot.json"))
        attacker = {"id": "cfbe-omega", "state": "attacker"}
        with sqlite3.connect(self.db) as con:
            con.execute(
                "UPDATE assets SET document=?,content_hash=? WHERE id='cfbe-omega'",
                (canonical_json(attacker), digest_json(attacker)),
            )
        blocker = {
            "id": "BLK-legitimate-followup",
            "state": "OPEN",
            "observed_at": "2026-08-26T18:00:00Z",
        }
        with self.assertRaisesRegex(PermissionError, "pre-write integrity"):
            self.store.record_blockers([blocker])
        self.assertEqual(self.store.integrity_check()["state"], "FAILED")

    def test_integrity_store_requires_independently_pinned_identity(self):
        with self.assertRaisesRegex(ValueError, "expected store identity"):
            FabricStore(
                Path(self.temp.name) / "unpinned.sqlite",
                integrity_key=INTEGRITY_KEY,
                integrity_authority_id=INTEGRITY_AUTHORITY,
                anchor_store=MemoryTrustedAnchorStore(),
            )

    def test_genesis_provisioning_rejects_nonempty_database(self):
        database = Path(self.temp.name) / "nonempty.sqlite"
        store = FabricStore(
            database,
            integrity_key=INTEGRITY_KEY,
            integrity_authority_id=INTEGRITY_AUTHORITY,
            anchor_store=MemoryTrustedAnchorStore(),
            expected_store_id="STORE-nonempty-provisioning-test",
        )
        store.initialize()
        attacker = {"id": "attacker-state"}
        with sqlite3.connect(database) as con:
            con.execute(
                "INSERT INTO assets(id,document,content_hash,observed_at) VALUES(?,?,?,?)",
                (
                    attacker["id"], canonical_json(attacker), digest_json(attacker),
                    "2026-08-26T18:00:00Z",
                ),
            )
        with self.assertRaisesRegex(PermissionError, "empty database"):
            store.provision_integrity()

    def test_cross_store_database_substitution_is_rejected(self):
        other_id = "STORE-independent-other-fixture"
        other_db = Path(self.temp.name) / "other.sqlite"
        other = FabricStore(
            other_db,
            integrity_key=INTEGRITY_KEY,
            integrity_authority_id=INTEGRITY_AUTHORITY,
            anchor_store=self.anchor_store,
            expected_store_id=other_id,
        )
        other.provision_integrity()
        with sqlite3.connect(other_db) as source, sqlite3.connect(self.db) as target:
            source.backup(target)
        with self.assertRaisesRegex(PermissionError, "store identity"):
            self.store.integrity_check()

    def test_chronologically_older_offset_snapshot_cannot_overwrite(self):
        first = load_example("estate_snapshot.json")
        first["snapshot_at"] = "2026-01-01T00:30:00Z"
        first["assets"][0]["state"] = "newer"
        for heartbeat in first["heartbeats"]:
            heartbeat["observed_at"] = first["snapshot_at"]
        self.store.apply_snapshot(first)
        older = load_example("estate_snapshot.json")
        older["snapshot_at"] = "2026-01-01T01:00:00+01:00"
        older["assets"][0]["state"] = "older"
        for heartbeat in older["heartbeats"]:
            heartbeat["observed_at"] = older["snapshot_at"]
        self.store.apply_snapshot(older)
        assets = {row["id"]: row for row in self.store.list_documents("assets")}
        self.assertEqual(assets[first["assets"][0]["id"]]["state"], "newer")

    def test_sensitive_material_fields_are_rejected(self):
        bad = load_example("estate_snapshot.json")
        bad["providers"][0]["authorization"] = "Bearer abcdefghijklmnopqrstuvwxyz"
        with self.assertRaisesRegex(ValueError, "sensitive material"):
            self.store.apply_snapshot(bad)


class CompilerAndResolverTests(unittest.TestCase):
    def test_reuse_route_wins_with_validated_receipt_stage(self):
        intent = IntentCompiler().compile(load_example("intent.json"))
        providers = load_example("providers.json")["providers"]
        adapted = dict(providers[0])
        adapted.update({"id": "adapted", "strategy": "ADAPT"})
        result = CapabilityResolver().resolve(
            intent, [adapted, providers[0]],
            now=datetime(2026, 8, 26, 17, 20, tzinfo=timezone.utc),
            verified_proof_stages={"adapted": "SEMANTICALLY_VERIFIED", "github-read": "SEMANTICALLY_VERIFIED"},
        )
        self.assertEqual(result["winner"]["provider_id"], "github-read")
        self.assertEqual(result["effectful_paths_allowed"], 0)

    def test_unbacked_self_declared_proof_is_rejected(self):
        intent = IntentCompiler().compile(load_example("intent.json"))
        result = CapabilityResolver().resolve(
            intent, load_example("providers.json")["providers"],
            now=datetime(2026, 8, 26, 17, 20, tzinfo=timezone.utc),
        )
        self.assertIn("VALIDATED_PROOF_CHAIN_MISSING", result["rejected"][0]["reasons"])

    def test_effectful_provider_cannot_be_downgraded_by_intent(self):
        intent = IntentCompiler().compile(load_example("intent.json"))
        provider = dict(load_example("providers.json")["providers"][0])
        provider["effectful"] = True
        result = CapabilityResolver().resolve(
            intent, [provider], now=datetime(2026, 8, 26, 17, 20, tzinfo=timezone.utc),
            verified_proof_stages={"github-read": "SEMANTICALLY_VERIFIED"},
        )
        self.assertIn("EFFECTFUL_DECLARATION_MISMATCH", result["rejected"][0]["reasons"])

    def test_unknown_cost_and_missing_semantics_fail_closed(self):
        intent = IntentCompiler().compile(load_example("intent.json"))
        provider = dict(load_example("providers.json")["providers"][0])
        provider.update({"cost_class": "UNKNOWN", "semantic_readback": False})
        result = CapabilityResolver().resolve(intent, [provider])
        self.assertIn("COST_UNKNOWN_OR_UNAPPROVED", result["rejected"][0]["reasons"])
        self.assertIn("SEMANTIC_READBACK_MISSING", result["rejected"][0]["reasons"])

    def test_strict_booleans_and_finite_numbers_fail_closed(self):
        intent = load_example("intent.json")
        intent["constraints"]["effectful"] = "false"
        with self.assertRaisesRegex(ValueError, "JSON boolean"):
            IntentCompiler().compile(intent)
        provider = dict(load_example("providers.json")["providers"][0])
        provider["reversible"] = "false"
        with self.assertRaisesRegex(ValueError, "JSON boolean"):
            ProviderDescriptor.from_mapping(provider)
        provider = dict(load_example("providers.json")["providers"][0])
        provider["owner_burden"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite"):
            ProviderDescriptor.from_mapping(provider)

    def test_stale_and_future_providers_are_rejected(self):
        intent_value = load_example("intent.json")
        intent_value["constraints"]["maximum_age_seconds"] = 60
        intent = IntentCompiler().compile(intent_value)
        stale = CapabilityResolver().resolve(
            intent, load_example("providers.json")["providers"],
            now=datetime(2026, 8, 26, 19, 20, tzinfo=timezone.utc),
            verified_proof_stages={"github-read": "SEMANTICALLY_VERIFIED"},
        )
        self.assertIn("PROOF_STALE", stale["rejected"][0]["reasons"])


class ProofKernelTests(unittest.TestCase):
    def setUp(self):
        self.evidence: dict[str, str] = {}
        self.kernel = ProofKernel(
            trusted_verifiers={"jarvis": JARVIS_KEY},
            evidence_resolver=lambda ref: self.evidence[ref],
        )

    def receipt(self, source: str, target: str, *, producer="executor", **kwargs):
        ref = f"evidence:{source}:{target}:{len(self.evidence)}"
        evidence_hash = digest_json({"source": source, "target": target, "ref": ref})
        self.evidence[ref] = evidence_hash
        unsigned = self.kernel.create_receipt(
            receipt_id=f"r-{source}-{target}-{len(self.evidence)}",
            mission_id="mission-1", mission_version=1, action_id="action-1",
            provider_id="provider", from_stage=source, to_stage=target,
            evidence_ref=ref, evidence_hash=evidence_hash,
            previous_receipt_hash="0" * 64, producer=producer,
            semantic_passed=kwargs.pop("semantic_passed", True), **kwargs,
        )
        return self.kernel.attest(unsigned, verifier="jarvis", verifier_key=JARVIS_KEY)

    def test_proof_stages_cannot_be_skipped(self):
        with self.assertRaisesRegex(ValueError, "cannot be skipped"):
            self.kernel.promote("DISCOVERED", self.receipt("DISCOVERED", "CONFIGURED"))

    def test_independent_trusted_verifier_is_required(self):
        with self.assertRaisesRegex(ValueError, "independent verifier"):
            self.kernel.promote(
                "DISCOVERED", self.receipt("DISCOVERED", "SOURCE_PRESENT", producer="jarvis")
            )
        receipt = self.receipt("DISCOVERED", "SOURCE_PRESENT")
        receipt["verifier"] = "stranger"
        with self.assertRaisesRegex(ValueError, "untrusted verifier"):
            self.kernel.verify(receipt)

    def test_evidence_readback_and_attestation_are_required(self):
        receipt = self.receipt("DISCOVERED", "SOURCE_PRESENT")
        self.evidence[receipt["evidence_ref"]] = "f" * 64
        with self.assertRaisesRegex(ValueError, "evidence readback"):
            self.kernel.verify(receipt)
        receipt = self.receipt("DISCOVERED", "SOURCE_PRESENT")
        receipt["attestation"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "attestation"):
            self.kernel.verify(receipt)

    def test_recovery_requires_rollback_and_replay(self):
        with self.assertRaisesRegex(ValueError, "rollback and replay"):
            self.kernel.promote(
                "SEMANTICALLY_VERIFIED",
                self.receipt("SEMANTICALLY_VERIFIED", "RECOVERY_VERIFIED"),
            )
        valid = self.receipt(
            "SEMANTICALLY_VERIFIED", "RECOVERY_VERIFIED",
            rollback_tested=True, replay_tested=True,
        )
        self.assertEqual(self.kernel.promote("SEMANTICALLY_VERIFIED", valid), "RECOVERY_VERIFIED")

    def test_soak_requires_duration_and_samples(self):
        receipt = self.receipt(
            "RECOVERY_VERIFIED", "SOAK_VERIFIED", rollback_tested=True,
            replay_tested=True, soak_seconds=100, sample_count=2,
        )
        with self.assertRaisesRegex(ValueError, "soak"):
            self.kernel.promote("RECOVERY_VERIFIED", receipt)

    def test_string_false_cannot_forge_recovery(self):
        ref = "evidence:string-false"
        self.evidence[ref] = digest_json(ref)
        with self.assertRaisesRegex(ValueError, "JSON boolean"):
            self.kernel.create_receipt(
                receipt_id="bad", mission_id="m", mission_version=1, action_id="a",
                provider_id="p", from_stage="SEMANTICALLY_VERIFIED",
                to_stage="RECOVERY_VERIFIED", evidence_ref=ref,
                evidence_hash=self.evidence[ref], previous_receipt_hash="0" * 64,
                producer="executor", semantic_passed="false",  # type: ignore[arg-type]
                rollback_tested="false", replay_tested="false",  # type: ignore[arg-type]
            )

    def test_store_rejects_nonproof_receipt_and_enforces_genesis(self):
        with tempfile.TemporaryDirectory() as temp:
            anchor_store = MemoryTrustedAnchorStore()
            store = FabricStore(
                Path(temp) / "state.sqlite",
                proof_kernel=self.kernel,
                integrity_key=INTEGRITY_KEY,
                integrity_authority_id=INTEGRITY_AUTHORITY,
                anchor_store=anchor_store,
                expected_store_id=INTEGRITY_STORE_ID,
            )
            store.provision_integrity()
            with self.assertRaises(ValueError):
                store.record_receipt({"receipt_id": "fake"})
            receipt = self.receipt("DISCOVERED", "SOURCE_PRESENT")
            with self.assertRaisesRegex(ValueError, "begin at UNKNOWN"):
                store.record_receipt(receipt)

    def test_stored_chain_is_reverified_and_scoped_by_version_and_action(self):
        with tempfile.TemporaryDirectory() as temp:
            anchor_store = MemoryTrustedAnchorStore()
            store = FabricStore(
                Path(temp) / "state.sqlite",
                proof_kernel=self.kernel,
                integrity_key=INTEGRITY_KEY,
                integrity_authority_id=INTEGRITY_AUTHORITY,
                anchor_store=anchor_store,
                expected_store_id=INTEGRITY_STORE_ID,
            )
            store.provision_integrity()
            transitions = [
                ("UNKNOWN", "DISCOVERED"),
                ("DISCOVERED", "SOURCE_PRESENT"),
                ("SOURCE_PRESENT", "CONFIGURED"),
                ("CONFIGURED", "AUTHENTICATED"),
                ("AUTHENTICATED", "TRANSPORT_PROVEN"),
                ("TRANSPORT_PROVEN", "SEMANTICALLY_VERIFIED"),
            ]
            previous = "0" * 64
            for index, (source, target) in enumerate(transitions):
                ref = f"chain:{index}"
                evidence_hash = digest_json(ref)
                self.evidence[ref] = evidence_hash
                unsigned = self.kernel.create_receipt(
                    receipt_id=f"chain-{index}", mission_id="mission-1",
                    mission_version=1, action_id="provider-admission",
                    provider_id="provider", from_stage=source, to_stage=target,
                    evidence_ref=ref, evidence_hash=evidence_hash,
                    previous_receipt_hash=previous, producer="executor",
                    semantic_passed=True,
                )
                receipt = self.kernel.attest(
                    unsigned, verifier="jarvis", verifier_key=JARVIS_KEY
                )
                store.record_receipt(receipt)
                previous = receipt["body_hash"]
            stages = store.verified_provider_stages(
                mission_id="mission-1", mission_version=1, action_id="provider-admission"
            )
            self.assertEqual(stages, {"provider": "SEMANTICALLY_VERIFIED"})
            self.assertEqual(
                store.verified_provider_stages(
                    mission_id="mission-1", mission_version=2, action_id="provider-admission"
                ),
                {},
            )


class ReconciliationAndRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.anchor_store = MemoryTrustedAnchorStore()
        self.store = FabricStore(
            Path(self.temp.name) / "state.sqlite",
            integrity_key=INTEGRITY_KEY,
            integrity_authority_id=INTEGRITY_AUTHORITY,
            anchor_store=self.anchor_store,
            expected_store_id=INTEGRITY_STORE_ID,
        )
        self.store.provision_integrity()
        EstateTwin(self.store).ingest(load_example("estate_snapshot.json"))
        self.store.set_mission_authority(
            mission_id="CFBE-ACF-EXAMPLE",
            current_version=1,
            state="ACTIVE",
            gate_decision="EXECUTE",
            maximum_authority_class="A2",
            maximum_cost=0,
        )
        self.authority = FormationPermitAuthority(
            store=self.store, signing_key=FORMATION_KEY, authority_id="formation-test"
        )

    def tearDown(self):
        self.temp.cleanup()

    def prepared_runtime(self, *, effectful=False, adapter=None):
        runtime = FabricRuntime(self.store, formation_authority=self.authority)
        adapter = adapter or (
            CountingAdapter("github-read", effectful=True)
            if effectful
            else DeterministicObservationAdapter("github-read", {"status": {"head": "abc"}})
        )
        runtime.register_adapter(adapter)
        intent_value = load_example("intent.json")
        intent_value["constraints"]["effectful"] = effectful
        intent_value["constraints"]["dry_run"] = not effectful
        provider = dict(load_example("providers.json")["providers"][0])
        provider["effectful"] = effectful
        compiled = IntentCompiler().compile(intent_value)
        resolution = CapabilityResolver().resolve(
            compiled, [provider], now=datetime(2026, 8, 26, 17, 20, tzinfo=timezone.utc),
            verified_proof_stages={"github-read": "SEMANTICALLY_VERIFIED"},
        )
        contract = runtime.build_execution_contract(
            compiled=compiled, resolution=resolution, action="status", payload={"scope": "public"}
        )
        return runtime, adapter, contract

    def test_stale_heartbeats_and_unverified_provider_create_real_blockers(self):
        result = Reconciler(self.store).plan(
            load_example("desired_state.json"),
            now=datetime(2026, 8, 26, 17, 20, tzinfo=timezone.utc),
        )
        self.assertEqual(result["state"], "DRIFT_DETECTED")
        stale = [b for b in result["blockers"] if b["reason"] == "HEARTBEAT_STALE"]
        self.assertEqual(len(stale), 13)
        self.assertTrue(any(b["reason"] == "PROOF_GAP" for b in result["blockers"]))
        self.assertFalse(result["completion_claim_allowed"])

    def test_repaired_blockers_are_superseded_before_completion(self):
        desired = load_example("desired_state.json")
        desired["capabilities"] = []
        Reconciler(self.store).plan(desired, now=datetime(2026, 8, 26, 17, 20, tzinfo=timezone.utc))
        fresh = load_example("estate_snapshot.json")
        fresh["snapshot_at"] = "2026-08-26T17:20:00Z"
        for heartbeat in fresh["heartbeats"]:
            heartbeat["observed_at"] = "2026-08-26T17:20:00Z"
        self.store.apply_snapshot(fresh)
        result = Reconciler(self.store).plan(
            desired, now=datetime(2026, 8, 26, 17, 20, tzinfo=timezone.utc)
        )
        self.assertTrue(result["completion_claim_allowed"])
        self.assertFalse(self.store.active_blockers(desired["id"]))
        self.assertTrue(
            all(row["state"] == "SUPERSEDED" for row in self.store.list_documents("blockers"))
        )

    def test_runtime_requires_signed_bound_single_use_permit(self):
        runtime, adapter, contract = self.prepared_runtime(effectful=True)
        with self.assertRaises(PermissionError):
            runtime.execute(contract=contract, payload={"scope": "public"}, formation_permit="anything")
        self.assertEqual(adapter.calls, 0)
        permit = self.authority.issue(contract)
        result = runtime.execute(contract=contract, payload={"scope": "public"}, formation_permit=permit)
        self.assertTrue(result["external_mutation_performed"])
        self.assertEqual(adapter.calls, 1)
        replay = runtime.execute(contract=contract, payload={"scope": "public"}, formation_permit=permit)
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(adapter.calls, 1)

    def test_stopped_or_superseded_mission_blocks_issue_and_consume(self):
        runtime, adapter, contract = self.prepared_runtime(effectful=True)
        permit = self.authority.issue(contract)
        self.store.set_mission_authority(
            mission_id=contract.mission_id,
            current_version=2,
            state="SUPERSEDED",
            gate_decision="CANCEL",
            maximum_authority_class="A2",
            maximum_cost=0,
        )
        with self.assertRaisesRegex(PermissionError, "stopped|superseded"):
            self.authority.issue(contract)
        with self.assertRaisesRegex(PermissionError, "stopped|superseded"):
            runtime.execute(
                contract=contract, payload={"scope": "public"}, formation_permit=permit
            )
        self.assertEqual(adapter.calls, 0)

    def test_mission_stop_between_permit_validation_and_reservation_blocks_execution(self):
        runtime, adapter, contract = self.prepared_runtime(effectful=True)
        permit = self.authority.issue(contract)
        original_validate = self.authority.validate

        def validate_then_stop(token, candidate):
            claims = original_validate(token, candidate)
            self.store.set_mission_authority(
                mission_id=candidate.mission_id,
                current_version=candidate.mission_version,
                state="STOPPED",
                gate_decision="CANCEL",
                maximum_authority_class="A2",
                maximum_cost=0,
            )
            return claims

        self.authority.validate = validate_then_stop  # type: ignore[method-assign]
        with self.assertRaisesRegex(PermissionError, "stopped"):
            runtime.execute(
                contract=contract, payload={"scope": "public"}, formation_permit=permit
            )
        self.assertEqual(adapter.calls, 0)
        self.assertIsNone(self.store.execution_result(contract.idempotency_key))

    def test_runtime_observation_is_contract_bound(self):
        runtime, _, contract = self.prepared_runtime()
        permit = self.authority.issue(contract)
        first = runtime.execute(contract=contract, payload={"scope": "public"}, formation_permit=permit)
        second = runtime.execute(contract=contract, payload={"scope": "public"}, formation_permit=permit)
        self.assertFalse(first["external_mutation_performed"])
        self.assertFalse(first["idempotent_replay"])
        self.assertTrue(second["idempotent_replay"])
        self.assertEqual(self.store.integrity_check()["counts"]["events"], 1)

    def test_concurrent_effect_executes_once(self):
        adapter = CountingAdapter("github-read", effectful=True, delay=0.08)
        runtime, _, contract = self.prepared_runtime(effectful=True, adapter=adapter)
        permits = [self.authority.issue(contract), self.authority.issue(contract)]
        outcomes = []
        barrier = threading.Barrier(2)

        def worker(permit):
            barrier.wait()
            try:
                outcomes.append(runtime.execute(
                    contract=contract, payload={"scope": "public"}, formation_permit=permit
                ))
            except Exception as exc:
                outcomes.append(exc)

        threads = [threading.Thread(target=worker, args=(permit,)) for permit in permits]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(adapter.calls, 1)
        self.assertEqual(sum(isinstance(item, dict) for item in outcomes), 1)

    def test_distinct_effectful_contracts_never_overlap(self):
        adapter = CountingAdapter("github-read", effectful=True, delay=0.08)
        runtime, _, contract_one = self.prepared_runtime(effectful=True, adapter=adapter)
        intent_value = load_example("intent.json")
        intent_value["constraints"].update({"effectful": True, "dry_run": False})
        provider = dict(load_example("providers.json")["providers"][0])
        provider["effectful"] = True
        compiled = IntentCompiler().compile(intent_value)
        resolution = CapabilityResolver().resolve(
            compiled, [provider], now=datetime(2026, 8, 26, 17, 20, tzinfo=timezone.utc),
            verified_proof_stages={"github-read": "SEMANTICALLY_VERIFIED"},
        )
        contract_two = runtime.build_execution_contract(
            compiled=compiled, resolution=resolution, action="status-two",
            payload={"scope": "second"},
        )
        jobs = [
            (contract_one, {"scope": "public"}, self.authority.issue(contract_one)),
            (contract_two, {"scope": "second"}, self.authority.issue(contract_two)),
        ]
        barrier = threading.Barrier(2)
        outcomes = []

        def worker(contract, payload, permit):
            barrier.wait()
            try:
                outcomes.append(runtime.execute(
                    contract=contract, payload=payload, formation_permit=permit
                ))
            except Exception as exc:
                outcomes.append(exc)

        threads = [threading.Thread(target=worker, args=job) for job in jobs]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(adapter.max_concurrent, 1)
        self.assertEqual(sum(isinstance(item, dict) for item in outcomes), 1)

    def test_persistence_failure_marks_unknown_and_blocks_retry(self):
        adapter = CountingAdapter("github-read", effectful=True)
        runtime, _, contract = self.prepared_runtime(effectful=True, adapter=adapter)
        permit = self.authority.issue(contract)
        original = self.store.complete_execution

        def fail_completion(**kwargs):
            raise OSError("simulated persistence failure")

        self.store.complete_execution = fail_completion  # type: ignore[method-assign]
        with self.assertRaises(OSError):
            runtime.execute(contract=contract, payload={"scope": "public"}, formation_permit=permit)
        self.store.complete_execution = original  # type: ignore[method-assign]
        retry_permit = self.authority.issue(contract)
        with self.assertRaisesRegex(RuntimeError, "ambiguous"):
            runtime.execute(
                contract=contract, payload={"scope": "public"}, formation_permit=retry_permit
            )
        self.assertEqual(adapter.calls, 1)

    def test_adapter_secret_result_is_not_persisted(self):
        adapter = CountingAdapter("github-read", effectful=True, secret=True)
        runtime, _, contract = self.prepared_runtime(effectful=True, adapter=adapter)
        with self.assertRaisesRegex(ValueError, "sensitive material"):
            runtime.execute(
                contract=contract, payload={"scope": "public"},
                formation_permit=self.authority.issue(contract),
            )
        journal = self.store.execution_result(contract.idempotency_key)
        self.assertEqual(journal["state"], "UNKNOWN")
        self.assertIsNone(journal["result"])

    def test_runtime_rejects_sensitive_payload_before_contract(self):
        runtime, _, contract = self.prepared_runtime()
        with self.assertRaisesRegex(ValueError, "sensitive material"):
            runtime.execute(
                contract=contract,
                payload={"authorization": "Bearer abcdefghijklmnopqrstuvwxyz"},
                formation_permit="unused",
            )

    def test_health_never_claims_provider_runtime_or_ignores_blockers(self):
        health = FabricRuntime(self.store).health()
        self.assertEqual(health["state"], "READY_LOCAL_NO_EXECUTION")
        self.assertFalse(health["provider_runtime_proven"])
        self.assertFalse(health["durable_autonomy_proven"])
        Reconciler(self.store).plan(
            load_example("desired_state.json"),
            now=datetime(2026, 8, 26, 17, 20, tzinfo=timezone.utc),
        )
        degraded = FabricRuntime(self.store).health()
        self.assertEqual(degraded["state"], "DEGRADED_LOCAL")
        self.assertFalse(degraded["completion_claim_allowed"])


if __name__ == "__main__":
    unittest.main()

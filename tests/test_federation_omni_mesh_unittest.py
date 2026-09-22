import json
from pathlib import Path
import tempfile
import unittest

from federation_omni_mesh_v1 import (
    AtomicJsonFileLedgerStore,
    DeliveryLedger,
    DeliveryReceipt,
    MeshControlPlane,
    MeshEnvelope,
    MeshRouter,
    MeshTelemetryWindow,
    NodeDescriptor,
)
from federation_omni_mesh_v1.provider_preflight import (
    CommandResult,
    build_identity_receipt,
)
from federation_omni_mesh_v1.telemetry import synthetic_scale_probe


def make_node(node_id: str, **overrides) -> NodeDescriptor:
    data = {
        "node_id": node_id,
        "name": node_id,
        "node_type": "SYSTEM",
        "provider": "FEDERATION",
        "capabilities": ("SYNC",),
        "authority_ceiling": "A2_REVERSIBLE_EXTERNAL",
        "privacy_ceiling": "P2_PRIVATE",
        "adapter": f"adapter:{node_id}",
    }
    data.update(overrides)
    return NodeDescriptor(**data)


def make_envelope(**overrides) -> MeshEnvelope:
    data = {
        "event_id": "EV-1",
        "event_type": "STATE",
        "source": "SOVARA",
        "topic": "state.v1",
        "idempotency_key": "IDEMP-1",
        "correlation_id": "CORR-1",
        "capability_required": "SYNC",
        "payload": {"state": "ACTIVE"},
    }
    data.update(overrides)
    return MeshEnvelope(**data)


class OmniMeshHostedAdmissionTests(unittest.TestCase):
    def test_unknown_authority_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unknown classification"):
            make_node("A", authority_ceiling="UNKNOWN")

    def test_descriptor_collision_requires_hash_bound_supersession(self):
        old = make_node("A")
        router = MeshRouter([old])
        with self.assertRaisesRegex(ValueError, "replacement version"):
            router.register(make_node("A", reliability=0.5))
        replacement = make_node(
            "A",
            reliability=0.5,
            descriptor_version=2,
            supersedes_descriptor_hash=old.descriptor_hash,
        )
        router.register(replacement)
        self.assertEqual(router.node("A"), replacement)

    def test_read_only_receipt_accepts_no_delta(self):
        receipt = DeliveryReceipt(
            event_id="EV-1",
            target_node="A",
            status="SEMANTICALLY_VERIFIED",
            transport_ok=True,
            semantic_match=True,
            readback_present=True,
            state_changed=False,
            expected_state_change=False,
        )
        self.assertTrue(receipt.verified)
        self.assertEqual(
            MeshControlPlane.promotion_gate(receipt),
            "VERIFIED_COMPLETE",
        )

    def test_unexpected_read_only_mutation_fails(self):
        receipt = DeliveryReceipt(
            event_id="EV-1",
            target_node="A",
            status="SEMANTICALLY_VERIFIED",
            transport_ok=True,
            semantic_match=True,
            readback_present=True,
            state_changed=True,
            expected_state_change=False,
        )
        self.assertEqual(
            MeshControlPlane.promotion_gate(receipt),
            "UNEXPECTED_STATE_CHANGE",
        )

    def test_crash_resume_only_reissues_unfinished_receivers(self):
        plane = MeshControlPlane(
            MeshRouter([make_node("A"), make_node("B")]),
            DeliveryLedger(),
        )
        plane.publish(make_envelope())
        plane.ledger.record_receipt(
            DeliveryReceipt(
                event_id="EV-1",
                target_node="A",
                status="SEMANTICALLY_VERIFIED",
                transport_ok=True,
                semantic_match=True,
                readback_present=True,
                state_changed=True,
            )
        )
        restored = DeliveryLedger.from_snapshot(
            plane.ledger.snapshot()
        )
        resumed = MeshControlPlane(
            MeshRouter([make_node("A"), make_node("B")]),
            restored,
        ).resume_incomplete(make_envelope())
        self.assertEqual(
            [route.node_id for route in resumed["routes"]],
            ["B"],
        )

    def test_secret_reference_allowed_but_raw_value_rejected(self):
        make_envelope(
            payload={
                "secret_ref": (
                    "projects/p/secrets/key/versions/latest"
                )
            }
        ).validate()
        with self.assertRaisesRegex(ValueError, "raw secret-like"):
            make_envelope(
                payload={
                    "configuration": (
                        "Bearer abcdefghijklmnopqrstuvwxyz"
                    )
                }
            ).validate()

    def test_stale_and_unbound_nodes_are_not_routable(self):
        router = MeshRouter(
            [
                make_node("A", health="STALE"),
                make_node("B", adapter="UNBOUND"),
                make_node("C"),
            ]
        )
        self.assertEqual(
            [route.node_id for route in router.route(make_envelope())],
            ["C"],
        )

    def test_unknown_cost_cannot_look_like_zero(self):
        receipt = DeliveryReceipt(
            event_id="EV-1",
            target_node="A",
            status="SEMANTICALLY_VERIFIED",
            transport_ok=True,
            semantic_match=True,
            readback_present=True,
            state_changed=True,
            trace_id="trace",
            latency_ms=1,
            attempt_count=1,
            incremental_cost_units=None,
            owner_action_count=0,
            failure_domain="cell-1",
        )
        window = MeshTelemetryWindow([receipt])
        self.assertIsNone(
            window.summary().total_incremental_cost_units
        )
        self.assertIn(
            "COST_TELEMETRY_UNKNOWN",
            window.evaluate_targets(
                max_p95_latency_ms=100,
                max_attempt_count=2,
            ),
        )

    def test_atomic_store_detects_tampering_and_cas_conflict(self):
        ledger = DeliveryLedger()
        ledger.admit(make_envelope())
        ledger.register_targets("EV-1", ["A"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            store = AtomicJsonFileLedgerStore(path)
            first = store.save(ledger.snapshot())
            with self.assertRaisesRegex(
                ValueError, "compare-and-set"
            ):
                store.save(
                    ledger.snapshot(),
                    expected_current_sha256="0" * 64,
                )
            content = json.loads(path.read_text(encoding="utf-8"))
            content["snapshot"]["tampered"] = True
            path.write_text(json.dumps(content), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                store.load()
            self.assertEqual(len(first.snapshot_sha256), 64)

    def test_provider_preflight_is_read_only_and_no_git(self):
        project_id = "example-project"
        project_number = "123456789012"
        deployer = (
            "deployer@example-project.iam.gserviceaccount.com"
        )
        provider = (
            "projects/123456789012/locations/global/"
            "workloadIdentityPools/pool/providers/provider"
        )
        commands = []

        def runner(args):
            commands.append(tuple(args))
            command = " ".join(args)
            if "auth list" in command:
                value = [{"account": deployer}]
            elif "projects describe" in command:
                value = {
                    "projectId": project_id,
                    "projectNumber": project_number,
                    "lifecycleState": "ACTIVE",
                }
            elif "services list" in command:
                value = [
                    {
                        "config": {
                            "name": "run.googleapis.com"
                        },
                        "state": "ENABLED",
                    }
                ]
            else:
                value = {}
            return CommandResult(True, 0, json.dumps(value), "")

        receipt = build_identity_receipt(
            project_id=project_id,
            expected_project_number=project_number,
            wif_provider=provider,
            deployer_service_account=deployer,
            required_apis=["run.googleapis.com"],
            runner=runner,
        )
        self.assertEqual(
            receipt["classification"],
            "PROVIDER_IDENTITY_PREFLIGHT_VERIFIED",
        )
        self.assertFalse(receipt["mutation_attempted"])
        command_text = "\n".join(" ".join(c) for c in commands)
        self.assertNotIn("git push", command_text)
        self.assertNotIn("secrets versions access", command_text)

    def test_scale_probe_labels_routability_not_capacity(self):
        result = synthetic_scale_probe(
            node_count=5000,
            failure_domain_count=50,
        )
        self.assertTrue(result.all_nodes_routable)
        self.assertEqual(
            result.measurement_kind,
            "IN_MEMORY_ROUTABILITY_ONLY",
        )


if __name__ == "__main__":
    unittest.main()

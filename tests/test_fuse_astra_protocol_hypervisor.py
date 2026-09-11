import unittest

from fuse_astra_protocol_awareness.hypervisor import (
    CommunicationRequirement,
    DeliverySemantic,
    EndpointContract,
    FlowWindow,
    HypervisorError,
    ProtocolDriftDetector,
    ProtocolHypervisor,
    ReplayProtector,
    SchemaContract,
    SessionMode,
    compare_schema,
    Compatibility,
)


class ProtocolHypervisorTests(unittest.TestCase):
    def setUp(self):
        self.schema = SchemaContract(
            "agent.task",
            "1",
            required_fields=("task_id", "input"),
            optional_fields=("deadline",),
            semantic_features=("task_lifecycle", "streaming", "cancellation"),
        )
        self.a2a = EndpointContract(
            endpoint_id="agent-a",
            protocol_id="PROTO.A2A",
            version="1.0",
            transport="grpc+tls",
            capabilities=("task", "stream", "cancel"),
            auth_schemes=("spiffe-mtls", "oauth2"),
            schema=self.schema,
            session_mode=SessionMode.STATEFUL,
            delivery=DeliverySemantic.EFFECTIVELY_ONCE,
            max_inflight=32,
            supports_idempotency=True,
            supports_resume=True,
            supports_deadlines=True,
        )

    def test_schema_fingerprint_is_stable(self):
        equivalent = SchemaContract(
            "agent.task",
            "1",
            required_fields=("input", "task_id"),
            optional_fields=("deadline",),
            semantic_features=("cancellation", "streaming", "task_lifecycle"),
        )
        self.assertEqual(self.schema.fingerprint, equivalent.fingerprint)
        self.assertEqual(compare_schema(self.schema, equivalent), Compatibility.EXACT)

    def test_missing_required_schema_field_is_incompatible(self):
        observed = SchemaContract(
            "agent.task",
            "1",
            required_fields=("task_id",),
            semantic_features=self.schema.semantic_features,
        )
        self.assertEqual(compare_schema(self.schema, observed), Compatibility.INCOMPATIBLE)

    def test_hypervisor_prefers_semantically_complete_route(self):
        weak = EndpointContract(
            endpoint_id="agent-b",
            protocol_id="PROTO.A2A",
            version="1.0",
            transport="https",
            capabilities=("task",),
            auth_schemes=("oauth2",),
            schema=SchemaContract(
                "agent.task",
                "1",
                required_fields=("task_id", "input"),
                semantic_features=("task_lifecycle",),
            ),
            delivery=DeliverySemantic.AT_LEAST_ONCE,
            max_inflight=100,
            supports_idempotency=False,
            supports_resume=False,
            supports_deadlines=False,
        )
        req = CommunicationRequirement(
            required_capabilities=("task", "stream", "cancel"),
            required_semantic_features=("task_lifecycle", "streaming", "cancellation"),
            allowed_protocols=("PROTO.A2A",),
            required_auth_schemes=("spiffe-mtls",),
            minimum_delivery=DeliverySemantic.EFFECTIVELY_ONCE,
            require_idempotency=True,
            require_resume=True,
            require_deadlines=True,
            max_semantic_loss=0.0,
        )
        route = ProtocolHypervisor((weak, self.a2a)).select(
            req,
            identities={"agent-a": "spiffe://fuse/agent/a"},
        )
        self.assertEqual(route.endpoint.endpoint_id, "agent-a")
        self.assertEqual(route.loss_report.loss, 0.0)
        self.assertEqual(route.auth_binding.workload_identity, "spiffe://fuse/agent/a")

    def test_auth_requirement_fails_closed_without_identity(self):
        req = CommunicationRequirement(
            required_capabilities=("task",),
            required_auth_schemes=("spiffe-mtls",),
            max_semantic_loss=0.0,
        )
        with self.assertRaises(HypervisorError):
            ProtocolHypervisor((self.a2a,)).select(req)

    def test_delivery_downgrade_is_rejected(self):
        weaker = EndpointContract(
            endpoint_id="agent-weak",
            protocol_id="PROTO.A2A",
            version="1.0",
            transport="grpc+tls",
            capabilities=("task",),
            auth_schemes=("oauth2",),
            schema=self.schema,
            delivery=DeliverySemantic.AT_MOST_ONCE,
        )
        req = CommunicationRequirement(
            required_capabilities=("task",),
            minimum_delivery=DeliverySemantic.AT_LEAST_ONCE,
            max_semantic_loss=1.0,
        )
        with self.assertRaises(HypervisorError):
            ProtocolHypervisor((weaker,)).select(req)

    def test_replay_protector_blocks_duplicate_and_out_of_order_messages(self):
        guard = ReplayProtector()
        self.assertTrue(guard.accept(session_id="s1", message_id="m1", sequence=1, idempotency_key="effect-1"))
        self.assertFalse(guard.accept(session_id="s1", message_id="m2", sequence=2, idempotency_key="effect-1"))
        self.assertFalse(guard.accept(session_id="s1", message_id="m0", sequence=0, idempotency_key="effect-0"))
        self.assertTrue(guard.accept(session_id="s1", message_id="m3", sequence=3, idempotency_key="effect-3"))

    def test_flow_window_enforces_backpressure(self):
        flow = FlowWindow(2)
        flow.acquire()
        flow.acquire()
        self.assertTrue(flow.backpressured)
        with self.assertRaises(HypervisorError):
            flow.acquire()
        flow.release()
        self.assertFalse(flow.backpressured)

    def test_drift_detector_flags_capability_and_schema_loss(self):
        observed = EndpointContract(
            endpoint_id="agent-a",
            protocol_id="PROTO.A2A",
            version="1.1",
            transport="https",
            capabilities=("task", "stream"),
            auth_schemes=("oauth2",),
            schema=SchemaContract(
                "agent.task",
                "2",
                required_fields=("task_id", "input"),
                semantic_features=("task_lifecycle", "streaming"),
            ),
            delivery=DeliverySemantic.EFFECTIVELY_ONCE,
        )
        report = ProtocolDriftDetector.compare(self.a2a, observed)
        self.assertTrue(report.changed)
        self.assertTrue(report.version_changed)
        self.assertTrue(report.transport_changed)
        self.assertEqual(report.capabilities_removed, ("cancel",))
        self.assertEqual(report.auth_removed, ("spiffe-mtls",))
        self.assertTrue(report.schema_changed)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import io
import json
import unittest
from urllib import error as urlerror

from federation.fuse_serving_kernel_v1 import ServingLaneSpec
from federation.mission_ir import MissionIR
from federation.opa_policy_adapter_v1 import OPAEndpoint, OPAHTTPPolicyGateV1, mission_effect_input


def mission(effect_class: str = "BOUNDED_EFFECT") -> MissionIR:
    return MissionIR(
        mission_id="opa-mission",
        objective="Evaluate one FUSE mission effect through OPA",
        domain="FUSE",
        outcome_contract="Policy decision is evidence bound",
        source_frontier="test-main",
        privacy_class="PRIVATE",
        rights_state="OWNER_CONTROLLED",
        effect_class=effect_class,
        owner_approval_required=effect_class == "CONSEQUENTIAL_EFFECT",
        rollback_required=True,
        authority_requirements=("A1_INTERNAL",),
    )


def lane(effect_class: str = "BOUNDED_EFFECT") -> ServingLaneSpec:
    return ServingLaneSpec(
        lane_id="effect",
        action="publish",
        effect_class=effect_class,
        expected_target_state={"status": "ok"},
    )


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


class OPAHTTPPolicyGateTests(unittest.TestCase):
    def endpoint(self):
        return OPAEndpoint(
            base_url="http://127.0.0.1:8181",
            policy_ref="git:6413be028e18759266f03f88d6b551e95fda0136",
        )

    def input_factory(self, m: MissionIR, l: ServingLaneSpec):
        return mission_effect_input(
            m,
            l,
            identity_authority="A2_PROVIDER_REVERSIBLE",
            identity_effect="PROVIDER_REVERSIBLE",
        )

    def test_input_shape_matches_fkpf_rego_contract_without_inferred_approval(self):
        value = self.input_factory(mission(), lane())
        self.assertEqual(value["kind"], "mission_effect")
        self.assertEqual(value["mission"]["effect"], "PROVIDER_REVERSIBLE")
        self.assertEqual(value["mission"]["authority"], "A1_INTERNAL")
        self.assertFalse(value["owner_approval"])
        self.assertTrue(value["provider_readback_required"])
        self.assertTrue(value["independent_verification_required"])

    def test_opa_allow_produces_hash_bound_allow_receipt(self):
        captured = {}

        def opener(req, timeout):
            captured["url"] = req.full_url
            captured["body"] = json.loads(req.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse(b'{"result":true}')

        gate = OPAHTTPPolicyGateV1(
            self.endpoint(),
            input_factory=self.input_factory,
            opener=opener,
        )
        receipt = gate.authorize(mission=mission(), lane=lane())
        self.assertEqual(receipt.decision, "ALLOW")
        self.assertEqual(
            captured["url"],
            "http://127.0.0.1:8181/v1/data/federation/fkpf_omega_v3/allow",
        )
        self.assertEqual(captured["body"]["input"]["kind"], "mission_effect")
        receipt.validate()

    def test_opa_false_result_fails_closed(self):
        gate = OPAHTTPPolicyGateV1(
            self.endpoint(),
            input_factory=self.input_factory,
            opener=lambda req, timeout: FakeResponse(b'{"result":false}'),
        )
        receipt = gate.authorize(mission=mission(), lane=lane())
        self.assertEqual(receipt.decision, "DENY")
        self.assertEqual(receipt.reason, "OPA_POLICY_DENY")

    def test_opa_transport_failure_fails_closed(self):
        def opener(req, timeout):
            raise urlerror.URLError("offline")

        gate = OPAHTTPPolicyGateV1(
            self.endpoint(),
            input_factory=self.input_factory,
            opener=opener,
        )
        receipt = gate.authorize(mission=mission(), lane=lane())
        self.assertEqual(receipt.decision, "DENY")
        self.assertEqual(receipt.reason, "OPA_TRANSPORT_FAILURE")

    def test_secret_shaped_input_is_denied_before_transport(self):
        called = []

        def opener(req, timeout):
            called.append(True)
            return FakeResponse(b'{"result":true}')

        gate = OPAHTTPPolicyGateV1(
            self.endpoint(),
            input_factory=lambda m, l: {
                "kind": "mission_effect",
                "authorization": "Bearer should-never-leave-process",
            },
            opener=opener,
        )
        receipt = gate.authorize(mission=mission(), lane=lane())
        self.assertEqual(receipt.decision, "DENY")
        self.assertEqual(receipt.reason, "RAW_SECRET_SHAPE_FORBIDDEN")
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()

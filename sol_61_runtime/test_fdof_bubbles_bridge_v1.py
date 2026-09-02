from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

try:
    from .fdof_bubbles_bridge_v1 import (
        FDOFBubblesBridge,
        HOST_CAPABILITY,
        HOST_EXECUTOR_ID,
        HOST_TARGET,
        QUALIFICATION_MESSAGE,
        deterministic_local_qualification_receipt,
    )
    from .fdof_v1 import FederationDistributedOperatingFabric, RouteRequest
    from .sol_62_frontier_primitives import ConstraintError
    from .sol_62_runtime import Sol62Runtime
except ImportError:
    from fdof_bubbles_bridge_v1 import (
        FDOFBubblesBridge,
        HOST_CAPABILITY,
        HOST_EXECUTOR_ID,
        HOST_TARGET,
        QUALIFICATION_MESSAGE,
        deterministic_local_qualification_receipt,
    )
    from fdof_v1 import FederationDistributedOperatingFabric, RouteRequest
    from sol_62_frontier_primitives import ConstraintError
    from sol_62_runtime import Sol62Runtime


class FDOFBubblesBridgeV1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = Sol62Runtime(Path(self.tmp.name))
        self.fdof = FederationDistributedOperatingFabric(self.runtime)
        self.bridge = FDOFBubblesBridge(self.fdof)
        self.now = int(time.time())

    def tearDown(self):
        self.runtime.close()
        self.tmp.cleanup()

    def test_executor_registration_does_not_auto_promote_health(self):
        self.bridge.register_hosted_executor()
        state = self.fdof.health_state(HOST_EXECUTOR_ID, now_epoch=self.now)
        self.assertEqual("UNKNOWN", state["state"])
        self.assertEqual(HOST_CAPABILITY, self.bridge.hosted_executor_spec().capabilities[0])

    def test_qualification_command_reuses_read_only_bubbles_canary(self):
        self.bridge.register_hosted_executor()
        qualification = self.bridge.qualification_command()
        self.assertEqual(HOST_EXECUTOR_ID, qualification.executor_id)
        self.assertEqual("bubbles_command_bus", qualification.command["adapter_id"])
        self.assertEqual("canary", qualification.command["action"])
        self.assertEqual("READ", qualification.command["effect"])
        self.assertEqual(QUALIFICATION_MESSAGE, qualification.command["payload"]["message"])
        self.assertFalse(qualification.command["payload"]["external_effect"])

    def test_local_semantic_receipt_can_validate_but_is_not_hosted_proof(self):
        self.bridge.register_hosted_executor()
        qualification = self.bridge.qualification_command()
        receipt = deterministic_local_qualification_receipt(qualification.command)
        observation = self.bridge.health_from_receipt(
            receipt, observed_at_epoch=self.now, ttl_seconds=60
        )
        self.assertEqual("HOSTED_RUNTIME_IMMUTABLE_READBACK", observation.evidence_class)
        self.assertFalse(observation.metadata["provider_effect_proven"])
        self.assertFalse(observation.metadata["repository_write_authority_proven"])

    def test_valid_receipt_admission_makes_only_registered_read_capability_routable(self):
        self.bridge.register_hosted_executor()
        qualification = self.bridge.qualification_command()
        receipt = deterministic_local_qualification_receipt(qualification.command)
        self.bridge.admit_hosted_receipt(receipt, observed_at_epoch=self.now, ttl_seconds=60)
        route = self.fdof.route(
            RouteRequest(
                route_id="route-host-read-1",
                mission_id="mission-host-read-1",
                transition_id="transition-host-read-1",
                operation=HOST_CAPABILITY,
                target=HOST_TARGET,
                required_capabilities=(HOST_CAPABILITY,),
                authority_ceiling="A1_INTERNAL",
                allowed_cost_classes=("C0_INCLUDED_FREE",),
                require_readback=True,
                require_rollback=False,
                consequential=False,
            ),
            now_epoch=self.now,
        )
        self.assertEqual(HOST_EXECUTOR_ID, route["executor_id"])
        with self.assertRaises(ConstraintError):
            self.fdof.route(
                RouteRequest(
                    route_id="route-host-write-1",
                    mission_id="mission-host-write-1",
                    transition_id="transition-host-write-1",
                    operation="REPOSITORY_WRITE",
                    target=HOST_TARGET,
                    required_capabilities=("REPOSITORY_WRITE",),
                    authority_ceiling="A1_INTERNAL",
                    allowed_cost_classes=("C0_INCLUDED_FREE",),
                    require_readback=True,
                    require_rollback=True,
                    consequential=True,
                ),
                now_epoch=self.now,
            )

    def test_tampered_receipt_fails_closed(self):
        self.bridge.register_hosted_executor()
        qualification = self.bridge.qualification_command()
        receipt = deterministic_local_qualification_receipt(qualification.command)
        receipt = {**receipt, "execution": {**receipt["execution"], "kind": "OTHER"}}
        with self.assertRaises(ConstraintError):
            self.bridge.admit_hosted_receipt(receipt, observed_at_epoch=self.now)

    def test_stale_hosted_health_stops_routing(self):
        self.bridge.register_hosted_executor()
        qualification = self.bridge.qualification_command()
        receipt = deterministic_local_qualification_receipt(qualification.command)
        self.bridge.admit_hosted_receipt(receipt, observed_at_epoch=self.now, ttl_seconds=5)
        self.assertEqual("STALE", self.fdof.health_state(HOST_EXECUTOR_ID, now_epoch=self.now + 6)["state"])
        with self.assertRaises(ConstraintError):
            self.fdof.route(
                RouteRequest(
                    route_id="route-stale",
                    mission_id="mission-stale",
                    transition_id="transition-stale",
                    operation=HOST_CAPABILITY,
                    target=HOST_TARGET,
                    required_capabilities=(HOST_CAPABILITY,),
                    authority_ceiling="A1_INTERNAL",
                    allowed_cost_classes=("C0_INCLUDED_FREE",),
                    require_readback=True,
                    require_rollback=False,
                    consequential=False,
                ),
                now_epoch=self.now + 6,
            )


if __name__ == "__main__":
    unittest.main()

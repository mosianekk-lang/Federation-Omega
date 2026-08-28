from datetime import datetime, timedelta, timezone
import unittest

from federation_automation_gateway.contracts import Command, EffectClass, MissionLease
from federation_automation_gateway.policy import evaluate

TZ = timezone(timedelta(hours=2))
NOW = datetime(2026, 8, 27, 19, 40, tzinfo=TZ)


def command(
    effect: EffectClass,
    *,
    action: str = "GCP_GET_PROJECT",
    target: str = "sov-hybrid-suite/project",
    engine: str = "SUPERIOR_LOGIC",
    lease_id: str = "L1",
) -> Command:
    return Command(
        command_id="C1",
        created_at_sast=NOW.isoformat(),
        requested_by_chat="chat-1",
        engine=engine,
        mission_id="M1",
        lease_id=lease_id,
        adapter_id="google_cloud",
        action=action,
        effect_class=effect,
        target_alias=target,
        payload={},
        idempotency_key="IDEM-1",
    )


def mission_lease(**overrides) -> MissionLease:
    data = dict(
        lease_id="L1",
        state="ACTIVE",
        scope={},
        allowed_effects=(
            EffectClass.CONTROL_PLANE_WRITE.value,
            EffectClass.PROVIDER_ADMIN_WRITE.value,
        ),
        allowed_targets=("sov-hybrid-suite/*",),
        issued_by="USER:CURRENT_DIRECTIVE",
        issued_at_sast=NOW.isoformat(),
        expires_at_sast=(NOW + timedelta(hours=2)).isoformat(),
        max_commands=100,
        commands_used=0,
        rollback_required=True,
        readback_required=True,
    )
    data.update(overrides)
    return MissionLease(**data)


class FederationAutomationPolicyTests(unittest.TestCase):
    def test_read_is_autonomous(self):
        decision = evaluate(command(EffectClass.READ, lease_id=""), None, now=NOW)
        self.assertEqual(decision.state, "ALLOW")
        self.assertEqual(decision.authority_mode, "AUTO_READ")
        self.assertFalse(decision.use_elevated_identity)

    def test_lab_write_is_autonomous_but_proof_gated(self):
        decision = evaluate(
            command(EffectClass.LAB_WRITE, action="LAB_BUILD", lease_id=""),
            None,
            now=NOW,
        )
        self.assertEqual(decision.state, "ALLOW")
        self.assertTrue(decision.rollback_required)
        self.assertTrue(decision.readback_required)

    def test_provider_admin_requires_mission_lease(self):
        denied = evaluate(command(EffectClass.PROVIDER_ADMIN_WRITE), None, now=NOW)
        self.assertEqual(denied.state, "DENY")
        allowed = evaluate(
            command(EffectClass.PROVIDER_ADMIN_WRITE),
            mission_lease(),
            now=NOW,
        )
        self.assertEqual(allowed.state, "ALLOW")
        self.assertTrue(allowed.use_elevated_identity)

    def test_expired_lease_is_denied(self):
        decision = evaluate(
            command(EffectClass.PROVIDER_ADMIN_WRITE),
            mission_lease(expires_at_sast=(NOW - timedelta(seconds=1)).isoformat()),
            now=NOW,
        )
        self.assertEqual(decision.state, "DENY")

    def test_communications_never_use_reusable_lease(self):
        decision = evaluate(
            command(EffectClass.COMMUNICATION_WRITE, action="SEND_EMAIL"),
            mission_lease(),
            now=NOW,
        )
        self.assertEqual(decision.state, "DENY")
        self.assertEqual(decision.authority_mode, "ONE_USE_EXPLICIT")

    def test_destructive_never_uses_reusable_lease(self):
        decision = evaluate(
            command(EffectClass.DESTRUCTIVE_WRITE, action="DELETE_SERVICE"),
            mission_lease(),
            now=NOW,
        )
        self.assertEqual(decision.state, "DENY")
        self.assertEqual(decision.authority_mode, "ONE_USE_EXPLICIT")

    def test_target_scope_is_enforced(self):
        decision = evaluate(
            command(EffectClass.PROVIDER_ADMIN_WRITE, target="other-project/x"),
            mission_lease(),
            now=NOW,
        )
        self.assertEqual(decision.state, "DENY")

    def test_command_budget_is_enforced(self):
        decision = evaluate(
            command(EffectClass.PROVIDER_ADMIN_WRITE),
            mission_lease(max_commands=2, commands_used=2),
            now=NOW,
        )
        self.assertEqual(decision.state, "DENY")


if __name__ == "__main__":
    unittest.main()

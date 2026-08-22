import unittest

from sovara_operator_adapter.cfbe_sovereign_core import (
    AdapterCapability,
    Authority,
    CFBEEvent,
    MissionRequirement,
    SovereignCoreError,
    VerificationReceipt,
    failover_route,
    platform_independence_state,
    portable_state_projection,
    rank_routes,
    require_independent_verification,
    select_route,
)


def adapter(
    adapter_id,
    surface_class,
    *,
    provider_state="PROVIDER_VERIFIED_SCOPED",
    semantic=True,
    presence="CONNECTED_VERIFIED",
    freshness="CURRENT",
    authority=Authority.PROVIDER_ACTION,
    capabilities=frozenset({"benchmark.read", "state.write"}),
):
    return AdapterCapability(
        adapter_id=adapter_id,
        surface_class=surface_class,
        capabilities=capabilities,
        authority_ceiling=authority,
        presence_state=presence,
        provider_execution_state=provider_state,
        freshness_state=freshness,
        cost_class="INCLUDED",
        reversible=True,
        semantic_readback=semantic,
        proof_ref=f"proof:{adapter_id}",
        truth_boundary="bounded test adapter",
    )


class CFBESovereignCoreTests(unittest.TestCase):
    def setUp(self):
        self.mission = MissionRequirement(
            objective_id="OBJ-1",
            capability="benchmark.read",
            authority_required=Authority.A0_READ,
            provider_execution_required=True,
            included_cost_only=True,
        )
        self.chatgpt = adapter("chatgpt", "CHATGPT")
        self.github = adapter("github", "GITHUB_ACTIONS")
        self.google = adapter("google", "GOOGLE_RUNTIME")

    def test_route_choice_is_not_host_bound(self):
        with_chat = rank_routes(self.mission, [self.chatgpt, self.github, self.google])
        without_chat = rank_routes(self.mission, [self.github, self.google])
        self.assertEqual([r.adapter_id for r in without_chat], ["github", "google"])
        self.assertIn("github", [r.adapter_id for r in with_chat])

    def test_chatgpt_loss_does_not_destroy_objective_when_alternative_exists(self):
        chosen = select_route(self.mission, [self.github, self.google])
        self.assertIn(chosen.surface_class, {"GITHUB_ACTIONS", "GOOGLE_RUNTIME"})

    def test_failover_excludes_failed_surface(self):
        chosen = failover_route(
            self.mission,
            [self.chatgpt, self.github, self.google],
            failed_adapter_ids={"chatgpt", "github"},
        )
        self.assertEqual(chosen.adapter_id, "google")

    def test_stale_adapter_is_not_eligible(self):
        stale = adapter("stale", "GOOGLE_RUNTIME", freshness="STALE")
        routes = rank_routes(self.mission, [stale, self.github])
        self.assertEqual([route.adapter_id for route in routes], ["github"])

    def test_control_plane_is_not_provider_execution(self):
        control = adapter(
            "control",
            "GOOGLE_CONTROL_PLANE",
            provider_state="CONTROL_PLANE_ONLY",
        )
        routes = rank_routes(self.mission, [control])
        self.assertEqual(routes, ())

    def test_executor_cannot_self_verify(self):
        receipt = VerificationReceipt(
            action_id="A1",
            action_fingerprint="sha256:abc",
            executor_adapter_id="github",
            verifier_adapter_id="github",
            semantic_readback=True,
            result_state="PASS",
            proof_ref="proof:self",
        )
        with self.assertRaises(SovereignCoreError):
            require_independent_verification(
                receipt, expected_action_fingerprint="sha256:abc"
            )

    def test_independent_semantic_verification_passes(self):
        receipt = VerificationReceipt(
            action_id="A1",
            action_fingerprint="sha256:abc",
            executor_adapter_id="github",
            verifier_adapter_id="drive",
            semantic_readback=True,
            result_state="VERIFIED",
            proof_ref="proof:drive",
        )
        require_independent_verification(receipt, expected_action_fingerprint="sha256:abc")

    def test_raw_secret_fields_are_rejected(self):
        with self.assertRaises(SovereignCoreError):
            CFBEEvent(
                event_id="E1",
                event_type="TEST",
                source_adapter_id="github",
                payload={"api_key": "not-allowed"},
                proof_ref="proof:test",
            )

    def test_secret_reference_is_allowed(self):
        event = CFBEEvent(
            event_id="E2",
            event_type="TEST",
            source_adapter_id="google",
            payload={"secret_reference": "provider-managed-handle"},
            proof_ref="proof:test",
        )
        self.assertTrue(event.fingerprint.startswith("sha256:"))

    def test_platform_independence_maturity_is_proof_bound(self):
        adapters = [self.chatgpt, self.github, self.google]
        self.assertEqual(platform_independence_state(adapters), "CONTROL_PLANE_NEUTRAL")
        self.assertEqual(
            platform_independence_state(adapters, ["github"]),
            "CORE_PORTABLE_NON_CHATGPT_PROVEN",
        )
        self.assertEqual(
            platform_independence_state(adapters, ["github", "google"]),
            "MULTI_SURFACE_EXECUTION_PROVEN",
        )
        self.assertEqual(
            platform_independence_state(
                adapters, ["github", "google"], failover_semantic_proof=True
            ),
            "SURFACE_INDEPENDENT_OPERATIONAL",
        )

    def test_projection_is_deterministic_across_adapter_order(self):
        first = portable_state_projection(
            state={"objective": "benchmark"}, adapters=[self.github, self.google]
        )
        second = portable_state_projection(
            state={"objective": "benchmark"}, adapters=[self.google, self.github]
        )
        self.assertEqual(first["state_fingerprint"], second["state_fingerprint"])


if __name__ == "__main__":
    unittest.main()

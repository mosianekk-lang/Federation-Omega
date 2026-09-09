from __future__ import annotations

import unittest

from federation.fuse_ai_bot_multistream_fabric_v1 import (
    FUSEAIBotMultiStreamFabric,
    PathOutcome,
    PathState,
    StreamPath,
)
from formation_omega.autonomic_fabric import AuthorityCeiling


def route(path_id: str, stream_id: str, *, group: str | None = None, domain: str = "", leverage: float = 0.8,
          authority: AuthorityCeiling = AuthorityCeiling.A1_INTERNAL, external: bool = False) -> StreamPath:
    return StreamPath(
        path_id=path_id,
        stream_id=stream_id,
        objective=f"Close {stream_id} through {path_id}",
        independent_group=group or path_id,
        closure_leverage=leverage,
        information_gain=0.8,
        success_probability=0.8,
        reversibility=0.9,
        cost=0.1,
        risk=0.1,
        latency=0.1,
        mutation_domain=domain,
        authority_ceiling=authority,
        external_effect=external,
        evidence_refs=(f"evidence:{path_id}",),
    )


class FUSEAIBotMultiStreamFabricTests(unittest.TestCase):
    def test_formation_swarm_roles_become_truth_bounded_logical_bots(self) -> None:
        fabric = FUSEAIBotMultiStreamFabric(max_parallel=2)
        plan = fabric.plan(
            mission_id="M1",
            objective="Close source and host proof",
            required_streams=("SOURCE", "HOST"),
            paths=(route("source-a", "SOURCE"), route("host-a", "HOST")),
        )
        self.assertEqual(7, len(plan.logical_bot_cells))
        self.assertEqual(
            {"BUILDER", "FALSIFIER", "EVIDENCE", "ROUTE", "SENTINEL", "RECOVERY", "WITNESS"},
            {bot.role for bot in plan.logical_bot_cells},
        )
        self.assertTrue(all(bot.logical_only for bot in plan.logical_bot_cells))
        self.assertTrue(all(not bot.may_self_certify for bot in plan.logical_bot_cells))
        self.assertEqual(0, plan.provider_native_worker_count)

    def test_shared_mutation_domain_is_serialized_while_independent_stream_can_run(self) -> None:
        fabric = FUSEAIBotMultiStreamFabric(max_parallel=3)
        plan = fabric.plan(
            mission_id="M2",
            objective="Run source repair and hosted proof safely",
            required_streams=("SOURCE", "HOST"),
            paths=(
                route("source-best", "SOURCE", domain="github-write", leverage=0.95),
                route("source-alt", "SOURCE", domain="github-write", leverage=0.70),
                route("host-read", "HOST", domain="provider-read", leverage=0.85),
            ),
        )
        selected = set(plan.selected_wave)
        self.assertEqual(1, len(selected & {"source-best", "source-alt"}))
        self.assertIn("host-read", selected)

    def test_authority_ceiling_holds_effectful_high_authority_path(self) -> None:
        fabric = FUSEAIBotMultiStreamFabric(authority_ceiling=AuthorityCeiling.A1_INTERNAL)
        plan = fabric.plan(
            mission_id="M3",
            objective="Keep consequential path held",
            required_streams=("SAFE",),
            paths=(
                route(
                    "effectful",
                    "SAFE",
                    authority=AuthorityCeiling.A2_BOUNDED_EFFECT,
                    external=True,
                ),
                route("read-only", "SAFE", leverage=0.5),
            ),
        )
        held = dict(plan.held_paths)
        self.assertEqual("AUTHORITY_CEILING_EXCEEDED", held["effectful"])
        self.assertNotIn("effectful", plan.selected_wave)

    def test_failed_path_does_not_freeze_alternate_path_or_other_stream(self) -> None:
        fabric = FUSEAIBotMultiStreamFabric(max_parallel=3)
        plan = fabric.plan(
            mission_id="M4",
            objective="Converge CI and host binding through alternate routes",
            required_streams=("CI", "HOST"),
            paths=(
                route("ci-primary", "CI", group="ci-provider-a"),
                route("ci-alt", "CI", group="ci-provider-b"),
                route("host-a", "HOST", group="host-provider-a"),
            ),
        )
        witness = fabric.reconcile(
            plan,
            (
                PathOutcome(
                    "ci-primary", "CI", "ci-provider-a", PathState.FAILED,
                    failure_fingerprint="CI_PRIMARY_IMPORT_CONTRACT",
                    retry_after_predicate="TEST_RUNNER_CONTRACT_CHANGED",
                ),
                PathOutcome(
                    "ci-alt", "CI", "ci-provider-b", PathState.VERIFIED,
                    evidence_refs=("airlock:pass",),
                ),
                PathOutcome(
                    "host-a", "HOST", "host-provider-a", PathState.VERIFIED,
                    evidence_refs=("host:readback",),
                ),
            ),
        )
        self.assertTrue(witness.completion_allowed)
        self.assertEqual("OMEGA_MULTIPATH_MULTISTREAM_VERIFIED", witness.state)
        self.assertTrue(any("CI_PRIMARY_IMPORT_CONTRACT" in item for item in witness.negative_knowledge))
        self.assertIn("ci-primary:TEST_RUNNER_CONTRACT_CHANGED", witness.retryable_failures)

    def test_held_path_outcome_cannot_satisfy_stream(self) -> None:
        fabric = FUSEAIBotMultiStreamFabric(
            authority_ceiling=AuthorityCeiling.A1_INTERNAL,
        )
        plan = fabric.plan(
            mission_id="M4-HELD",
            objective="Reject proof claimed by an authority-held path",
            required_streams=("SOURCE",),
            paths=(
                route(
                    "source-high-authority",
                    "SOURCE",
                    authority=AuthorityCeiling.A2_BOUNDED_EFFECT,
                ),
                route("source-external-effect", "SOURCE", external=True),
            ),
        )
        self.assertEqual((), plan.selected_wave)
        self.assertEqual(
            {
                "source-high-authority": "AUTHORITY_CEILING_EXCEEDED",
                "source-external-effect": "EXTERNAL_EFFECT_NOT_AUTHORIZED",
            },
            dict(plan.held_paths),
        )
        for path_id in ("source-high-authority", "source-external-effect"):
            with self.subTest(path_id=path_id), self.assertRaisesRegex(
                ValueError, "OUTCOME_FROM_HELD_PATH"
            ):
                fabric.reconcile(
                    plan,
                    (
                        PathOutcome(
                            path_id,
                            "SOURCE",
                            path_id,
                            PathState.VERIFIED,
                            evidence_refs=("self:claimed-proof",),
                        ),
                    ),
                )

    def test_declared_alternate_requires_selected_path_failure(self) -> None:
        fabric = FUSEAIBotMultiStreamFabric(max_parallel=2)
        plan = fabric.plan(
            mission_id="M4-ALT-GATE",
            objective="Use an alternate only after the selected route fails",
            required_streams=("CI", "HOST"),
            paths=(
                route("ci-primary", "CI", group="ci-a", domain="ci-read", leverage=0.95),
                route("ci-alternate", "CI", group="ci-b", domain="ci-read", leverage=0.70),
                route("host-primary", "HOST", group="host-a", domain="host-read", leverage=0.90),
            ),
        )
        self.assertIn(("ci-alternate", "CI", "ci-primary"), plan.declared_alternates)
        with self.assertRaisesRegex(ValueError, "ALTERNATE_REQUIRES_SELECTED_PATH_FAILURE"):
            fabric.reconcile(
                plan,
                (
                    PathOutcome(
                        "ci-alternate",
                        "CI",
                        "ci-b",
                        PathState.VERIFIED,
                        evidence_refs=("proof:alternate",),
                    ),
                ),
            )

    def test_declared_alternate_is_admissible_after_selected_path_failure(self) -> None:
        fabric = FUSEAIBotMultiStreamFabric(max_parallel=2)
        plan = fabric.plan(
            mission_id="M4-ALT-RECOVERY",
            objective="Recover one failed selected route through its declared alternate",
            required_streams=("CI", "HOST"),
            paths=(
                route("ci-primary", "CI", group="ci-a", domain="ci-read", leverage=0.95),
                route("ci-alternate", "CI", group="ci-b", domain="ci-read", leverage=0.70),
                route("host-primary", "HOST", group="host-a", domain="host-read", leverage=0.90),
            ),
        )
        witness = fabric.reconcile(
            plan,
            (
                PathOutcome(
                    "ci-primary",
                    "CI",
                    "ci-a",
                    PathState.FAILED,
                    failure_fingerprint="CI_PRIMARY_FAILED",
                    retry_after_predicate="CI_SOURCE_CHANGED",
                ),
                PathOutcome(
                    "ci-alternate",
                    "CI",
                    "ci-b",
                    PathState.VERIFIED,
                    evidence_refs=("proof:alternate",),
                ),
                PathOutcome(
                    "host-primary",
                    "HOST",
                    "host-a",
                    PathState.VERIFIED,
                    evidence_refs=("proof:host",),
                ),
            ),
        )
        self.assertTrue(witness.completion_allowed)
        self.assertEqual("OMEGA_MULTIPATH_MULTISTREAM_VERIFIED", witness.state)

    def test_required_corroboration_can_demand_two_independent_path_groups(self) -> None:
        fabric = FUSEAIBotMultiStreamFabric(corroboration_required_per_stream=2)
        plan = fabric.plan(
            mission_id="M5",
            objective="Require independent proof corroboration",
            required_streams=("PROOF",),
            paths=(
                route("proof-a", "PROOF", group="provider-a"),
                route("proof-b", "PROOF", group="provider-b"),
            ),
        )
        one = fabric.reconcile(
            plan,
            (PathOutcome("proof-a", "PROOF", "provider-a", PathState.VERIFIED, evidence_refs=("p:a",)),),
        )
        self.assertFalse(one.completion_allowed)
        two = fabric.reconcile(
            plan,
            (
                PathOutcome("proof-a", "PROOF", "provider-a", PathState.VERIFIED, evidence_refs=("p:a",)),
                PathOutcome("proof-b", "PROOF", "provider-b", PathState.VERIFIED, evidence_refs=("p:b",)),
            ),
        )
        self.assertTrue(two.completion_allowed)

    def test_critical_path_conflict_fails_closed(self) -> None:
        fabric = FUSEAIBotMultiStreamFabric()
        plan = fabric.plan(
            mission_id="M6",
            objective="Detect contradictory paths",
            required_streams=("STATE",),
            paths=(route("state-a", "STATE", group="provider-a"),),
        )
        witness = fabric.reconcile(
            plan,
            (
                PathOutcome(
                    "state-a", "STATE", "provider-a", PathState.VERIFIED,
                    evidence_refs=("provider:conflict",), critical_conflict=True,
                ),
            ),
        )
        self.assertEqual("REJECT_CONFLICTED", witness.state)
        self.assertFalse(witness.completion_allowed)

    def test_every_required_stream_must_have_a_candidate_path(self) -> None:
        fabric = FUSEAIBotMultiStreamFabric()
        with self.assertRaisesRegex(ValueError, "STREAM_WITHOUT_PATH:HOST"):
            fabric.plan(
                mission_id="M7",
                objective="Reject missing stream coverage",
                required_streams=("SOURCE", "HOST"),
                paths=(route("source-a", "SOURCE"),),
            )

    def test_failed_outcome_requires_failure_fingerprint(self) -> None:
        fabric = FUSEAIBotMultiStreamFabric()
        plan = fabric.plan(
            mission_id="M8",
            objective="Preserve negative knowledge",
            required_streams=("CI",),
            paths=(route("ci-a", "CI"),),
        )
        with self.assertRaisesRegex(ValueError, "FAILED_PATH_REQUIRES_FINGERPRINT"):
            fabric.reconcile(plan, (PathOutcome("ci-a", "CI", "ci-a", PathState.FAILED),))

    def test_plan_digest_is_deterministic(self) -> None:
        fabric = FUSEAIBotMultiStreamFabric(max_parallel=2)
        kwargs = dict(
            mission_id="M9",
            objective="Deterministic multi-path planning",
            required_streams=("A", "B"),
            paths=(route("a1", "A"), route("a2", "A"), route("b1", "B")),
        )
        self.assertEqual(fabric.plan(**kwargs).plan_sha256, fabric.plan(**kwargs).plan_sha256)


if __name__ == "__main__":
    unittest.main()

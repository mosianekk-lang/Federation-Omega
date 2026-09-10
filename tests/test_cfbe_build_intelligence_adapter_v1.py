from __future__ import annotations

from hashlib import sha256
import unittest

from federation.cfbe_build_intelligence_adapter_v1 import (
    BuildAction,
    BuildIntelligenceAdapter,
    CreativeFreedomEnvelope,
    EstateGraph,
    EstateKind,
    EstateNode,
    ExecutorBinding,
    ExecutorKind,
)
from federation.cfbe_chat_hyperperformance_v1 import EffectClass, RouteProfile, WorkUnit
from federation.execution_topology_compiler_v1 import TopologyTask

H = sha256(b"x").hexdigest()
EPOCH = sha256(b"0266b4be18044df495d02847d6a1cbc060a125cb").hexdigest()


def estate(*nodes):
    return EstateGraph(tuple(nodes), EPOCH)


def enode(name, deps=(), digest=H):
    return EstateNode(name, EstateKind.REPOSITORY, f"github://repo/{name}", digest, deps)


def action(name, node="repo", deps=(), effect=EffectClass.READ_ONLY, domain=""):
    return BuildAction(
        action_id=name,
        estate_node_id=node,
        operation="test",
        command=("python", "-m", "unittest"),
        input_sha256={"src": H},
        dependencies=deps,
        effect_class=effect,
        mutation_domain=domain,
    )


class BuildIntelligenceAdapterTests(unittest.TestCase):
    def test_estate_digest_is_order_independent(self):
        a, b = enode("a"), enode("b", ("a",))
        self.assertEqual(estate(a, b).graph_digest, estate(b, a).graph_digest)

    def test_estate_rejects_invalid_digest(self):
        with self.assertRaisesRegex(ValueError, "ESTATE_CONTENT_SHA256_REQUIRED"):
            estate(enode("a", digest="bad")).validate()

    def test_estate_rejects_missing_dependency(self):
        with self.assertRaisesRegex(ValueError, "MISSING_ESTATE_DEPENDENCY"):
            estate(enode("a", ("missing",))).validate()

    def test_estate_rejects_cycle(self):
        with self.assertRaisesRegex(ValueError, "CYCLIC_ESTATE_GRAPH"):
            estate(enode("a", ("b",)), enode("b", ("a",))).validate()

    def test_action_fingerprint_changes_with_command(self):
        left = action("a")
        right = BuildAction("a", "repo", "test", ("different",), {"src": H})
        self.assertNotEqual(left.input_fingerprint, right.input_fingerprint)

    def test_mutating_action_requires_domain(self):
        with self.assertRaisesRegex(ValueError, "MUTATING_ACTION_REQUIRES_MUTATION_DOMAIN"):
            action("a", effect=EffectClass.INTERNAL_WRITE).validate()

    def test_compile_emits_existing_contracts(self):
        units, tasks, routes, receipt = BuildIntelligenceAdapter().compile(
            estate=estate(enode("repo")),
            actions=(action("lint"), action("test", deps=("lint",))),
            executor_bindings=(ExecutorBinding("local-1", ExecutorKind.LOCAL, "local", H, ("proof:local",), True, True),),
        )
        self.assertTrue(all(isinstance(item, WorkUnit) for item in units))
        self.assertTrue(all(isinstance(item, TopologyTask) for item in tasks))
        self.assertTrue(all(isinstance(item, RouteProfile) for item in routes))
        self.assertEqual(units[1].deps, ("lint",))
        self.assertFalse(receipt.authority_granted)
        self.assertEqual(receipt.source_epoch_sha256, "sha256:" + EPOCH)

    def test_external_effect_is_never_cacheable(self):
        units, _, _, _ = BuildIntelligenceAdapter().compile(
            estate=estate(enode("repo")),
            actions=(action("deploy", effect=EffectClass.EXTERNAL_EFFECT, domain="cloudrun:service:x"),),
            executor_bindings=(),
        )
        self.assertFalse(units[0].cacheable)

    def test_missing_action_dependency_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "MISSING_BUILD_ACTION_DEPENDENCY"):
            BuildIntelligenceAdapter().compile(
                estate=estate(enode("repo")),
                actions=(action("test", deps=("build",)),),
                executor_bindings=(),
            )

    def test_cyclic_action_graph_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "CYCLIC_BUILD_ACTION_GRAPH"):
            BuildIntelligenceAdapter().compile(
                estate=estate(enode("repo")),
                actions=(action("a", deps=("b",)), action("b", deps=("a",))),
                executor_bindings=(),
            )

    def test_executor_surface_must_match_declared_kind(self):
        invalid = BuildAction(
            "a",
            "repo",
            "test",
            ("run",),
            {"src": H},
            surface="github",
            executor_kinds=(ExecutorKind.LOCAL,),
        )
        with self.assertRaisesRegex(ValueError, "BUILD_ACTION_EXECUTOR_SURFACE_MISMATCH"):
            invalid.validate()

    def test_missing_estate_binding_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "ACTION_ESTATE_NODE_NOT_FOUND"):
            BuildIntelligenceAdapter().compile(
                estate=estate(enode("repo")),
                actions=(action("test", node="missing"),),
                executor_bindings=(),
            )

    def test_available_executor_requires_proof(self):
        with self.assertRaisesRegex(ValueError, "EXECUTOR_BINDING_PROOF_REQUIRED"):
            ExecutorBinding("github", ExecutorKind.GITHUB, "github", H, (), True, True).to_route_profile()

    def test_unverified_executor_can_be_represented_but_not_selected(self):
        route = ExecutorBinding("remote", ExecutorKind.REMOTE_EXECUTION, "remote", H, (), False, False).to_route_profile()
        self.assertFalse(route.available)
        self.assertFalse(route.fresh)

    def test_duplicate_executor_binding_fails_closed(self):
        binding = ExecutorBinding("local", ExecutorKind.LOCAL, "local", H, ("proof",), True, True)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_EXECUTOR_BINDING"):
            BuildIntelligenceAdapter().compile(
                estate=estate(enode("repo")), actions=(action("test"),), executor_bindings=(binding, binding)
            )

    def test_protected_creative_change_requires_override(self):
        env = CreativeFreedomEnvelope(protected_paths=frozenset({"ui/brand.css"}))
        with self.assertRaisesRegex(PermissionError, "PROTECTED_CREATIVE_PATH"):
            env.validate_changes(["ui/brand.css"])

    def test_creative_override_requires_owner_receipt(self):
        env = CreativeFreedomEnvelope(protected_paths=frozenset({"ui/brand.css"}))
        with self.assertRaisesRegex(ValueError, "OWNER_OVERRIDE_RECEIPT_SHA256_REQUIRED"):
            env.validate_changes(["ui/brand.css"], requested_overrides=["ui/brand.css"])
        env.validate_changes(
            ["ui/brand.css"], requested_overrides=["ui/brand.css"], owner_override_receipt_sha256=H
        )

    def test_invariant_is_never_overridable(self):
        env = CreativeFreedomEnvelope(invariants=frozenset({"security"}))
        with self.assertRaisesRegex(PermissionError, "INVARIANT_NOT_OVERRIDABLE"):
            env.validate_changes([], requested_overrides=["security"], owner_override_receipt_sha256=H)


if __name__ == "__main__":
    unittest.main()

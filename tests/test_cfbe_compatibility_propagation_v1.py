from __future__ import annotations

from hashlib import sha256
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "federation/cfbe_compatibility_propagation_v1.py"
spec = importlib.util.spec_from_file_location("cfbe_compatibility_propagation_v1", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

CompatibilityPropagationPlanner = module.CompatibilityPropagationPlanner
CompatibilityWindow = module.CompatibilityWindow
CreativeOverrideReceipt = module.CreativeOverrideReceipt
PropagationPolicy = module.PropagationPolicy
RepositoryPropagation = module.RepositoryPropagation

H = sha256(b"fixture").hexdigest()
EPOCH = sha256(b"0266b4be18044df495d02847d6a1cbc060a125cb").hexdigest()


def change(repository="mosianekk-lang/Federation-Omega", **kwargs):
    values = {
        "repository": repository,
        "current_version": "1.0.0",
        "target_version": "1.1.0",
        "source_epoch_sha256": EPOCH,
        "rollback_sha256": H,
        "canary_artifact_sha256": H,
        "changed_paths": ("federation/adapter.py",),
        "semantic_change_points": 2,
        "observation_cycles": 3,
        "dependencies": (),
    }
    values.update(kwargs)
    return RepositoryPropagation(**values)


def policy(**kwargs):
    repo = "mosianekk-lang/Federation-Omega"
    values = {
        "current_source_epoch_sha256": EPOCH,
        "allowed_repositories": frozenset({repo}),
        "compatibility_windows": {repo: CompatibilityWindow("1.0.1", "1.9.9")},
        "maximum_repositories": 1,
    }
    values.update(kwargs)
    return PropagationPolicy(**values)


class CompatibilityPropagationTests(unittest.TestCase):
    def test_valid_plan_has_all_stages_and_never_authorizes_promotion(self):
        receipt = CompatibilityPropagationPlanner().plan((change(),), policy())
        self.assertEqual([step.stage for step in receipt.steps], ["PREIMAGE", "CANARY", "OBSERVATION", "PROMOTION_READY"])
        self.assertFalse(receipt.promotion_authorized)
        self.assertEqual(receipt.rollback_identities, ("sha256:" + H,))

    def test_repository_allowlist_fails_closed(self):
        with self.assertRaisesRegex(PermissionError, "REPOSITORY_NOT_ALLOWLISTED"):
            CompatibilityPropagationPlanner().plan((change("other/repo"),), policy())

    def test_source_epoch_mismatch_fails_closed(self):
        with self.assertRaisesRegex(PermissionError, "SOURCE_EPOCH_MISMATCH"):
            CompatibilityPropagationPlanner().plan((change(source_epoch_sha256=sha256(b"stale").hexdigest()),), policy())

    def test_target_outside_compatibility_window_fails_closed(self):
        with self.assertRaisesRegex(PermissionError, "TARGET_OUTSIDE_COMPATIBILITY_WINDOW"):
            CompatibilityPropagationPlanner().plan((change(target_version="2.0.0"),), policy())

    def test_invalid_or_nonadvancing_semver_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "TARGET_VERSION_SEMVER_REQUIRED"):
            change(target_version="latest").validate()
        with self.assertRaisesRegex(ValueError, "TARGET_VERSION_MUST_ADVANCE"):
            change(target_version="1.0.0").validate()

    def test_missing_rollback_or_canary_hash_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "ROLLBACK_SHA256_REQUIRED"):
            change(rollback_sha256="missing").validate()
        with self.assertRaisesRegex(ValueError, "CANARY_ARTIFACT_SHA256_REQUIRED"):
            change(canary_artifact_sha256="missing").validate()

    def test_duplicate_changed_path_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_PROPAGATION_PATH"):
            change(changed_paths=("federation/a.py", "federation/a.py")).validate()

    def test_blast_radius_and_semantic_budgets_fail_closed(self):
        with self.assertRaisesRegex(PermissionError, "CHANGED_PATH_BUDGET_EXCEEDED"):
            CompatibilityPropagationPlanner().plan((change(changed_paths=("a", "b")),), policy(maximum_total_changed_paths=1))
        with self.assertRaisesRegex(PermissionError, "SEMANTIC_CHANGE_BUDGET_EXCEEDED"):
            CompatibilityPropagationPlanner().plan((change(semantic_change_points=11),), policy())

    def test_observation_window_is_mandatory(self):
        with self.assertRaisesRegex(PermissionError, "OBSERVATION_WINDOW_TOO_SHORT"):
            CompatibilityPropagationPlanner().plan((change(observation_cycles=2),), policy())

    def test_protected_creative_path_requires_exact_owner_receipt(self):
        creative = change(changed_paths=("ui/brand.css",))
        with self.assertRaisesRegex(PermissionError, "PROTECTED_CREATIVE_LAYER_EXCLUDED"):
            CompatibilityPropagationPlanner().plan((creative,), policy())
        wrong = CreativeOverrideReceipt("other/repo", EPOCH, ("ui/brand.css",), H)
        with self.assertRaisesRegex(PermissionError, "OWNER_OVERRIDE_REPOSITORY_MISMATCH"):
            CompatibilityPropagationPlanner().plan((creative,), policy(), {creative.repository: wrong})

    def test_exact_owner_override_allows_only_bound_path_and_epoch(self):
        creative = change(changed_paths=("ui/brand.css",))
        receipt = CreativeOverrideReceipt(creative.repository, EPOCH, ("ui/brand.css",), H)
        result = CompatibilityPropagationPlanner().plan((creative,), policy(), {creative.repository: receipt})
        self.assertEqual(result.ordered_repositories, (creative.repository,))

    def test_dependency_graph_is_deterministic_and_cycles_fail_closed(self):
        a, b = "org/a", "org/b"
        pol = policy(
            allowed_repositories=frozenset({a, b}),
            compatibility_windows={a: CompatibilityWindow("1.0.1", "1.9.9"), b: CompatibilityWindow("1.0.1", "1.9.9")},
            maximum_repositories=2,
        )
        ordered = CompatibilityPropagationPlanner().plan((change(b, dependencies=(a,)), change(a)), pol)
        self.assertEqual(ordered.ordered_repositories, (a, b))
        with self.assertRaisesRegex(ValueError, "CYCLIC_PROPAGATION_GRAPH"):
            CompatibilityPropagationPlanner().plan((change(a, dependencies=(b,)), change(b, dependencies=(a,))), pol)

    def test_receipt_digest_is_order_stable(self):
        a, b = "org/a", "org/b"
        pol = policy(
            allowed_repositories=frozenset({a, b}),
            compatibility_windows={a: CompatibilityWindow("1.0.1", "1.9.9"), b: CompatibilityWindow("1.0.1", "1.9.9")},
            maximum_repositories=2,
        )
        planner = CompatibilityPropagationPlanner()
        self.assertEqual(planner.plan((change(a), change(b)), pol).receipt_digest, planner.plan((change(b), change(a)), pol).receipt_digest)

    def test_receipt_binds_canary_paths_and_observation(self):
        planner = CompatibilityPropagationPlanner()
        base = planner.plan((change(),), policy())
        canary = planner.plan((change(canary_artifact_sha256=sha256(b"other-canary").hexdigest()),), policy())
        path = planner.plan((change(changed_paths=("federation/other.py",)),), policy())
        observation = planner.plan((change(observation_cycles=4),), policy())
        self.assertEqual(len({base.receipt_digest, canary.receipt_digest, path.receipt_digest, observation.receipt_digest}), 4)


if __name__ == "__main__":
    unittest.main()

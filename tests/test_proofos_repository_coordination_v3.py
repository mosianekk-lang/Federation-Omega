from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from proofos_omega.repository_coordination_v3 import (
    CLAIM_SCHEMA,
    DEFAULT_REGISTRY_REF,
    LEASE_SCHEMA,
    REGISTRY_SCHEMA,
    can_acquire,
    evaluate,
    evaluate_hosted_pull_request_v3,
    extract_claim,
    load_policy,
    normalize_write_set,
    parse_registry_message,
    reclaim_lease,
    scopes_overlap,
    transition_recovery,
    validate_fence,
    write_set_digest,
)

ROOT = Path(__file__).resolve().parents[1]
BASE = "1" * 40
REGISTRY_SHA = "9" * 40
NOW = datetime(2026, 9, 2, 20, 50, tzinfo=timezone.utc)


def lease(lease_id: str, write_set: list[str], fence: int, writer: str, *, expires="2026-09-02T23:19:04+02:00") -> dict:
    return {
        "schema": LEASE_SCHEMA,
        "lease_id": lease_id,
        "state": "ACTIVE",
        "fencing_token": fence,
        "writer_node": writer,
        "system": "FDOF_V3",
        "workstream": f"ws-{lease_id}",
        "transaction_id": f"txn-{lease_id}",
        "idempotency_key": f"idem-{lease_id}",
        "source_head": BASE,
        "source_tree": "5" * 40,
        "write_set": write_set,
        "write_set_digest": write_set_digest(write_set),
        "acquired_at": "2026-09-02T22:49:04+02:00",
        "expires_at": expires,
        "turn_capture_id": f"tc-{lease_id}",
        "effect": "NONE",
        "authority": "A1_INTERNAL_SOURCE_CI",
    }


def registry(*leases: dict, generation=10) -> dict:
    return {"schema": REGISTRY_SCHEMA, "generation": generation, "updated_at": "2026-09-02T22:49:04+02:00", "active_leases": list(leases), "effect": "NONE"}


def message(reg: dict) -> str:
    return REGISTRY_SCHEMA + "\n" + json.dumps(reg, sort_keys=True, separators=(",", ":"))


def claim(l: dict, **overrides) -> dict:
    out = {
        "schema": CLAIM_SCHEMA,
        "lease_id": l["lease_id"],
        "writer_node": l["writer_node"],
        "system": l["system"],
        "workstream": l["workstream"],
        "transaction_id": l["transaction_id"],
        "idempotency_key": l["idempotency_key"],
        "source_head": l["source_head"],
        "turn_capture_id": l["turn_capture_id"],
        "registry_ref": DEFAULT_REGISTRY_REF,
        "fencing_token": l["fencing_token"],
        "write_set_digest": l["write_set_digest"],
    }
    out.update(overrides)
    return out


class FDOFV3ScopedRegistryTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy()

    def assess(self, paths, body, reg):
        return evaluate(base_sha=BASE, pr_paths=paths, pr_body=body, registry_message=message(reg), registry_sha=REGISTRY_SHA, now=NOW, policy=self.policy)

    @staticmethod
    def rules(result):
        return {x["rule"] for x in result["findings"]}

    def test_short_cas_policy_does_not_serialize_work_duration(self):
        self.assertEqual("DUAL_COMPATIBILITY", self.policy["mode"])
        self.assertEqual("GIT_REF_FAST_FORWARD_CAS", self.policy["registry_transaction_model"]["provider"])
        self.assertFalse(self.policy["registry_transaction_model"]["work_duration_serialized"])

    def test_v31_policy_declares_recovery_and_stale_fence_law(self):
        self.assertEqual("3.1.0", self.policy["version"])
        recovery = self.policy["recovery_lifecycle"]
        self.assertEqual(["ACTIVE", "SUSPECT", "ORPHANED", "RECLAIMABLE"], recovery["nonterminal_states"])
        self.assertTrue(self.policy["proof_boundary"]["orphan_recovery_canary_required"])
        self.assertTrue(self.policy["proof_boundary"]["stale_fence_rejection_canary_required"])

    def test_registry_parses(self):
        self.assertEqual(REGISTRY_SCHEMA, parse_registry_message(message(registry()))["schema"])

    def test_scope_overlap_math(self):
        self.assertEqual(("cfbe/**", "mobile/app.py"), normalize_write_set(["./mobile/app.py", "cfbe/**"]))
        self.assertTrue(scopes_overlap("mobile/**", "mobile/app.py"))
        self.assertTrue(scopes_overlap("repository:*", "cfbe/x.py"))
        self.assertFalse(scopes_overlap("mobile/**", "cfbe/x.py"))

    def test_two_disjoint_active_leases_are_both_valid(self):
        a = lease("A", ["mobile/**"], 11, "NODE-A")
        b = lease("B", ["cfbe/**"], 12, "NODE-B")
        reg = registry(a, b, generation=12)
        self.assertEqual("PASS", self.assess(["mobile/app.py"], json.dumps(claim(a)), reg)["status"])
        self.assertEqual("PASS", self.assess(["cfbe/core.py"], json.dumps(claim(b)), reg)["status"])

    def test_registry_rejects_overlapping_active_leases(self):
        a = lease("A", ["mobile/**"], 11, "NODE-A")
        b = lease("B", ["mobile/app.py"], 12, "NODE-B")
        result = self.assess(["docs/x.md"], "legacy", registry(a, b, generation=12))
        self.assertEqual("FAIL", result["status"])
        self.assertIn("V3_REGISTRY_ACTIVE_OVERLAP", self.rules(result))

    def test_foreign_overlap_rejected(self):
        a = lease("A", ["mobile/**"], 11, "NODE-A")
        result = self.assess(["mobile/app.py"], "legacy", registry(a, generation=11))
        self.assertEqual("FAIL", result["status"])
        self.assertIn("V3_FOREIGN_WRITE_CONFLICT", self.rules(result))

    def test_disjoint_legacy_pr_can_continue_during_migration(self):
        a = lease("A", ["mobile/**"], 11, "NODE-A")
        result = self.assess(["cfbe/x.py"], "legacy", registry(a, generation=11))
        self.assertEqual("PASS", result["status"])
        self.assertEqual("V3_LEGACY_UNSCOPED_NO_CONFLICT", result["state"])

    def test_claim_cannot_escape_declared_write_set(self):
        a = lease("A", ["mobile/**"], 11, "NODE-A")
        result = self.assess(["mobile/app.py", "cfbe/x.py"], json.dumps(claim(a)), registry(a, generation=11))
        self.assertEqual("FAIL", result["status"])
        self.assertIn("V3_WRITE_SET_ESCAPE", self.rules(result))

    def test_repository_global_path_requires_repository_scope(self):
        a = lease("A", ["proofos_omega/repository_coordination.py"], 11, "NODE-A")
        result = self.assess(["proofos_omega/repository_coordination.py"], json.dumps(claim(a)), registry(a, generation=11))
        self.assertEqual("FAIL", result["status"])
        self.assertIn("V3_GLOBAL_PATH_REQUIRES_REPOSITORY_SCOPE", self.rules(result))
        g = lease("G", ["repository:*"], 12, "NODE-G")
        self.assertEqual("PASS", self.assess(["proofos_omega/repository_coordination.py"], json.dumps(claim(g)), registry(g, generation=12))["status"])

    def test_expired_active_never_silently_releases(self):
        a = lease("A", ["mobile/**"], 11, "NODE-A", expires="2026-09-02T22:49:30+02:00")
        result = self.assess(["cfbe/x.py"], "legacy", registry(a, generation=11))
        self.assertEqual("FAIL", result["status"])
        self.assertIn("V3_ACTIVE_EXPIRED_NOT_TERMINAL", self.rules(result))

    def test_recovery_cannot_mark_suspect_before_expiry(self):
        a = lease("A", ["mobile/**"], 11, "NODE-A")
        result = transition_recovery(
            registry(a, generation=11),
            "A",
            expected_fencing_token=11,
            actor="RECOVERY-WATCHER",
            target_state="SUSPECT",
            now=NOW,
            policy=self.policy,
        )
        self.assertEqual("FAIL", result["status"])
        self.assertEqual("V3_RECOVERY_NOT_EXPIRED", result["state"])

    def test_recovery_lifecycle_requires_independent_reclaimer_and_permanently_fences_old_writer(self):
        a = lease("A", ["mobile/**"], 11, "NODE-A", expires="2026-09-02T22:49:30+02:00")
        reg = registry(a, generation=11)

        suspect = transition_recovery(
            reg,
            "A",
            expected_fencing_token=11,
            actor="RECOVERY-WATCHER",
            target_state="SUSPECT",
            now=NOW,
            policy=self.policy,
        )
        self.assertEqual("PASS", suspect["status"])
        self.assertEqual(12, suspect["registry"]["generation"])
        self.assertEqual("SUSPECT", suspect["registry"]["active_leases"][0]["state"])
        self.assertEqual("FAIL", can_acquire(suspect["registry"], ["mobile/app.py"], now=NOW, policy=self.policy)["status"])

        orphaned = transition_recovery(
            suspect["registry"],
            "A",
            expected_fencing_token=11,
            actor="RECOVERY-WATCHER",
            target_state="ORPHANED",
            now=NOW,
            policy=self.policy,
        )
        self.assertEqual("PASS", orphaned["status"])
        self.assertEqual(13, orphaned["registry"]["generation"])

        self_reclaimable = transition_recovery(
            orphaned["registry"],
            "A",
            expected_fencing_token=11,
            actor="NODE-A",
            target_state="RECLAIMABLE",
            now=NOW,
            policy=self.policy,
        )
        self.assertEqual("FAIL", self_reclaimable["status"])
        self.assertEqual("V3_RECOVERY_INDEPENDENT_ACTOR_REQUIRED", self_reclaimable["state"])

        reclaimable = transition_recovery(
            orphaned["registry"],
            "A",
            expected_fencing_token=11,
            actor="RECOVERY-JUDGE",
            target_state="RECLAIMABLE",
            now=NOW,
            policy=self.policy,
        )
        self.assertEqual("PASS", reclaimable["status"])
        self.assertEqual(14, reclaimable["registry"]["generation"])
        self.assertEqual("RECLAIMABLE", reclaimable["registry"]["active_leases"][0]["state"])

        blocked_claim = self.assess(["mobile/app.py"], json.dumps(claim(reclaimable["registry"]["active_leases"][0])), reclaimable["registry"])
        self.assertEqual("FAIL", blocked_claim["status"])
        self.assertIn("V3_OWN_LEASE_NOT_ACTIVE_STATE", self.rules(blocked_claim))

        replacement = lease("A-R1", ["mobile/**"], 15, "NODE-R")
        reclaimed = reclaim_lease(
            reclaimable["registry"],
            "A",
            replacement,
            expected_fencing_token=11,
            actor="RECOVERY-JUDGE",
            now=NOW,
            policy=self.policy,
        )
        self.assertEqual("PASS", reclaimed["status"])
        self.assertEqual(15, reclaimed["registry"]["generation"])
        self.assertEqual("ACTIVE", reclaimed["registry"]["active_leases"][0]["state"])
        self.assertEqual([11], reclaimed["registry"]["stale_fencing_tokens"])
        self.assertEqual("FAIL", validate_fence(reclaimed["registry"], "A", 11)["status"])
        self.assertEqual("V3_STALE_FENCE_REJECTED", validate_fence(reclaimed["registry"], "A", 11)["state"])
        self.assertEqual("PASS", validate_fence(reclaimed["registry"], "A-R1", 15)["status"])

    def test_reclaim_requires_same_write_set_and_next_generation_fence(self):
        a = lease("A", ["mobile/**"], 11, "NODE-A", expires="2026-09-02T22:49:30+02:00")
        reg = registry(a, generation=11)
        suspect = transition_recovery(reg, "A", expected_fencing_token=11, actor="R", target_state="SUSPECT", now=NOW, policy=self.policy)["registry"]
        orphaned = transition_recovery(suspect, "A", expected_fencing_token=11, actor="R", target_state="ORPHANED", now=NOW, policy=self.policy)["registry"]
        reclaimable = transition_recovery(orphaned, "A", expected_fencing_token=11, actor="JUDGE", target_state="RECLAIMABLE", now=NOW, policy=self.policy)["registry"]

        bad_scope = lease("A-R1", ["cfbe/**"], 15, "NODE-R")
        result = reclaim_lease(reclaimable, "A", bad_scope, expected_fencing_token=11, actor="JUDGE", now=NOW, policy=self.policy)
        self.assertEqual("V3_RECLAIM_WRITE_SET_CHANGED", result["state"])

        bad_fence = lease("A-R1", ["mobile/**"], 16, "NODE-R")
        result = reclaim_lease(reclaimable, "A", bad_fence, expected_fencing_token=11, actor="JUDGE", now=NOW, policy=self.policy)
        self.assertEqual("V3_RECLAIM_FENCE_NOT_MONOTONIC", result["state"])

    def test_stale_fence_tombstone_cannot_be_reused_by_active_lease(self):
        a = lease("A", ["mobile/**"], 11, "NODE-A")
        reg = registry(a, generation=12)
        reg["stale_fencing_tokens"] = [11]
        result = self.assess(["docs/x.md"], "legacy", reg)
        self.assertEqual("FAIL", result["status"])
        self.assertIn("V3_STALE_FENCE_REUSED", self.rules(result))

    def test_acquire_preflight_disjoint_pass_overlap_fails(self):
        a = lease("A", ["mobile/**"], 11, "NODE-A")
        reg = registry(a, generation=11)
        self.assertEqual("PASS", can_acquire(reg, ["cfbe/**"], now=NOW, policy=self.policy)["status"])
        bad = can_acquire(reg, ["mobile/app.py"], now=NOW, policy=self.policy)
        self.assertEqual("FAIL", bad["status"])
        self.assertIn("V3_ACQUIRE_CONFLICT", {x["rule"] for x in bad["findings"]})

    def test_v3_markdown_claim_extracts(self):
        a = lease("A", ["mobile/**"], 11, "NODE-A")
        body = "Summary\n<!-- FEDERATION_COORDINATION_V2\n" + json.dumps(claim(a)) + "\n-->"
        self.assertEqual("A", extract_claim(body)["lease_id"])

    def test_workflow_free_export_without_origin_is_explicitly_not_applicable(self):
        prior_event_path = os.environ.get("GITHUB_EVENT_PATH")
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                event_path = root / "event.json"
                event_path.write_text(
                    json.dumps({"pull_request": {"base": {"sha": BASE}, "head": {"sha": "2" * 40}, "body": ""}}),
                    encoding="utf-8",
                )
                os.environ["GITHUB_EVENT_PATH"] = str(event_path)
                result = evaluate_hosted_pull_request_v3(root)
        finally:
            if prior_event_path is None:
                os.environ.pop("GITHUB_EVENT_PATH", None)
            else:
                os.environ["GITHUB_EVENT_PATH"] = prior_event_path
        self.assertEqual("NOT_APPLICABLE", result["status"])
        self.assertEqual("V3_HOSTED_PROVIDER_NOT_APPLICABLE_NO_ORIGIN", result["state"])
        self.assertFalse(result["provider_effect_authorized"])

    @unittest.skipUnless(
        os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_EVENT_NAME") == "pull_request",
        "hosted scoped coordination court runs only on GitHub pull_request",
    )
    def test_hosted_pull_request_honours_scoped_registry(self):
        result = evaluate_hosted_pull_request_v3(ROOT)
        if result["state"] == "V3_HOSTED_PROVIDER_NOT_APPLICABLE_NO_ORIGIN":
            origin_probe = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(0, origin_probe.returncode)
            self.assertEqual("NOT_APPLICABLE", result["status"])
            self.assertFalse(result["provider_effect_authorized"])
            return
        self.assertEqual("PASS", result["status"], json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    unittest.main()

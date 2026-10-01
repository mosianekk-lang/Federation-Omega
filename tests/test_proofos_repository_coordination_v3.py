from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from proofos_omega import repository_coordination as legacy_coordination

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


def load_tests(loader, standard_tests, pattern):
    """Keep the real issuer CAS court inside the existing ProofOS bootstrap.

    Load one explicit TestCase, never this module or another load_tests hook.
    Missing, empty or skipped issuer coverage is an admission failure.
    """
    path = Path(__file__).with_name("test_repository_lease_issuer.py")
    spec = importlib.util.spec_from_file_location("_f355_issuer_court", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    case = module.RepositoryLeaseIssuerTests
    issuer_suite = unittest.TestLoader().loadTestsFromTestCase(case)
    if issuer_suite.countTestCases() == 0:
        raise RuntimeError("F355_ISSUER_COURT_EMPTY")
    for test in issuer_suite:
        method = getattr(test, test._testMethodName)
        if getattr(case, "__unittest_skip__", False) or getattr(method, "__unittest_skip__", False):
            raise RuntimeError("F355_ISSUER_COURT_SKIPPED")
    return unittest.TestSuite([standard_tests, issuer_suite])


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
        self.assertEqual("3.2.0", self.policy["version"])
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
        reg = registry(a, generation=11)
        result = self.assess(["mobile/app.py"], "legacy", reg)
        self.assertEqual("FAIL", result["status"])
        self.assertIn("V3_FOREIGN_WRITE_CONFLICT", self.rules(result))
        self.assertEqual("ACTIVE", reg["active_leases"][0]["state"])
        self.assertEqual("PASS", self.assess(["cfbe/x.py"], "legacy", reg)["status"])
        self.assertEqual("PASS", can_acquire(reg, ["cfbe/**"], now=NOW)["status"])
        self.assertEqual("FAIL", can_acquire(reg, ["mobile/**"], now=NOW)["status"])

    def test_expired_owner_cannot_commit_even_with_exact_claim(self):
        a = lease("A", ["mobile/**"], 11, "NODE-A", expires="2026-09-02T22:49:30+02:00")
        result = self.assess(["mobile/app.py"], json.dumps(claim(a)), registry(a, generation=11))
        self.assertEqual("FAIL", result["status"])
        self.assertIn("V3_ACTIVE_EXPIRED_NOT_TERMINAL", self.rules(result))

    def test_expired_repository_scope_still_blocks_every_write_set(self):
        a = lease("A", ["repository:*"], 11, "NODE-A", expires="2026-09-02T22:49:30+02:00")
        reg = registry(a, generation=11)
        self.assertEqual("FAIL", self.assess(["docs/x.md"], "legacy", reg)["status"])
        self.assertEqual("FAIL", can_acquire(reg, ["docs/**"], now=NOW)["status"])

    def test_two_expired_disjoint_leases_can_be_recovered_without_mutual_deadlock(self):
        expired = "2026-09-02T22:49:30+02:00"
        a = lease("A", ["mobile/**"], 11, "NODE-A", expires=expired)
        b = lease("B", ["cfbe/**"], 12, "NODE-B", expires=expired)
        original = registry(a, b, generation=12)
        first = transition_recovery(original, "A", expected_fencing_token=11, actor="RECOVERY", target_state="SUSPECT", now=NOW)
        self.assertEqual("PASS", first["status"])
        self.assertEqual(["SUSPECT", "ACTIVE"], [row["state"] for row in first["registry"]["active_leases"]])
        second = transition_recovery(first["registry"], "B", expected_fencing_token=12, actor="RECOVERY", target_state="SUSPECT", now=NOW)
        self.assertEqual("PASS", second["status"])
        self.assertEqual(["SUSPECT", "SUSPECT"], [row["state"] for row in second["registry"]["active_leases"]])
        self.assertEqual(["ACTIVE", "ACTIVE"], [row["state"] for row in original["active_leases"]])
        self.assertEqual("FAIL", can_acquire(second["registry"], ["mobile/**"], now=NOW)["status"])
        self.assertEqual("PASS", can_acquire(second["registry"], ["docs/**"], now=NOW)["status"])

    def test_malformed_time_is_still_registry_corruption_for_disjoint_work(self):
        a = lease("A", ["mobile/**"], 11, "NODE-A", expires="not-a-time")
        result = self.assess(["docs/x.md"], "legacy", registry(a, generation=11))
        self.assertEqual("FAIL", result["status"])
        self.assertIn("V3_LEASE_TIME_INVALID", self.rules(result))

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

    @staticmethod
    def legacy_lease(*, state="ACTIVE", expires="2099-01-01T00:00:00+00:00"):
        return {
            "schema": legacy_coordination.LEASE_SCHEMA,
            "state": state, "fencing_token": 353, "writer_node": "F353",
            "system": "FDOF", "workstream": "source-admission",
            "transaction_id": "T353", "idempotency_key": "test-f353",
            "source_head": BASE, "scope": "repository:*",
            "acquired_at": "2026-09-02T00:00:00+00:00", "expires_at": expires,
            "turn_capture_id": "test-capture-353", "effect": "NONE",
            "authority": "A1_INTERNAL_SOURCE_CI",
        }

    def hosted_assess(self, legacy, *, body="unrelated PR", tree_matches=True, legacy_error=None,
                      event_payload=None, event_name="pull_request", registry_payload=None, paths="docs/x.md", source_tree="5" * 40):
        legacy_sha = "7" * 40
        legacy_message = legacy if isinstance(legacy, str) else legacy_coordination.LEASE_SCHEMA + "\n" + json.dumps(legacy)
        def fake_git(root, args):
            if args[0] == "ls-remote":
                return REGISTRY_SHA + "\t" + DEFAULT_REGISTRY_REF
            if args[0] == "show":
                if "--format=%T" in args:
                    return "5" * 40 if args[-1] == "a" * 40 else source_tree
                return message(registry(generation=1) if registry_payload is None else registry_payload)
            if args[0] == "diff":
                return paths
            return ""
        with tempfile.TemporaryDirectory() as td:
            event = Path(td) / "event.json"
            payload = {"pull_request": {
                "base": {"sha": BASE}, "head": {"sha": "2" * 40}, "body": body,
            }} if event_payload is None else event_payload
            event.write_text(json.dumps(payload), encoding="utf-8")
            with patch.dict(os.environ, {"GITHUB_EVENT_PATH": str(event), "GITHUB_EVENT_NAME": event_name}), patch(
                "proofos_omega.repository_coordination_v3._origin_available", return_value=True
            ), patch(
                "proofos_omega.repository_coordination._runtime_lease",
                return_value=(legacy_sha, legacy_message, tree_matches), side_effect=legacy_error,
            ) as legacy_read, patch(
                "proofos_omega.repository_coordination_v3._git", side_effect=fake_git
            ) as registry_read:
                result = evaluate_hosted_pull_request_v3(ROOT)
        return result, legacy_read, registry_read

    def test_hosted_legacy_active_global_lease_blocks_disjoint_unclaimed_pr(self):
        result, legacy_read, registry_read = self.hosted_assess(self.legacy_lease())
        self.assertEqual("FAIL", result["status"])
        self.assertIn("ACTIVE_REPOSITORY_LEASE_UNCLAIMED", self.rules(result))
        legacy_read.assert_called_once_with(ROOT, legacy_coordination.DEFAULT_LEASE_REF)
        self.assertTrue(registry_read.called)

    def test_hosted_exact_active_legacy_claim_keeps_v2_absolute_without_v3_promotion(self):
        active = self.legacy_lease()
        body = dict(active, schema=legacy_coordination.CLAIM_SCHEMA,
                    lock_ref=legacy_coordination.DEFAULT_LEASE_REF, lease_commit_sha="7" * 40)
        result, _, registry_read = self.hosted_assess(active, body=json.dumps(body))
        self.assertEqual("PASS", result["status"])
        self.assertEqual("V3_DEFERRED_TO_ACTIVE_V2", result["state"])
        self.assertFalse(result["provider_effect_authorized"])
        self.assertTrue(registry_read.called)

    def test_hosted_expired_legacy_active_and_malformed_descriptors_fail_closed(self):
        for value, expected_rule in (
            (self.legacy_lease(expires="2020-01-01T00:00:00+00:00"), "ACTIVE_LEASE_EXPIRED_NOT_TERMINAL"),
            (legacy_coordination.LEASE_SCHEMA + "\n{broken", "LEASE_DESCRIPTOR_MALFORMED"),
        ):
            with self.subTest(rule=expected_rule):
                result, _, registry_read = self.hosted_assess(value)
                self.assertEqual("FAIL", result["status"])
                self.assertIn(expected_rule, self.rules(result))
                if isinstance(value, dict):
                    self.assertTrue(registry_read.called)

    def test_hosted_explicit_terminal_legacy_lease_allows_v3_assessment(self):
        for state in ("RELEASED", "ABORTED"):
            with self.subTest(state=state):
                result, legacy_read, registry_read = self.hosted_assess(self.legacy_lease(state=state))
                self.assertEqual("PASS", result["status"])
                self.assertEqual("V3_LEGACY_UNSCOPED_NO_CONFLICT", result["state"])
                self.assertEqual("LEASE_" + state, result["legacy_coordination"]["state"])
                self.assertTrue(legacy_read.called)
                self.assertTrue(registry_read.called)

    def test_hosted_legacy_provider_read_failure_never_becomes_absence(self):
        result, _, registry_read = self.hosted_assess(self.legacy_lease(), legacy_error=RuntimeError("readback failed"))
        self.assertEqual("FAIL", result["status"])
        self.assertEqual("V3_LEGACY_PROVIDER_READBACK_FAILED", result["state"])
        registry_read.assert_not_called()

    def migration(self):
        return {"schema":"FEDERATION_FDOF_MIGRATION_V1", "state":"COMPLETE", "cutover_id":"cutover-355",
                "legacy_ref":legacy_coordination.DEFAULT_LEASE_REF,"registry_ref":DEFAULT_REGISTRY_REF,
                "predecessor_registry_sha":"8"*40,"legacy_tombstone_sha":"7"*40,"turn_capture_id":"tc-cutover",
                "issuer_source_head":"a"*40,"issuer_source_tree":"5"*40}

    def tombstone(self):
        frozen=dict(self.migration(),state="FROZEN")
        frozen.pop("legacy_tombstone_sha")
        return dict(self.legacy_lease(state="MIGRATED_TO_V3"),migration=frozen,turn_capture_id="tc-cutover")

    def test_migrated_registry_requires_claim_even_with_legacy_compatibility(self):
        reg=dict(registry(generation=12),migration=self.migration())
        result,_,_=self.hosted_assess(self.tombstone(),registry_payload=reg)
        self.assertEqual("FAIL",result["status"])
        self.assertIn("V3_SCOPED_CLAIM_REQUIRED",self.rules(result))

    def test_migrated_legacy_active_exact_claim_is_drift_not_authority(self):
        active=self.legacy_lease()
        body=dict(active,schema=legacy_coordination.CLAIM_SCHEMA,
                  lock_ref=legacy_coordination.DEFAULT_LEASE_REF,lease_commit_sha="7"*40)
        reg=dict(registry(generation=12),migration=self.migration())
        result,_,_=self.hosted_assess(active,body=json.dumps(body),registry_payload=reg)
        self.assertEqual("FAIL",result["status"])
        self.assertIn("MIGRATION_LEGACY_DRIFT",self.rules(result))

    def test_frozen_gap_mismatched_barrier_and_tombstone_tree_fail_closed(self):
        complete=dict(registry(generation=12),migration=self.migration())
        for reg,tree_matches in [(registry(generation=12),True),
                (dict(complete,migration=dict(self.migration(),cutover_id="other")),True),(complete,False)]:
            result,_,_=self.hosted_assess(self.tombstone(),registry_payload=reg,tree_matches=tree_matches)
            self.assertEqual("FAIL",result["status"])
            self.assertEqual("V3_MIGRATION_REJECTED",result["state"])
        for changes in [{"fencing_token":True},{"turn_capture_id":"wrong"},{"effect":"WRITE"}]:
            result,_,_=self.hosted_assess(dict(self.tombstone(),**changes),registry_payload=complete)
            self.assertEqual("FAIL",result["status"])
        for tree in ["malformed", "0"*40]:
            bad_registry=dict(complete,migration=dict(self.migration(),issuer_source_tree=tree))
            bad_tombstone=dict(self.tombstone(),migration=dict(self.tombstone()["migration"],issuer_source_tree=tree))
            result,_,_=self.hosted_assess(bad_tombstone,registry_payload=bad_registry)
            self.assertEqual("FAIL",result["status"])

    def test_migrated_hosted_claim_checks_actual_paths_global_scope_and_source_tree(self):
        for scopes,paths,tree,expected in [(["docs/**"],"docs/x.md","5"*40,None),
                (["docs/**"],"src/app.py","5"*40,"V3_WRITE_SET_ESCAPE"),
                (["proofos_omega/**"],"proofos_omega/repository_lease_issuer.py","5"*40,"V3_GLOBAL_PATH_REQUIRES_REPOSITORY_SCOPE"),
                (["docs/**"],"docs/x.md","6"*40,"V3_SOURCE_TREE_MISMATCH")]:
            own=lease("A",scopes,12,"writer",expires="2099-01-01T00:00:00+00:00")
            reg=dict(registry(own,generation=12),migration=self.migration())
            result,_,_=self.hosted_assess(self.tombstone(),registry_payload=reg,body=json.dumps(claim(own)),paths=paths,source_tree=tree)
            self.assertEqual("PASS" if expected is None else "FAIL",result["status"])
            if expected:
                self.assertIn(expected,self.rules(result))

    def test_recovery_and_reclaim_preserve_migration_and_unrelated_metadata(self):
        own=lease("A",["alpha/**"],12,"original",expires="2020-01-01T00:00:00+00:00")
        reg=dict(registry(own,generation=12),migration=self.migration(),custom_metadata={"keep":True})
        for state in ["SUSPECT","ORPHANED","RECLAIMABLE"]:
            result=transition_recovery(reg,"A",target_state=state,expected_fencing_token=12,actor="recovery",now=NOW,policy=self.policy)
            self.assertEqual("PASS",result["status"])
            reg=result["registry"]
        replacement=lease("B",["alpha/**"],reg["generation"]+1,"new-owner")
        result=reclaim_lease(reg,"A",replacement,expected_fencing_token=12,actor="recovery",now=NOW,policy=self.policy)
        self.assertEqual("PASS",result["status"])
        self.assertEqual(self.migration(),result["registry"]["migration"])
        self.assertEqual({"keep":True},result["registry"]["custom_metadata"])

    def test_recovery_and_fence_validation_reject_nonexact_integer_fences(self):
        active=lease("A",["alpha/**"],12,"original",expires="2020-01-01T00:00:00+00:00")
        reg=registry(active,generation=15)
        reclaimable=registry(dict(active,state="RECLAIMABLE"),generation=15)
        replacement=lease("B",["alpha/**"],16,"new-owner")
        for invalid in [True,False,12.9,"12",None]:
            with self.subTest(fence=invalid):
                self.assertEqual("FAIL",transition_recovery(reg,"A",expected_fencing_token=invalid,
                    actor="recovery",target_state="SUSPECT",now=NOW)["status"])
                self.assertEqual("FAIL",reclaim_lease(reclaimable,"A",replacement,
                    expected_fencing_token=invalid,actor="recovery",now=NOW)["status"])
                self.assertEqual("FAIL",validate_fence(reg,"A",invalid)["status"])
        for invalid in [True,16.75,"16"]:
            self.assertEqual("FAIL",reclaim_lease(reclaimable,"A",dict(replacement,fencing_token=invalid),
                expected_fencing_token=12,actor="recovery",now=NOW)["status"])
        for invalid in [True,12.9,"12"]:
            self.assertEqual("FAIL",validate_fence(dict(reg,stale_fencing_tokens=[invalid]),"A",12)["status"])

    def test_reclaim_rejects_expired_future_or_incoherent_replacement_time(self):
        old=lease("A",["alpha/**"],12,"original",expires="2020-01-01T00:00:00+00:00")
        reg=registry(dict(old,state="RECLAIMABLE"),generation=15)
        replacement=lease("B",["alpha/**"],16,"new-owner")
        for changes in [{"expires_at":"2020-01-01T00:00:00+00:00"},
                        {"acquired_at":replacement["expires_at"]},
                        {"acquired_at":"2098-01-01T00:00:00+00:00","expires_at":"2099-01-01T00:00:00+00:00"},
                        {"acquired_at":"invalid"}]:
            result=reclaim_lease(reg,"A",dict(replacement,**changes),
                expected_fencing_token=12,actor="recovery",now=NOW)
            self.assertEqual("FAIL",result["status"])

    def test_recovery_cannot_erase_original_registry_corruption(self):
        own=lease("A",["alpha/**"],12,"original",expires="2020-01-01T00:00:00+00:00")
        replacement=lease("B",["alpha/**"],16,"new-owner")
        for changes in [{"source_head":"invalid"},{"effect":"WRITE"},{"write_set_digest":"0"*64}]:
            active=registry(dict(own,**changes),generation=15)
            result=transition_recovery(active,"A",expected_fencing_token=12,
                actor="recovery",target_state="SUSPECT",now=NOW)
            self.assertEqual("FAIL",result["status"])
            self.assertEqual(active,result["registry"])
            reclaimable=registry(dict(own,state="RECLAIMABLE",**changes),generation=15)
            result=reclaim_lease(reclaimable,"A",replacement,expected_fencing_token=12,
                actor="recovery",now=NOW)
            self.assertEqual("FAIL",result["status"])
            self.assertEqual(reclaimable,result["registry"])

    def test_hosted_malformed_or_non_pr_context_cannot_pass_empty_compatibility(self):
        for event in ({}, {"merge_group": {}}, {"pull_request": []}, {"pull_request": {"base": {}, "head": {}}}):
            with self.subTest(event=event):
                result, legacy_read, registry_read = self.hosted_assess(self.legacy_lease(state="RELEASED"), event_payload=event)
                self.assertEqual("FAIL", result["status"])
                self.assertEqual("V3_HOSTED_EVENT_CONTEXT_INVALID", result["state"])
                self.assertEqual(0, legacy_read.call_count)
                self.assertEqual(0, registry_read.call_count)

    def test_hosted_merge_group_requires_explicit_adapter_instead_of_pr_assumption(self):
        result, legacy_read, registry_read = self.hosted_assess(self.legacy_lease(state="RELEASED"), event_name="merge_group")
        self.assertEqual("FAIL", result["status"])
        self.assertEqual("V3_HOSTED_EVENT_UNSUPPORTED", result["state"])
        self.assertEqual(0, legacy_read.call_count)
        self.assertEqual(0, registry_read.call_count)

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

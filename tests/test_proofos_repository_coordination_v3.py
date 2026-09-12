from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from proofos_omega.repository_coordination_v3 import (
    CLAIM_SCHEMA,
    DEFAULT_REGISTRY_REF,
    LEASE_SCHEMA,
    REGISTRY_SCHEMA,
    can_acquire,
    evaluate,
    extract_claim,
    load_policy,
    normalize_write_set,
    parse_registry_message,
    scopes_overlap,
    write_set_digest,
)

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


if __name__ == "__main__":
    unittest.main()

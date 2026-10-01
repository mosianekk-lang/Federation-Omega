from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from proofos_omega import repository_lease_issuer as issuer
from proofos_omega import repository_coordination as legacy
from proofos_omega import repository_coordination_v3 as scoped

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
LOCK = legacy.DEFAULT_LEASE_REF
REGISTRY = scoped.DEFAULT_REGISTRY_REF


def witness(capture="tc-cutover", verified=True):
    return {"provider":"FEDERATION_SYNC_BUS_TURN_CAPTURE", "capture_id":capture,
            "provider_readback_verified":verified}


class RepositoryLeaseIssuerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "work"
        self.root.mkdir()
        self.git("init", "--bare", "-q", str(base / "origin.git"))
        self.git("init", "-q")
        self.git("config", "user.name", "Lease Test")
        self.git("config", "user.email", "lease@example.invalid")
        self.git("remote", "add", "origin", str(base / "origin.git"))
        (self.root / "source.txt").write_text("source\n")
        self.git("add", "source.txt")
        self.git("commit", "-qm", "source")
        self.head = self.git("rev-parse", "HEAD")
        self.tree = self.git("show", "-s", "--format=%T", self.head)
        self.push(self.head, "refs/heads/main")
        self.legacy_payload = {"schema":legacy.LEASE_SCHEMA,"state":"RELEASED","fencing_token":355,
                               "source_head":self.head,"effect":"NONE"}
        self.legacy_sha = self.commit(legacy.LEASE_SCHEMA, self.legacy_payload, self.head)
        self.push(self.legacy_sha, LOCK)
        self.registry = {"schema":scoped.REGISTRY_SCHEMA,"generation":12,"active_leases":[],
                         "mode":"SHADOW_CANARY","custom_metadata":{"preserve":True}}
        self.registry_sha = self.commit(scoped.REGISTRY_SCHEMA,self.registry,self.head)
        self.push(self.registry_sha,REGISTRY)

    def git(self,*args,check=True):
        result=subprocess.run(["git",*args],cwd=self.root,text=True,capture_output=True)
        if check and result.returncode:
            self.fail(result.stderr)
        return result.stdout.strip() if check else result

    def push(self,sha,ref,check=True):
        return self.git("push","-q","origin",f"{sha}:{ref}",check=check)

    def commit(self,schema,payload,parent):
        return self.git("commit-tree",self.tree,"-p",parent,"-m",schema+"\n"+json.dumps(payload,sort_keys=True))

    def publish(self,spec):
        sha=self.git("commit-tree",spec["tree_sha"],"-p",spec["parent_sha"],"-m",spec["message"])
        self.push(sha,spec["lease_ref"])
        return sha

    def freeze_spec(self):
        return issuer.build_migration_freeze_commit_spec(self.root,
            predecessor_lease_sha=self.legacy_sha,predecessor_registry_sha=self.registry_sha,
            cutover_id="cutover-355",turn_capture_id="tc-cutover",turn_capture_witness=witness(),now=NOW)

    def activate(self):
        self.tombstone_sha=self.publish(self.freeze_spec())
        spec=issuer.build_registry_cutover_commit_spec(self.root,
            predecessor_registry_sha=self.registry_sha,migration_tombstone_sha=self.tombstone_sha,
            turn_capture_witness=witness(),now=NOW)
        self.registry_sha=self.publish(spec)
        self.registry=json.loads(spec["message"].split("\n",1)[1])

    def lease(self,name="a",paths=None):
        paths=paths or ["alpha/**"]
        return {"schema":scoped.LEASE_SCHEMA,"lease_id":name,"state":"ACTIVE",
            "fencing_token":self.registry["generation"]+1,"writer_node":"writer-"+name,
            "system":"FDOF","workstream":"test","transaction_id":"txn-"+name,
            "idempotency_key":"idem-"+name,"source_head":self.head,"source_tree":self.tree,
            "write_set":paths,"write_set_digest":scoped.write_set_digest(paths),
            "acquired_at":"2026-10-01T11:59:00+00:00","expires_at":"2026-10-01T13:00:00+00:00",
            "turn_capture_id":"tc-"+name,"effect":"NONE","authority":"A1_INTERNAL_SOURCE_CI"}

    def spec(self,payload):
        return issuer.build_lease_commit_spec(self.root,payload,predecessor_lease_sha=self.registry_sha,
            turn_capture_witness=witness(payload["turn_capture_id"]),now=NOW)

    def acquire(self,payload):
        spec=self.spec(payload)
        self.registry_sha=self.publish(spec)
        self.registry=json.loads(spec["message"].split("\n",1)[1])
        return spec

    def test_default_rejects_new_v2_even_with_explicit_legacy_policy(self):
        with self.assertRaisesRegex(ValueError,"V2_NEW_ACQUISITION_FROZEN"):
            issuer.build_lease_commit_spec(self.root,dict(self.legacy_payload,state="ACTIVE"),
                predecessor_lease_sha=self.legacy_sha,turn_capture_witness=witness(),policy=legacy.load_policy())

    def test_v3_issue_requires_barrier_and_preserves_source_tree_capture(self):
        with self.assertRaisesRegex(ValueError,"MIGRATION"):
            self.spec(self.lease())
        self.activate()
        spec=self.acquire(self.lease())
        self.assertEqual(self.tree,spec["tree_sha"])
        self.assertEqual(REGISTRY,spec["lease_ref"])
        self.assertFalse(spec["provider_effect_authorized"])
        self.assertEqual("SHADOW_CANARY",self.registry["mode"])
        self.assertEqual({"preserve":True},self.registry["custom_metadata"])
        self.assertEqual(self.tombstone_sha,self.registry["migration"]["legacy_tombstone_sha"])
        self.assertEqual(self.head,self.registry["migration"]["issuer_source_head"])
        self.assertEqual(self.tree,self.registry["migration"]["issuer_source_tree"])

    def test_active_or_expired_legacy_cannot_be_retired(self):
        for expiry in ["2099-01-01T00:00:00+00:00","2020-01-01T00:00:00+00:00"]:
            self.legacy_payload.update(state="ACTIVE",expires_at=expiry)
            self.legacy_sha=self.commit(legacy.LEASE_SCHEMA,self.legacy_payload,self.legacy_sha)
            self.push(self.legacy_sha,LOCK)
            with self.assertRaisesRegex(ValueError,"PREDECESSOR_LEASE_NOT_TERMINAL"):
                self.freeze_spec()

    def test_v2_acquire_wins_race_and_cutover_loses_non_fast_forward(self):
        freeze=self.freeze_spec()
        old_acquire=self.commit(legacy.LEASE_SCHEMA,dict(self.legacy_payload,state="ACTIVE"),self.legacy_sha)
        self.push(old_acquire,LOCK)
        tombstone=self.git("commit-tree",freeze["tree_sha"],"-p",freeze["parent_sha"],"-m",freeze["message"])
        self.assertNotEqual(0,self.push(tombstone,LOCK,check=False).returncode)
        with self.assertRaisesRegex(ValueError,"MIGRATION"):
            issuer.build_registry_cutover_commit_spec(self.root,predecessor_registry_sha=self.registry_sha,
                migration_tombstone_sha=tombstone,turn_capture_witness=witness(),now=NOW)

    def test_tombstone_wins_race_and_stale_v2_acquire_loses(self):
        old_acquire=self.commit(legacy.LEASE_SCHEMA,dict(self.legacy_payload,state="ACTIVE"),self.legacy_sha)
        tombstone=self.publish(self.freeze_spec())
        self.assertNotEqual(0,self.push(old_acquire,LOCK,check=False).returncode)
        descriptor=json.loads(self.git("show","-s","--format=%B",tombstone).split("\n",1)[1])
        self.assertEqual("MIGRATED_TO_V3",descriptor["state"])
        self.assertNotIn(descriptor["state"],issuer.TERMINAL_STATES)
        with self.assertRaisesRegex(ValueError,"MIGRATION"):
            self.spec(self.lease())
        activated=issuer.build_registry_cutover_commit_spec(self.root,
            predecessor_registry_sha=self.registry_sha,migration_tombstone_sha=tombstone,
            turn_capture_witness=witness(),now=NOW)
        self.assertEqual(self.registry_sha,activated["parent_sha"])

    def test_disjoint_same_parent_cas_loser_rereads_and_recompiles(self):
        self.activate()
        a,b=self.spec(self.lease("a")),self.spec(self.lease("b",["beta/**"]))
        a_sha=self.publish(a)
        b_sha=self.git("commit-tree",b["tree_sha"],"-p",b["parent_sha"],"-m",b["message"])
        self.assertNotEqual(0,self.push(b_sha,REGISTRY,check=False).returncode)
        with self.assertRaisesRegex(ValueError,"CURRENT"):
            self.spec(self.lease("b",["beta/**"]))
        self.registry_sha=a_sha
        self.registry=json.loads(a["message"].split("\n",1)[1])
        self.acquire(self.lease("b",["beta/**"]))
        self.assertEqual({"a","b"},{x["lease_id"] for x in self.registry["active_leases"]})
        self.assertEqual(15,self.registry["generation"])

    def test_global_and_scoped_leases_share_overlap_exclusion(self):
        self.activate()
        self.acquire(self.lease("a"))
        for paths in [["alpha/x.py"],["repository:*"]]:
            with self.assertRaisesRegex(ValueError,"V3_ACQUIRE_CONFLICT"):
                self.spec(self.lease("b",paths))

    def test_new_global_scope_blocks_every_other_scope(self):
        self.activate()
        self.acquire(self.lease("global",["repository:*"]))
        with self.assertRaisesRegex(ValueError,"V3_ACQUIRE_CONFLICT"):
            self.spec(self.lease("b",["unrelated/**"]))

    def test_capture_source_head_tree_and_fence_fail_closed(self):
        self.activate()
        for changes,error in [({"source_tree":"0"*40},"TREE"),({"source_head":"1"*40},"SOURCE"),
                              ({"fencing_token":12},"FENCE"),({"effect":"WRITE"},"EFFECT")]:
            with self.subTest(changes=changes),self.assertRaisesRegex(ValueError,error):
                self.spec(dict(self.lease(),**changes))
        for capture in [witness("wrong"),witness("tc-a",False),dict(witness("tc-a"),provider="wrong")]:
            with self.assertRaisesRegex(ValueError,"TURN_CAPTURE"):
                issuer.build_lease_commit_spec(self.root,self.lease(),predecessor_lease_sha=self.registry_sha,
                    turn_capture_witness=capture,now=NOW)

    def test_release_requires_exact_owner_fence_and_preserves_migration(self):
        self.activate()
        self.acquire(self.lease())
        original=dict(self.registry["migration"])
        args=dict(predecessor_registry_sha=self.registry_sha,lease_id="a",fencing_token=14,
                  writer_node="writer-a",terminal_state="RELEASED",turn_capture_id="tc-release",
                  turn_capture_witness=witness("tc-release"),now=NOW)
        for changes,error in [({"writer_node":"other"},"OWNER"),({"fencing_token":13},"FENCE")]:
            with self.assertRaisesRegex(ValueError,error):
                issuer.build_release_commit_spec(self.root,**dict(args,**changes))
        for invalid in [True,14.75,"14",None]:
            with self.assertRaisesRegex(ValueError,"FENCE"):
                issuer.build_release_commit_spec(self.root,**dict(args,fencing_token=invalid))
        spec=issuer.build_release_commit_spec(self.root,**args)
        result=json.loads(spec["message"].split("\n",1)[1])
        self.assertEqual([],result["active_leases"])
        self.assertEqual(original,result["migration"])
        self.assertEqual("SHADOW_CANARY",result["mode"])
        self.assertIn(14,result["stale_fencing_tokens"])
        self.assertEqual(15,result["generation"])

    def test_mismatched_barrier_and_registry_drift_fail_closed(self):
        self.activate()
        for migration in [None,{},dict(self.registry["migration"],cutover_id="fake")]:
            changed=dict(self.registry,migration=migration)
            self.registry_sha=self.commit(scoped.REGISTRY_SCHEMA,changed,self.registry_sha)
            self.push(self.registry_sha,REGISTRY)
            with self.assertRaisesRegex(ValueError,"MIGRATION"):
                self.spec(self.lease())

    def test_nonempty_pre_cutover_registry_is_not_discarded(self):
        self.registry["active_leases"]=[self.lease()]
        self.registry_sha=self.commit(scoped.REGISTRY_SCHEMA,self.registry,self.registry_sha)
        self.push(self.registry_sha,REGISTRY)
        with self.assertRaisesRegex(ValueError,"EMPTY"):
            self.freeze_spec()

    def test_registry_change_during_cutover_gap_cannot_rebind_seed(self):
        tombstone=self.publish(self.freeze_spec())
        old_seed=self.registry_sha
        changed=dict(self.registry,generation=13,other_observation="changed")
        self.registry_sha=self.commit(scoped.REGISTRY_SCHEMA,changed,old_seed)
        self.push(self.registry_sha,REGISTRY)
        for seed,error in [(old_seed,"CURRENT"),(self.registry_sha,"SEED_MISMATCH")]:
            with self.assertRaisesRegex(ValueError,error):
                issuer.build_registry_cutover_commit_spec(self.root,predecessor_registry_sha=seed,
                    migration_tombstone_sha=tombstone,turn_capture_witness=witness(),now=NOW)
        with self.assertRaisesRegex(ValueError,"MIGRATION"):
            self.spec(self.lease())

    def test_stale_release_cas_cannot_erase_new_disjoint_owner(self):
        self.activate()
        self.acquire(self.lease())
        args=dict(predecessor_registry_sha=self.registry_sha,lease_id="a",fencing_token=14,
                  writer_node="writer-a",terminal_state="RELEASED",turn_capture_id="tc-release",
                  turn_capture_witness=witness("tc-release"),now=NOW)
        release=issuer.build_release_commit_spec(self.root,**args)
        self.acquire(self.lease("b",["beta/**"]))
        stale=self.git("commit-tree",release["tree_sha"],"-p",release["parent_sha"],"-m",release["message"])
        self.assertNotEqual(0,self.push(stale,REGISTRY,check=False).returncode)
        with self.assertRaisesRegex(ValueError,"CURRENT"):
            issuer.build_release_commit_spec(self.root,**args)
        release=issuer.build_release_commit_spec(self.root,**dict(args,predecessor_registry_sha=self.registry_sha))
        result=json.loads(release["message"].split("\n",1)[1])
        self.assertEqual(["b"],[x["lease_id"] for x in result["active_leases"]])
        self.assertEqual(self.registry["migration"],result["migration"])

    def test_freeze_source_provenance_tree_mismatch_cannot_activate(self):
        spec=self.freeze_spec()
        payload=json.loads(spec["message"].split("\n",1)[1])
        payload["migration"]["issuer_source_tree"]="0"*40
        bad=self.commit(legacy.LEASE_SCHEMA,payload,spec["parent_sha"])
        self.push(bad,LOCK)
        with self.assertRaisesRegex(ValueError,"TREE"):
            issuer.build_registry_cutover_commit_spec(self.root,predecessor_registry_sha=self.registry_sha,
                migration_tombstone_sha=bad,turn_capture_witness=witness(),now=NOW)


if __name__ == "__main__":
    unittest.main()

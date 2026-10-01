from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from federation.fuse_x_finality_v1 import *

class FakeTransport:
    def whoami(self): return {"data":{"id":"u1","username":"owner"}}
    def timeline(self,n=100): return {"data":[{"id":"1","text":"AI agents https://github.com/example/repo","author_id":"u2","created_at":"2026-09-19T00:00:00Z"},{"id":"2","text":"multimodal"}],"meta":{"newest_id":"2","oldest_id":"1","result_count":2}}
    def search_recent(self,q,n=100): return {"data":[{"id":"3","text":f"search {q}"}],"meta":{"newest_id":"3","oldest_id":"3","result_count":1}}

class FuseXFinalityV1Tests(unittest.TestCase):
    def setUp(self): self.td=tempfile.TemporaryDirectory(); self.path=str(Path(self.td.name)/"x.db")
    def tearDown(self): self.td.cleanup()
    def test_digest_stable(self): self.assertEqual(digest({"a":1}),digest({"a":1}))
    def test_observation_requires_id(self):
        with self.assertRaises(ValueError): Observation.from_post("home",{"text":"x"})
    def test_observation_hash_changes(self): self.assertNotEqual(Observation.from_post("h",{"id":"1","text":"a"}).content_hash,Observation.from_post("h",{"id":"1","text":"b"}).content_hash)
    def test_exactly_once(self):
        s=ObservationStore(self.path); o=Observation.from_post("home",{"id":"1","text":"a"}); self.assertEqual(s.commit_page("home",[o],{}),1); self.assertEqual(s.commit_page("home",[o],{}),0); self.assertEqual(s.count(),1); s.close()
    def test_versioned_content(self):
        s=ObservationStore(self.path); s.commit_page("home",[Observation.from_post("home",{"id":"1","text":"a"})],{}); s.commit_page("home",[Observation.from_post("home",{"id":"1","text":"b"})],{}); self.assertEqual(s.count(),2); s.close()
    def test_cursor_persistence(self):
        s=ObservationStore(self.path); s.commit_page("home",[],{"newest_id":"9"}); s.close(); s=ObservationStore(self.path); self.assertEqual(s.get_cursor("home")["newest_id"],"9"); s.close()
    def test_local_search(self):
        s=ObservationStore(self.path); s.commit_page("home",[Observation.from_post("home",{"id":"1","text":"sovereign agent"})],{}); self.assertTrue(s.search("sovereign")); s.close()
    def test_harvest_home(self):
        s=ObservationStore(self.path); r=Harvester(FakeTransport(),s).home_once(); self.assertEqual((r.observed,r.inserted),(2,2)); s.close()
    def test_search_harvest(self):
        s=ObservationStore(self.path); self.assertEqual(Harvester(FakeTransport(),s).search_once("AI",10).inserted,1); s.close()
    def test_restart_recovery(self):
        s=ObservationStore(self.path); s.commit_page("home",[Observation.from_post("home",{"id":"1","text":"a"})],{"newest_id":"1"}); s.close(); self.assertTrue(restart_recovery_probe(self.path))
    def test_finality_empty_open(self): self.assertFalse(evaluate({}).complete)
    def test_finality_all_closed(self): self.assertTrue(evaluate({p:"VERIFIED" for p in REQUIRED}).complete)
    def test_feed_term(self):
        s=ObservationStore(self.path); Harvester(FakeTransport(),s).home_once(); self.assertEqual(derived_feed(s,["agents"])[0]["canonical_id"],"1"); s.close()
    def test_feed_no_terms(self):
        s=ObservationStore(self.path); Harvester(FakeTransport(),s).home_once(); self.assertEqual(len(derived_feed(s,[])),2); s.close()
    def test_verification_candidate_primary(self): self.assertEqual(len(verification_candidate("1","see https://github.com/a/b")["primary_hints"]),1)
    def test_verification_candidate_none(self): self.assertEqual(verification_candidate("1","none")["status"],"NO_EXTERNAL_SOURCE")
    def test_live_tick_closes_transport_and_home(self):
        s=ObservationStore(self.path); r=bounded_live_tick(FakeTransport(),s,["AI"],10); fm=s.finality_map(); self.assertFalse(r["errors"]); self.assertEqual(fm["X_AUTHORIZED_TRANSPORT_VERIFIED"]["state"],"VERIFIED"); self.assertEqual(fm["X_HOME_TIMELINE_INGESTION_VERIFIED"]["state"],"VERIFIED"); s.close()
    def test_missing_token_fails_closed(self):
        with self.assertRaises(XTransportError): DirectXTransport(token_provider=lambda:"").whoami()
    def test_required_predicates_include_owner_zero_routine(self): self.assertIn("OWNER_ROUTINE_ACTION_FALSE",REQUIRED)
    def test_no_write_methods_exist(self):
        self.assertFalse(set(dir(DirectXTransport)) & {"post","reply","like","repost","follow","message","delete"})

if __name__=="__main__": unittest.main()

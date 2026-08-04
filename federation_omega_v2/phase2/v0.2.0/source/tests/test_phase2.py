from pathlib import Path
import json,tempfile,unittest
from federation_omega_v2 import EventStore,Relationship,CanonicalQueryService,import_canonical_register,run_evidenceops_reference_mission

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.db=Path(self.temp.name)/"state.sqlite"; self.store=EventStore(self.db)
        self.register=json.loads((Path(__file__).parents[1]/"CANONICAL_SYSTEM_REGISTER.json").read_text())
    def tearDown(self): self.temp.cleanup()
    def test_01_import_count(self): self.assertEqual(import_canonical_register(self.store,self.register)["system_count"],20)
    def test_02_entity_count(self): import_canonical_register(self.store,self.register); self.assertEqual(self.store.verify()["entity_count"],20)
    def test_03_relationship_count(self): import_canonical_register(self.store,self.register); self.assertEqual(self.store.verify()["relationship_count"],22)
    def test_04_idempotent_import(self):
        import_canonical_register(self.store,self.register); result=import_canonical_register(self.store,self.register)
        self.assertTrue(all(item["state"]=="IDEMPOTENT_REPLAY" for item in result["systems"]))
    def test_05_query_system(self):
        import_canonical_register(self.store,self.register); query=CanonicalQueryService(self.store).system("SYS-EVIDENCEOPS")
        self.assertEqual(query["state"]["name"],"EvidenceOps")
    def test_06_query_edges(self):
        import_canonical_register(self.store,self.register); query=CanonicalQueryService(self.store).system("SYS-EVIDENCEOPS")
        self.assertTrue(query["incoming"] and query["outgoing"])
    def test_07_restart(self):
        import_canonical_register(self.store,self.register); before=self.store.project("SYS-FEDERATION-OMEGA")
        after=EventStore(self.db).project("SYS-FEDERATION-OMEGA"); self.assertEqual(before,after)
    def test_08_hash_verify(self): import_canonical_register(self.store,self.register); self.assertEqual(self.store.verify()["quick_check"],"ok")
    def test_09_self_edge(self):
        with self.assertRaises(ValueError): self.store.add_relationship(Relationship("SYS-A","SYS-A","USES"))
    def test_10_edge_idempotent(self):
        relationship=Relationship("SYS-A","SYS-B","USES"); self.store.add_relationship(relationship)
        self.assertEqual(self.store.add_relationship(relationship)["state"],"IDEMPOTENT_REPLAY")
    def test_11_reference_mission(self): self.assertEqual(run_evidenceops_reference_mission(self.store)["stage_count"],10)
    def test_12_reference_zero_effect(self): self.assertEqual(run_evidenceops_reference_mission(self.store)["external_effects"],0)
    def test_13_reference_idempotent(self):
        first=run_evidenceops_reference_mission(self.store); second=run_evidenceops_reference_mission(self.store)
        self.assertEqual(first["mission"]["mission_id"],second["mission"]["mission_id"]); self.assertEqual(self.store.verify()["event_count"],10)
    def test_14_reference_restart(self):
        result=run_evidenceops_reference_mission(self.store); query=CanonicalQueryService(EventStore(self.db)).mission(result["mission"]["mission_id"])
        self.assertEqual(len(query["projection"]["state"]["stages"]),10)
    def test_15_route_legal(self): self.assertEqual(CanonicalQueryService(self.store).route("legal evidence")["system"],"SYS-EVIDENCEOPS")
    def test_16_route_cloud(self): self.assertEqual(CanonicalQueryService(self.store).route("deploy cloud software")["system"],"SYS-CLOUDOPS")
    def test_17_route_no_effect(self): self.assertFalse(CanonicalQueryService(self.store).route("trade strategy")["external_effects"])
    def test_18_all_a1(self):
        import_canonical_register(self.store,self.register)
        self.assertTrue(all(item["payload_obj"]["state"]["authority_ceiling"]=="A1" for item in self.store.events()))
    def test_19_canonical(self):
        import_canonical_register(self.store,self.register); self.assertTrue(self.store.project("SYS-BIBLE")["state"]["canonical"])
    def test_20_unknown(self): self.assertEqual(CanonicalQueryService(self.store).system("SYS-UNKNOWN")["proof_state"],"UNKNOWN")

if __name__=="__main__": unittest.main()

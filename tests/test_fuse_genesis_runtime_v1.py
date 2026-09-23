import tempfile,shutil,pathlib,unittest
from fuse_genesis.cold_boot import *
from fuse_genesis.currentness import SourceEpoch,SourceCurrentnessError,resolve_source_epoch

E=SourceEpoch("a"*40,"F323",323,"GENESIS")
class T(unittest.TestCase):
 def setUp(self): self.d=pathlib.Path(tempfile.mkdtemp())
 def tearDown(self): shutil.rmtree(self.d,ignore_errors=True)
def add(n,fn): setattr(T,f"test_{n:02d}",fn)
def receipt(s,n="b"): return cold_boot_receipt(s.d/n,E)
add(1,lambda s:s.assertTrue(receipt(s)["state_chain_valid"]))
add(2,lambda s:s.assertEqual(receipt(s)["lease_state"],"ACTIVE_EXPIRED_NONTERMINAL"))
add(3,lambda s:s.assertEqual(receipt(s)["unknown_preserved"],"UNKNOWN"))
add(4,lambda s:s.assertTrue(receipt(s)["object_verified"]))
add(5,lambda s:s.assertTrue(receipt(s)["event_drained"]))
add(6,lambda s:s.assertTrue(receipt(s)["identity_valid"]))
add(7,lambda s:s.assertTrue(receipt(s)["session_admitted"]))
add(8,lambda s:s.assertEqual(receipt(s)["local_model"],"local-reasoner"))
add(9,lambda s:s.assertEqual(receipt(s)["local_creative"],"local-renderer"))
add(10,lambda s:s.assertFalse(receipt(s)["external_provider_required"]))
def stale(s):
 x=SovereignState(s.d/"s"); x.acquire_lease("x","F323",323)
 with s.assertRaises(StaleFence): x.acquire_lease("x","old",322)
 x.close()
add(11,stale)
def rel(s):
 x=SovereignState(s.d/"s"); x.acquire_lease("x","F323",323); x.release("x","F323",323); s.assertEqual(x.lease("x")["state"],"RELEASED"); x.close()
add(12,rel)
def fact(s):
 x=SovereignState(s.d/"s"); x.put_fact("f","DISPUTED",{"x":1}); s.assertEqual(x.fact("f")["state"],"DISPUTED"); x.close()
add(13,fact)
def term(s):
 x=SovereignState(s.d/"s"); x.upsert_mission("m","RUNNING",{}); x.terminalize("m","COMPLETE")
 with s.assertRaises(InvalidTransition): x.upsert_mission("m","RUNNING",{})
 x.close()
add(14,term)
def eff(s):
 x=SovereignState(s.d/"s"); x.prepare_effect("e","k",{"x":1})
 with s.assertRaises(DuplicateEffect): x.prepare_effect("z","k",{"x":2})
 x.close()
add(15,eff)
def rb(s):
 x=SovereignState(s.d/"s"); x.prepare_effect("e","k",{}); x.unknown_effect("e"); s.assertEqual(x.readback_effect("e",True)["state"],"VERIFIED"); x.close()
add(16,rb)
def chain(s):
 x=SovereignState(s.d/"s"); x.append_event("a",{"x":1}); x.append_event("b",{"x":2}); s.assertTrue(x.verify_chain()); x.close()
add(17,chain)
def obj(s):
 o=ObjectStore(s.d/"o"); oid=o.put(b"x"); s.assertEqual(o.get(oid),b"x")
add(18,obj)
def corrupt(s):
 o=ObjectStore(s.d/"o"); oid=o.put(b"x"); (o.root/oid.split(":",1)[1]).write_bytes(b"y"); s.assertFalse(o.verify(oid))
add(19,corrupt)
def bus(s):
 e=EventFabric(s.d/"e"); a=e.publish(Event("a","k",{})); b=e.publish(Event("b","k",{"x":1})); s.assertEqual(a,b); e.close()
add(20,bus)
def ident(s):
 r=IdentityRegistry()
 with s.assertRaises(ValueError): r.add(Identity("x","PRIVATE:key"))
add(21,ident)
def tok(s):
 r=IdentityRegistry(); r.add(Identity("u","keyref:u")); t=TokenIssuer(r).issue("u","a",0,100); s.assertTrue(TokenIssuer(r).valid(t,"a",50)); r.revoke("u"); s.assertFalse(TokenIssuer(r).valid(t,"a",50))
add(22,tok)
add(23,lambda s:s.assertFalse(SessionGateway("m","F",1).admit("z","F",1)))
add(24,lambda s:s.assertFalse(SessionGateway("m","F",1).admit("m","Q",1)))
add(25,lambda s:s.assertFalse(SessionGateway("m","F",1).admit("m","F",2)))
def model(s):
 m=ModelMarket(); m.add(Model("hosted",False,("reason",),True)); m.add(Model("local",True,("reason",),True)); s.assertEqual(m.choose(("reason",)).id,"local")
add(26,model)
def creative(s):
 m=CreativeMarket(); m.add(Creative("hosted",False,("image",),True,True)); m.add(Creative("local",True,("image",),True,True)); s.assertEqual(m.choose(("image",)).id,"local")
add(27,creative)
add(28,lambda s:s.assertEqual(len(receipt(s)["digest"]),64))
add(29,lambda s:s.assertEqual(receipt(s)["source_epoch"]["main_sha"],"a"*40))
def source_pair(s):
 r=receipt(s); s.assertEqual((r["source_epoch"]["writer"],r["source_epoch"]["fence"]),("F323",323))
add(30,source_pair)
def missing(s):
 with s.assertRaises(SourceCurrentnessError): cold_boot_receipt(s.d/"missing",environ={})
add(31,missing)
def env(s):
 e={"FUSE_GENESIS_SOURCE_MAIN":"b"*40,"FUSE_GENESIS_SOURCE_WRITER":"F400","FUSE_GENESIS_SOURCE_FENCE":"400","FUSE_GENESIS_MISSION_ID":"M400"}
 x=cold_boot_receipt(s.d/"env",environ=e); s.assertEqual(x["source_epoch"]["fence"],400); s.assertEqual(x["source_epoch"]["mission_id"],"M400")
add(32,env)
def badsha(s):
 with s.assertRaises(SourceCurrentnessError): SourceEpoch("stale","F1",1)
add(33,badsha)
def badfence(s):
 with s.assertRaises(SourceCurrentnessError): SourceEpoch("a"*40,"F1",0)
add(34,badfence)
add(35,lambda s:s.assertEqual(len(E.digest),64))
for n in range(36,66):
 def make(n):
  def f(s):
   ep=SourceEpoch((f"{n:040x}")[-40:],"F"+str(300+n),300+n,"GENESIS")
   r=cold_boot_receipt(s.d/f"b{n}",ep)
   s.assertTrue(r["state_chain_valid"] and r["object_verified"] and r["identity_valid"] and r["session_admitted"])
   s.assertEqual(r["source_epoch"]["main_sha"],ep.main_sha); s.assertEqual(r["source_epoch"]["fence"],ep.fence)
   s.assertEqual(r["unknown_preserved"],"UNKNOWN"); s.assertFalse(r["external_provider_required"])
  return f
 add(n,make(n))
if __name__=="__main__": unittest.main(verbosity=2)

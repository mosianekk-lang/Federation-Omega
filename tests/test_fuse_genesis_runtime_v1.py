import tempfile,shutil,pathlib,unittest
from fuse_genesis.cold_boot import *
class T(unittest.TestCase):
 def setUp(self): self.d=pathlib.Path(tempfile.mkdtemp())
 def tearDown(self): shutil.rmtree(self.d,ignore_errors=True)
def add(n,fn): setattr(T,f"test_{n:02d}",fn)
add(1,lambda s:s.assertTrue(cold_boot_receipt(s.d/"b")["state_chain_valid"]))
add(2,lambda s:s.assertEqual(cold_boot_receipt(s.d/"b")["lease_state"],"ACTIVE_EXPIRED_NONTERMINAL"))
add(3,lambda s:s.assertEqual(cold_boot_receipt(s.d/"b")["unknown_preserved"],"UNKNOWN"))
add(4,lambda s:s.assertTrue(cold_boot_receipt(s.d/"b")["object_verified"]))
add(5,lambda s:s.assertTrue(cold_boot_receipt(s.d/"b")["event_drained"]))
add(6,lambda s:s.assertTrue(cold_boot_receipt(s.d/"b")["identity_valid"]))
add(7,lambda s:s.assertTrue(cold_boot_receipt(s.d/"b")["session_admitted"]))
add(8,lambda s:s.assertEqual(cold_boot_receipt(s.d/"b")["local_model"],"local-reasoner"))
add(9,lambda s:s.assertEqual(cold_boot_receipt(s.d/"b")["local_creative"],"local-renderer"))
add(10,lambda s:s.assertFalse(cold_boot_receipt(s.d/"b")["external_provider_required"]))
def stale(s):
 x=SovereignState(s.d/"s"); x.acquire_lease("x","F320",320)
 with s.assertRaises(StaleFence): x.acquire_lease("x","old",319)
 x.close()
add(11,stale)
def rel(s):
 x=SovereignState(s.d/"s"); x.acquire_lease("x","F320",320); x.release("x","F320",320); s.assertEqual(x.lease("x")["state"],"RELEASED"); x.close()
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
add(28,lambda s:s.assertEqual(len(cold_boot_receipt(s.d/"b")["digest"]),64))
add(29,lambda s:s.assertEqual(MAIN,"55fd191796327e0b4ab131c0faf2e09a8ad7b575"))
add(30,lambda s:s.assertEqual((WRITER,FENCE),("F320",320)))
for n in range(31,61):
 def make(n):
  def f(s):
   r=cold_boot_receipt(s.d/f"b{n}")
   s.assertTrue(r["state_chain_valid"] and r["object_verified"] and r["identity_valid"] and r["session_admitted"])
   s.assertEqual(r["unknown_preserved"],"UNKNOWN"); s.assertFalse(r["external_provider_required"])
  return f
 add(n,make(n))
if __name__=="__main__": unittest.main(verbosity=2)

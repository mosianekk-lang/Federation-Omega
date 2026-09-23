import pathlib,tempfile,unittest

from fuse_genesis.runtime_continuity import (
    ContinuityError,DispatchCollision,DispatchEnvelope,DispatchIngress,DispatchRejected,
    EffectCollision,EffectExecutor,EffectJournal,UnknownEffect,assess_runtime,payload_digest
)

EPOCH="a"*64
PAYLOAD={"kind":"noop","value":1}

def envelope(**kw):
    v=dict(
        dispatch_id="DISPATCH-1",task_id="TASK-1",idempotency_key="IDEM-1",
        mission_id="MISSION-1",scheduler_id="GOOGLE_APPS_SCRIPT",
        source_epoch_digest=EPOCH,payload_sha256=payload_digest(PAYLOAD),
        authority_ref="GOOGLE_APPS_SCRIPT:TRIGGER:gasSchedulerRunV3",
        provider_event_id="GAS-EVENT-1",issued_at=100,expires_at=200,effect_class="A1_INTERNAL"
    )
    v.update(kw)
    return DispatchEnvelope(**v)

class T(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.root=pathlib.Path(self.t.name)
    def tearDown(self): self.t.cleanup()

    def test_01_payload_digest_stable(self):
        self.assertEqual(payload_digest({"a":1,"b":2}),payload_digest({"b":2,"a":1}))
    def test_02_gas_envelope_valid(self):
        self.assertIs(envelope().validate(),envelope().validate().__class__ and envelope().validate())
    def test_03_non_gas_scheduler_rejected(self):
        with self.assertRaisesRegex(DispatchRejected,"GOOGLE_APPS_SCRIPT"):
            envelope(scheduler_id="CHATGPT").validate()
    def test_04_bad_epoch_rejected(self):
        with self.assertRaises(ContinuityError): envelope(source_epoch_digest="bad").validate()
    def test_05_expired_dispatch_rejected(self):
        d=DispatchIngress(self.root/"i.db")
        with self.assertRaisesRegex(DispatchRejected,"EXPIRED"):
            d.accept(envelope(),PAYLOAD,current_epoch_digest=EPOCH,now=200,authority_verifier=lambda a,e:True)
        d.close()
    def test_06_stale_epoch_rejected(self):
        d=DispatchIngress(self.root/"i.db")
        with self.assertRaisesRegex(DispatchRejected,"STALE_SOURCE_EPOCH"):
            d.accept(envelope(),PAYLOAD,current_epoch_digest="b"*64,now=120,authority_verifier=lambda a,e:True)
        d.close()
    def test_07_payload_mismatch_rejected(self):
        d=DispatchIngress(self.root/"i.db")
        with self.assertRaisesRegex(DispatchRejected,"PAYLOAD_HASH_MISMATCH"):
            d.accept(envelope(),{"kind":"other"},current_epoch_digest=EPOCH,now=120,authority_verifier=lambda a,e:True)
        d.close()
    def test_08_authority_readback_required(self):
        d=DispatchIngress(self.root/"i.db")
        with self.assertRaisesRegex(DispatchRejected,"AUTHORITY_READBACK"):
            d.accept(envelope(),PAYLOAD,current_epoch_digest=EPOCH,now=120,authority_verifier=lambda a,e:False)
        d.close()
    def test_09_accept_success(self):
        d=DispatchIngress(self.root/"i.db")
        row=d.accept(envelope(),PAYLOAD,current_epoch_digest=EPOCH,now=120,authority_verifier=lambda a,e:True)
        self.assertEqual(row["task_id"],"TASK-1"); d.close()
    def test_10_dispatch_replay_idempotent(self):
        d=DispatchIngress(self.root/"i.db"); e=envelope()
        a=d.accept(e,PAYLOAD,current_epoch_digest=EPOCH,now=120,authority_verifier=lambda a,e:True)
        b=d.accept(e,PAYLOAD,current_epoch_digest=EPOCH,now=121,authority_verifier=lambda a,e:True)
        self.assertEqual(a["semantic_sha256"],b["semantic_sha256"]); d.close()
    def test_11_dispatch_collision(self):
        d=DispatchIngress(self.root/"i.db")
        d.accept(envelope(),PAYLOAD,current_epoch_digest=EPOCH,now=120,authority_verifier=lambda a,e:True)
        p2={"kind":"noop","value":2}
        with self.assertRaises(DispatchCollision):
            d.accept(envelope(dispatch_id="DISPATCH-2",payload_sha256=payload_digest(p2)),p2,current_epoch_digest=EPOCH,now=121,authority_verifier=lambda a,e:True)
        d.close()
    def test_12_dispatch_persists_restart(self):
        p=self.root/"i.db"; d=DispatchIngress(p)
        d.accept(envelope(),PAYLOAD,current_epoch_digest=EPOCH,now=120,authority_verifier=lambda a,e:True); d.close()
        d=DispatchIngress(p); self.assertEqual(d.row("DISPATCH-1")["scheduler_id"],"GOOGLE_APPS_SCRIPT"); d.close()

    def test_13_effect_prepare(self):
        j=EffectJournal(self.root/"e.db"); self.assertEqual(j.prepare("E1","K1",{"x":1},1)["state"],"PREPARED"); j.close()
    def test_14_effect_collision(self):
        j=EffectJournal(self.root/"e.db"); j.prepare("E1","K1",{"x":1},1)
        with self.assertRaises(EffectCollision): j.prepare("E2","K1",{"x":2},2)
        j.close()
    def test_15_effect_start(self):
        j=EffectJournal(self.root/"e.db"); j.prepare("E1","K1",{},1); self.assertEqual(j.start("E1",2)["state"],"EXECUTING"); j.close()
    def test_16_unknown_blocks_direct_retry(self):
        j=EffectJournal(self.root/"e.db"); j.prepare("E1","K1",{},1); j.mark_unknown("E1",2,"timeout")
        with self.assertRaisesRegex(UnknownEffect,"READBACK_EFFECT"): j.start("E1",3)
        j.close()
    def test_17_negative_unknown_readback_makes_retry_safe(self):
        j=EffectJournal(self.root/"e.db"); j.prepare("E1","K1",{},1); j.mark_unknown("E1",2,"timeout")
        self.assertEqual(j.readback("E1",applied=False,now=3,evidence={"applied":False})["state"],"PREPARED"); j.close()
    def test_18_positive_unknown_readback_closes_effect(self):
        j=EffectJournal(self.root/"e.db"); j.prepare("E1","K1",{},1); j.mark_unknown("E1",2,"timeout")
        self.assertEqual(j.readback("E1",applied=True,now=3,evidence={"applied":True})["state"],"READBACK_VERIFIED"); j.close()
    def test_19_execute_once(self):
        j=EffectJournal(self.root/"e.db"); calls=[]; x=EffectExecutor(j)
        r=x.execute(effect_id="E1",idempotency_key="K1",request={"x":1},now=1,
                    effect_fn=lambda:calls.append(1) or {"ok":1},
                    readback_fn=lambda:{"applied":True,"receipt":"R"})
        self.assertEqual(r["state"],"EXECUTED_AND_VERIFIED"); self.assertEqual(calls,[1]); j.close()
    def test_20_idempotent_effect_replay(self):
        j=EffectJournal(self.root/"e.db"); calls=[]; x=EffectExecutor(j)
        args=dict(effect_id="E1",idempotency_key="K1",request={"x":1},now=1,
                  effect_fn=lambda:calls.append(1) or {"ok":1},readback_fn=lambda:{"applied":True})
        x.execute(**args); r=x.execute(**{**args,"now":2})
        self.assertEqual(r["state"],"IDEMPOTENT_REPLAY"); self.assertEqual(len(calls),1); j.close()
    def test_21_effect_exception_becomes_unknown(self):
        j=EffectJournal(self.root/"e.db"); x=EffectExecutor(j)
        def boom(): raise RuntimeError("transport lost")
        with self.assertRaises(RuntimeError):
            x.execute(effect_id="E1",idempotency_key="K1",request={},now=1,effect_fn=boom,readback_fn=lambda:{"applied":False})
        self.assertEqual(j.row("E1")["state"],"UNKNOWN"); j.close()
    def test_22_unknown_positive_readback_prevents_duplicate_effect(self):
        j=EffectJournal(self.root/"e.db"); j.prepare("E1","K1",{},1); j.mark_unknown("E1",2,"timeout"); calls=[]
        r=EffectExecutor(j).execute(effect_id="E1",idempotency_key="K1",request={},now=3,
             effect_fn=lambda:calls.append(1),readback_fn=lambda:{"applied":True,"provider":"P"})
        self.assertEqual(r["state"],"READBACK_RECOVERED"); self.assertEqual(calls,[]); j.close()
    def test_23_interrupted_executing_negative_readback_allows_retry(self):
        j=EffectJournal(self.root/"e.db"); j.prepare("E1","K1",{},1); j.start("E1",2); calls=[]
        r=EffectExecutor(j).execute(effect_id="E1",idempotency_key="K1",request={},now=3,
             effect_fn=lambda:calls.append(1) or {"ok":1},readback_fn=lambda:{"applied":False} if not calls else {"applied":True})
        self.assertEqual(r["state"],"EXECUTED_AND_VERIFIED"); self.assertEqual(calls,[1]); j.close()
    def test_24_applied_effect_readback_recovery(self):
        j=EffectJournal(self.root/"e.db"); j.prepare("E1","K1",{},1); j.start("E1",2); j.mark_applied("E1",{"ok":1},3); calls=[]
        r=EffectExecutor(j).execute(effect_id="E1",idempotency_key="K1",request={},now=4,
             effect_fn=lambda:calls.append(1),readback_fn=lambda:{"applied":True})
        self.assertEqual(r["state"],"READBACK_RECOVERED"); self.assertEqual(calls,[]); j.close()
    def test_25_post_effect_negative_readback_holds_unknown(self):
        j=EffectJournal(self.root/"e.db"); x=EffectExecutor(j)
        with self.assertRaises(UnknownEffect):
            x.execute(effect_id="E1",idempotency_key="K1",request={},now=1,
                      effect_fn=lambda:{"ok":1},readback_fn=lambda:{"applied":False})
        self.assertEqual(j.row("E1")["state"],"UNKNOWN"); j.close()
    def test_26_compensation_terminal(self):
        j=EffectJournal(self.root/"e.db"); j.prepare("E1","K1",{},1); self.assertEqual(j.compensate("E1",2,{"rolled_back":True})["state"],"COMPENSATED"); j.close()
    def test_27_effect_restart_persists_unknown(self):
        p=self.root/"e.db"; j=EffectJournal(p); j.prepare("E1","K1",{},1); j.mark_unknown("E1",2,"timeout"); j.close()
        j=EffectJournal(p); self.assertEqual(j.row("E1")["state"],"UNKNOWN"); self.assertFalse(j.retry_allowed("E1")); j.close()

    def test_28_watchdog_healthy(self):
        self.assertEqual(assess_runtime(last_heartbeat=100,now=105,max_gap_seconds=10,pending_tasks=0,oldest_task_age_seconds=0).state,"HEALTHY")
    def test_29_watchdog_stale(self):
        self.assertIn("HEARTBEAT_STALE",assess_runtime(last_heartbeat=100,now=120,max_gap_seconds=10,pending_tasks=0,oldest_task_age_seconds=0).reasons)
    def test_30_watchdog_queue_stalled(self):
        self.assertIn("QUEUE_STALLED",assess_runtime(last_heartbeat=100,now=105,max_gap_seconds=10,pending_tasks=1,oldest_task_age_seconds=20).reasons)
    def test_31_watchdog_unknown_effect(self):
        self.assertIn("UNKNOWN_EFFECT",assess_runtime(last_heartbeat=100,now=105,max_gap_seconds=10,pending_tasks=0,oldest_task_age_seconds=0,effect_state="UNKNOWN").reasons)
    def test_32_watchdog_bad_gap(self):
        with self.assertRaises(ContinuityError): assess_runtime(last_heartbeat=1,now=2,max_gap_seconds=0,pending_tasks=0,oldest_task_age_seconds=0)

if __name__=="__main__": unittest.main(verbosity=2)

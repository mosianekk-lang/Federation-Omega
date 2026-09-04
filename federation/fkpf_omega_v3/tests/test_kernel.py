import os
import tempfile
import unittest

from federation.fkpf_omega_v3.kernel import (
    AgentCard, AgentSkill, ArtifactAttestation, Authority, Disposition, Effect,
    IdentityEnvelope, KnowledgeDelta, Ledger, MCPBoundary, PolicyEngine,
    Proof, Receiver, ReplayBus, Propagator, ReleaseCourt, RetryRouter,
    advance, compile_mission, digest,
)


def kd(seq=1, did=None, domain="WORKFLOW", proof=Proof.TESTED, privacy="P1", matter=(), authority=Authority.A1, effect=Effect.INTERNAL):
    return KnowledgeDelta(
        did or f"D{seq}", seq, "CFBE", "epoch-1", domain, "finding",
        proof, authority, effect, "P0", privacy, tuple(matter), ("workflow",), (),
    )


def receiver(rid="R", domains=("WORKFLOW",), tags=("workflow",), authority=Authority.A1, effect=Effect.INTERNAL, proof=Proof.TESTED, privacy=("P0","P1"), matters=()):
    return Receiver(rid, tuple(domains), tuple(tags), authority, effect, proof, tuple(privacy), tuple(matters))


class DeltaPolicyTests(unittest.TestCase):
    def test_hash_stable(self): self.assertEqual(kd().content_hash(), kd().content_hash())
    def test_hash_changes_with_payload(self): self.assertNotEqual(kd().content_hash(), kd(domain="OTHER").content_hash())
    def test_allow(self): self.assertTrue(PolicyEngine().evaluate(kd(), receiver()).allow)
    def test_not_applicable(self): self.assertEqual(PolicyEngine().evaluate(kd(domain="OTHER"), receiver(domains=("X",),tags=("x",))).code, "NOT_APPLICABLE")
    def test_privacy_hold(self): self.assertEqual(PolicyEngine().evaluate(kd(privacy="P3"), receiver()).code, "PRIVACY_HELD")
    def test_matter_wall(self): self.assertEqual(PolicyEngine().evaluate(kd(matter=("A",)), receiver(matters=("B",))).code, "MATTER_WALL")
    def test_proof_hold(self): self.assertEqual(PolicyEngine().evaluate(kd(proof=Proof.BUILT), receiver(proof=Proof.TESTED)).code, "PROOF_HELD")
    def test_authority_hold(self): self.assertEqual(PolicyEngine().evaluate(kd(authority=Authority.A2), receiver(authority=Authority.A1)).code, "AUTHORITY_HELD")
    def test_effect_hold(self): self.assertEqual(PolicyEngine().evaluate(kd(effect=Effect.CONSEQUENTIAL), receiver(effect=Effect.INTERNAL)).code, "EFFECT_HELD")


class LedgerTests(unittest.TestCase):
    def test_monotonic_head(self):
        l=Ledger(); l.publish(kd()); l.publish(kd(2)); self.assertEqual(l.head(),2)
    def test_non_monotonic_rejected(self):
        l=Ledger()
        with self.assertRaises(RuntimeError): l.publish(kd(2))
    def test_ack_upsert(self):
        l=Ledger(); l.publish(kd()); l.ack("D1","R",Disposition.ADAPT); l.ack("D1","R",Disposition.APPLIED)
        row=l.db.execute("SELECT disposition FROM acks WHERE delta_id='D1' AND receiver_id='R'").fetchone(); self.assertEqual(row[0],"APPLIED")
    def test_watermark_stale_default(self): self.assertEqual(Ledger().watermark("R")["state"],"ACTIVE_STALE")
    def test_watermark_current(self):
        l=Ledger(); l.set_watermark("R",2,"ACTIVE_CURRENT"); self.assertEqual(l.watermark("R")["seq"],2)
    def test_idempotency(self):
        l=Ledger(); self.assertTrue(l.reserve("K","H")); self.assertFalse(l.reserve("K","H"))
    def test_durable_resume(self):
        with tempfile.TemporaryDirectory() as d:
            p=os.path.join(d,"state.db"); a=Ledger(p); a.publish(kd()); a.db.close(); b=Ledger(p); self.assertEqual(b.head(),1); b.db.close()
    def test_supersession_invalidates_ack(self):
        l=Ledger(); l.publish(kd()); l.ack("D1","R",Disposition.READBACK_VERIFIED); l.publish(kd(2,"D2")); l.supersede("D1","D2")
        row=l.db.execute("SELECT disposition FROM acks WHERE delta_id='D1'").fetchone(); self.assertEqual(row[0],Disposition.STALE_PENDING_REVALIDATION.value)


class BusPropagationTests(unittest.TestCase):
    def test_bus_deduplicates_message_id(self):
        b=ReplayBus(); a=b.publish("s",{"x":1},"m"); c=b.publish("s",{"x":1},"m"); self.assertEqual(a.seq,c.seq)
    def test_consumer_ack(self):
        b=ReplayBus(); m=b.publish("s",{"x":1},"m"); self.assertEqual(len(b.consume("s","C")),1); b.ack(m,"C"); self.assertEqual(len(b.consume("s","C")),0)
    def test_propagates_adapt(self):
        l=Ledger(); p=Propagator(l,ReplayBus()); r=p.publish(kd(),[receiver()]); self.assertEqual(r["adopted"],1)
    def test_propagation_hold(self):
        l=Ledger(); p=Propagator(l,ReplayBus()); r=p.publish(kd(privacy="P3"),[receiver()]); self.assertEqual(r["held"],1)
    def test_matter_not_applicable(self):
        l=Ledger(); p=Propagator(l,ReplayBus()); r=p.publish(kd(matter=("A",)),[receiver(matters=("B",))]); self.assertEqual(r["not_applicable"],1)


class MissionWorkflowTests(unittest.TestCase):
    def test_mission_deterministic(self):
        a=compile_mission("objective","domain",("x",)); b=compile_mission("objective","domain",("x",)); self.assertEqual(a.mission_id,b.mission_id)
    def test_mission_idempotency_key(self): self.assertTrue(compile_mission("o","d",("x",)).idempotency_key.startswith("IDEM-"))
    def test_workflow_happy_path(self):
        l=Ledger(); m=compile_mission("o","d",("x",));
        for state in ("SOURCE_GROUNDED","PROPAGATION_PREFLIGHT","SCREEN_REVIEW","USER_APPROVED","COMPLETE"): advance(l,m.mission_id,state)
        self.assertEqual(l.restore_state(m.mission_id),"COMPLETE")
    def test_workflow_skip_rejected(self):
        l=Ledger(); m=compile_mission("o","d",("x",));
        with self.assertRaises(RuntimeError): advance(l,m.mission_id,"ARTIFACT_BUILT")
    def test_workflow_resume(self):
        with tempfile.TemporaryDirectory() as d:
            p=os.path.join(d,"w.db"); l=Ledger(p); m=compile_mission("o","d",("x",)); advance(l,m.mission_id,"SOURCE_GROUNDED"); l.db.close(); l2=Ledger(p); self.assertEqual(l2.restore_state(m.mission_id),"SOURCE_GROUNDED"); l2.db.close()


class InteropIdentityTests(unittest.TestCase):
    def test_agent_card_a2a_1(self): AgentCard("A","https://a.example","1",(AgentSkill("x","X","d"),)).validate()
    def test_agent_card_old_protocol_rejected(self):
        with self.assertRaises(ValueError): AgentCard("A","https://a.example","1",(AgentSkill("x","X","d"),),"0.3").validate()
    def test_agent_card_requires_skill(self):
        with self.assertRaises(ValueError): AgentCard("A","https://a.example","1",()).validate()
    def test_spiffe_prefix(self): IdentityEnvelope("spiffe://federation.internal/modisa","M",Authority.A1,Effect.INTERNAL).validate()
    def test_bad_identity_rejected(self):
        with self.assertRaises(ValueError): IdentityEnvelope("http://not-spiffe","M",Authority.A1,Effect.INTERNAL).validate()
    def test_mcp_boundary_readback(self): self.assertTrue(MCPBoundary("s",("read",),("send",),Authority.A1,Effect.INTERNAL).require_readback)
    def test_mcp_no_raw_secret_default(self): self.assertTrue(MCPBoundary("s",("read",),(),Authority.A1,Effect.INTERNAL).no_raw_secret_values)


class RetryReleaseProofTests(unittest.TestCase):
    def test_stale_provider_id_no_blind_retry(self): self.assertEqual(RetryRouter().classify("stale grid id"),("STALE_PROVIDER_ID",False,"REFRESH_PROVIDER_METADATA_AND_RECOMPILE"))
    def test_403_no_retry(self): self.assertFalse(RetryRouter().classify("403 forbidden")[1])
    def test_effect_unknown_probe(self): self.assertEqual(RetryRouter().classify("EFFECT_UNKNOWN")[2],"PROBE_PROVIDER_BEFORE_RETRY")
    def test_timeout_one_retry(self): self.assertTrue(RetryRouter().classify("502 timeout")[1])
    def test_attestation_hash(self): self.assertEqual(len(ArtifactAttestation("a"*64,"c","b","t").statement_hash()),64)
    def test_internal_release_pass(self):
        r=ReleaseCourt().check(source_grounded=True,screen_review=True,semantic_diff=True,metadata_ok=True,idempotent=True,consequential=False,owner_approval=False,provider_readback=False,independent_verification=False); self.assertTrue(r["passed"])
    def test_consequential_needs_owner(self):
        r=ReleaseCourt().check(source_grounded=True,screen_review=True,semantic_diff=True,metadata_ok=True,idempotent=True,consequential=True,owner_approval=False,provider_readback=True,independent_verification=True); self.assertIn("OWNER_APPROVAL",r["failures"])
    def test_consequential_needs_readback(self):
        r=ReleaseCourt().check(source_grounded=True,screen_review=True,semantic_diff=True,metadata_ok=True,idempotent=True,consequential=True,owner_approval=True,provider_readback=False,independent_verification=True); self.assertIn("PROVIDER_READBACK",r["failures"])
    def test_consequential_needs_independent_verification(self):
        r=ReleaseCourt().check(source_grounded=True,screen_review=True,semantic_diff=True,metadata_ok=True,idempotent=True,consequential=True,owner_approval=True,provider_readback=True,independent_verification=False); self.assertIn("INDEPENDENT_VERIFICATION",r["failures"])


if __name__ == "__main__": unittest.main()

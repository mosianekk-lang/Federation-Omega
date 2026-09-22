import pytest
from benchmarking.cfbe_omega.bible_memory_fabric_v1 import MemoryEvent
from federation.fcoa.memory_fabric_v1.fcoa_memory_node import *


def verified_event(stream="system:x", version=1, idem="i1", payload=None):
    return MemoryEvent(
        event_id=f"e-{stream}-{version}", stream_id=stream, stream_version=version,
        event_type="STATE_SET", recorded_at="2026-09-21T20:00:00+02:00", valid_at="2026-09-21T20:00:00+02:00",
        idempotency_key=idem, truth_class="EVENT_TRUTH", privacy_class="GLOBAL",
        payload=payload or {"state":"READY"}, source_refs=("source:1",), proof_refs=("proof:1",)
    )


def proposal(proofs=("proof:p",)):
    return IntelligenceProposal(
        topic="global-routing", summary="Use changed mechanism after repeated same-semantic failure.",
        recorded_at="2026-09-21T20:01:00+02:00", source_refs=("source:fcoa",), proof_refs=proofs,
        causal_parent_ids=("event:prior",), metadata={"confidence":"high"}
    )


def verification(verifier="FUSE-JUDGE"):
    return VerificationReceipt(verifier, "receipt:judge", "2026-09-21T20:02:00+02:00", ("proof:judge",))


def test_ingests_verified_global_event():
    n=FCOAMemoryNode(); r=n.ingest(verified_event()); assert r.state=="APPENDED"; assert len(n.current_global_events())==1


def test_rejects_unverified_ingest():
    n=FCOAMemoryNode(); e=verified_event()
    e=MemoryEvent(event_id=e.event_id,stream_id=e.stream_id,stream_version=e.stream_version,event_type=e.event_type,
        recorded_at=e.recorded_at,valid_at=e.valid_at,idempotency_key=e.idempotency_key,truth_class="DERIVED_INTERPRETATION",
        privacy_class=e.privacy_class,payload=e.payload,source_refs=e.source_refs,proof_refs=e.proof_refs)
    with pytest.raises(ValueError,match="UNVERIFIED"): n.ingest(e)


def test_global_sensitive_payload_rejected():
    with pytest.raises(ValueError,match="SENSITIVE"): verified_event(payload={"secret":"x"}).validate()


def test_proposal_is_not_canonical_truth():
    n=FCOAMemoryNode(); e=n.compile_proposal_event(proposal()); assert e.truth_class=="DERIVED_INTERPRETATION"; assert e.payload["canonical_promotion_authorized"] is False


def test_fcoa_cannot_self_verify():
    n=FCOAMemoryNode()
    with pytest.raises(ValueError,match="SELF_VERIFICATION"): n.verify_and_accept(proposal(), verification("FCOA-OMEGA"))


def test_acceptance_requires_proposal_proof():
    n=FCOAMemoryNode()
    with pytest.raises(ValueError,match="PROPOSAL_PROOF"): n.verify_and_accept(proposal(proofs=()), verification())


def test_verified_acceptance_preserves_causal_lineage_and_no_effect_authority():
    n=FCOAMemoryNode(); e=n.verify_and_accept(proposal(), verification())
    assert e.truth_class=="DERIVED_VERIFIED" and proposal().proposal_id in e.causal_parent_ids
    assert e.payload["external_effect_authority_inherited"] is False


def test_dynamic_receiver_fanout_and_convergence():
    rr=ReceiverRegistry([Receiver("Bubbles"),Receiver("EvidenceOps")]); f=ReceiverFanout(rr); n=FCOAMemoryNode(); e=n.verify_and_accept(proposal(),verification())
    r=f.publish(e); assert r.state=="PENDING_ACKS" and set(r.pending)=={"Bubbles","EvidenceOps"}
    r=f.ack(e.event_id,"Bubbles",e.digest()); assert r.state=="PENDING_ACKS"
    r=f.ack(e.event_id,"EvidenceOps",e.digest()); assert r.state=="CONVERGED"


def test_future_receiver_is_inherited_on_next_publish():
    rr=ReceiverRegistry([Receiver("A")]); f=ReceiverFanout(rr); n=FCOAMemoryNode(); e=n.verify_and_accept(proposal(),verification()); assert f.publish(e).targets==("A",)
    rr.register(Receiver("FutureSystem"))
    p2=IntelligenceProposal(topic="next",summary="new",recorded_at="2026-09-21T20:03:00+02:00",source_refs=("s",),proof_refs=("p",))
    e2=n.verify_and_accept(p2,verification()); assert set(f.publish(e2).targets)=={"A","FutureSystem"}


def test_ack_digest_mismatch_fails_closed():
    rr=ReceiverRegistry([Receiver("A")]); f=ReceiverFanout(rr); n=FCOAMemoryNode(); e=n.verify_and_accept(proposal(),verification()); f.publish(e)
    with pytest.raises(ValueError,match="DIGEST_MISMATCH"): f.ack(e.event_id,"A","bad")


def test_idempotent_ingest_replays_safely():
    n=FCOAMemoryNode(); e=verified_event(); assert n.ingest(e).state=="APPENDED"; assert n.ingest(e).state=="IDEMPOTENT_REPLAY"


def test_private_domain_event_not_imported_to_global_node():
    n=FCOAMemoryNode(); e=verified_event()
    e2=MemoryEvent(event_id="e2",stream_id="x",stream_version=1,event_type="STATE_SET",recorded_at=e.recorded_at,valid_at=e.valid_at,
        idempotency_key="private",truth_class="EVENT_TRUTH",privacy_class="P3_PRIVATE",payload={"state":"x"},source_refs=("s",),proof_refs=("p",))
    with pytest.raises(ValueError,match="PORTABLE_GLOBAL"): n.ingest(e2)

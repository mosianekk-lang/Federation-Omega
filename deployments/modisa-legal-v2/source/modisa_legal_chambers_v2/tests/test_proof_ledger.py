from modisa_v2.schemas import ProofAppendRequest, ProofType


def test_hash_chain_and_signature_verify(services):
    services.repo.ensure_matter("MAT-1")
    first = services.ledger.append(
        ProofAppendRequest(
            matter_id="MAT-1",
            mission_id="MIS-1",
            proof_type=ProofType.MISSION_SCOPE,
            subject_id="MIS-1",
            actor_id="tester",
            payload={"question": "What happened?"},
        )
    )
    second = services.ledger.append(
        ProofAppendRequest(
            matter_id="MAT-1",
            mission_id="MIS-1",
            proof_type=ProofType.SOURCE_READ,
            subject_id="SRC-1",
            actor_id="tester",
            source_ids=["SRC-1"],
            payload={"hash_verified": True},
        )
    )
    assert second.previous_hash == first.chain_hash
    result = services.ledger.verify_chain("MAT-1")
    assert result.valid is True
    assert result.checked_count == 2


def test_tampered_payload_is_detected(services):
    services.repo.ensure_matter("MAT-2")
    proof = services.ledger.append(
        ProofAppendRequest(
            matter_id="MAT-2",
            mission_id="MIS-2",
            proof_type=ProofType.MISSION_SCOPE,
            subject_id="MIS-2",
            actor_id="tester",
            payload={"question": "original"},
        )
    )
    services.repo.execute(
        "UPDATE proof_records SET payload_json=? WHERE proof_id=?",
        ('{"question":"tampered"}', proof.proof_id),
    )
    result = services.ledger.verify_chain("MAT-2")
    assert result.valid is False
    assert result.failed_proof_id == proof.proof_id

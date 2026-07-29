from modisa_v2.canonical import sha256_text
from modisa_v2.schemas import AuthorityRegisterRequest


def test_versioned_legal_knowledge_full_text_search(services):
    text = (
        "Section 1 establishes jurisdiction. Section 2 provides a remedy. "
        "The tribunal may grant compensation where the statutory elements are proved."
    )
    authority = services.graph.register_authority(
        AuthorityRegisterRequest(
            matter_id="MAT-K",
            mission_id="MIS-K",
            citation="Test Act 2 of 2026",
            title="Test Act",
            authority_type="STATUTE",
            source_url="https://www.gov.za/documents/test-act-2",
            proposition="The tribunal may grant compensation.",
            binding_level="BINDING",
            content_hash=sha256_text(text),
        )
    )
    document_id, chunk_ids, proof_id = services.knowledge.ingest(
        authority_id=authority.authority_id,
        matter_id="MAT-K",
        mission_id="MIS-K",
        actor_id="authority-verifier",
        text=text,
    )
    hits = services.knowledge.search(matter_id="MAT-K", query="tribunal compensation")
    assert document_id
    assert chunk_ids
    assert proof_id
    assert hits
    assert hits[0].authority_id == authority.authority_id

import pytest

from modisa_v2.schemas import ClaimCreateRequest, ClaimKind, ClaimLinkRequest, LinkType


def test_claim_link_rejects_invented_evidence(services):
    services.repo.ensure_matter("MAT-G")
    claim = services.graph.create_claim(
        ClaimCreateRequest(
            matter_id="MAT-G",
            mission_id="MIS-G",
            kind=ClaimKind.FACT,
            proposition="A notice was sent.",
        )
    )
    with pytest.raises(ValueError):
        services.graph.link_claim(
            ClaimLinkRequest(
                claim_id=claim.claim_id,
                object_id="EVID-INVENTED",
                object_type="EVIDENCE",
                link_type=LinkType.SUPPORTS,
            )
        )

from sovara.creative.gemini_workflow_receipt_verifier import verify_challenge_identity


SPEC_PATH = "governance/sovara_creative_gemini_architecture_challenge_v1.json"


def packet(challenge_id: str):
    return (
        {"challenge_id": challenge_id},
        {"challenge_id": challenge_id},
        {"request_id": challenge_id, "challenge_spec": SPEC_PATH},
    )


def test_accepts_arbitrary_admitted_challenge_identity():
    receipt, spec, request = packet("CFBE-GEMINI-REPAIR-20990101-777")
    assert verify_challenge_identity(receipt, spec, request) is True


def test_rejects_receipt_mismatch():
    receipt, spec, request = packet("CFBE-GEMINI-REPAIR-20990101-777")
    receipt["challenge_id"] = "STALE-HISTORICAL-ID"
    assert verify_challenge_identity(receipt, spec, request) is False


def test_rejects_request_mismatch():
    receipt, spec, request = packet("CFBE-GEMINI-REPAIR-20990101-777")
    request["request_id"] = "DIFFERENT-REQUEST"
    assert verify_challenge_identity(receipt, spec, request) is False


def test_rejects_wrong_challenge_spec_binding():
    receipt, spec, request = packet("CFBE-GEMINI-REPAIR-20990101-777")
    request["challenge_spec"] = "governance/unrelated.json"
    assert verify_challenge_identity(receipt, spec, request) is False

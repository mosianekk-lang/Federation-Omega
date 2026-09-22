from evidenceops.security.public_repository_leak_guard import ID_ASSIGNMENT, OPENAI_KEY_PATTERN


def test_detects_project_scoped_openai_key_pattern() -> None:
    candidate = "sk" + "-proj-" + ("A" * 32)
    assert OPENAI_KEY_PATTERN.search(candidate) is not None


def test_detects_legacy_openai_key_pattern() -> None:
    candidate = "sk" + "-" + ("B" * 32)
    assert OPENAI_KEY_PATTERN.search(candidate) is not None


def test_ignores_short_or_placeholder_values() -> None:
    assert OPENAI_KEY_PATTERN.search("OPENAI_API_KEY") is None
    assert OPENAI_KEY_PATTERN.search("REDACTED") is None
    assert OPENAI_KEY_PATTERN.search("sk" + "-short") is None


def test_identifier_detector_does_not_match_profile_id_suffix() -> None:
    text = 'PROFILE_ID = "FCOA_INTERNAL_SUPER_ADMIN_V1"'
    assert ID_ASSIGNMENT.search(text) is None


def test_identifier_detector_still_matches_real_file_id() -> None:
    field = "file" + "_id"
    value = "A" + ("1" * 31)
    text = f'{field} = "{value}"'
    match = ID_ASSIGNMENT.search(text)
    assert match is not None
    assert match.group(1).lower() == "file_id"

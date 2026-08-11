from evidenceops.security.public_repository_leak_guard import OPENAI_KEY_PATTERN


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

from pathlib import Path


def test_service_source_contains_required_routes():
    source = Path(__file__).parents[1].joinpath("app.py").read_text(encoding="utf-8")
    for route in (
        '/health',
        '/v1/uploads',
        '/v1/jobs/<job_id>/start',
        '/v1/jobs/<job_id>',
        '/internal/prepare/<job_id>',
        '/internal/poll/<job_id>',
    ):
        assert route in source


def test_no_static_credentials_embedded():
    source = Path(__file__).parents[1].joinpath("app.py").read_text(encoding="utf-8")
    assert "BEGIN PRIVATE KEY" not in source
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in source
    assert "x-fo-admin-token" not in source

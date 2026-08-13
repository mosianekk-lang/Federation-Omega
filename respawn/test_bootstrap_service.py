from fastapi.testclient import TestClient

from bootstrap_service import app

client = TestClient(app)


def test_health():
    r = client.get('/health')
    assert r.status_code == 200
    body = r.json()
    assert body['ok'] is True
    assert body['registered_system_count'] >= 1


def test_bootstrap_known_system():
    r = client.post('/bootstrap', json={
        'system': 'Bubbles',
        'matter': 'Federation continuity',
        'chat_ref': 'smoke-test',
        'objective': 'avoid duplicate work'
    })
    assert r.status_code == 200
    body = r.json()
    assert body['system'] == 'Bubbles'
    assert 'bootstrap_order' in body


def test_reject_unknown_system():
    r = client.post('/bootstrap', json={'system': 'UNKNOWN_SYSTEM'})
    assert r.status_code == 400

import pytest
from complete_backend import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    rv = client.get('/healthz')
    assert rv.status_code == 200
    assert rv.json.get('status') == 'ok'


def test_protected_requires_token(client):
    rv = client.get('/me')
    assert rv.status_code == 401

# Additional tests for auth would need a test token; keep minimal to verify wiring

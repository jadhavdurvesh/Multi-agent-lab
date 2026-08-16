import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_my_string_endpoint(client):
    response = client.get('/my-string')
    assert response.status_code == 200
    assert response.data.decode('utf-8') == 'Hello, Flask App!'

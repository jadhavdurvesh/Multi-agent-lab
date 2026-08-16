import pytest
from app import app, MY_STRING

@pytest.fixture
def client():
    """Configures the Flask app for testing and provides a test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_get_my_string_endpoint(client):
    """Tests that the /my-string endpoint returns the correct string and status code."""
    response = client.get('/my-string')
    assert response.status_code == 200
    assert response.data.decode('utf-8') == MY_STRING

def test_get_my_string_endpoint_content_type(client):
    """Tests that the /my-string endpoint returns 'text/html' content type by default (Flask's default for strings)."""
    response = client.get('/my-string')
    assert response.headers['Content-Type'] == 'text/html; charset=utf-8'

def test_non_existent_endpoint(client):
    """Tests that a non-existent endpoint returns a 404 Not Found error."""
    response = client.get('/non-existent-path')
    assert response.status_code == 404

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_unknown_route():
    """
    Tests that a request to an unknown route returns a 404 status.
    This verifies basic application routing and error handling works.
    """
    response = client.get("/api/v1/unknown-route-that-does-not-exist")
    
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Not Found"

def test_app_loads():
    """
    Tests that the FastAPI application can be instantiated properly.
    (If `app` failed to initialize, this file wouldn't even load, but it's good to have a simple sanity test).
    """
    assert app is not None
    assert app.title == "AURORA"

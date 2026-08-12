from fastapi.testclient import TestClient
from app.main import app

# Use FastAPI's TestClient to simulate HTTP requests during testing
client = TestClient(app)

def test_health_endpoint():
    """
    Tests the /api/v1/health endpoint.
    Verifies that it returns a 200 OK status and the expected JSON structure.
    """
    response = client.get("/api/v1/health")
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "AURORA backend"
    assert "version" in data

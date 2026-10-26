from fastapi.testclient import TestClient
import pytest

from app.core.rate_limit import auth_rate_limiter
from app.main import app


def test_login_rate_limiting():
    client = TestClient(app)
    email = "ratelimit_user@example.com"

    # Register the user
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "RL User"},
    )
    assert reg.status_code == 201

    # First 10 invalid login attempts should return 401
    for _ in range(10):
        res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "wrongpassword"},
        )
        assert res.status_code == 401

    # The 11th attempt should trigger 429 Too Many Requests
    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "wrongpassword"},
    )
    assert blocked.status_code == 429
    assert "Too many login attempts" in blocked.json()["detail"]
    assert "Retry-After" in blocked.headers

    # Resetting the limiter should restore access immediately
    auth_rate_limiter.reset()
    res_after_reset = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "wrongpassword"},
    )
    assert res_after_reset.status_code == 401


def test_register_rate_limiting():
    client = TestClient(app)

    # 10 registrations or attempts from same IP
    for i in range(10):
        res = client.post(
            "/api/v1/auth/register",
            json={"email": f"burst_{i}@example.com", "password": "password123", "display_name": f"User {i}"},
        )
        assert res.status_code == 201

    # 11th attempt should be blocked
    blocked = client.post(
        "/api/v1/auth/register",
        json={"email": "burst_11@example.com", "password": "password123", "display_name": "User 11"},
    )
    assert blocked.status_code == 429
    assert "Too many registration attempts" in blocked.json()["detail"]
    assert "Retry-After" in blocked.headers

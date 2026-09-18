from fastapi.testclient import TestClient
from sqlalchemy import select
from datetime import datetime, timezone, timedelta

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.session import Session as DBSession
from app.core.config import settings
from app.core.security import verify_password, hash_session_token

client = TestClient(app)

def register_test_user(email: str = "test@example.com", password: str = "testpassword123"):
    """Register a uniquely named user in the disposable test database."""
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Test User"}
    )
    return response

def test_1_registration_succeeds():
    response = register_test_user("reg1@example.com", "mypassword123")
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "reg1@example.com"
    assert data["display_name"] == "Test User"
    assert "password_hash" not in data
    assert "password" not in data

def test_2_duplicate_email_rejected():
    register_test_user("dup@example.com")
    response2 = client.post(
        "/api/v1/auth/register",
        json={"email": "DUP@example.com", "password": "anotherpassword", "display_name": "Dup"}
    )
    assert response2.status_code == 400
    assert "already registered" in response2.json()["detail"].lower()

def test_3_4_password_stored_as_argon2id_and_plaintext_absent():
    register_test_user("hash@example.com", "secret123")
    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == "hash@example.com")).first()
        assert user is not None
        # Argon2id hashes usually start with $argon2id$
        assert user.password_hash.startswith("$argon2id$")
        assert "secret123" not in user.password_hash
        assert verify_password("secret123", user.password_hash) is True

def test_5_6_7_login_success_failure_and_generic_response():
    register_test_user("login@example.com", "correctpass")
    
    # 5. Success
    res_success = client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "correctpass"}
    )
    assert res_success.status_code == 200
    
    # 6. Invalid password
    res_fail1 = client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "wrongpassword"}
    )
    assert res_fail1.status_code == 401
    
    # Invalid email
    res_fail2 = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "correctpass"}
    )
    assert res_fail2.status_code == 401
    
    # 7. Generic response
    assert res_fail1.json()["detail"] == res_fail2.json()["detail"]
    assert res_fail1.json()["detail"] == "Invalid email or password"

def test_8_9_10_session_created_no_raw_token_httponly_cookie():
    register_test_user("session@example.com", "password123")
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "session@example.com", "password": "password123"}
    )
    assert res.status_code == 200
    
    # 10. HttpOnly cookie set
    cookies = res.cookies
    cookie_header = res.headers.get("set-cookie", "")
    assert settings.AUTH_COOKIE_NAME in cookies
    assert "HttpOnly" in cookie_header
    assert "samesite=lax" in cookie_header.lower()
    
    raw_token = cookies.get(settings.AUTH_COOKIE_NAME)
    
    # 8. Session created
    # 9. Raw token not stored
    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == "session@example.com")).first()
        sessions = user.sessions
        assert len(sessions) == 1
        db_session = sessions[0]
        
        # Validate that the database contains the hash, not the raw token
        assert db_session.token_hash != raw_token
        assert db_session.token_hash == hash_session_token(raw_token)

def test_11_12_auth_me_works_and_unauth_fails():
    register_test_user("me@example.com", "password123")
    
    # 12. Unauth fails
    client_unauth = TestClient(app)
    res_unauth = client_unauth.get("/api/v1/auth/me")
    assert res_unauth.status_code == 401
    
    # 11. Auth works
    client_auth = TestClient(app)
    client_auth.post("/api/v1/auth/login", json={"email": "me@example.com", "password": "password123"})
    res_auth = client_auth.get("/api/v1/auth/me")
    assert res_auth.status_code == 200
    assert res_auth.json()["email"] == "me@example.com"

def test_13_14_logout_revokes_session_and_fails_me():
    register_test_user("logout@example.com", "password123")
    c = TestClient(app)
    c.post("/api/v1/auth/login", json={"email": "logout@example.com", "password": "password123"})
    
    res_me1 = c.get("/api/v1/auth/me")
    assert res_me1.status_code == 200
    
    # 13. Logout
    res_logout = c.post("/api/v1/auth/logout")
    assert res_logout.status_code == 200
    
    # Verify cookie cleared (max-age=0 or expires in past)
    cookie_header = res_logout.headers.get("set-cookie", "").lower()
    assert "max-age=0" in cookie_header or "expires=" in cookie_header
    
    # 14. /me fails after logout
    res_me2 = c.get("/api/v1/auth/me")
    assert res_me2.status_code == 401

def test_15_expired_session_rejected():
    register_test_user("exp@example.com", "password123")
    c = TestClient(app)
    c.post("/api/v1/auth/login", json={"email": "exp@example.com", "password": "password123"})
    
    # Manually expire the session in the DB
    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == "exp@example.com")).first()
        sess = user.sessions[0]
        sess.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
        
    res_me = c.get("/api/v1/auth/me")
    assert res_me.status_code == 401

def test_16_revoked_session_rejected():
    register_test_user("rev@example.com", "password123")
    c = TestClient(app)
    c.post("/api/v1/auth/login", json={"email": "rev@example.com", "password": "password123"})
    
    # Manually revoke the session in the DB
    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == "rev@example.com")).first()
        sess = user.sessions[0]
        sess.revoked_at = datetime.now(timezone.utc)
        db.commit()
        
    res_me = c.get("/api/v1/auth/me")
    assert res_me.status_code == 401

def test_17_inactive_user_rejected():
    register_test_user("inact@example.com", "password123")
    
    # Deactivate user
    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == "inact@example.com")).first()
        user.is_active = False
        db.commit()
        
    # Attempt login
    res = client.post("/api/v1/auth/login", json={"email": "inact@example.com", "password": "password123"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password"

def test_18_19_password_hash_and_token_never_returned():
    register_test_user("leak@example.com", "password123")
    c = TestClient(app)
    res_login = c.post("/api/v1/auth/login", json={"email": "leak@example.com", "password": "password123"})
    data1 = res_login.json()
    # 18/19 checks
    assert "password_hash" not in str(data1)
    assert "token" not in str(data1)
    
    res_me = c.get("/api/v1/auth/me")
    data2 = res_me.json()
    assert "password_hash" not in str(data2)
    assert "token" not in str(data2)

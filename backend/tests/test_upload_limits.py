import io
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def get_authenticated_client(email: str = "upload_limits@example.com") -> tuple[TestClient, str]:
    client = TestClient(app)
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "Upload Tester"},
    )
    client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    ws_res = client.post(
        "/api/v1/workspaces",
        json={"name": "Upload Test Space", "description": "Testing upload boundary limits"},
    )
    return client, ws_res.json()["id"]


def test_document_max_size_setting():
    """Verify that settings enforce 10MB max upload size."""
    assert settings.DOCUMENT_MAX_SIZE_BYTES == 10 * 1024 * 1024


def test_oversized_file_upload_rejected():
    """Verify that uploading a payload exceeding 10MB is rejected with 422."""
    client, workspace_id = get_authenticated_client("oversized_test@example.com")
    
    # 10MB + 1 byte dummy text file
    oversized_data = b"A" * (settings.DOCUMENT_MAX_SIZE_BYTES + 1)
    
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("large_document.txt", io.BytesIO(oversized_data), "text/plain")},
    )
    assert response.status_code == 422
    assert "upload limit" in response.json()["detail"]


def test_unsupported_file_type_rejected():
    """Verify that uploading unsupported file types (.exe, .sh, etc.) is rejected with 422."""
    client, workspace_id = get_authenticated_client("unsupported_type@example.com")

    # Executable file
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("malicious.exe", io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00"), "application/x-msdownload")},
    )
    assert response.status_code == 422
    assert "Unsupported document type" in response.json()["detail"]


def test_valid_text_upload_accepted():
    """Verify that a valid text document within limits is accepted."""
    client, workspace_id = get_authenticated_client("valid_upload@example.com")

    valid_content = b"AURORA Multilingual RAG Platform test document content."
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": ("notes.txt", io.BytesIO(valid_content), "text/plain")},
    )
    assert response.status_code == 201
    assert response.json()["original_filename"] == "notes.txt"
    assert response.json()["file_size"] == len(valid_content)

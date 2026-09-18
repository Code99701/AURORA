from io import BytesIO
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace
from app.services import document as document_service
from app.storage.base import StorageError
from app.storage.deps import get_file_storage
from app.storage.local import LocalFileStorage


PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


@pytest.fixture
def local_storage(tmp_path: Path):
    storage = LocalFileStorage(tmp_path / "private-document-storage")
    app.dependency_overrides[get_file_storage] = lambda: storage
    try:
        yield storage
    finally:
        app.dependency_overrides.pop(get_file_storage, None)


def authenticated_client(email: str) -> tuple[TestClient, dict]:
    client = TestClient(app)
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "document-password",
            "display_name": email.split("@", 1)[0],
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "document-password"},
    )
    assert login.status_code == 200
    return client, registration.json()


def create_workspace(client: TestClient, name: str) -> dict:
    response = client.post(
        "/api/v1/workspaces",
        json={"name": name, "description": "Document test workspace"},
    )
    assert response.status_code == 201
    return response.json()


def upload_pdf(
    client: TestClient,
    workspace_id: str,
    filename: str = "research.pdf",
    content: bytes = PDF_BYTES,
    content_type: str = "application/pdf",
):
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        files={"file": (filename, content, content_type)},
    )


def test_authenticated_pdf_upload_persists_metadata_and_storage(local_storage):
    client, user = authenticated_client("document-upload@example.com")
    workspace = create_workspace(client, "Upload workspace")

    response = upload_pdf(client, workspace["id"])
    assert response.status_code == 201
    payload = response.json()
    assert payload["workspace_id"] == workspace["id"]
    assert payload["uploaded_by"] == user["id"]
    assert payload["original_filename"] == "research.pdf"
    assert payload["content_type"] == "application/pdf"
    assert payload["file_size"] == len(PDF_BYTES)
    assert payload["status"] == "UPLOADED"
    assert len(payload["checksum"]) == 64
    assert "storage_key" not in payload
    assert "storage_provider" not in payload

    with SessionLocal() as db:
        document = db.get(Document, UUID(payload["id"]))
        assert document is not None
        assert document.workspace_id == UUID(workspace["id"])
        assert document.uploaded_by == user["id"]
        assert document.storage_key == (
            f"workspaces/{workspace['id']}/documents/{payload['id']}/original"
        )
        assert local_storage.exists(document.storage_key)


def test_unauthenticated_upload_is_rejected(local_storage):
    response = upload_pdf(
        TestClient(app),
        "00000000-0000-0000-0000-000000000001",
    )
    assert response.status_code == 401


def test_non_member_upload_is_concealed(local_storage):
    owner_client, _ = authenticated_client("document-upload-owner@example.com")
    outsider_client, _ = authenticated_client("document-upload-outsider@example.com")
    workspace = create_workspace(owner_client, "Private upload")

    response = upload_pdf(outsider_client, workspace["id"])
    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


@pytest.mark.parametrize(
    ("filename", "content", "content_type"),
    [
        ("notes.json", b'{"plain": "text"}', "application/json"),
        ("fake.pdf", b"not a PDF", "application/pdf"),
        ("paper.pdf", PDF_BYTES, "application/octet-stream"),
        ("spoofed.docx", b"plain text", "text/plain"),
    ],
)
def test_unsupported_or_mismatched_files_are_rejected(
    local_storage, filename, content, content_type
):
    client, _ = authenticated_client(
        f"document-invalid-{filename.replace('.', '-')}-{content_type.split('/')[-1]}@example.com"
    )
    workspace = create_workspace(client, f"Invalid {filename}")

    response = upload_pdf(client, workspace["id"], filename, content, content_type)
    assert response.status_code == 422
    assert not any(local_storage.root.rglob("original"))


def test_oversized_file_is_rejected(local_storage, monkeypatch):
    client, _ = authenticated_client("document-oversized@example.com")
    workspace = create_workspace(client, "Size limit")
    monkeypatch.setattr(settings, "DOCUMENT_MAX_SIZE_BYTES", len(PDF_BYTES) - 1)

    response = upload_pdf(client, workspace["id"])
    assert response.status_code == 422
    assert "upload limit" in response.json()["detail"]
    assert not any(local_storage.root.rglob("original"))


def test_unsafe_filename_is_safely_normalized(local_storage):
    client, _ = authenticated_client("document-filename@example.com")
    workspace = create_workspace(client, "Filename safety")

    response = upload_pdf(client, workspace["id"], "../../private/research.pdf")
    assert response.status_code == 201
    assert response.json()["original_filename"] == "research.pdf"
    with SessionLocal() as db:
        document = db.get(Document, UUID(response.json()["id"]))
        assert document is not None
        assert "research.pdf" not in document.storage_key
        assert ".." not in document.storage_key
        assert local_storage.exists(document.storage_key)


def test_unicode_filename_is_preserved_as_display_metadata(local_storage):
    client, _ = authenticated_client("document-unicode-filename@example.com")
    workspace = create_workspace(client, "Unicode filename")

    response = upload_pdf(client, workspace["id"], "Aurora-स्रोत.pdf")

    assert response.status_code == 201
    assert response.json()["original_filename"] == "Aurora-स्रोत.pdf"
    with SessionLocal() as db:
        document = db.get(Document, UUID(response.json()["id"]))
        assert document is not None
        assert "स्रोत" not in document.storage_key
        assert local_storage.exists(document.storage_key)


def test_authorized_listing_returns_only_workspace_documents(local_storage):
    client, _ = authenticated_client("document-list@example.com")
    first_workspace = create_workspace(client, "Document list first")
    second_workspace = create_workspace(client, "Document list second")
    first_document = upload_pdf(client, first_workspace["id"], "first.pdf").json()
    upload_pdf(client, second_workspace["id"], "second.pdf")

    response = client.get(f"/api/v1/workspaces/{first_workspace['id']}/documents")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["id"] for item in response.json()["items"]] == [first_document["id"]]


def test_cross_workspace_listing_is_blocked(local_storage):
    owner_client, _ = authenticated_client("document-list-owner@example.com")
    outsider_client, _ = authenticated_client("document-list-outsider@example.com")
    workspace = create_workspace(owner_client, "Private list")
    upload_pdf(owner_client, workspace["id"])

    response = outsider_client.get(f"/api/v1/workspaces/{workspace['id']}/documents")
    assert response.status_code == 404


def test_authorized_detail_returns_metadata_only(local_storage):
    client, _ = authenticated_client("document-detail@example.com")
    workspace = create_workspace(client, "Document detail")
    document = upload_pdf(client, workspace["id"]).json()

    response = client.get(
        f"/api/v1/workspaces/{workspace['id']}/documents/{document['id']}"
    )
    assert response.status_code == 200
    assert response.json()["id"] == document["id"]
    assert "storage_key" not in response.json()
    assert "storage_provider" not in response.json()


def test_cross_workspace_document_detail_is_blocked(local_storage):
    client, _ = authenticated_client("document-detail-cross@example.com")
    first_workspace = create_workspace(client, "Detail first")
    second_workspace = create_workspace(client, "Detail second")
    document = upload_pdf(client, first_workspace["id"]).json()

    response = client.get(
        f"/api/v1/workspaces/{second_workspace['id']}/documents/{document['id']}"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_authorized_download_streams_original_bytes(local_storage):
    client, _ = authenticated_client("document-download@example.com")
    workspace = create_workspace(client, "Document download")
    document = upload_pdf(client, workspace["id"], "research notes.pdf").json()

    response = client.get(
        f"/api/v1/workspaces/{workspace['id']}/documents/{document['id']}/download"
    )
    assert response.status_code == 200
    assert response.content == PDF_BYTES
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]


def test_authorized_preview_streams_pdf_inline_without_caching(local_storage):
    client, _ = authenticated_client("document-preview@example.com")
    workspace = create_workspace(client, "Document preview")
    document = upload_pdf(client, workspace["id"], "research notes.pdf").json()

    response = client.get(
        f"/api/v1/workspaces/{workspace['id']}/documents/{document['id']}/preview"
    )
    assert response.status_code == 200
    assert response.content == PDF_BYTES
    assert response.headers["content-type"] == "application/pdf"
    assert "inline" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_cross_workspace_preview_is_blocked_before_storage(local_storage):
    owner_client, _ = authenticated_client("document-preview-owner@example.com")
    outsider_client, _ = authenticated_client("document-preview-outsider@example.com")
    workspace = create_workspace(owner_client, "Private preview")
    document = upload_pdf(owner_client, workspace["id"]).json()

    response = outsider_client.get(
        f"/api/v1/workspaces/{workspace['id']}/documents/{document['id']}/preview"
    )
    assert response.status_code == 404


def test_preview_reports_missing_stored_document(local_storage):
    client, _ = authenticated_client("document-preview-missing@example.com")
    workspace = create_workspace(client, "Missing preview")
    document = upload_pdf(client, workspace["id"]).json()
    with SessionLocal() as db:
        stored = db.get(Document, UUID(document["id"]))
        local_storage.delete(stored.storage_key)

    response = client.get(
        f"/api/v1/workspaces/{workspace['id']}/documents/{document['id']}/preview"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Stored document not found"


def test_cross_workspace_download_is_blocked_before_storage(local_storage):
    owner_client, _ = authenticated_client("document-download-owner@example.com")
    outsider_client, _ = authenticated_client("document-download-outsider@example.com")
    workspace = create_workspace(owner_client, "Private download")
    document = upload_pdf(owner_client, workspace["id"]).json()

    response = outsider_client.get(
        f"/api/v1/workspaces/{workspace['id']}/documents/{document['id']}/download"
    )
    assert response.status_code == 404


def test_owner_deletes_document_file_and_metadata(local_storage):
    client, _ = authenticated_client("document-delete@example.com")
    workspace = create_workspace(client, "Document deletion")
    document_payload = upload_pdf(client, workspace["id"]).json()
    with SessionLocal() as db:
        storage_key = db.get(Document, UUID(document_payload["id"])).storage_key

    response = client.delete(
        f"/api/v1/workspaces/{workspace['id']}/documents/{document_payload['id']}"
    )
    assert response.status_code == 204
    assert not local_storage.exists(storage_key)
    with SessionLocal() as db:
        assert db.get(Document, UUID(document_payload["id"])) is None


def test_owner_deletes_workspace_document_files_and_metadata(local_storage):
    client, _ = authenticated_client("document-workspace-delete@example.com")
    workspace = create_workspace(client, "Workspace document cleanup")
    document_payload = upload_pdf(client, workspace["id"]).json()
    with SessionLocal() as db:
        storage_key = db.get(Document, UUID(document_payload["id"])).storage_key

    response = client.delete(f"/api/v1/workspaces/{workspace['id']}")
    assert response.status_code == 204
    assert not local_storage.exists(storage_key)
    with SessionLocal() as db:
        assert db.get(Workspace, UUID(workspace["id"])) is None
        assert db.get(Document, UUID(document_payload["id"])) is None


def test_cross_workspace_delete_is_blocked(local_storage):
    owner_client, _ = authenticated_client("document-delete-owner@example.com")
    outsider_client, _ = authenticated_client("document-delete-outsider@example.com")
    workspace = create_workspace(owner_client, "Private deletion")
    document = upload_pdf(owner_client, workspace["id"]).json()

    response = outsider_client.delete(
        f"/api/v1/workspaces/{workspace['id']}/documents/{document['id']}"
    )
    assert response.status_code == 404
    with SessionLocal() as db:
        persisted = db.get(Document, UUID(document["id"]))
        assert persisted is not None
        assert local_storage.exists(persisted.storage_key)


def test_member_cannot_delete_workspace_document(local_storage):
    owner_client, _ = authenticated_client("document-member-delete-owner@example.com")
    member_client, member = authenticated_client("document-member-delete@example.com")
    workspace = create_workspace(owner_client, "Owner-managed documents")
    document = upload_pdf(owner_client, workspace["id"]).json()
    from app.models.workspace import WorkspaceMembership

    with SessionLocal.begin() as db:
        db.add(
            WorkspaceMembership(
                workspace_id=UUID(workspace["id"]),
                user_id=member["id"],
                role="MEMBER",
            )
        )

    response = member_client.delete(
        f"/api/v1/workspaces/{workspace['id']}/documents/{document['id']}"
    )
    assert response.status_code == 403


def test_storage_failure_returns_safe_error(monkeypatch):
    class FailingStorage:
        provider_name = "test"

        def save(self, key, source):
            raise StorageError("sensitive storage detail")

        def open(self, key):
            raise AssertionError

        def delete(self, key):
            raise AssertionError

        def exists(self, key):
            return False

    app.dependency_overrides[get_file_storage] = lambda: FailingStorage()
    try:
        client, _ = authenticated_client("document-storage-failure@example.com")
        workspace = create_workspace(client, "Storage failure")
        response = upload_pdf(client, workspace["id"])
    finally:
        app.dependency_overrides.pop(get_file_storage, None)

    assert response.status_code == 503
    assert response.json()["detail"] == "Document storage is unavailable"
    assert "sensitive" not in response.text
    with SessionLocal() as db:
        assert db.scalar(
            select(Document).where(
                Document.workspace_id == UUID(workspace["id"])
            )
        ) is None


def test_database_failure_removes_newly_stored_file(local_storage, monkeypatch):
    client, user_payload = authenticated_client("document-db-failure@example.com")
    workspace_payload = create_workspace(client, "Database failure")
    upload = UploadFile(
        filename="cleanup.pdf",
        file=BytesIO(PDF_BYTES),
        headers={"content-type": "application/pdf"},
    )

    with SessionLocal() as db:
        workspace = db.get(Workspace, UUID(workspace_payload["id"]))
        user = db.get(User, user_payload["id"])
        monkeypatch.setattr(db, "commit", lambda: (_ for _ in ()).throw(SQLAlchemyError()))
        with pytest.raises(document_service.DocumentPersistenceError):
            document_service.create_document(
                db,
                local_storage,
                workspace,
                user,
                upload,
                settings.DOCUMENT_MAX_SIZE_BYTES,
            )

    assert not any(local_storage.root.rglob("original"))


def test_local_storage_rejects_arbitrary_paths(tmp_path):
    storage = LocalFileStorage(tmp_path / "private")
    for unsafe_key in ("../outside", "/absolute/path", r"..\outside"):
        with pytest.raises(StorageError):
            storage.save(unsafe_key, BytesIO(PDF_BYTES))


def test_document_migration_upgrade_downgrade_and_reupgrade(
    disposable_database, run_alembic
):
    database_url = make_url(str(settings.SQLALCHEMY_DATABASE_URI)).set(
        database=disposable_database
    )
    migration_engine = create_engine(database_url)
    try:
        run_alembic("upgrade", "d7f2a6b91c40", database=disposable_database)
        with migration_engine.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name='documents')"
                )
            ).scalar_one() is False

        run_alembic("upgrade", "head", database=disposable_database)
        with migration_engine.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name='documents')"
                )
            ).scalar_one() is True

        run_alembic("downgrade", "d7f2a6b91c40", database=disposable_database)
        with migration_engine.connect() as connection:
            remaining = set(
                connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema='public'"
                    )
                ).scalars()
            )
            assert "documents" not in remaining
            assert {"users", "sessions", "workspaces", "workspace_memberships"}.issubset(
                remaining
            )

        run_alembic("upgrade", "head", database=disposable_database)
        with migration_engine.connect() as connection:
            assert connection.execute(
                text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name='documents')"
                )
            ).scalar_one() is True
    finally:
        migration_engine.dispose()

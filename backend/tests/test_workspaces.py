from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership


def authenticated_client(email: str) -> tuple[TestClient, dict]:
    client = TestClient(app)
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "workspace-password",
            "display_name": email.split("@", 1)[0],
        },
    )
    assert registration.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "workspace-password"},
    )
    assert login.status_code == 200
    return client, registration.json()


def create_workspace(client: TestClient, name: str = "Research") -> dict:
    response = client.post(
        "/api/v1/workspaces",
        json={"name": name, "description": "Workspace boundary test"},
    )
    assert response.status_code == 201
    return response.json()


def add_member(workspace_id: str, user_id: int, role: str = "MEMBER") -> None:
    with SessionLocal.begin() as db:
        db.add(
            WorkspaceMembership(
                workspace_id=UUID(workspace_id),
                user_id=user_id,
                role=role,
            )
        )


def test_authenticated_user_creates_workspace_and_becomes_owner():
    client, user = authenticated_client("workspace-owner-create@example.com")
    workspace = create_workspace(client)

    assert workspace["created_by"] == user["id"]
    with SessionLocal() as db:
        membership = db.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == UUID(workspace["id"]),
                WorkspaceMembership.user_id == user["id"],
            )
        )
        assert membership is not None
        assert membership.role == "OWNER"


def test_unauthenticated_user_cannot_create_workspace():
    response = TestClient(app).post(
        "/api/v1/workspaces",
        json={"name": "Denied", "description": None},
    )
    assert response.status_code == 401


def test_user_lists_only_their_workspaces():
    first_client, _ = authenticated_client("workspace-list-first@example.com")
    second_client, _ = authenticated_client("workspace-list-second@example.com")
    first = create_workspace(first_client, "First user's workspace")
    second = create_workspace(second_client, "Second user's workspace")

    response = first_client.get("/api/v1/workspaces")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert first["id"] in ids
    assert second["id"] not in ids
    assert response.json()["total"] == len(ids)


def test_workspace_member_can_access_workspace():
    owner_client, _ = authenticated_client("workspace-access-owner@example.com")
    member_client, member = authenticated_client("workspace-access-member@example.com")
    workspace = create_workspace(owner_client)
    add_member(workspace["id"], member["id"])

    response = member_client.get(f"/api/v1/workspaces/{workspace['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == workspace["id"]


def test_non_member_cannot_discover_or_access_workspace():
    owner_client, _ = authenticated_client("workspace-idor-owner@example.com")
    outsider_client, _ = authenticated_client("workspace-idor-outsider@example.com")
    workspace = create_workspace(owner_client)

    response = outsider_client.get(f"/api/v1/workspaces/{workspace['id']}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def test_owner_can_update_workspace():
    owner_client, _ = authenticated_client("workspace-update-owner@example.com")
    workspace = create_workspace(owner_client)

    response = owner_client.patch(
        f"/api/v1/workspaces/{workspace['id']}",
        json={"name": "Updated research", "description": None},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated research"
    assert response.json()["description"] is None


def test_member_cannot_update_workspace_or_escalate_role():
    owner_client, owner = authenticated_client("workspace-member-update-owner@example.com")
    member_client, member = authenticated_client("workspace-member-update@example.com")
    workspace = create_workspace(owner_client)
    add_member(workspace["id"], member["id"])

    response = member_client.patch(
        f"/api/v1/workspaces/{workspace['id']}",
        json={"name": "Unauthorized change"},
    )
    assert response.status_code == 403

    mass_assignment = member_client.patch(
        f"/api/v1/workspaces/{workspace['id']}",
        json={"role": "OWNER"},
    )
    assert mass_assignment.status_code == 403

    owner_mass_assignment = owner_client.patch(
        f"/api/v1/workspaces/{workspace['id']}",
        json={"role": "OWNER"},
    )
    assert owner_mass_assignment.status_code == 422
    with SessionLocal() as db:
        roles = dict(
            db.execute(
                select(WorkspaceMembership.user_id, WorkspaceMembership.role).where(
                    WorkspaceMembership.workspace_id == UUID(workspace["id"])
                )
            ).all()
        )
        assert roles[member["id"]] == "MEMBER"
        assert roles[owner["id"]] == "OWNER"


def test_owner_can_delete_workspace_and_memberships_cascade():
    owner_client, owner = authenticated_client("workspace-delete-owner@example.com")
    workspace = create_workspace(owner_client)

    response = owner_client.delete(f"/api/v1/workspaces/{workspace['id']}")
    assert response.status_code == 204
    assert response.content == b""
    with SessionLocal() as db:
        assert db.get(Workspace, UUID(workspace["id"])) is None
        membership_count = db.scalar(
            select(func.count()).select_from(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == UUID(workspace["id"]),
                WorkspaceMembership.user_id == owner["id"],
            )
        )
        assert membership_count == 0


def test_member_cannot_delete_workspace():
    owner_client, _ = authenticated_client("workspace-member-delete-owner@example.com")
    member_client, member = authenticated_client("workspace-member-delete@example.com")
    workspace = create_workspace(owner_client)
    add_member(workspace["id"], member["id"])

    response = member_client.delete(f"/api/v1/workspaces/{workspace['id']}")
    assert response.status_code == 403
    with SessionLocal() as db:
        assert db.get(Workspace, UUID(workspace["id"])) is not None


def test_duplicate_membership_is_rejected():
    owner_client, owner = authenticated_client("workspace-duplicate-owner@example.com")
    workspace = create_workspace(owner_client)

    with SessionLocal() as db:
        db.add(
            WorkspaceMembership(
                workspace_id=UUID(workspace["id"]),
                user_id=owner["id"],
                role="MEMBER",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/workspaces"),
        ("get", "/api/v1/workspaces/00000000-0000-0000-0000-000000000001"),
        ("patch", "/api/v1/workspaces/00000000-0000-0000-0000-000000000001"),
        ("delete", "/api/v1/workspaces/00000000-0000-0000-0000-000000000001"),
    ],
)
def test_unauthenticated_user_cannot_access_workspace_apis(method: str, path: str):
    client = TestClient(app)
    kwargs = {"json": {"name": "Denied"}} if method == "patch" else {}
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 401


def test_workspace_migration_upgrade_downgrade_and_reupgrade(
    disposable_database, run_alembic
):
    database_url = make_url(str(settings.SQLALCHEMY_DATABASE_URI)).set(
        database=disposable_database
    )
    migration_engine = create_engine(database_url)
    try:
        run_alembic("upgrade", "c4e41fd76a03", database=disposable_database)
        with migration_engine.connect() as connection:
            before = connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            ).scalars().all()
            assert "users" in before
            assert "sessions" in before
            assert "workspaces" not in before

        run_alembic("upgrade", "head", database=disposable_database)
        with migration_engine.connect() as connection:
            upgraded = set(
                connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                ).scalars()
            )
            assert {"workspaces", "workspace_memberships"}.issubset(upgraded)

        run_alembic("downgrade", "c4e41fd76a03", database=disposable_database)
        with migration_engine.connect() as connection:
            downgraded = set(
                connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                ).scalars()
            )
            assert "workspaces" not in downgraded
            assert "workspace_memberships" not in downgraded
            assert {"users", "sessions"}.issubset(downgraded)

        run_alembic("upgrade", "head", database=disposable_database)
        with migration_engine.connect() as connection:
            reupgraded = set(
                connection.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                ).scalars()
            )
            assert {"workspaces", "workspace_memberships"}.issubset(reupgraded)
    finally:
        migration_engine.dispose()

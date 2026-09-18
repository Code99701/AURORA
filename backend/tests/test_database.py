from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
import os
import subprocess
import time

from app.main import app
from app.core.config import settings
from app.db.session import SessionLocal, engine

client = TestClient(app)

def test_database_connection():
    """
    Test that SQLAlchemy can establish a connection and execute SELECT 1.
    """
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        assert result.scalar() == 1

def test_db_health_endpoint():
    """
    Test the /api/v1/health/db endpoint.
    It should return status: ok and database: connected.
    """
    response = client.get("/api/v1/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"

def test_pgvector_extension_exists():
    """
    Test that pgvector extension is installed in the database.
    """
    with engine.connect() as connection:
        result = connection.execute(text(
            "SELECT extname FROM pg_extension WHERE extname = 'vector';"
        ))
        assert result.scalar() == "vector"

def test_db_verification_table_exists():
    """
    Test that the db_verification table exists, proving migrations ran.
    """
    with engine.connect() as connection:
        result = connection.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'db_verification');"
        ))
        assert result.scalar() is True


def test_migrations_downgrade_and_reupgrade(disposable_database, run_alembic):
    """The complete migration chain must upgrade, downgrade, and upgrade cleanly."""
    disposable_url = make_url(str(settings.SQLALCHEMY_DATABASE_URI)).set(
        database=disposable_database
    )
    from sqlalchemy import create_engine

    disposable_engine = create_engine(disposable_url)
    try:
        with disposable_engine.begin() as connection:
            connection.execute(text("CREATE TABLE unrelated_test_data (id integer PRIMARY KEY)"))

        run_alembic("upgrade", "head", database=disposable_database)
        run_alembic("downgrade", "base", database=disposable_database)

        with disposable_engine.connect() as connection:
            extension = connection.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one_or_none()
            unrelated_table = connection.execute(
                text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema = 'public' "
                    "AND table_name = 'unrelated_test_data')"
                )
            ).scalar_one()
            assert extension == "vector"
            assert unrelated_table is True

        run_alembic("upgrade", "head", database=disposable_database)

        with disposable_engine.connect() as connection:
            tables = connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            ).scalars().all()
            assert {
                "alembic_version",
                "db_verification",
                "sessions",
                "unrelated_test_data",
                "users",
            }.issubset(set(tables))
    finally:
        disposable_engine.dispose()


def test_database_persists_across_container_restart():
    """A committed marker must remain in the named volume after a DB restart."""
    marker_id = 2_147_483_000
    with SessionLocal.begin() as db:
        db.execute(
            text(
                "INSERT INTO db_verification (id) VALUES (:id) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": marker_id},
        )

    engine.dispose()
    repository_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    subprocess.run(
        ["docker", "compose", "restart", "db"],
        cwd=repository_root,
        check=True,
    )

    deadline = time.monotonic() + 30
    while True:
        try:
            with engine.connect() as connection:
                persisted = connection.execute(
                    text("SELECT id FROM db_verification WHERE id = :id"),
                    {"id": marker_id},
                ).scalar_one_or_none()
            break
        except Exception:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)

    assert persisted == marker_id

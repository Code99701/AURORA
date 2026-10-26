import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
TEST_DATABASE_PREFIX = "aurora_test_"
TEST_DATABASE_NAME = f"{TEST_DATABASE_PREFIX}{uuid.uuid4().hex[:12]}"


def _connection_parameters(database: str) -> dict[str, object]:
    return {
        "host": os.getenv("POSTGRES_SERVER", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "user": os.getenv("POSTGRES_USER", "aurora"),
        "password": os.getenv("POSTGRES_PASSWORD", "aurora_password"),
        "dbname": database,
    }


def _validate_test_database_name(database: str) -> None:
    if not re.fullmatch(r"aurora_test_[a-f0-9]{12}", database):
        raise RuntimeError(f"Refusing to manage unsafe test database name: {database}")


def _create_test_database(database: str) -> None:
    _validate_test_database_name(database)
    with psycopg.connect(**_connection_parameters("postgres"), autocommit=True) as connection:
        connection.execute(f'CREATE DATABASE "{database}"')


def _drop_test_database(database: str) -> None:
    _validate_test_database_name(database)
    with psycopg.connect(**_connection_parameters("postgres"), autocommit=True) as connection:
        connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (database,),
        )
        connection.execute(f'DROP DATABASE IF EXISTS "{database}"')


def _run_alembic(*arguments: str, database: str = TEST_DATABASE_NAME) -> None:
    environment = os.environ.copy()
    environment["POSTGRES_DB"] = database
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), *arguments],
        cwd=BACKEND_DIR,
        env=environment,
        check=True,
    )


def pytest_configure(config: pytest.Config) -> None:
    os.environ["POSTGRES_DB"] = TEST_DATABASE_NAME
    try:
        _create_test_database(TEST_DATABASE_NAME)
        _run_alembic("upgrade", "head")
    except Exception:
        try:
            _drop_test_database(TEST_DATABASE_NAME)
        except Exception:
            pass
        raise


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    try:
        from app.db.session import engine

        engine.dispose()
    finally:
        _drop_test_database(TEST_DATABASE_NAME)


@pytest.fixture
def disposable_database() -> str:
    database = f"{TEST_DATABASE_PREFIX}{uuid.uuid4().hex[:12]}"
    _create_test_database(database)
    try:
        yield database
    finally:
        _drop_test_database(database)


@pytest.fixture
def run_alembic():
    return _run_alembic


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    from app.core.rate_limit import auth_rate_limiter

    auth_rate_limiter.reset()
    yield
    auth_rate_limiter.reset()

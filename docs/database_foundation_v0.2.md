# Database Foundation v0.2

Database Foundation v0.2 is the implemented persistence layer for AURORA. It intentionally contains no document-ingestion or RAG functionality.

## Implemented architecture

```text
Docker Compose
  -> PostgreSQL 16 with pgvector
  -> psycopg 3
  -> SQLAlchemy 2.x engine and sessions
  -> Alembic schema migrations
  -> FastAPI get_db() dependency
```

The `db` service in `docker-compose.yml` uses `pgvector/pgvector:pg16`, publishes the configured PostgreSQL port, has a readiness health check, and stores its cluster in the named `postgres_data` volume. `docker compose restart db` restarts the container without removing that volume.

Application settings are loaded from the repository-root `.env` regardless of the process working directory. SQLAlchemy uses the `postgresql+psycopg` driver, enables `pool_pre_ping`, and supplies request-scoped sessions through `get_db()`.

## Migrations

Alembic configuration lives in `backend/alembic.ini`; its paths are anchored to that file, so commands work from the repository root or `backend/`.

The migration history is:

1. `8e7fbff5b5cd`: creates the pgvector extension and `db_verification` table.
2. `9baf81b19738`: creates the `users` and `sessions` tables and their indexes.
3. `c4e41fd76a03`: adds database-side defaults and aligns the display-name constraint with the API schema.

Downgrading to `base` removes only AURORA-owned tables and Alembic state. It deliberately leaves the pgvector extension installed and does not delete the Docker volume or unrelated database objects.

Run the cycle manually against a disposable database only:

```powershell
cd backend
alembic upgrade head
alembic downgrade base
alembic upgrade head
```

## Health endpoint

`GET /api/v1/health/db` obtains a SQLAlchemy session and executes `SELECT 1`. It returns HTTP 200 with `{"status":"ok","database":"connected"}` when PostgreSQL is reachable, or a non-sensitive HTTP 503 response when it is not.

## Verification strategy

The backend suite automatically creates a uniquely named `aurora_test_<random>` database, migrates it, and removes it after the run. It never truncates or migrates the configured development database. Coverage includes:

- SQLAlchemy connectivity;
- the database health endpoint;
- pgvector installation;
- verification-table existence;
- a full upgrade/downgrade/re-upgrade cycle in another disposable database;
- committed marker persistence through `docker compose restart db`.

Run:

```powershell
docker compose up -d db
cd backend
pytest tests
```

Stopping the container with `docker compose stop db` preserves data. Do not use `docker compose down -v` unless intentionally deleting the named volume.

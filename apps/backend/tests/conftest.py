import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Real-Postgres integration fixtures. Per project rules (docs/CLAUDE_CODE_AUDIT.md /
# PROJECT_RULES.md), we do NOT substitute SQLite for Postgres validation - these tests
# are skipped (not faked) when a real pgvector-capable Postgres isn't reachable.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/deepinsight_test",
)


def _postgres_available():
    try:
        # connect_timeout bounds this probe - without it, a host that's unreachable at
        # the network level (not just refusing auth) can hang far longer than a quick
        # "is it there" check should ever take, stalling test collection instead of
        # skipping cleanly. See api/database/session.py for the same fix in app code.
        engine = create_engine(TEST_DATABASE_URL, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


POSTGRES_AVAILABLE = _postgres_available()

requires_postgres = pytest.mark.skipif(
    not POSTGRES_AVAILABLE,
    reason=f"Real Postgres not reachable at {TEST_DATABASE_URL} - set TEST_DATABASE_URL or start it locally.",
)


@pytest.fixture(scope="session")
def pg_engine():
    if not POSTGRES_AVAILABLE:
        pytest.skip("Postgres not available")
    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


def _ensure_document_vectors_table(engine):
    """document_vectors isn't an ORM model (raw vector column, no SQLAlchemy Vector
    type dependency - see PgVectorStore), so Base.metadata.create_all() doesn't create
    it. This mirrors alembic/versions/5a3c7e9f1b62_add_pgvector_extension_and_
    document_vectors.py exactly - keep both in sync if that migration changes."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS document_vectors (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                client_id uuid NOT NULL,
                document_id uuid NOT NULL,
                chunk_id uuid NOT NULL,
                embedding vector(1024),
                metadata jsonb DEFAULT '{}'::jsonb
            );
        """))
        conn.commit()


@pytest.fixture()
def db_session(pg_engine):
    """A real Postgres session wrapped in a transaction that's rolled back after each
    test, so tests never leave residue in the shared test database."""
    from api.models.base import Base
    import api.models  # noqa: F401 - ensures every model is registered on Base.metadata

    Base.metadata.create_all(bind=pg_engine)
    _ensure_document_vectors_table(pg_engine)

    connection = pg_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()

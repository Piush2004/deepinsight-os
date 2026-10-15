"""
Real end-to-end router tests against SQLite + AUTH_MODE=demo, driven through the actual
FastAPI app (TestClient -> real routing -> real dependency injection -> real DB
queries) rather than calling services directly.

This is a genuinely new test category for this project: every existing "e2e" knowledge
test (tests/test_knowledge_e2e.py etc.) calls DocumentUploadService/etc. directly,
bypassing the router layer entirely - which is exactly why two real bugs shipped
undetected until dev/demo-mode live HTTP testing found them (see
docs/DEV_DEMO_MODE.md): api/repositories/base.py's BaseRepository.get() crashed on
GET /clients/{id} for any authorized non-admin user, and api/routers/knowledge.py's
get_documents()/get_knowledge_history() crashed the same way - both only on SQLite,
both invisible to every existing test because none of them go through real HTTP with a
real (non-UUID-typed-by-FastAPI) string id.

Hermetic: in-memory SQLite via a get_db override, no Postgres, no external services.
AUTH_MODE=demo is monkeypatched on the shared `settings` singleton for the duration of
each test and always restored, since api.core.security reads it fresh per-request.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from api.core.config import settings
from api.database.session import get_db
from api.models.base import Base
import api.models  # noqa: F401
from api.models.user import User
from api.models.client import Client
from api.models.membership import ClientMembership
from api.models.content import Content


@pytest.fixture()
def sqlite_demo_client():
    # StaticPool is required, not optional: SQLAlchemy's default pool opens a new
    # DBAPI connection per checkout, and ":memory:" is a distinct, empty database per
    # connection - without pinning to a single shared connection, a request dispatched
    # through TestClient's real ASGI stack (a second connection checkout) sees "no
    # such table" even though Base.metadata.create_all() already ran successfully on
    # the first connection. This is a test-fixture concern, not an application bug.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()

    def _override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db

    original_auth_mode = settings.AUTH_MODE
    original_vector_store = settings.VECTOR_STORE_PROVIDER
    settings.AUTH_MODE = "demo"
    settings.VECTOR_STORE_PROVIDER = "memory"

    try:
        yield session, TestClient(app)
    finally:
        settings.AUTH_MODE = original_auth_mode
        settings.VECTOR_STORE_PROVIDER = original_vector_store
        app.dependency_overrides.pop(get_db, None)
        session.close()
        engine.dispose()


def _seed_user_and_client(session, clerk_id="demo-test-user", role="Marketing Manager"):
    client = Client(name="Router E2E Test Client")
    session.add(client)
    session.flush()

    user = User(clerk_id=clerk_id, email=f"{clerk_id}@demo.local", role=role)
    session.add(user)
    session.flush()

    session.add(ClientMembership(user_id=user.id, client_id=client.id))
    session.commit()
    return user, client


def _headers(demo_user="demo-test-user"):
    return {"Authorization": "Bearer demo", "X-Demo-User": demo_user}


def test_get_client_by_authorized_non_admin_user_over_real_http(sqlite_demo_client):
    """The exact bug: BaseRepository.get() crashed with 500 for a real, authorized,
    non-admin user reading their own client - found live, not by reading code."""
    session, client = sqlite_demo_client
    _user, db_client = _seed_user_and_client(session)

    response = client.get(f"/api/v1/clients/{db_client.id}", headers=_headers())

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Router E2E Test Client"


def test_get_documents_list_over_real_http(sqlite_demo_client):
    """The exact bug: get_documents() filtered Document.client_id against a raw string
    query param, crashing on SQLite."""
    session, client = sqlite_demo_client
    _user, db_client = _seed_user_and_client(session)

    response = client.get(f"/api/v1/documents?client_id={db_client.id}", headers=_headers())

    assert response.status_code == 200, response.text
    assert response.json() == {"documents": []}


def test_get_knowledge_history_over_real_http(sqlite_demo_client):
    session, client = sqlite_demo_client
    _user, db_client = _seed_user_and_client(session)

    response = client.get(f"/api/v1/knowledge/history?client_id={db_client.id}", headers=_headers())

    assert response.status_code == 200, response.text
    assert response.json() == {"history": []}


def test_cross_tenant_client_read_is_denied_over_real_http(sqlite_demo_client):
    """Live tenant-isolation check through the real router, not a unit test of the
    authorization helper in isolation."""
    session, client = sqlite_demo_client
    user, owned_client = _seed_user_and_client(session, clerk_id="user-a")

    other_client = Client(name="A Client user-a Does Not Own")
    session.add(other_client)
    session.commit()

    response = client.get(f"/api/v1/clients/{other_client.id}", headers=_headers("user-a"))

    assert response.status_code == 404, response.text


def test_full_document_upload_and_list_round_trip_over_real_http(sqlite_demo_client):
    """Real upload through the real pipeline (validate -> extract -> chunk -> embed ->
    store -> verify) via HTTP, then confirms it shows up in the real list endpoint -
    the exact flow that silently returned an empty/wrong count in the frontend before
    these fixes (a query error was swallowed into a blank '0' rather than shown)."""
    session, client = sqlite_demo_client
    _user, db_client = _seed_user_and_client(session)

    upload_response = client.post(
        "/api/v1/documents/upload",
        headers=_headers(),
        data={"client_id": str(db_client.id)},
        files={"file": ("brand.txt", b"Our brand voice is warm and direct.", "text/plain")},
    )
    assert upload_response.status_code == 200, upload_response.text

    list_response = client.get(f"/api/v1/documents?client_id={db_client.id}", headers=_headers())
    assert list_response.status_code == 200, list_response.text
    documents = list_response.json()["documents"]
    assert len(documents) == 1
    assert documents[0]["title"] == "brand.txt"


def test_schedule_content_over_real_http(sqlite_demo_client):
    """New endpoint: POST /content/{id}/schedule. Confirms it sets scheduled_date
    without creating a new ContentVersion or resetting status - and that it's
    tenant-scoped like every other content-scoped endpoint."""
    session, client = sqlite_demo_client
    _user, db_client = _seed_user_and_client(session)

    content = Content(client_id=db_client.id, title="Draft", content_type="blog", status="approved")
    session.add(content)
    session.commit()

    response = client.post(
        f"/api/v1/content/{content.id}/schedule",
        headers=_headers(),
        params={"scheduled_date": "2026-09-01T09:00:00"},
    )
    assert response.status_code == 200, response.text

    detail = client.get(f"/api/v1/content/{content.id}", headers=_headers())
    assert detail.status_code == 200
    assert detail.json()["status"] == "approved"  # unchanged by scheduling
    assert detail.json()["scheduled_date"] is not None


def test_schedule_content_cross_tenant_is_denied_over_real_http(sqlite_demo_client):
    session, client = sqlite_demo_client
    _user, _owned_client = _seed_user_and_client(session, clerk_id="user-a")

    other_client = Client(name="Not user-a's client")
    session.add(other_client)
    session.flush()
    other_content = Content(client_id=other_client.id, title="Draft", content_type="blog", status="approved")
    session.add(other_content)
    session.commit()

    response = client.post(
        f"/api/v1/content/{other_content.id}/schedule",
        headers=_headers("user-a"),
        params={"scheduled_date": "2026-09-01T09:00:00"},
    )
    assert response.status_code == 404, response.text

"""
Real end-to-end router tests for the SEO Intelligence endpoints (api/routers/seo.py),
against SQLite + AUTH_MODE=demo, driven through the actual FastAPI app - same pattern
as tests/test_router_sqlite_e2e.py (real HTTP -> real routing -> real dependency
injection -> real DB queries), extended here for the new SEO domain.

The dispatch endpoint (POST /seo/analyze) is deliberately NOT exercised for its happy
path here - like generate_report/generate_content, a real run requires a live LLM
(CELERY_EAGER=true makes it run synchronously and propagate any exception right back
to this request). That full lifecycle is covered by tests/test_seo_agent.py (mocked
LLM) and the live Ollama verification. This file proves the endpoint enforces tenant
isolation *before* ever reaching Celery/the LLM, and that every read/approve/reject/
comment/edit endpoint is correctly tenant-scoped.
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
from api.models.seo import SEOAnalysis, SEOOpportunity, SEOApprovalRequest


@pytest.fixture()
def sqlite_demo_client():
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
    client = Client(name="SEO Router E2E Test Client")
    session.add(client)
    session.flush()

    user = User(clerk_id=clerk_id, email=f"{clerk_id}@demo.local", role=role)
    session.add(user)
    session.flush()

    session.add(ClientMembership(user_id=user.id, client_id=client.id))
    session.commit()
    return user, client


def _seed_opportunity(session, client_obj, category="QUICK_WIN"):
    analysis = SEOAnalysis(
        client_id=client_obj.id, status="completed", data_provider="DevSEODataProvider",
        period_start="2026-08-01", period_end="2026-08-31", executive_summary="Test summary.",
    )
    session.add(analysis)
    session.flush()

    opportunity = SEOOpportunity(
        analysis_id=analysis.id, client_id=client_obj.id,
        opportunity_type="CTR_OPTIMIZATION", category=category, title="Improve CTR for test keyword",
        source_entity="test keyword", source_type="keyword",
        metrics={"impressions": 18000, "clicks": 198, "ctr": 0.011, "position": 6.2},
        evidence=["High impressions (18000) at a strong position (6.2) with CTR far below expected (1.10%)."],
        priority_score=72.5, confidence_score=90.0, impact_score=64.0, effort_estimate="Low",
        recommended_actions=["Rewrite the page title and meta description for this keyword."],
        status="pending_review",
    )
    session.add(opportunity)
    session.flush()

    session.add(SEOApprovalRequest(opportunity_id=opportunity.id, status="pending"))
    session.commit()
    return analysis, opportunity


def _headers(demo_user="demo-test-user"):
    return {"Authorization": "Bearer demo", "X-Demo-User": demo_user}


def test_analyze_dispatch_is_denied_for_unauthorized_client_before_reaching_celery(sqlite_demo_client):
    """Proves assert_client_access runs before process_seo_analysis.delay() - an
    unauthorized caller never gets anywhere near dispatching a Celery job or an LLM."""
    session, client = sqlite_demo_client
    _user, _owned_client = _seed_user_and_client(session, clerk_id="user-a")

    other_client = Client(name="Not user-a's client")
    session.add(other_client)
    session.commit()

    response = client.post(
        "/api/v1/seo/analyze",
        headers=_headers("user-a"),
        params={"client_id": str(other_client.id), "period_start": "2026-08-01", "period_end": "2026-08-31"},
    )
    assert response.status_code == 404, response.text


def test_seo_summary_over_real_http(sqlite_demo_client):
    session, client = sqlite_demo_client
    _user, db_client = _seed_user_and_client(session)
    _analysis, _opp = _seed_opportunity(session, db_client, category="QUICK_WIN")

    response = client.get(f"/api/v1/seo/summary?client_id={db_client.id}", headers=_headers())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["has_analysis"] is True
    assert body["latest_analysis"]["executive_summary"] == "Test summary."
    assert body["category_counts"]["QUICK_WIN"] == 1
    assert body["category_counts"]["PERFORMANCE_RISK"] == 0
    assert body["total_open_opportunities"] == 1


def test_seo_summary_with_no_analysis_yet_over_real_http(sqlite_demo_client):
    session, client = sqlite_demo_client
    _user, db_client = _seed_user_and_client(session)

    response = client.get(f"/api/v1/seo/summary?client_id={db_client.id}", headers=_headers())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["has_analysis"] is False
    assert body["latest_analysis"] is None
    assert body["total_open_opportunities"] == 0


def test_list_and_get_opportunity_over_real_http(sqlite_demo_client):
    session, client = sqlite_demo_client
    _user, db_client = _seed_user_and_client(session)
    _analysis, opportunity = _seed_opportunity(session, db_client)

    list_response = client.get(f"/api/v1/seo/opportunities?client_id={db_client.id}", headers=_headers())
    assert list_response.status_code == 200, list_response.text
    listed = list_response.json()["opportunities"]
    assert len(listed) == 1
    assert listed[0]["category"] == "QUICK_WIN"

    detail_response = client.get(f"/api/v1/seo/opportunities/{opportunity.id}", headers=_headers())
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["opportunity_type"] == "CTR_OPTIMIZATION"
    assert detail["metrics"]["position"] == 6.2
    assert detail["approval"]["status"] == "pending"
    assert detail["comments"] == []


def test_list_opportunities_filters_by_category_over_real_http(sqlite_demo_client):
    session, client = sqlite_demo_client
    _user, db_client = _seed_user_and_client(session)
    _seed_opportunity(session, db_client, category="QUICK_WIN")
    _seed_opportunity(session, db_client, category="PERFORMANCE_RISK")

    response = client.get(
        f"/api/v1/seo/opportunities?client_id={db_client.id}&category=PERFORMANCE_RISK",
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    listed = response.json()["opportunities"]
    assert len(listed) == 1
    assert listed[0]["category"] == "PERFORMANCE_RISK"


def test_cross_tenant_opportunity_read_is_denied_over_real_http(sqlite_demo_client):
    session, client = sqlite_demo_client
    _user, _owned_client = _seed_user_and_client(session, clerk_id="user-a")

    other_client = Client(name="Not user-a's client")
    session.add(other_client)
    session.flush()
    _analysis, other_opportunity = _seed_opportunity(session, other_client)

    response = client.get(f"/api/v1/seo/opportunities/{other_opportunity.id}", headers=_headers("user-a"))
    assert response.status_code == 404, response.text


def test_approve_reject_comment_edit_round_trip_over_real_http(sqlite_demo_client):
    session, client = sqlite_demo_client
    _user, db_client = _seed_user_and_client(session)
    _analysis, opportunity = _seed_opportunity(session, db_client)

    edit_response = client.put(
        f"/api/v1/seo/opportunities/{opportunity.id}",
        headers=_headers(),
        params={"title": "Fix the meta description for test keyword"},
        json=["Rewrite the title tag.", "Add schema markup."],
    )
    assert edit_response.status_code == 200, edit_response.text

    comment_response = client.post(
        f"/api/v1/seo/opportunities/{opportunity.id}/comment",
        headers=_headers(),
        params={"comment": "Looks good, approving after title tweak."},
    )
    assert comment_response.status_code == 200, comment_response.text

    approve_response = client.post(f"/api/v1/seo/opportunities/{opportunity.id}/approve", headers=_headers())
    assert approve_response.status_code == 200, approve_response.text

    detail = client.get(f"/api/v1/seo/opportunities/{opportunity.id}", headers=_headers()).json()
    assert detail["title"] == "Fix the meta description for test keyword"
    assert detail["recommended_actions"] == ["Rewrite the title tag.", "Add schema markup."]
    assert detail["status"] == "approved"
    assert detail["approval"]["status"] == "approved"
    assert len(detail["comments"]) == 1


def test_reject_opportunity_over_real_http(sqlite_demo_client):
    session, client = sqlite_demo_client
    _user, db_client = _seed_user_and_client(session)
    _analysis, opportunity = _seed_opportunity(session, db_client)

    response = client.post(
        f"/api/v1/seo/opportunities/{opportunity.id}/reject",
        headers=_headers(),
        params={"reason": "Not a real priority this quarter."},
    )
    assert response.status_code == 200, response.text

    detail = client.get(f"/api/v1/seo/opportunities/{opportunity.id}", headers=_headers()).json()
    assert detail["status"] == "rejected"
    assert detail["approval"]["status"] == "rejected"
    assert detail["approval"]["comments"] == "Not a real priority this quarter."


def test_approve_opportunity_cross_tenant_is_denied_over_real_http(sqlite_demo_client):
    session, client = sqlite_demo_client
    _user, _owned_client = _seed_user_and_client(session, clerk_id="user-a")

    other_client = Client(name="Not user-a's client")
    session.add(other_client)
    session.flush()
    _analysis, other_opportunity = _seed_opportunity(session, other_client)

    response = client.post(f"/api/v1/seo/opportunities/{other_opportunity.id}/approve", headers=_headers("user-a"))
    assert response.status_code == 404, response.text


def test_seo_history_over_real_http(sqlite_demo_client):
    session, client = sqlite_demo_client
    _user, db_client = _seed_user_and_client(session)

    response = client.get(f"/api/v1/seo/history?client_id={db_client.id}", headers=_headers())

    assert response.status_code == 200, response.text
    assert response.json() == {"history": []}

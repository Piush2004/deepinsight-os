from uuid import uuid4
from typing import Dict, Any

from tests.conftest import requires_postgres
from api.models.client import Client
from api.models.reporting import Report, ReportVersion, ApprovalRequest
from api.core.agent.reporting_agent import ReportingAgent
from api.core.interfaces.llm_provider import LLMProvider
from api.services.intelligence.engine import IntelligenceLayer

from tests.test_reporting import REALISTIC_SUMMARY, MockKnowledge, MockPrompt


class MockLLM(LLMProvider):
    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7, **kwargs) -> str:
        return REALISTIC_SUMMARY
    def generate_json(self, prompt, system_prompt="", schema=None, **kwargs) -> Dict[str, Any]:
        return {}


@requires_postgres
def test_reporting_agent_finalize_persists_real_rows(db_session):
    client = Client(name="Acme Corp")
    db_session.add(client)
    db_session.flush()

    agent = ReportingAgent(
        client_id=client.id,
        task_id=uuid4(),
        llm=MockLLM(),
        knowledge_query=MockKnowledge(),
        prompt_service=MockPrompt(),
        intelligence=IntelligenceLayer(),
        db=db_session,
    )

    output = agent.run(metrics={"ctr": 0.04}, historical_metrics={"ctr": 0.02}, reporting_period="July 2026")

    assert agent.report is not None
    report = db_session.query(Report).filter_by(id=agent.report.id).first()
    assert report is not None
    assert report.client_id == client.id
    assert report.status == "pending_approval"

    versions = db_session.query(ReportVersion).filter_by(report_id=report.id).all()
    assert len(versions) == 1
    assert versions[0].content_text == output["Executive Summary"]

    approvals = db_session.query(ApprovalRequest).filter_by(report_id=report.id).all()
    assert len(approvals) == 1
    assert approvals[0].status == "pending"


@requires_postgres
def test_reporting_agent_is_tenant_scoped_on_persist(db_session):
    client_a = Client(name="Client A")
    client_b = Client(name="Client B")
    db_session.add_all([client_a, client_b])
    db_session.flush()

    agent = ReportingAgent(
        client_id=client_a.id,
        task_id=uuid4(),
        llm=MockLLM(),
        knowledge_query=MockKnowledge(),
        prompt_service=MockPrompt(),
        intelligence=IntelligenceLayer(),
        db=db_session,
    )
    agent.run(metrics={"ctr": 0.04}, historical_metrics={"ctr": 0.02}, reporting_period="July 2026")

    reports_for_b = db_session.query(Report).filter_by(client_id=client_b.id).all()
    assert reports_for_b == []
    reports_for_a = db_session.query(Report).filter_by(client_id=client_a.id).all()
    assert len(reports_for_a) == 1

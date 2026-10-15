from uuid import uuid4

from tests.conftest import requires_postgres
from api.models.client import Client
from api.models.content import Content, ContentVersion, ContentScore, ContentApprovalRequest
from api.core.agent.content_agent import ContentAgent
from api.services.validation.content_quality import ContentQualityEngine

from tests.test_content import MockLLM, MockKnowledge, MockPrompt, MockIntelligence, REALISTIC_BLOG_BODY


@requires_postgres
def test_content_agent_finalize_persists_real_rows(db_session):
    client = Client(name="Acme Corp")
    db_session.add(client)
    db_session.flush()

    agent = ContentAgent(
        client_id=client.id,
        task_id=uuid4(),
        llm=MockLLM(),
        knowledge_query=MockKnowledge(),
        prompt_service=MockPrompt(),
        intelligence=MockIntelligence(),
        quality_engine=ContentQualityEngine(),
        db=db_session,
    )

    output = agent.run(content_type="blog", target_audience="Developers", goal="Drive signups")

    assert agent.content is not None
    content = db_session.query(Content).filter_by(id=agent.content.id).first()
    assert content.client_id == client.id
    assert content.status == "pending_review"

    versions = db_session.query(ContentVersion).filter_by(content_id=content.id).all()
    assert len(versions) == 1
    assert versions[0].body == REALISTIC_BLOG_BODY

    scores = db_session.query(ContentScore).filter_by(version_id=versions[0].id).first()
    assert scores is not None
    assert scores.overall_score == output["scores"]["overall_score"]

    approvals = db_session.query(ContentApprovalRequest).filter_by(content_id=content.id).all()
    assert len(approvals) == 1
    assert approvals[0].status == "pending"


@requires_postgres
def test_content_agent_edit_creates_new_version_not_new_content(db_session):
    client = Client(name="Acme Corp")
    db_session.add(client)
    db_session.flush()

    agent = ContentAgent(
        client_id=client.id, task_id=uuid4(), llm=MockLLM(), knowledge_query=MockKnowledge(),
        prompt_service=MockPrompt(), intelligence=MockIntelligence(),
        quality_engine=ContentQualityEngine(), db=db_session,
    )
    agent.run(content_type="blog", target_audience="Developers", goal="Drive signups")
    first_content_id = agent.content.id

    agent2 = ContentAgent(
        client_id=client.id, task_id=uuid4(), llm=MockLLM(), knowledge_query=MockKnowledge(),
        prompt_service=MockPrompt(), intelligence=MockIntelligence(),
        quality_engine=ContentQualityEngine(), db=db_session,
    )
    agent2.run(content_type="blog", target_audience="Developers", goal="Drive signups",
               content_id=str(first_content_id))

    assert agent2.content.id == first_content_id
    versions = db_session.query(ContentVersion).filter_by(content_id=first_content_id).all()
    assert len(versions) == 2

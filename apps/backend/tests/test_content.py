import pytest
from uuid import uuid4, UUID
from api.core.agent.content_agent import ContentAgent
from api.core.interfaces.llm_provider import LLMProvider
from api.core.interfaces.knowledge_query_service import KnowledgeQueryService
from api.services.prompt_service import PromptService
from api.services.intelligence.engine import IntelligenceLayer
from api.services.validation.content_quality import ContentQualityEngine
from typing import Dict, Any

REALISTIC_BLOG_BODY = (
    "Mocked marketing teams face a familiar challenge: turning scattered performance "
    "data into a clear, confident story for leadership. Developers building internal "
    "tools often start with a dashboard, but a dashboard alone rarely drives a decision. "
    "What teams need is a narrative that explains why the numbers moved and what to do "
    "next. That is the gap this platform closes. By combining structured business rules "
    "with a knowledge base of brand context, the system produces summaries that a busy "
    "director can read in under a minute and still trust. The approach favors "
    "transparency over cleverness. Every claim traces back to a source, every "
    "recommendation ties to an observed signal, and every draft waits for a human "
    "reviewer before anything is published. That discipline is what makes the workflow "
    "usable for a real marketing organization rather than a flashy demo. Teams adopting "
    "this pattern report faster review cycles and fewer late-night edits before a "
    "board meeting, because the first draft already reflects the brand voice."
)


class MockLLM(LLMProvider):
    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7, **kwargs) -> str:
        return REALISTIC_BLOG_BODY
    def generate_json(self, prompt: str, system_prompt: str = "", schema: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        return {}

class MockKnowledge(KnowledgeQueryService):
    def query(self, question: str, client_id: UUID, context_filters: Dict[str, Any] = None) -> Dict[str, Any]:
        return {
            "content": {"forbidden_terms": ["badword"], "required_keywords": ["Mocked"]},
            "sources": ["citation_1"],
        }

class MockPrompt(PromptService):
    def load_prompt(self, agent_name: str, template_name: str, context: Dict[str, Any] = None) -> str:
        return "mock prompt"
    def get_prompt_version_hash(self, agent_name: str, template_name: str) -> str:
        return "def67890"

class MockIntelligence(IntelligenceLayer):
    def generate_context(self, raw_metrics: Dict[str, Any], knowledge_context: Dict[str, Any]) -> Dict[str, Any]:
        return {"insights": [], "recommendations": []}

def test_content_agent_lifecycle():
    client_id = uuid4()
    task_id = uuid4()
    
    agent = ContentAgent(
        client_id=client_id,
        task_id=task_id,
        llm=MockLLM(),
        knowledge_query=MockKnowledge(),
        prompt_service=MockPrompt(),
        intelligence=MockIntelligence(),
        quality_engine=ContentQualityEngine()
    )
    
    # Run the full lifecycle
    output = agent.run(
        content_type="blog",
        target_audience="Developers",
        goal="Drive signups"
    )
    
    # Assertions
    assert "body" in output
    assert output["body"] == REALISTIC_BLOG_BODY
    assert "scores" in output
    # Real, computed scores (see api/services/intelligence/text_heuristics.py) - not
    # hardcoded stub values. This mock body is long-form, on-brand, well-punctuated,
    # cited, and contains no numbers, so it should clear the real quality gate.
    assert output["scores"]["overall_score"] >= 80
    assert output["scores"]["completeness"] == 100  # >=150 words
    assert output["scores"]["brand_consistency"] == 100  # no forbidden terms, has required keyword
    assert output["scores"]["citation_coverage"] == 100  # MockKnowledge returns non-empty sources
    assert output["scores"]["hallucination_risk"] == 0  # no numbers in the body to fabricate
    
    # Validate base state changes
    assert agent.is_approved is False
    assert agent.execution_logs["prompt_version"] == "def67890"

def test_content_agent_validation_failure():
    agent = ContentAgent(
        client_id=uuid4(),
        task_id=uuid4(),
        llm=MockLLM(),
        knowledge_query=MockKnowledge(),
        prompt_service=MockPrompt(),
        intelligence=MockIntelligence(),
        quality_engine=ContentQualityEngine()
    )
    
    with pytest.raises(ValueError, match="Content type is required"):
        agent.run(target_audience="Developers") # Missing content_type

class BadMockLLM(LLMProvider):
    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7, **kwargs) -> str:
        return "This text contains a badword."
    def generate_json(self, prompt: str, system_prompt: str = "", schema: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        return {}

def test_content_agent_brand_voice_failure():
    agent = ContentAgent(
        client_id=uuid4(),
        task_id=uuid4(),
        llm=BadMockLLM(),
        knowledge_query=MockKnowledge(),
        prompt_service=MockPrompt(),
        intelligence=MockIntelligence(),
        quality_engine=ContentQualityEngine()
    )
    
    with pytest.raises(ValueError, match="Forbidden term detected: 'badword'"):
        agent.run(
            content_type="blog",
            target_audience="Developers",
            goal="Drive signups"
        )


def test_content_agent_gather_context_provides_every_variable_the_real_prompt_needs():
    """Regression test for a real bug found during dev/demo-mode live testing
    (docs/DEV_DEMO_MODE.md): gather_context() computed 'goal'/'audience' into a local
    raw_knowledge dict but never copied them onto self.context, which is what
    PromptService.load_prompt() str.format()s against - every real content-generation
    call failed instantly with "Missing context variable for prompt: 'goal'", before
    ever reaching the LLM. Every other test in this file uses MockPrompt, which
    ignores its context argument entirely and so never exercises the real
    str.format() call - this test deliberately uses the real PromptService against the
    real prompts/content/blog.md template to close that gap."""
    agent = ContentAgent(
        client_id=uuid4(),
        task_id=uuid4(),
        llm=MockLLM(),
        knowledge_query=MockKnowledge(),
        prompt_service=PromptService(base_dir="prompts"),
        intelligence=MockIntelligence(),
        quality_engine=ContentQualityEngine(),
    )

    output = agent.run(content_type="Blog", target_audience="Developers", goal="Drive signups")

    assert output["body"] == REALISTIC_BLOG_BODY


@pytest.mark.parametrize("content_type", ["blog", "linkedin", "email", "social"])
def test_every_frontend_exposed_content_type_has_a_real_working_prompt(content_type):
    """The frontend's content-type dropdown (apps/frontend/src/app/(dashboard)/content/page.tsx,
    CONTENT_TYPES) offered 'linkedin'/'email'/'social' with no matching prompt file -
    generating any of them would have raised FileNotFoundError, violating this
    project's own rule that only content types with real prompts may be exposed in the
    UI. This runs every type the frontend actually offers through the real
    ContentAgent + real PromptService to prove each one genuinely works, not just
    'blog'."""
    agent = ContentAgent(
        client_id=uuid4(),
        task_id=uuid4(),
        llm=MockLLM(),
        knowledge_query=MockKnowledge(),
        prompt_service=PromptService(base_dir="prompts"),
        intelligence=MockIntelligence(),
        quality_engine=ContentQualityEngine(),
    )

    output = agent.run(content_type=content_type, target_audience="Developers", goal="Drive signups")

    assert output["body"] == REALISTIC_BLOG_BODY

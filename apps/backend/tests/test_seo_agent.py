import pytest
from uuid import uuid4, UUID
from typing import Any, Dict, List

from api.core.agent.seo_agent import SEOAgent
from api.core.interfaces.llm_provider import LLMProvider
from api.core.interfaces.knowledge_query_service import KnowledgeQueryService
from api.core.interfaces.seo_data_provider import SEODataProvider
from api.services.prompt_service import PromptService
from api.services.intelligence.engine import IntelligenceLayer

# Long enough (150+ words) and grounded enough in the fixture's real vocabulary
# (impressions, position, CTR, "test keyword quick win") to legitimately clear the
# real, unmodified Evaluation Engine's quality gate - mirrors tests/test_reporting.py's
# REALISTIC_SUMMARY, which exists for the identical reason (a short, generic mock
# string fails completeness/groundedness for real, not because of a code bug).
REALISTIC_EXEC_SUMMARY = (
    "This period's search performance data points to a clear, low-effort opportunity "
    "worth acting on first. The keyword test keyword quick win is already earning real "
    "impressions and holding a solid position, but its click-through rate is well below "
    "what a listing at that position typically earns, which points at the search "
    "snippet rather than the ranking itself as the thing worth fixing. A stronger, more "
    "specific page title and meta description aligned with what searchers are actually "
    "looking for should convert more of that existing visibility into real clicks "
    "without requiring any new content or additional ranking work. By contrast, the "
    "test keyword stable term is already converting impressions into clicks at a strong "
    "rate and does not need attention this period - it can be left as-is while the team "
    "focuses effort on the click-through rate opportunity, since that keyword's "
    "position, impressions, and click-through rate all remain essentially unchanged "
    "period over period. Prioritizing the click-through rate fix first should produce "
    "the fastest measurable improvement in organic clicks for the lowest amount of work."
)

REALISTIC_EXPLANATION = (
    "This keyword already earns real visibility at a strong position, so the fastest "
    "path to more traffic is not higher rankings but a snippet that better matches "
    "what searchers are actually looking for - a low-effort, high-leverage fix."
)


class MockLLM(LLMProvider):
    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7, **kwargs) -> str:
        return REALISTIC_EXEC_SUMMARY

    def generate_json(self, prompt: str, system_prompt: str = "", schema: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        return {
            "executive_summary": REALISTIC_EXEC_SUMMARY,
            "opportunity_explanations": [REALISTIC_EXPLANATION] * 10,  # more than enough for any opportunity count
        }


class MockKnowledge(KnowledgeQueryService):
    def query(self, question: str, client_id: UUID, context_filters: Dict[str, Any] = None) -> Dict[str, Any]:
        return {"content": "The brand voice is confident and direct.", "sources": ["citation_1"], "grounded": True}


class MockPrompt(PromptService):
    def load_prompt(self, agent_name: str, template_name: str, context: Dict[str, Any] = None) -> str:
        return "mock prompt"

    def get_prompt_version_hash(self, agent_name: str, template_name: str) -> str:
        return "seo00001"


class FixtureSEOProvider(SEODataProvider):
    """A small, deterministic fixture distinct from DevSEODataProvider - keeps this
    test file's expectations independent of the real fixture's exact numbers, so a
    future edit to the real dev fixture can't silently change what this test asserts."""

    def get_search_performance(self, client_id: UUID, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        return [
            {
                "entity": "test keyword quick win",
                "entity_type": "keyword",
                "page": "/test-page",
                "impressions": 20000,
                "clicks": 200,
                "ctr": 0.01,
                "position": 5.0,
                "impressions_previous": 19500,
                "clicks_previous": 195,
                "ctr_previous": 0.01,
                "position_previous": 5.2,
            },
            {
                "entity": "test keyword stable",
                "entity_type": "keyword",
                "page": "/stable-page",
                "impressions": 1000,
                "clicks": 300,
                "ctr": 0.30,
                "position": 1.2,
                "impressions_previous": 990,
                "clicks_previous": 295,
                "ctr_previous": 0.30,
                "position_previous": 1.2,
            },
        ]


class EmptySEOProvider(SEODataProvider):
    def get_search_performance(self, client_id: UUID, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        return []


def _agent(seo_data_provider=None, llm=None):
    return SEOAgent(
        client_id=uuid4(),
        task_id=uuid4(),
        llm=llm or MockLLM(),
        knowledge_query=MockKnowledge(),
        prompt_service=MockPrompt(),
        intelligence=IntelligenceLayer(),
        seo_data_provider=seo_data_provider or FixtureSEOProvider(),
    )


def test_seo_agent_lifecycle_detects_opportunity_and_generates_explanation():
    agent = _agent()

    output = agent.run(period_start="2026-08-01", period_end="2026-08-31")

    # The fixture's first row is a deliberate CTR_OPTIMIZATION case (high impressions,
    # position in the page-one band, CTR well below expected) - the second is a
    # stable, already-strong performer that should produce zero opportunities.
    assert len(output["opportunities"]) == 1
    opp = output["opportunities"][0]
    assert opp["opportunity_type"] == "CTR_OPTIMIZATION"
    assert opp["source_entity"] == "test keyword quick win"
    assert opp["strategic_explanation"] == REALISTIC_EXPLANATION
    assert output["executive_summary"] == REALISTIC_EXEC_SUMMARY
    assert output["evaluation"]["passed"] is True

    assert agent.is_approved is False
    assert agent.execution_logs["prompt_version"] == "seo00001"


def test_seo_agent_with_no_opportunities_short_circuits_without_llm_call():
    class ExplodingLLM(LLMProvider):
        def generate(self, *a, **kw):
            raise AssertionError("LLM should not be called when there are no opportunities")

        def generate_json(self, *a, **kw):
            raise AssertionError("LLM should not be called when there are no opportunities")

    agent = _agent(seo_data_provider=EmptySEOProvider(), llm=ExplodingLLM())

    output = agent.run(period_start="2026-08-01", period_end="2026-08-31")

    assert output["opportunities"] == []
    assert "No SEO opportunities" in output["executive_summary"]


def test_seo_agent_validation_failure_missing_period():
    agent = _agent()

    with pytest.raises(ValueError, match="period_start and period_end are required"):
        agent.run(period_start="2026-08-01")  # missing period_end


def test_seo_agent_gather_context_provides_every_variable_the_real_prompt_needs():
    """Regression-shaped test for the exact class of bug found in ContentAgent this
    project already hit once (docs/DEV_DEMO_MODE.md: gather_context() computing values
    that never actually reach self.context, invisible to any test using a mock
    PromptService that ignores its context argument). Uses the real PromptService
    against the real prompts/seo/strategic_explanation.md template."""
    agent = SEOAgent(
        client_id=uuid4(),
        task_id=uuid4(),
        llm=MockLLM(),
        knowledge_query=MockKnowledge(),
        prompt_service=PromptService(base_dir="prompts"),
        intelligence=IntelligenceLayer(),
        seo_data_provider=FixtureSEOProvider(),
    )

    output = agent.run(period_start="2026-08-01", period_end="2026-08-31")

    assert output["executive_summary"] == REALISTIC_EXEC_SUMMARY


def test_seo_agent_evaluation_rejects_fabricated_numbers():
    """If the LLM states a number that doesn't appear anywhere in the real opportunity
    evidence, the existing hallucination_risk heuristic must catch it - proving the
    Evaluation Engine is genuinely wired in, not bypassed for this agent."""

    class FabricatingLLM(LLMProvider):
        def generate(self, *a, **kw):
            return "irrelevant"

        def generate_json(self, prompt, system_prompt="", schema=None, **kwargs):
            return {
                "executive_summary": (
                    "This keyword is ranking on page 47 with 9,999,999 impressions and a "
                    "conversion rate of 88.8%, numbers invented here and present nowhere in "
                    "the real opportunity evidence supplied to this prompt at all."
                ),
                "opportunity_explanations": ["fabricated"] * 10,
            }

    agent = _agent(llm=FabricatingLLM())

    with pytest.raises(ValueError, match="Validation Failed"):
        agent.run(period_start="2026-08-01", period_end="2026-08-31")

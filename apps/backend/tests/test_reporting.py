import pytest
from uuid import uuid4, UUID
from api.core.agent.reporting_agent import ReportingAgent
from api.core.interfaces.llm_provider import LLMProvider
from api.core.interfaces.knowledge_query_service import KnowledgeQueryService
from api.services.prompt_service import PromptService
from api.services.intelligence.engine import IntelligenceLayer
from typing import Dict, Any

REALISTIC_SUMMARY = (
    "This is the mock knowledge report for July 2026. "
    "Ctr increased this period over period. Ctr moved from a low value to a higher value this period. "
    "Mock knowledge shows a positive trend this period. "
    "Ctr improved period over period, and mock knowledge found no recent campaigns issues this period. "
    "This trend is positive for this period. "
    "Mock knowledge remains the source for this period report. "
    "Ctr rose this period compared to last period, and the trend moved up. "
    "The team used mock knowledge to confirm the trend this period. "
    "No recent campaigns problems were found this period. "
    "Ctr trend looks good for July 2026 this period. "
    "Mock knowledge and ctr trend align well this period. "
    "This report ends with a positive ctr trend this period. "
    "Mock knowledge confirms the ctr moved this period. "
    "This period showed ctr trend growth this period. "
    "The next period should continue this ctr trend. "
    "Mock knowledge will guide the next period this period. "
    "Ctr trend and mock knowledge match this period. "
    "This ends the July 2026 mock knowledge report for this period."
)


class MockLLM(LLMProvider):
    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.7, **kwargs) -> str:
        return REALISTIC_SUMMARY
    def generate_json(self, prompt: str, system_prompt: str = "", schema: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        return {}

class MockKnowledge(KnowledgeQueryService):
    def query(self, question: str, client_id: UUID, context_filters: Dict[str, Any] = None) -> Dict[str, Any]:
        return {"content": "mock knowledge", "sources": ["citation_1"]}

class MockPrompt(PromptService):
    def load_prompt(self, agent_name: str, template_name: str, context: Dict[str, Any] = None) -> str:
        return "mock prompt"
    def get_prompt_version_hash(self, agent_name: str, template_name: str) -> str:
        return "abc12345"

def test_reporting_agent_lifecycle():
    client_id = uuid4()
    task_id = uuid4()

    agent = ReportingAgent(
        client_id=client_id,
        task_id=task_id,
        llm=MockLLM(),
        knowledge_query=MockKnowledge(),
        prompt_service=MockPrompt(),
        intelligence=IntelligenceLayer(),
    )

    # Run the full lifecycle
    output = agent.run(
        metrics={"ctr": 0.04},
        historical_metrics={"ctr": 0.02},
        reporting_period="July 2026"
    )

    # Assertions
    assert "Executive Summary" in output
    assert output["Executive Summary"] == REALISTIC_SUMMARY
    assert "citation_1" in output["Citations"]

    # Real Intelligence Layer output flows through, not a hardcoded stub
    assert len(output["Insights"]) == 1
    assert output["Insights"][0]["percentage_change"] == 100.0  # CTR 2% -> 4% doubling
    assert output["Recommendations"] == [output["Insights"][0]["business_translation"]]
    assert output["evaluation"]["passed"] is True

    # Validate base state changes
    assert agent.is_approved is False
    assert agent.execution_logs["prompt_version"] == "abc12345"
    assert agent.execution_logs["end_time"] is not None

def test_reporting_agent_validation_failure():
    agent = ReportingAgent(
        client_id=uuid4(),
        task_id=uuid4(),
        llm=MockLLM(),
        knowledge_query=MockKnowledge(),
        prompt_service=MockPrompt(),
        intelligence=IntelligenceLayer(),
    )

    with pytest.raises(ValueError, match="Metrics data is required"):
        agent.run(reporting_period="July 2026") # Missing metrics


def test_reporting_agent_rejects_low_quality_output():
    class TerseLLM(LLMProvider):
        def generate(self, prompt, system_prompt="", temperature=0.7, **kwargs):
            return "Too short."
        def generate_json(self, prompt, system_prompt="", schema=None, **kwargs):
            return {}

    agent = ReportingAgent(
        client_id=uuid4(),
        task_id=uuid4(),
        llm=TerseLLM(),
        knowledge_query=MockKnowledge(),
        prompt_service=MockPrompt(),
        intelligence=IntelligenceLayer(),
    )

    with pytest.raises(ValueError, match="Validation Failed"):
        agent.run(metrics={"ctr": 0.04}, reporting_period="July 2026")

from typing import Any
from uuid import UUID
from api.core.agent.base import BaseAgent
from api.core.interfaces.llm_provider import LLMProvider
from api.core.interfaces.knowledge_query_service import KnowledgeQueryService
from api.services.prompt_service import PromptService
from api.services.intelligence.engine import IntelligenceLayer


class ReportingAgent(BaseAgent):
    """
    The Reporting Agent.
    Produces monthly marketing reports using structured business context from the Knowledge Base
    and deterministic signals from the Intelligence Layer.
    """

    def __init__(
        self,
        client_id: UUID,
        task_id: UUID,
        llm: LLMProvider,
        knowledge_query: KnowledgeQueryService,
        prompt_service: PromptService,
        intelligence: IntelligenceLayer,
        db=None,
        **kwargs: Any
    ):
        super().__init__(client_id, task_id, **kwargs)
        self.llm = llm
        self.knowledge_query = knowledge_query
        self.prompt_service = prompt_service
        self.intelligence = intelligence
        self.db = db
        self.metrics = None
        self.historical_metrics = None
        self.reporting_period = None
        self.report = None  # set in finalize() once persisted

    def initialize(self, **kwargs: Any) -> None:
        self.metrics = kwargs.get("metrics")
        self.historical_metrics = kwargs.get("historical_metrics")
        self.reporting_period = kwargs.get("reporting_period")
        self.execution_logs["agent"] = "ReportingAgent"

    def validate(self) -> None:
        if not self.metrics:
            raise ValueError("Metrics data is required for the Reporting Agent.")
        if not self.reporting_period:
            raise ValueError("Reporting period is required.")

    def gather_context(self) -> None:
        """
        Queries KnowledgeQueryService for Brand Voice/Campaigns, and runs the
        Intelligence Layer's deterministic Rule/Insight engines over the metrics -
        the LLM never computes trends/percentages itself, it only narrates numbers
        the Intelligence Layer already produced.
        """
        self.context["brand_voice"] = self.knowledge_query.query(
            "What is the brand voice and tone?", self.client_id
        )
        self.context["campaigns"] = self.knowledge_query.query(
            "What were the active campaigns and objectives recently?", self.client_id
        )
        self.context["metrics"] = self.metrics
        self.context["period"] = self.reporting_period
        self.context["intelligence"] = self.intelligence.generate_context(
            self.metrics, self.context, self.historical_metrics
        )

    def execute(self) -> Any:
        """
        Generates the report sections using LLMProvider and PromptService.
        """
        exec_hash = self.prompt_service.get_prompt_version_hash("reporting", "executive_summary")
        self.execution_logs["prompt_version"] = exec_hash

        prompt_context = {**self.context, "insights": self.context["intelligence"]["insights"]}
        exec_prompt = self.prompt_service.load_prompt("reporting", "executive_summary", prompt_context)

        executive_summary = self.llm.generate(exec_prompt, system_prompt="You are an expert marketing analyst.")

        return {
            "Executive Summary": executive_summary,
            "Metrics": self.metrics,
            "Insights": self.context["intelligence"]["insights"],
            "Recommendations": self.context["intelligence"]["recommendations"],
            "Citations": self.context["brand_voice"].get("sources", []) + self.context["campaigns"].get("sources", [])
        }

    def validate_output(self) -> None:
        """
        Validates that the report contains citations, no empty sections, and passes the
        Intelligence Layer's deterministic groundedness/hallucination-risk gate.
        """
        if not self.output.get("Executive Summary"):
            raise ValueError("Validation Failed: Executive Summary is empty.")

        if not self.output.get("Citations"):
            raise ValueError("Validation Failed: No citations found. Output must be grounded.")

        evaluation = self.intelligence.evaluate_agent_output(self.output["Executive Summary"], self.context)
        self.output["evaluation"] = evaluation
        if not evaluation["passed"]:
            raise ValueError(f"Validation Failed: {evaluation['feedback']} (scores: {evaluation['scores']})")

    def requires_human_approval(self) -> bool:
        return True

    def request_approval(self) -> None:
        # Report creation + status transition happens in finalize(); this only flips
        # the in-memory flag BaseAgent.run() checks.
        self.is_approved = False

    def finalize(self) -> None:
        """Persists the report as a new Report + ReportVersion, and opens an
        ApprovalRequest so it lands in the approval queue rather than auto-publishing."""
        if self.db is None:
            return  # unit-test / dry-run mode with no DB session provided

        from api.models.reporting import Report, ReportVersion, ApprovalRequest

        self.report = Report(
            client_id=self.client_id,
            title=f"{self.reporting_period} Performance Report",
            reporting_period=self.reporting_period,
            status="pending_approval",
        )
        self.db.add(self.report)
        self.db.flush()

        version = ReportVersion(
            report_id=self.report.id,
            version=1,
            content=self.output,
            content_text=self.output.get("Executive Summary"),
        )
        self.db.add(version)

        self.db.add(ApprovalRequest(report_id=self.report.id, status="pending"))
        self.db.commit()

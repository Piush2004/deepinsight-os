from typing import Any
from uuid import UUID

from api.core.agent.base import BaseAgent
from api.core.interfaces.llm_provider import LLMProvider
from api.core.interfaces.knowledge_query_service import KnowledgeQueryService
from api.core.interfaces.seo_data_provider import SEODataProvider
from api.services.prompt_service import PromptService
from api.services.intelligence.engine import IntelligenceLayer
from api.services.seo.opportunity_detector import detect_opportunities

# Only the top N opportunities get an LLM-generated strategic explanation each
# analysis run - caps latency/context size regardless of how many rows the data
# provider returns. Every opportunity still exists and is still approvable; the rest
# just carry their deterministic evidence/recommended_actions without LLM prose.
MAX_EXPLAINED_OPPORTUNITIES = 5


class SEOAgent(BaseAgent):
    """
    The SEO Intelligence Agent.

    Deterministic rules (api/services/seo/rules.py) detect and score opportunities
    from structured search-performance data BEFORE the LLM is ever involved - the LLM
    only explains opportunities the rules already found, grounded in real client
    knowledge retrieved through KnowledgeQueryService. Per docs/PROJECT_RULES.md Rule
    4, the LLM is never the source of truth for whether an opportunity exists.
    """

    def __init__(
        self,
        client_id: UUID,
        task_id: UUID,
        llm: LLMProvider,
        knowledge_query: KnowledgeQueryService,
        prompt_service: PromptService,
        intelligence: IntelligenceLayer,
        seo_data_provider: SEODataProvider,
        db=None,
        **kwargs: Any,
    ):
        super().__init__(client_id, task_id, **kwargs)
        self.llm = llm
        self.knowledge_query = knowledge_query
        self.prompt_service = prompt_service
        self.intelligence = intelligence
        self.seo_data_provider = seo_data_provider
        self.db = db

        self.period_start = None
        self.period_end = None
        self.analysis = None  # set in finalize() once persisted

    def initialize(self, **kwargs: Any) -> None:
        self.period_start = kwargs.get("period_start")
        self.period_end = kwargs.get("period_end")
        self.execution_logs["agent"] = "SEOAgent"

    def validate(self) -> None:
        if not self.period_start or not self.period_end:
            raise ValueError("period_start and period_end are required.")

    def gather_context(self) -> None:
        """Runs the deterministic rule engine over real search-performance rows
        (from SEODataProvider, never queried directly - see the factory in
        api/services/seo/provider_factory.py), then retrieves real client knowledge
        through the same KnowledgeQueryService abstraction ReportingAgent/ContentAgent
        use - never pgvector directly."""
        rows = self.seo_data_provider.get_search_performance(self.client_id, self.period_start, self.period_end)
        self.context["data_provider"] = self.seo_data_provider.__class__.__name__
        self.context["opportunities"] = detect_opportunities(rows)
        self.context["brand_voice"] = self.knowledge_query.query(
            "What is the brand voice and business goals?", self.client_id
        )
        self.context["business_goals"] = self.knowledge_query.query(
            "What are the business goals and target audience?", self.client_id
        )

    def execute(self) -> Any:
        """Asks the LLM for a strategic explanation of the top-priority opportunities
        the rule engine already found - never for the opportunities themselves. Empty
        opportunity set short-circuits before any LLM call (nothing to explain)."""
        opportunities = self.context["opportunities"]
        if not opportunities:
            return {
                "opportunities": [],
                "executive_summary": "No SEO opportunities were detected for this period - search performance looks stable across the analyzed keywords and pages.",
            }

        top = opportunities[:MAX_EXPLAINED_OPPORTUNITIES]
        exec_hash = self.prompt_service.get_prompt_version_hash("seo", "strategic_explanation")
        self.execution_logs["prompt_version"] = exec_hash

        opportunities_list = "\n".join(
            f"{i+1}. [{o['opportunity_type']}] {o['title']}\n"
            f"   Evidence: {'; '.join(o['evidence'])}\n"
            f"   Priority: {o['priority_score']}, Confidence: {o['confidence_score']}, Effort: {o['effort_estimate']}"
            for i, o in enumerate(top)
        )
        prompt_context = {
            "opportunities_list": opportunities_list,
            "brand_voice": self.context["brand_voice"].get("content", "Not yet defined."),
            "business_goals": self.context["business_goals"].get("content", "Not yet defined."),
        }
        prompt = self.prompt_service.load_prompt("seo", "strategic_explanation", prompt_context)

        # A malformed/unparseable LLM response raises LLMGenerationError here and
        # propagates uncaught - matches how ReportingAgent/ContentAgent treat the same
        # error class (api/core/tasks.py re-raises it as non-retryable, not silently
        # swallowed or faked).
        result = self.llm.generate_json(prompt, system_prompt="You are a senior SEO strategist.")

        explanations = result.get("opportunity_explanations", [])
        for i, opp in enumerate(top):
            opp["strategic_explanation"] = explanations[i] if i < len(explanations) else None

        return {
            "opportunities": opportunities,
            "executive_summary": result.get("executive_summary", ""),
        }

    def validate_output(self) -> None:
        """Runs the real Evaluation Engine against the executive summary, grounded in
        the real opportunity evidence and knowledge context - the same mechanism
        ReportingAgent/ContentAgent use, not a separate SEO-specific evaluator. A
        fabricated number here (e.g. the LLM saying "page 4" when the real position is
        6.2) shows up as a real hallucination_risk hit, because that heuristic
        compares numbers in the generated text against numbers in source_context -
        and source_context here includes the real opportunity metrics."""
        if not self.output["opportunities"]:
            return  # nothing to evaluate - the short-circuit summary needs no LLM grounding check

        source_context = {
            "opportunities": self.context["opportunities"],
            "brand_voice": self.context["brand_voice"],
            "business_goals": self.context["business_goals"],
        }
        evaluation = self.intelligence.evaluate_agent_output(self.output["executive_summary"], source_context)
        self.output["evaluation"] = evaluation
        if not evaluation["passed"]:
            raise ValueError(f"Validation Failed: {evaluation['feedback']} (scores: {evaluation['scores']})")

    def requires_human_approval(self) -> bool:
        return True

    def request_approval(self) -> None:
        self.is_approved = False

    def finalize(self) -> None:
        """Persists the SEOAnalysis + one SEOOpportunity row per detected opportunity,
        each with its own SEOApprovalRequest - so every opportunity enters the
        Approval Queue individually, not as one all-or-nothing batch."""
        if self.db is None:
            return  # unit-test / dry-run mode with no DB session provided

        from api.models.seo import SEOAnalysis, SEOOpportunity, SEOApprovalRequest

        analysis = SEOAnalysis(
            client_id=self.client_id,
            status="completed",
            data_provider=self.context["data_provider"],
            period_start=self.period_start,
            period_end=self.period_end,
            executive_summary=self.output.get("executive_summary"),
        )
        self.db.add(analysis)
        self.db.flush()

        evaluation_scores = self.output.get("evaluation", {}).get("scores")
        for opp in self.output["opportunities"]:
            opportunity = SEOOpportunity(
                analysis_id=analysis.id,
                client_id=self.client_id,
                opportunity_type=opp["opportunity_type"],
                category=opp["category"],
                title=opp["title"],
                source_entity=opp["source_entity"],
                source_type=opp["source_type"],
                metrics=opp["metrics"],
                evidence=opp["evidence"],
                priority_score=opp["priority_score"],
                confidence_score=opp["confidence_score"],
                impact_score=opp["impact_score"],
                effort_estimate=opp["effort_estimate"],
                recommended_actions=opp["recommended_actions"],
                strategic_explanation=opp.get("strategic_explanation"),
                evaluation_scores=evaluation_scores,
                status="pending_review",
            )
            self.db.add(opportunity)
            self.db.flush()
            self.db.add(SEOApprovalRequest(opportunity_id=opportunity.id, status="pending"))

        self.db.commit()
        self.analysis = analysis

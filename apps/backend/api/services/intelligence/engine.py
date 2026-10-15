from typing import Dict, Any
from api.services.intelligence.rule_engine import RuleEngine
from api.services.intelligence.insight_engine import InsightEngine
from api.services.intelligence.evaluation_engine import EvaluationEngine

class IntelligenceLayer:
    """
    The Intelligence Layer Facade.
    Sits between the Knowledge Layer and the Agents.
    Prevents duplication of reasoning, validation, and insight generation across multiple agents.
    """
    def __init__(self):
        self.rule_engine = RuleEngine()
        self.insight_engine = InsightEngine(self.rule_engine)
        self.evaluation_engine = EvaluationEngine()
        
    def generate_context(self, raw_metrics: Dict[str, Any], knowledge_context: Dict[str, Any],
                          historical_metrics: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Takes raw metrics and vector knowledge, outputs structured insights with confidence scores.
        Agents will use this output instead of raw data.
        """
        insights = self.insight_engine.generate_insights(raw_metrics, knowledge_context, historical_metrics)
        recommendations = [
            insight["business_translation"] for insight in insights if insight.get("actionable")
        ]

        return {
            "insights": insights,
            "raw_metrics_processed": True,
            "recommendations": recommendations,
        }
        
    def evaluate_agent_output(self, generated_content: str, source_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scores an agent's output. Agents should call this in their validate_output() step.
        """
        return self.evaluation_engine.evaluate(generated_content, source_context)

from typing import Dict, Any, List
from api.services.intelligence.rule_engine import RuleEngine

class InsightEngine:
    """
    Combines deterministic rules, trend analysis, and Knowledge Base context
    to generate high-confidence insights. 
    Prevents the LLM from hallucinating business logic.
    """
    
    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine

    def generate_insights(self, metrics: Dict[str, Any], knowledge_context: Dict[str, Any],
                           historical_metrics: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        # 1. Evaluate Deterministic Rules (including period-over-period trends when
        #    historical_metrics is provided)
        signals = self.rule_engine.evaluate_metrics(metrics, historical_metrics)

        insights = []
        for signal in signals:
            # 2. Enrich signal with Knowledge Base context
            # (e.g. check if "Low Open Rate" aligns with "Target Audience" preference)
            enriched_insight = {
                "category": signal["category"],
                "finding": signal["observation"],
                "business_translation": signal["insight"],
                "confidence_score": signal["confidence"],
                "actionable": signal.get("actionable", False),
                "grounding_context": knowledge_context.get("campaigns", {}).get("content", "No recent campaigns found"),
            }
            # Carry through trend-specific fields (metric/previous_value/current_value/percentage_change)
            # so callers can render the exact numbers the confidence score was derived from.
            for key in ("metric", "previous_value", "current_value", "percentage_change"):
                if key in signal:
                    enriched_insight[key] = signal[key]
            insights.append(enriched_insight)

        return insights

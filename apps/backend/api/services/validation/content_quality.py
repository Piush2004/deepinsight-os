from typing import Dict, Any
from api.services.intelligence.text_heuristics import (
    extract_source_text, readability_score, citation_coverage_score,
    hallucination_risk_score, completeness_score, professional_tone_score,
    originality_score, grammar_score, brand_consistency_score,
)


class ContentQualityEngine:
    """
    Scores content before it enters the Approval Queue.
    Metrics: Originality, Readability, Grammar, Professional Tone, Brand Consistency,
    Citation Coverage, Hallucination Risk, Completeness, Overall Score.

    Every score is computed from the actual generated `text` and the agent's `context`
    dict (which carries the retrieved knowledge and brand rules) - none are hardcoded.
    These are deliberately simple, dependency-free heuristics (see
    api/services/intelligence/text_heuristics.py), not a call out to an external
    grammar/plagiarism API - swap in a real one behind the same method signature when
    one is available.
    """

    def score_content(self, text: str, context: Dict[str, Any]) -> Dict[str, float]:
        source_text = extract_source_text(context)
        brand_voice_result = (context or {}).get("brand_voice", {})
        brand_rules = brand_voice_result.get("content", {}) if isinstance(brand_voice_result, dict) else {}
        if not isinstance(brand_rules, dict):
            brand_rules = {}

        scores = {
            "originality": float(originality_score(text, source_text)),
            "readability": float(readability_score(text)),
            "grammar": float(grammar_score(text)),
            "professional_tone": float(professional_tone_score(text)),
            "brand_consistency": float(brand_consistency_score(text, brand_rules)),
            "citation_coverage": float(citation_coverage_score(context or {})),
            "hallucination_risk": float(hallucination_risk_score(text, source_text)),
            "completeness": float(completeness_score(text)),
        }

        # Overall score is an average of positive metrics minus hallucination risk
        positive_metrics = [v for k, v in scores.items() if k != "hallucination_risk"]
        avg_positive = sum(positive_metrics) / len(positive_metrics)
        scores["overall_score"] = round(avg_positive - (scores["hallucination_risk"] / 2), 2)

        return scores

from typing import Dict, Any
from api.services.intelligence.text_heuristics import (
    extract_source_text, groundedness_score, completeness_score,
    citation_coverage_score, readability_score, professional_tone_score,
    hallucination_risk_score,
)


class EvaluationEngine:
    """
    Scores agent outputs automatically before they hit the Approval Queue.
    Every score below is computed from the actual generated_content/source_context
    passed in - none are hardcoded constants. These are intentionally simple,
    dependency-free heuristics (no LLM call), consistent with the Rule Engine's
    "deterministic, not LLM-judged" requirement for anything gating an approval queue.
    """

    # A well-written paraphrase of source material legitimately uses different words
    # than the source, so we don't require every individual metric to clear a high bar
    # (that would reject good writing for not being a lexical copy). Instead: an
    # overall weighted floor, plus two hard, non-negotiable gates - hallucinated
    # numbers and content with essentially no connection to any source at all.
    OVERALL_PASS_THRESHOLD = 70
    MIN_GROUNDEDNESS_FLOOR = 20
    MAX_HALLUCINATION_RISK = 25

    def evaluate(self, generated_content: str, source_context: Dict[str, Any]) -> Dict[str, Any]:
        source_text = extract_source_text(source_context)

        scores = {
            "groundedness": groundedness_score(generated_content, source_text),
            "completeness": completeness_score(generated_content),
            "citation_coverage": citation_coverage_score(source_context),
            "readability": readability_score(generated_content),
            "professional_tone": professional_tone_score(generated_content),
            "hallucination_risk": hallucination_risk_score(generated_content, source_text),
        }

        positive_scores = [v for k, v in scores.items() if k != "hallucination_risk"]
        overall_score = round(sum(positive_scores) / len(positive_scores) - scores["hallucination_risk"] / 2, 2)
        scores["overall_score"] = overall_score

        reasons = []
        if overall_score < self.OVERALL_PASS_THRESHOLD:
            reasons.append(f"overall score {overall_score} below {self.OVERALL_PASS_THRESHOLD}")
        if scores["groundedness"] < self.MIN_GROUNDEDNESS_FLOOR:
            reasons.append(f"groundedness {scores['groundedness']} below floor {self.MIN_GROUNDEDNESS_FLOOR}")
        if scores["hallucination_risk"] >= self.MAX_HALLUCINATION_RISK:
            reasons.append(f"hallucination risk {scores['hallucination_risk']} at/above {self.MAX_HALLUCINATION_RISK}")

        passed = not reasons
        feedback = (
            "Content is well grounded and meets the quality bar."
            if passed
            else f"Content failed quality gate: {'; '.join(reasons)}."
        )

        return {"passed": passed, "scores": scores, "feedback": feedback}

"""
Assembles the deterministic rules in rules.py into fully-scored opportunity dicts -
the structured contract between the Intelligence Layer and the SEOAgent (and, via the
API, the frontend). No LLM involvement anywhere in this file.
"""
from typing import Any, Dict, List

from api.services.seo import rules

# priority_score weighting - documented here, not buried in the expression below.
# Impact matters more than confidence for ranking what to work on first, but both
# count: a huge-impact finding built on a single low-traffic data point still needs
# real weight taken off it.
PRIORITY_IMPACT_WEIGHT = 0.6
PRIORITY_CONFIDENCE_WEIGHT = 0.4

# Confidence is a proxy for statistical reliability, not a true Bayesian estimate -
# documented as exactly that. More impressions behind a finding = more confidence
# that the pattern is real and not noise. Saturates at IMPRESSIONS_FOR_FULL_CONFIDENCE.
IMPRESSIONS_FOR_FULL_CONFIDENCE = 5000


def _confidence_score(impressions: int) -> float:
    return round(min(100.0, 100.0 * impressions / IMPRESSIONS_FOR_FULL_CONFIDENCE), 1)


def _impact_score(impressions: int, magnitude: float) -> float:
    return round(rules.volume_factor(impressions) * magnitude * 100, 1)


def _category(opportunity_type: str, effort_estimate: str) -> str:
    """Drives the frontend's four opportunity buckets (Quick Wins / Growth
    Opportunities / Performance Risks / Emerging Momentum) - computed once here,
    server-side, so the API and frontend can never disagree about which bucket an
    opportunity belongs in."""
    if opportunity_type == "PERFORMANCE_RISK":
        return "PERFORMANCE_RISK"
    if opportunity_type == "MOMENTUM_OPPORTUNITY":
        return "EMERGING_MOMENTUM"
    if effort_estimate == "Low":
        return "QUICK_WIN"
    return "GROWTH_OPPORTUNITY"


def _finalize(raw: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    impact = _impact_score(row["impressions"], raw.pop("opportunity_magnitude"))
    confidence = _confidence_score(row["impressions"])
    priority = round(impact * PRIORITY_IMPACT_WEIGHT + confidence * PRIORITY_CONFIDENCE_WEIGHT, 1)
    return {
        **raw,
        "source_entity": row["entity"],
        "source_type": row["entity_type"],
        "metrics": {
            "impressions": row["impressions"],
            "clicks": row["clicks"],
            "ctr": row["ctr"],
            "position": row["position"],
            "impressions_previous": row["impressions_previous"],
            "clicks_previous": row["clicks_previous"],
            "ctr_previous": row["ctr_previous"],
            "position_previous": row["position_previous"],
            "page": row.get("page"),
        },
        "priority_score": priority,
        "confidence_score": confidence,
        "impact_score": impact,
        "category": _category(raw["opportunity_type"], raw["effort_estimate"]),
    }


def detect_opportunities(search_performance_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Runs every deterministic rule over every row and returns fully-scored
    opportunities, sorted by priority_score descending - the ranking the mission's
    workflow diagram calls "Opportunities Ranked by Priority", computed here, not
    guessed by the LLM or the frontend."""
    opportunities: List[Dict[str, Any]] = []

    for row in search_performance_rows:
        fired_ctr = rules.detect_ctr_optimization(row)
        if fired_ctr:
            opportunities.append(_finalize(fired_ctr, row))
            # A below-expected CTR is the more specific, more actionable finding for
            # this exact position band - don't also emit the generic positional
            # opportunity for the same row (see rules.detect_page_one_opportunity's
            # docstring).
            trend_rules = [r for r in rules.ALL_RULES if r not in (rules.detect_page_one_opportunity, rules.detect_page_two_opportunity)]
        else:
            trend_rules = rules.ALL_RULES

        for rule_fn in trend_rules:
            fired = rule_fn(row)
            if fired:
                opportunities.append(_finalize(fired, row))

    opportunities.sort(key=lambda o: o["priority_score"], reverse=True)
    return opportunities
